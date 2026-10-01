#!/usr/bin/env python3
"""Install a Room-scoped Relink media node from a hash-bound Linux x64 bundle."""
import argparse,hashlib,ipaddress,json,os,pathlib,platform,shutil,socket,subprocess,tarfile,time,urllib.parse
P=pathlib.Path
PREFIX=P('/opt/relink-room-node')
SERVICE='relink-room'
def run(args,cwd=None):
 subprocess.run(args,cwd=str(cwd) if cwd else None,check=True,timeout=600)
def unpack(archive,target):
 target.mkdir(parents=True,exist_ok=True)
 with tarfile.open(str(archive)) as tar:
  for member in tar.getmembers():
   resolved=(target/member.name).resolve()
   if not str(resolved).startswith(str(target.resolve())+'/'):raise ValueError('Unsafe archive member')
   if member.isfile() or member.isdir():tar.extract(member,str(target))
def turn_config(setup,local):
 # Shared capacity is admitted by the coordinator. coturn reserves max-bps for
 # each allocation, so a computed global cap rejects idle voice allocations.
 lines=['listening-port=3478','listening-ip='+local,'relay-ip='+local,'external-ip='+setup['publicHost']+'/'+local,'min-port=49160','max-port=50183','realm=relink-room-node','fingerprint','use-auth-secret','static-auth-secret='+setup['turnSecret'],'user-quota=64','total-quota=512','max-bps=65536','bps-capacity=0','relay-threads=2','no-tls','no-dtls','no-tcp-relay','no-cli','no-multicast-peers','no-software-attribute','log-file=stdout','simple-log','pidfile=/run/relink-room-turn/turnserver.pid']
 for block in ['0.0.0.0-0.255.255.255','10.0.0.0-10.255.255.255','100.64.0.0-100.127.255.255','127.0.0.0-127.255.255.255','169.254.0.0-169.254.255.255','172.16.0.0-172.31.255.255','192.168.0.0-192.168.255.255','198.18.0.0-198.19.255.255','224.0.0.0-255.255.255.255','::1','fc00::-fdff:ffff:ffff:ffff:ffff:ffff:ffff:ffff','fe80::-febf:ffff:ffff:ffff:ffff:ffff:ffff:ffff']:lines.append('denied-peer-ip='+block)
 return '\n'.join(lines)+'\n'
def validate(setup):
 if not isinstance(setup,dict) or setup.get('version')!=1:raise ValueError('Invalid setup version')
 if not isinstance(setup.get('nodeId'),str) or len(setup['nodeId'])!=32 or any(c not in '0123456789abcdef' for c in setup['nodeId']):raise ValueError('Invalid registered node ID')
 address=ipaddress.ip_address(setup.get('publicHost',''))
 if address.version!=4 or not address.is_global:raise ValueError('A public IPv4 address is required')
 if not all(isinstance(setup.get(k),str) and len(setup[k])==64 and all(c in '0123456789abcdef' for c in setup[k]) for k in ['token','turnSecret']):raise ValueError('Invalid node credentials')
 url=urllib.parse.urlparse(setup.get('serverUrl',''))
 if not (url.scheme=='wss' and url.hostname=='relinkus.cn' and url.port in [None,443] and url.path=='/relink/ws' and not url.username and not url.password and not url.query and not url.fragment):raise ValueError('Unexpected official coordinator URL')
 if type(setup.get('capacityMbps')) is not int or not 5<=setup['capacityMbps']<=1000:raise ValueError('Capacity must be 5 to 1000 Mbps')

def verify_bundle(base):
 manifest=json.loads((base/'manifest.json').read_text())
 if manifest.get('version')!='2.1.3' or not isinstance(manifest.get('files'),dict):raise ValueError('Invalid bundle manifest')
 required={'setup.sh','manage.py','install-node.py','mediamtx','ffprobe','node-runtime.tar.xz','coturn-source.tar.gz','agent/agent.mjs','agent/screen-relay.mjs','agent/media-probe.mjs','licenses/MEDIAMTX-LICENSE.txt'}
 if not required.issubset(manifest['files']):raise ValueError('Incomplete bundle manifest')
 for name,expected in manifest['files'].items():
  file=(base/name).resolve()
  try:file.relative_to(base.resolve())
  except ValueError:raise ValueError('Unsafe bundle path')
  if any(p.is_symlink() for p in [(base/name), *(base/name).parents] if p != base.parent) or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=expected:raise ValueError('Bundle checksum mismatch: '+name)
 return manifest
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--setup',required=True);parser.add_argument('--plan',action='store_true');parser.add_argument('--local-ip');args=parser.parse_args()
 base=P(__file__).resolve().parent;setup=json.loads(P(args.setup).read_text(encoding='utf-8-sig'));validate(setup)
 manifest=verify_bundle(base)
 if args.plan:
  print(json.dumps({'bundleValidated':True,'version':manifest['version'],'requiredPlatform':'Linux x64 / glibc >= 2.28','hostChecked':False,'installDirectory':str(PREFIX),'services':['media','turn','agent'],'ports':['3478/tcp','3478/udp','8890/udp','49160-50183/udp'],'screenPricePoints':0,'changesMade':False}));return
 if platform.system()!='Linux' or platform.machine() not in ['x86_64','amd64']:raise ValueError('Linux x64 is required')
 if platform.libc_ver()[0]!='glibc' or tuple(int(p) for p in platform.libc_ver()[1].split('.')[:2])<(2,28):raise ValueError('glibc 2.28 or newer is required')
 if os.geteuid()!=0:raise ValueError('Run with sudo')
 if PREFIX.exists():raise ValueError('Existing node: installation will not overwrite it')
 import pwd
 for kind in ['media','turn','agent']:
  if (P('/etc/systemd/system')/(SERVICE+'-'+kind+'.service')).exists():raise ValueError('Existing Room node service; no changes made')
 for proto,ports in [(socket.SOCK_STREAM,[3478,8554,9997,9998,4329]),(socket.SOCK_DGRAM,[3478,8890]+list(range(49160,50184)))]:
  for port in ports:
   with socket.socket(socket.AF_INET,proto) as check:check.bind(('0.0.0.0',port))
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:probe.connect(('1.1.1.1',53));local=args.local_ip or probe.getsockname()[0]
 assert ipaddress.ip_address(local).version==4
 if shutil.which('apt-get'):
  run(['apt-get','update']);run(['apt-get','install','-y','build-essential','pkg-config','libssl-dev','libevent-dev'])
 elif shutil.which('dnf'):run(['dnf','install','-y','gcc','make','pkgconf-pkg-config','openssl-devel','libevent-devel'])
 else:raise ValueError('This installer supports apt-get and dnf systems')
 try:account=pwd.getpwnam('relink-room-node')
 except KeyError:
  run(['useradd','--system','--no-create-home','--shell','/sbin/nologin','relink-room-node']);account=pwd.getpwnam('relink-room-node')
 os.umask(0o022)
 PREFIX.mkdir(mode=0o755);os.chmod(str(PREFIX),0o755)
 for folder in ['bin','sources','licenses','agent','config']:(PREFIX/folder).mkdir(mode=0o755)
 unpack(base/'node-runtime.tar.xz',PREFIX/'runtime');runtime=next((PREFIX/'runtime').glob('node-*-linux-x64'))
 for name in ['mediamtx','ffprobe']:shutil.copyfile(str(base/name),str(PREFIX/'bin'/name));os.chmod(str(PREFIX/'bin'/name),0o755)
 for item in (base/'agent').iterdir():
  if item.is_dir():shutil.copytree(str(item),str(PREFIX/'agent'/item.name))
  else:shutil.copyfile(str(item),str(PREFIX/'agent'/item.name))
 for item in (base/'licenses').iterdir():shutil.copyfile(str(item),str(PREFIX/'licenses'/item.name))
 unpack(base/'coturn-source.tar.gz',PREFIX/'sources');source=PREFIX/'sources/coturn-4.18.0'
 run(['./configure','--disable-mysql','--disable-postgresql','--disable-redis','--disable-sqlite'],source);run(['nice','-n','10','make','-j1'],source)
 shutil.copyfile(str(source/'bin/turnserver'),str(PREFIX/'bin/turnserver'));os.chmod(str(PREFIX/'bin/turnserver'),0o755)
 os.chmod(str(PREFIX/'config'),0o750);os.chown(str(PREFIX/'config'),0,account.pw_gid)
 cfg={**setup,'ffprobe':str(PREFIX/'bin/ffprobe'),'authPort':4329}
 media={'logLevel':'warn','authMethod':'http','authHTTPAddress':'http://127.0.0.1:4329/auth','authHTTPExclude':[{'action':'api'},{'action':'metrics'}],'api':True,'apiAddress':'127.0.0.1:9997','metrics':True,'metricsAddress':'127.0.0.1:9998','rtsp':True,'rtspAddress':'127.0.0.1:8554','rtspTransports':['tcp'],'rtmp':False,'hls':False,'webrtc':False,'moq':False,'srt':True,'srtAddress':':8890','paths':{}}
 for name,contents in [('agent.json',json.dumps(cfg)),('mediamtx.json',json.dumps(media)),('turnserver.conf',turn_config(setup,local))]:
  path=PREFIX/'config'/name;path.write_text(contents+'\n');os.chmod(str(path),0o640);os.chown(str(path),0,account.pw_gid)
 os.chmod(str(PREFIX/'config'),0o750);os.chown(str(PREFIX/'config'),0,account.pw_gid)
 commands={'media':str(PREFIX/'bin/mediamtx')+' '+str(PREFIX/'config/mediamtx.json'),'turn':str(PREFIX/'bin/turnserver')+' -c '+str(PREFIX/'config/turnserver.conf'),'agent':str(runtime/'bin/node')+' '+str(PREFIX/'agent/agent.mjs')+' '+str(PREFIX/'config/agent.json')}
 for kind,command in commands.items():
  unit=P('/etc/systemd/system')/(SERVICE+'-'+kind+'.service');assert not unit.exists()
  unit.write_text('[Unit]\nDescription=Relink Room '+kind+'\nAfter=network-online.target\nWants=network-online.target\n[Service]\nUser=relink-room-node\nGroup=relink-room-node\nExecStart='+command+'\nRestart=on-failure\nRestartSec=3\nRuntimeDirectory=relink-room-'+kind+'\nNoNewPrivileges=true\nPrivateTmp=true\nProtectSystem=strict\nProtectHome=true\nLimitNOFILE=65536\n[Install]\nWantedBy=multi-user.target\n');os.chmod(str(unit),0o644)
 run(['systemctl','daemon-reload']);run(['systemctl','enable','--now']+[SERVICE+'-'+k for k in commands]);time.sleep(2);run(['systemctl','is-active']+[SERVICE+'-'+k for k in commands])
 print('节点进程已安装。放行云防火墙 TCP/UDP 3478、UDP 8890、UDP 49160–50183，然后回到 Relink 刷新节点状态并进行实际通话。账号登录地址保持官方地址。')
if __name__=='__main__':main()
