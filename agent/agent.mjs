import {readFileSync} from 'node:fs';
import {createServer} from 'node:http';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {randomUUID} from 'node:crypto';
import {WebSocket} from 'ws';
import {createMediaMtxRelay} from './screen-relay.mjs';
import {measuredVideoProbe} from './media-probe.mjs';

const config=JSON.parse(readFileSync(process.argv[2]??'/etc/relink-media-node/agent.json','utf8'));
const target=new URL(config.serverUrl);
if(!['wss:','ws:'].includes(target.protocol)||target.protocol==='ws:'&&!['127.0.0.1','10.203.17.1'].includes(target.hostname)||!/^[a-f0-9]{64}$/.test(config.token))throw Error('Invalid node setup');
target.pathname=target.pathname.replace(/\/ws\/?$/,'').replace(/\/$/,'')+'/media-node';
// Alternate loopback ports allow isolated acceptance without touching the live relay.
const apiUrl=config.apiUrl??'http://127.0.0.1:9997';
const rtspPort=config.rtspPort??8554;
if(!Number.isInteger(rtspPort)||rtspPort<1024||rtspPort>65535)throw Error('Invalid local probe port');
const relay=createMediaMtxRelay({host:config.publicHost,apiUrl});
const execute=promisify(execFile),probes=new Map(),samples=new Map(),authorizations=new Map();
let socket,closing=false,lastAck=0;
const ownedPaths=new Set();
async function revokePaths(){for(const path of await relay.listPaths()){try{await relay.deletePath(path);ownedPaths.delete(path);}catch{/* Retry while disconnected. */}}}
const methods={
  async createPath(path,...args){await relay.createPath(path,...args);ownedPaths.add(path);},
  async deletePath(path){probes.delete(path);samples.delete(path);await relay.deletePath(path);ownedPaths.delete(path);},
  isPathReady:(...args)=>relay.isPathReady(...args),
  listConnections:()=>relay.listConnections(),
  kickConnection:id=>relay.kickConnection(id),
  async mediaUsage(path,profile) {
    if(!/^relink-[a-f0-9]{32}$/.test(path))throw Error('Invalid path');
    const response=await fetch(new URL(`/v3/paths/get/${path}`,apiUrl),{signal:AbortSignal.timeout(2500)});
    if(!response.ok)return {verified:false};const state=await response.json(),now=Date.now();
    let probe=probes.get(path);
    if(!probe||now-probe.at>8000&&!probe.pending) {
      const pending={...probe,at:probe?.at??0,pending:true};probes.set(path,pending);
      void execute(config.ffprobe??'/usr/bin/ffprobe',['-v','error','-rtsp_transport','tcp','-analyzeduration','1000000','-probesize','1000000','-select_streams','v:0','-read_intervals','%+1.5','-show_entries','stream=codec_type,width,height,r_frame_rate:packet=pts_time,dts_time','-of','json',`rtsp://${config.rtspHost??'127.0.0.1'}:${rtspPort}/${path}`],{timeout:5000,maxBuffer:262144}).then(({stdout})=>{
        const parsed=JSON.parse(stdout),measured=measuredVideoProbe(parsed);
        if(probes.get(path)===pending){if(measured)probes.set(path,{at:Date.now(),...measured});else {const times=p=>({pts_time:p.pts_time,dts_time:p.dts_time});probes.set(path,{at:0,diagnostic:{code:'INVALID_PACKET_TIMESTAMPS',packets:parsed.packets?.length??0,first:parsed.packets?.slice(0,4).map(times),last:parsed.packets?.slice(-2).map(times)}});}}
      }).catch(error=>{if(probes.get(path)===pending)probes.set(path,{at:0,diagnostic:{code:error.killed?'PROBE_TIMEOUT':'PROBE_PROCESS_FAILED'}});});
    }
    if(!probe?.width||now-probe.at>12000)return {verified:false,...(probe?.diagnostic?{probeDiagnostic:probe.diagnostic}:{})};
    const prior=samples.get(path);samples.set(path,{at:now,bytes:state.bytesReceived??0});
    const rate=prior&&now>prior.at?(state.bytesReceived-prior.bytes)*8000/(now-prior.at):0;
    const violation=probe.width!==profile.width||probe.height!==profile.height||!Number.isFinite(probe.fps)||probe.fps>profile.fps+1||rate>(profile.bitrate+192000)*1.5;
    return {verified:state.ready===true&&!violation,violation,actual:{width:probe.width,height:probe.height,fps:probe.fps,bitrate:rate},bytesReceived:state.bytesReceived??0,bytesSent:state.bytesSent??0};
  },
};
const authServer=createServer(async(req,res)=>{
  if(req.method!=='POST'||req.url!=='/auth'){res.writeHead(404).end();return;}
  try{const chunks=[];let size=0;for await(const part of req){size+=part.length;if(size>8192)throw Error('Too large');chunks.push(part);}const payload=JSON.parse(Buffer.concat(chunks));
    if(payload.protocol==='rtsp'&&payload.action==='read'&&['127.0.0.1','::1'].includes(payload.ip)&&/^relink-[a-f0-9]{32}$/.test(payload.path)){res.writeHead(204).end();return;}
    if(socket?.readyState!==WebSocket.OPEN){res.writeHead(503).end();return;}
    const requestId=randomUUID();const allowed=await new Promise(resolve=>{const timer=setTimeout(()=>{authorizations.delete(requestId);resolve(false);},3000);authorizations.set(requestId,{resolve,timer});socket.send(JSON.stringify({type:'node:authorize',requestId,payload}));});
    res.writeHead(allowed?204:401).end();
  }catch{res.writeHead(401).end();}
});
authServer.listen(config.authPort??4329,'127.0.0.1');
function connect(){if(closing)return;lastAck=Date.now();socket=new WebSocket(target,{headers:{Authorization:`Bearer ${config.token}`},maxPayload:262144,handshakeTimeout:8000});
  const connection=socket;
  const heartbeat=setInterval(()=>{if(Date.now()-lastAck>=15000){connection.terminate();return;}if(connection.readyState===WebSocket.OPEN)connection.send(JSON.stringify({type:'node:heartbeat'}));},5000);
  let commands=0;
  connection.on('message',async raw=>{let event;try{event=JSON.parse(raw);}catch{return;}
    if(['node:connected','node:pong'].includes(event.type)){lastAck=Date.now();return;}
    if(event.type==='node:authorized'){const pending=authorizations.get(event.requestId);if(pending){clearTimeout(pending.timer);pending.resolve(event.allowed===true);authorizations.delete(event.requestId);}return;}
    if(event.type!=='node:command'||typeof event.requestId!=='string'||!Array.isArray(event.args)||event.args.length>4||!Object.hasOwn(methods,event.method))return;
    if(commands>=24)return;commands++;
    try{const result=await methods[event.method](...event.args);if(connection.readyState!==WebSocket.OPEN&&event.method==='createPath')await relay.deletePath(event.args[0]);if(connection.readyState===WebSocket.OPEN)connection.send(JSON.stringify({type:'node:result',requestId:event.requestId,ok:true,result}));}
    catch{if(connection.readyState===WebSocket.OPEN)connection.send(JSON.stringify({type:'node:result',requestId:event.requestId,ok:false}));}finally{commands--;}
  });
  connection.on('close',()=>{void revokePaths().catch(()=>{});clearInterval(heartbeat);for(const p of authorizations.values()){clearTimeout(p.timer);p.resolve(false);}authorizations.clear();if(!closing)setTimeout(connect,3000);});connection.on('error',()=>{});
}
await revokePaths();connect();
const cleanupTimer=setInterval(()=>{if(socket?.readyState!==WebSocket.OPEN)void revokePaths().catch(()=>{});},5000);cleanupTimer.unref();
for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{closing=true;clearInterval(cleanupTimer);void revokePaths().catch(()=>{});socket?.close();authServer.close();setTimeout(()=>process.exit(0),1000).unref();});
