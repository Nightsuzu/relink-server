# 运维与排错

## 日常检查

```bash
sudo systemctl status relink-room-agent relink-room-media relink-room-turn --no-pager
sudo journalctl -u relink-room-agent -n 80 --no-pager
sudo journalctl -u relink-room-media -n 80 --no-pager
sudo journalctl -u relink-room-turn -n 80 --no-pager
```

安装日志在 `/var/log/relink-node-install-*.log`，仅 root 可读取。日志和服务配置可能包含 IP 或访问凭据，分享前手动脱敏；不要将日志整份上传 Issue。

## 常见问题

| 现象 | 检查与处理 |
| --- | --- |
| 找不到配置 | 将官方签发文件放在部署包旁或 `/root/relink-node-setup.json`，也可使用 `--setup` 指定绝对路径 |
| 配置无效 | 核对是否官方完整文件、UTF-8 编码和非示例占位值；不要手工生成 token |
| 包校验失败 | 重新下载部署包和校验文件；不要跳过校验或混用版本 |
| 端口被占用 | 先确认占用者；使用另一台服务器或规划迁移，不要直接杀掉未知进程 |
| 安装未完成 | 保留原文件和私密安装日志，运行 `doctor`；脚本不会自动清理或强行重装 |
| 三个服务运行但线路离线 | 检查官方 WSS、DNS、服务器时钟、出站 TCP 443、登记 IP 与真实出口 IP；NAT、VPN 或代理出口不匹配会被拒绝 |
| 语音能通、屏幕无画面 | 检查双层防火墙的 UDP 8890，确认共享选择的是该自建线路；语音直连不代表屏幕链路正常 |
| 同网络成功、异地失败 | 使用不同运营商/网络验收，检查 UDP 49160–50183 和 NAT；不要只在同一局域网测试 |
| 并发增加后失败 | 检查云出站带宽、流量额度、节点容量登记值与 CPU；降低共享画质或分散线路 |

代理与官方断开后每 3 秒尝试重新连接。失去授权时会清理共享路径，不能把重连理解为允许继续匿名传输。

## 备份、更新与停用

备份官方配置与 `/opt/relink-room-node/config/`，仅保存到自己的私密备份位置。现有安装器不会原地升级；升级前安排维护窗口、备份并核实目标版本，不要混用旧程序和新 manifest。

停用会断开节点上的媒体会话：

```bash
sudo systemctl disable --now relink-room-agent relink-room-turn relink-room-media
```

随后由 Room 域主通过 Relink 运营撤销该节点登记。此项目没有自动卸载或删除配置功能。

## 带宽与费用

节点的 `capacityMbps` 是官方线路分配的容量参考，不是操作系统流量整形；TCP/UDP 实际吞吐仍由你的云服务与网络决定。自建线路的 Relink 屏幕价格为零，云服务器、带宽和流量费用仍由服务器所有者承担。其他账号、订阅权益与商城计费不因部署节点而改变。

## 验证范围

源码包含安装器拒绝无效配置、保护既有安装、预演不写系统、包路径与完整性检查、帧率探测测试。运行测试通过不等于每种 Linux、每个云厂商、防火墙规则或真实公网媒体流都已验收。按照部署文档完成在线状态、异网语音/屏幕和重启检查。
