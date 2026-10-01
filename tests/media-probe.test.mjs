import test from 'node:test';import assert from 'node:assert/strict';
import {measuredVideoProbe} from '../agent/media-probe.mjs';
const fixture=(fps=30)=>({streams:[{codec_type:'video',width:1280,height:720,r_frame_rate:'60/1'}],packets:Array.from({length:fps+1},(_,i)=>({pts_time:String(i/fps),dts_time:String(i/fps)}))});
test('unique packet timestamps measure 30 fps despite a misleading 60 Hz metadata field',()=>{assert.equal(measuredVideoProbe(fixture()).fps,30);assert.equal(measuredVideoProbe(fixture(60)).fps,60);});
test('B-frame presentation order does not change measured rate when decoding order is monotonic',()=>{const p=fixture();for(let i=1;i<28;i+=3)[p.packets[i].pts_time,p.packets[i+1].pts_time]=[p.packets[i+1].pts_time,p.packets[i].pts_time];assert.equal(measuredVideoProbe(p).fps,30);});
test('duplicate packets do not double measured frame rate',()=>{const p=fixture();p.packets=p.packets.flatMap(p=>[p,{...p}]);assert.equal(measuredVideoProbe(p).fps,30);});
test('insufficient samples never fall back to trusting advertised frame rate',()=>{const p=fixture();p.packets=p.packets.slice(0,3);assert.equal(measuredVideoProbe(p),null);});
test('live RTSP header and decoder warm-up prefix do not count as frames',()=>{const p=fixture();p.packets.unshift({}, {pts_time:'-0.033333'});assert.equal(measuredVideoProbe(p).fps,30);});
test('invalid timestamps and decoding timestamp rollback are unverified',()=>{
  for(const value of ['N/A','','Infinity',undefined]){const p=fixture();p.packets[8].pts_time=value;assert.equal(measuredVideoProbe(p),null);}
  const p=fixture();p.packets[12].dts_time='0';assert.equal(measuredVideoProbe(p),null);
  const q=fixture();q.packets[12].dts_time=q.packets[11].dts_time;assert.equal(measuredVideoProbe(q),null);
});
