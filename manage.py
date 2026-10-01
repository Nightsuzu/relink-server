#!/usr/bin/env python3
"""Small, secret-free operator interface for the Room node installer."""
import argparse
import datetime
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys

BASE = Path(__file__).resolve().parent
PREFIX = Path('/opt/relink-room-node')
UNITS = ['relink-room-' + name for name in ['media', 'turn', 'agent']]
FIELDS = ['version', 'nodeId', 'token', 'turnSecret', 'publicHost', 'capacityMbps', 'serverUrl']

def installer():
    spec = importlib.util.spec_from_file_location('room_installer', BASE / 'install-node.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_setup(path):
    path = Path(path).expanduser()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise ValueError('节点配置必须是小于 8 KB 的普通文件。')
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        installer().validate(data)
    except (ValueError, TypeError, KeyError):
        raise ValueError('节点配置无效。请使用官方登记后签发的配置，不要手工填写密钥。') from None
    # Unknown fields cannot override loopback API or local binary paths.
    return {key: data[key] for key in FIELDS}

def resolve_setup(explicit):
    if explicit:
        return Path(explicit).expanduser()
    options = [Path.cwd() / 'relink-node-setup.json', BASE / 'relink-node-setup.json', Path('/root/relink-node-setup.json')]
    for path in options:
        if path.is_file():
            return path
    if sys.stdin.isatty():
        answer = input('请输入 relink-node-setup.json 的路径（不需要粘贴密钥）：').strip()
        if answer:
            return Path(answer).expanduser()
    raise ValueError('未找到节点配置。把 relink-node-setup.json 放在安装包旁，或用 --setup 指定路径。')

def installed_matches(setup):
    if not PREFIX.exists():
        return False
    try:
        old = load_setup(PREFIX / 'config/agent.json')
    except (ValueError, OSError):
        raise ValueError('发现旧安装或未完成安装，已停止覆盖。运行 sudo bash setup.sh doctor 查看状态，保留现有配置。') from None
    if old != setup:
        raise ValueError('此机器已安装其他节点或配置不同，已停止覆盖。请先核对所属 Room。')
    if not (PREFIX / 'install-complete.json').is_file():
        raise ValueError('检测到旧版或未完成安装，保留原配置；请运行 doctor 检查，不会自动重装。')
    try:
        stamp = json.loads((PREFIX / 'install-complete.json').read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise ValueError('安装记录无效，保留现有配置；请运行 doctor 检查。') from None
    if not isinstance(stamp, dict) or stamp.get('version') != '2.1.3':
        raise ValueError('此机器已有其他版本，保留现有配置；本命令不会自动升级。')
    return True

def service_states():
    states = {}
    for unit in UNITS:
        result = subprocess.run(['systemctl', 'is-active', unit], capture_output=True, universal_newlines=True, timeout=10)
        states[unit] = result.stdout.strip() or 'unknown'
    return states

def doctor():
    if platform.system() != 'Linux' or not shutil.which('systemctl'):
        raise ValueError('状态检查需要 Linux + systemd。')
    states = service_states()
    for unit, state in states.items():
        print('{}：{}'.format(unit, state))
    print('配置存在：{}'.format((PREFIX / 'config/agent.json').is_file()))
    print('进程 active 不代表节点已接入官方，也不代表公网媒体端口已通。')
    print('请核对云安全组：TCP/UDP 3478、UDP 8890、UDP 49160–50183。')
    print('下一步：在 Relink 确认节点在线，并用两个网络测试语音中继和共享。')
    print('日志：sudo journalctl -u relink-room-agent -n 50 --no-pager')
    return 0 if all(value == 'active' for value in states.values()) else 1

def preflight(local_ip=None):
    if platform.system() != 'Linux' or platform.machine() not in ['x86_64', 'amd64']:
        raise ValueError('目前安装包仅支持 Linux x64。')
    if os.geteuid() != 0:
        raise ValueError('请运行 sudo bash setup.sh。')
    if not shutil.which('systemctl') or not Path('/run/systemd/system').is_dir():
        raise ValueError('需要使用 systemd 的主机，不能在普通容器中安装。')
    if not any(shutil.which(name) for name in ['apt-get', 'dnf']):
        raise ValueError('需要 apt-get 或 dnf 软件源。')
    if shutil.disk_usage('/opt').free < 2 * 1024 ** 3:
        raise ValueError('/opt 可用空间不足 2 GB。')
    if local_ip:
        address = ipaddress.ip_address(local_ip)
        if address.version != 4 or address.is_loopback or address.is_unspecified or address.is_multicast:
            raise ValueError('--local-ip 必须是本机实际网卡 IPv4。')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind((local_ip, 0))
    # Single installer per host; no service stop or firewall mutation.
    import fcntl
    lock = open('/run/lock/relink-room-install.lock', 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        raise ValueError('另一个节点安装任务正在运行，请等待完成。') from None
    return lock

def main():
    parser = argparse.ArgumentParser(description='Relink 自有服务器安装与诊断')
    parser.add_argument('command', nargs='?', default='install', choices=['install', 'plan', 'doctor', 'status'])
    parser.add_argument('--setup', help='官方签发的节点配置文件路径')
    parser.add_argument('--local-ip', help='多网卡机器可显式指定本机 IPv4')
    parser.add_argument('--plan', action='store_true', help='只校验，不安装')
    args = parser.parse_args()
    if args.command in ['doctor', 'status']:
        return doctor()
    print('1/3 正在核对安装包和节点配置…', flush=True)
    installer().verify_bundle(BASE)
    setup = load_setup(resolve_setup(args.setup))
    if args.command == 'plan' or args.plan:
        print('校验通过。将安装：语音中继、屏幕共享、官方接入代理。')
        print('目标：Linux x64 / glibc >= 2.28 / systemd；目录：/opt/relink-room-node')
        print('放行：TCP/UDP 3478、UDP 8890、UDP 49160–50183。')
        print('预演未修改系统，未验证目标主机、官方连接或公网端口。')
        return 0
    lock = preflight(args.local_ip)
    try:
        if installed_matches(setup):
            print('同一节点已经安装，配置和密钥保持不变；仅检查状态。')
            return doctor()
        import tempfile
        # Pass a strict allow-list, never arbitrary downloaded extra fields.
        with tempfile.TemporaryDirectory(prefix='relink-node-') as tmp:
            config = Path(tmp) / 'setup.json'
            config.write_text(json.dumps(setup), encoding='utf-8')
            os.chmod(str(config), 0o600)
            stamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            log = Path('/var/log/relink-node-install-' + stamp + '.log')
            fd = os.open(str(log), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            print('2/3 正在安装依赖与服务，编译可能需要几分钟。日志：' + str(log), flush=True)
            cmd = [sys.executable, str(BASE / 'install-node.py'), '--setup', str(config)]
            if args.local_ip:
                cmd += ['--local-ip', args.local_ip]
            with os.fdopen(fd, 'w') as output:
                result = subprocess.run(cmd, stdout=output, stderr=subprocess.STDOUT)
            if result.returncode:
                print('安装未完成。已保留文件及日志，不会删除配置或停止其他服务。')
                print('请运行 sudo bash setup.sh doctor；查看日志：sudo less ' + str(log))
                return 1
            (PREFIX / 'install-complete.json').write_text(json.dumps({'version': '2.1.3', 'installedAt': stamp}), encoding='utf-8')
            print('3/3 安装完成，正在检查服务状态。')
            return doctor()
    finally:
        lock.close()

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError):
        # No traceback / config values in user-visible diagnostic output.
        error = sys.exc_info()[1]
        print('未完成：' + (str(error) if isinstance(error, ValueError) else '系统操作失败，请检查权限、磁盘和安装日志。'), file=sys.stderr)
        sys.exit(1)
