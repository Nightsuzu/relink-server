# 搭建 Relink 服务器

适用部署包：**2.1.3**。客户端继续使用官方 Relink 账号；自建服务器为指定 Room 提供语音中继和屏幕共享，不需要修改登录地址。

## 1. 准备服务器

| 项目 | 要求 |
| --- | --- |
| 系统 | Linux x64，glibc ≥ 2.28，systemd，支持 apt-get 或 dnf |
| 安装工具 | Bash、Python 3.9+、unzip、curl 或 wget，sudo/root 权限 |
| 网络 | 固定公网 IPv4，入站 UDP 可用，能访问官方 HTTPS/WSS 和系统软件源 |
| 磁盘 | `/opt` 至少 2 GB 可用空间，另留日志空间 |
| 资源 | 小型 Room 可先选 2 核 / 2 GB，再依据实际流量和并发调整；此项不是容量承诺 |

优先选择成员距离近、UDP 线路稳定的服务器。无需显卡或域名。家用 NAT、多出口或代理出口可能导致接入失败：登记的公网 IP 必须与节点连接官方服务时的实际出口 IP 一致。ARM、Windows 和 Alpine/musl 不适用本安装器。

带宽按实际可用值填写，不是购买套餐的宣传峰值。屏幕共享每多一个观看者都会增加出站流量。例如一路 5 Mbps 的画面、4 位观看者，出站约为 20 Mbps，再为协议和语音留余量。服务器租金、带宽和云流量由服务器所有者承担。

## 2. 取得节点配置

当前客户端尚未提供自助登记表单。由 **Room 域主**在 Relink 的「反馈留言 → 使用问题」申请接入，提供 Room Code、节点名称、公网 IPv4 和计划提供的带宽（5–1000 Mbps）。运营核实所属 Room 后，协助登记并通过私密方式交付 `relink-node-setup.json`。

配置包含节点 ID、节点令牌和 TURN 密钥。它们由官方签发，**不能把示例文件改成随机值来代替**。同一 Room 最多三个自建节点。SSH 登录私钥和此配置是两类不同凭据，不要相互替代。

通过自己服务器的文件传输功能把配置上传到 `/root/relink-node-setup.json`，并限制权限：

```bash
sudo chmod 600 /root/relink-node-setup.json
```

不要把配置提交到 GitHub、粘贴进聊天或写进命令行。备份时同样保护此文件。

## 3. 放行网络

在云控制台安全组和系统防火墙同时允许：

| 方向 | 协议 / 端口 | 用途 |
| --- | --- | --- |
| 入站 | TCP、UDP 3478 | STUN / TURN 语音接入 |
| 入站 | UDP 49160–50183 | TURN 中继端口范围 |
| 入站 | UDP 8890 | SRT 屏幕传输 |
| 出站 | TCP 443 及系统软件源所需端口 | 官方认证、WSS 心跳和安装依赖 |
| 出站 | UDP 媒体流量、DNS | 语音中继及域名解析 |

SSH 管理端口保留给自己的管理 IP。`8554`、`9997`、`9998`、`4329` 是本机控制与探测接口，**不要开放到公网**。安装脚本不会自行改防火墙。

如果你已经使用 UFW，可按需执行以下规则；不要为了部署关闭整个防火墙，也不要未检查 SSH 规则就启用 UFW：

```bash
sudo ufw allow 3478/tcp
sudo ufw allow 3478/udp
sudo ufw allow 8890/udp
sudo ufw allow 49160:50183/udp
```

使用 firewalld 的服务器请添加对应规则，不要同时启用两套防火墙。安全组放行并不替代系统防火墙。

## 4. 下载、校验、安装

推荐先在[官网教程](https://relinkus.cn/server/)下载部署包和校验文件。也可以在服务器运行：

```bash
mkdir -p ~/relink-server-install
cd ~/relink-server-install
curl -fLO https://relinkus.cn/server/releases/Relink-Room-Node-2.1.3.zip
curl -fLO https://relinkus.cn/server/releases/Relink-Room-Node-2.1.3.zip.sha256
sha256sum -c Relink-Room-Node-2.1.3.zip.sha256
unzip Relink-Room-Node-2.1.3.zip -d bundle
cd bundle
sudo bash setup.sh --setup /root/relink-node-setup.json
```

看到校验通过后再安装。配置也可以放在解压后的 `setup.sh` 旁；其他路径使用 `--setup` 指定。安装时保留 SSH 会话，coturn 会以单线程低优先级编译，可能需要几分钟。

安装位置 `/opt/relink-room-node`，服务名为 `relink-room-media`、`relink-room-turn`、`relink-room-agent`。同版本、同配置重复执行只检查状态；旧版、不同节点或未完成的安装会停止覆盖，不自动升级、删除文件或停掉其他软件。

不进行安装的预演：

```bash
bash setup.sh plan --setup /root/relink-node-setup.json
```

预演仅检查配置和包完整性；不会探测目标系统、占用端口、官方接入或真实网络。安装阶段才会执行系统和端口预检。

## 5. 验收后使用

```bash
sudo bash setup.sh doctor
sudo systemctl is-enabled relink-room-media relink-room-turn relink-room-agent
```

依次确认：

1. 三个服务为 `active`，开机自启为 `enabled`。
2. 官方接入状态已在线；屏幕共享线路列表能看到对应的自建线路。
3. 两个客户端分别使用不同网络加入同一 Room，测试语音。在支持的隐私设置中开启隐藏 IP/中继模式，避免把成功直连误当成 TURN 已正常工作。
4. 开始屏幕共享，选择该自建线路；另一端确认画面、声音及关闭后重新开启均正常。成功通话并不代表 SRT 已放通。
5. 经服务器所有者确认维护窗口后重启服务器，再检查上述服务和媒体传输。不要在有人使用时随意重启。

默认语音会优先尝试成员直连，必要时使用中继；因此正常通话不一定经过自建服务器。自建节点只服务所属 Room，离线后的行为由客户端和官方线路策略决定，不能据此承诺无中断切换。

故障定位、升级与停用请看[运维文档](OPERATIONS.md)。
