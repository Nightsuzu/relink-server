# Relink Server

为自己的 Relink Room 搭建语音中继和屏幕共享节点。

**[完整部署教程](docs/DEPLOYMENT.md) · [运维与排错](docs/OPERATIONS.md) · [官网下载入口](https://relinkus.cn/server/)**

## 这个项目包含什么

Relink 编写的节点代理、安装器、诊断工具、打包工具及部署文档，使用 MIT 许可证。节点通过 coturn 提供语音中继，通过 MediaMTX 提供 SRT 屏幕传输。

账号登录、Room 管理、消息、星卡与星律等仍使用官方服务。本项目不是完整商业客户端或中心业务服务器的开源版。节点仅服务登记的 Room；每个 Room 最多登记三个节点。

## 快速开始

1. 准备带公网 IPv4 的 Linux x64 云服务器，使用 systemd、glibc 2.28 或更新版本。
2. Room 域主先向 Relink 运营申请登记节点，取得 `relink-node-setup.json`。**当前尚无客户端自助登记表单，示例配置不能用于接入。**
3. 从[官网教程](https://relinkus.cn/server/)下载 `2.1.3` 部署包及 SHA-256 校验文件，解压，将配置放在部署包旁。
4. 放行 TCP/UDP `3478`、UDP `8890` 和 UDP `49160–50183`，运行：

```bash
sudo bash setup.sh
```

安装器会检查系统、配置、端口和包完整性，再安装三个服务并启用开机自启。不会修改防火墙，也不会覆盖已有节点。编译 coturn 及安装系统依赖需要访问软件源。

```bash
bash setup.sh plan --setup /absolute/path/relink-node-setup.json
sudo bash setup.sh doctor
```

`plan` 只校验包及配置，不代表云服务器或公网通话已经验证。三个服务均为 `active` 后，还要确认官方接入状态，再用两个不同网络的客户端测试语音和屏幕共享。

## 从源码制作部署包

需要 Python 3.9+、Node.js 24 和 npm：

```bash
npm ci --ignore-scripts
python3 tools/fetch-components.py
python3 tools/build-bundle.py
```

输出位于 `dist/`。二进制依赖固定版本并校验 SHA-256；组件信息见 [components.lock.json](components.lock.json) 和 [第三方声明](THIRD_PARTY_NOTICES.md)。其中 MediaMTX 是 Relink 当前兼容构建，不要未经验证自行替换。

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.mjs
```

安装器的自动检查、源码测试与真实服务器部署是不同的验证环节。当前发布附带完整性和自动测试结果；具体服务器的防火墙、重启及公网媒体传输请按教程验收。

## 许可与反馈

Relink 自有代码与文档采用 [MIT](LICENSE)。第三方组件保留各自许可证；源码仓库不包含账号数据、生产配置或已授权密钥。请勿在 Issue 上传配置文件或完整日志。问题报告建议附操作系统、部署包版本、发生时间和已脱敏的错误信息。
