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

## 2. 选购与配置参考

### 云服务器入口

| 平台 | 入口 | 选购时检查 |
| --- | --- | --- |
| 阿里云 | [阿里云入口](https://developer.aliyun.com/article/771060?userCode=e0fuza3h) | 选择 x86_64 ECS；购买前向厂商确认允许用于 TURN/SRT 媒体中继 |
| 腾讯云 | [腾讯云 CVM](https://cloud.tencent.com/product/cvm) | 选择 x86_64 云服务器、固定公网 IPv4，确认 UDP 与公网带宽 |
| 雨云 | [雨云推荐入口](https://www.rainyun.com/ODA2NzMx_) · 推荐码 `ODA2NzMx` | 选择 RCS 云服务器、x86_64 Linux、独立公网 IPv4；不要选仅有 NAT 映射的套餐 |

雨云新人五折券：使用推荐入口或推荐码 `ODA2NzMx` 注册，按活动要求绑定微信后领取；实际可领状态、有效期和适用产品以雨云账户及下单页面为准。该入口为推荐链接。

优先选择靠近大多数成员的地域、普通 Linux 系统镜像和可稳定提供的公网出站带宽。建议 Ubuntu 24.04 LTS x86_64，系统盘 40 GB；不要选 ARM、应用集成镜像或会被随时回收的竞价实例。无需 GPU。云主机不负责转码，编码与解码由客户端完成。

阿里云 [ECS 使用须知](https://help.aliyun.com/zh/ecs/user-guide/usage-notes)和[轻量应用服务器使用须知](https://help.aliyun.com/zh/simple-application-server/product-overview/usage-notes)均限制流量穿透类服务。本项目包含 TURN 中继，因此阿里云列为需先确认用途的选项，不表示厂商已批准 Relink。腾讯云、雨云也应按当前产品条款确认用途。雨云需核对[服务器 IP](https://www.rainyun.com/docs/products/rcs/manual/ip)与[选购指南](https://www.rainyun.com/docs/products/rcs/buy/rcs)中的公网 IP、带宽和计费信息；NAT 端口映射套餐不符合本安装器要求。

### 人数与语音配置

下表是购买起点，**不是实测容量或保证在线人数**。人数指同时参加语音的人数，不是 Room 总成员。估算条件：每个频道最多 8 人、默认 96 kbps、所有人同时持续说话且全部经过中继，带宽加 25% 余量；更多人分散到多个频道。

| 同时语音人数 | 起步 CPU / 内存 | 系统盘 | 建议公网出站带宽（仅语音） |
| --- | --- | --- | --- |
| 1–8 人 | 2 核 / 2 GB | 40 GB | 10 Mbps |
| 9–16 人 | 2 核 / 4 GB | 40 GB | 20 Mbps |
| 17–32 人 | 4 核 / 4 GB | 40 GB | 40 Mbps |
| 33–64 人 | 4 核 / 8 GB | 40 GB | 80 Mbps |

当前语音按成员之间逐对连接，不能简单按“人数 × 码率”购买带宽。若全部在同一个频道并同时说话，16 人约需 30 Mbps、32 人约需 120 Mbps（均含 25% 余量），请按下式重新计算。直连成功、不说话和语音检测静音会降低实际流量。

语音出站带宽（Mbps）≈ `1.25 × Σ[每频道人数 × (每频道人数 − 1)] × 语音码率(Mbps)`。

### 屏幕共享要额外加多少带宽

以下按当前画质预设的目标视频码率，含 25% 余量，向上取整；**需加到上面的语音带宽上**。一路共享当前最多 7 位观看者；多路同时共享时累加。系统声音、SRT 重传及线路波动可能还需要更多余量。

| 画质 / 目标视频码率 | 1 位观看者 | 3 位观看者 | 7 位观看者 |
| --- | --- | --- | --- |
| 720p / 30 FPS · 3 Mbps | +4 Mbps | +12 Mbps | +27 Mbps |
| 1080p / 30 FPS · 5 Mbps | +7 Mbps | +19 Mbps | +44 Mbps |
| 1080p / 60 FPS · 8 Mbps | +10 Mbps | +30 Mbps | +70 Mbps |
| 1440p / 120 FPS · 20 Mbps | +25 Mbps | +75 Mbps | +175 Mbps |

例如 8 人语音，加一路 1080p / 60 FPS、3 人观看：可从 **2 核 / 4 GB、40 GB 系统盘、50 Mbps 稳定公网出站带宽**开始试用，再依据 CPU、内存、丢包与峰值带宽调整。共享者的上行和每个观看者的下行也要能承载对应码率，扩容服务器不能修复成员本地线路。

### 固定带宽还是按流量

每天长时间使用，可优先比较固定带宽；偶尔使用，可比较按流量并设置费用提醒。套餐宣传的峰值不等于持续可用带宽。5 Mbps 画面发给 4 人，视频载荷约 **9 GB/小时**（十进制 GB，未含语音、音频和重传），一个月使用 60 小时约 540 GB；先算流量再选套餐。

价格受地域、带宽和续费影响，以下单页面为准。本页不保存固定促销价。计费依据：[阿里云公网带宽计费](https://help.aliyun.com/zh/ecs/public-bandwidth/)、[腾讯云公网计费模式](https://cloud.tencent.com/document/product/213/10578)。厂商资料核对日期：2026-10-02。

## 3. 取得节点配置

### 为新 Room 自助生成

使用 **Relink 1.0.5 自建服务器补丁（revision 3）或更新客户端**：

1. 打开「加入 / 创建 → 创建 Room → 使用自有服务器创建」。
2. 填写 Room 名称、服务器公网 IPv4、可用出站带宽（5–1000 Mbps）；服务器名称可选填。页面内可展开人数与服务器配置表，以及云商入口。
3. 点击「创建 Room 并生成配置」。一次操作会创建 Room 并为它登记节点，不会立即切换或中断当前通话。
4. 点击「保存节点配置」，在系统保存窗口保存 `relink-node-setup.json`。取消或保存失败可以重试。
5. 上传配置、放行端口，再复制页面中的安装命令到服务器执行。页面每 10 秒检查节点状态，显示“服务器已连接”后再做真实通话验收。

配置领取有效期为 **30 分钟**。断线或退出软件后，重新进入同一创建入口，点击「恢复创建结果」或「恢复并取得配置」，会继续原来的 Room，不会重复创建。恢复记录只保存请求信息和公开状态；专属密钥不写入客户端本地存储。超过领取期限可使用之前保存的配置；未保存时请通过「反馈留言 → 使用问题」申请处理。

若提示当前客户端不支持配置文件保存，请安装最新完整客户端后再继续。旧版本可继续使用已有 Room，无需强制更新。

### 给已有 Room 增加节点

当前创建向导用于新 Room。已有 Room 的域主仍可在「反馈留言 → 使用问题」申请接入，提供 Room Code、节点名称、公网 IPv4 和可用带宽，由运营核实后私密交付配置。

配置包含节点 ID、节点令牌和 TURN 密钥。它们由官方签发，**不能把示例文件改成随机值来代替**。同一 Room 最多三个自建节点。SSH 登录私钥和此配置是两类不同凭据，不要相互替代。

通过自己服务器的文件传输功能把配置上传到 `/root/relink-node-setup.json`，并限制权限：

```bash
sudo chmod 600 /root/relink-node-setup.json
```

不要把配置提交到 GitHub、粘贴进聊天或写进命令行。备份时同样保护此文件。

## 4. 放行网络

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

## 5. 下载、校验、安装

推荐先在[官网教程](https://relinkus.cn/server/)下载部署包和校验文件。也可以在服务器运行：

```bash
relink_install_dir=$(mktemp -d) &&
cd "$relink_install_dir" &&
curl -fLO https://relinkus.cn/server/releases/Relink-Room-Node-2.1.3.zip &&
curl -fLO https://relinkus.cn/server/releases/Relink-Room-Node-2.1.3.zip.sha256 &&
sha256sum -c Relink-Room-Node-2.1.3.zip.sha256 &&
unzip Relink-Room-Node-2.1.3.zip -d bundle &&
cd bundle &&
sudo chmod 600 /root/relink-node-setup.json &&
sudo bash setup.sh --setup /root/relink-node-setup.json
```

看到校验通过后再安装。配置也可以放在解压后的 `setup.sh` 旁；其他路径使用 `--setup` 指定。安装时保留 SSH 会话，coturn 会以单线程低优先级编译，可能需要几分钟。

安装位置 `/opt/relink-room-node`，服务名为 `relink-room-media`、`relink-room-turn`、`relink-room-agent`。同版本、同配置重复执行只检查状态；旧版、不同节点或未完成的安装会停止覆盖，不自动升级、删除文件或停掉其他软件。

不进行安装的预演：

```bash
bash setup.sh plan --setup /root/relink-node-setup.json
```

预演仅检查配置和包完整性；不会探测目标系统、占用端口、官方接入或真实网络。安装阶段才会执行系统和端口预检。

## 6. 验收后使用

```bash
sudo bash setup.sh doctor
sudo systemctl is-enabled relink-room-media relink-room-turn relink-room-agent
```

依次确认：

1. 三个服务为 `active`，开机自启为 `enabled`。
2. 创建窗口显示“服务器已连接”；屏幕共享线路列表能看到对应的自建线路。这只证明控制连接正常，不代表公网媒体端口已经验收。
3. 两个客户端分别使用不同网络加入同一 Room，测试语音。在支持的隐私设置中开启隐藏 IP/中继模式，避免把成功直连误当成 TURN 已正常工作。
4. 开始屏幕共享，选择该自建线路；另一端确认画面、声音及关闭后重新开启均正常。成功通话并不代表 SRT 已放通。
5. 经服务器所有者确认维护窗口后重启服务器，再检查上述服务和媒体传输。不要在有人使用时随意重启。

默认语音会优先尝试成员直连，必要时使用中继；因此正常通话不一定经过自建服务器。自建节点只服务所属 Room，离线后的行为由客户端和官方线路策略决定，不能据此承诺无中断切换。

故障定位、升级与停用请看[运维文档](OPERATIONS.md)。
