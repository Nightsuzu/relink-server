# 第三方组件

源码仓库的 MIT 许可仅适用于 Relink 自有代码和文档，不改变以下组件的许可。

| 组件 | 版本 | 许可与来源 |
| --- | --- | --- |
| Node.js | 24.20.0 | [官方源码与许可证](https://github.com/nodejs/node/tree/v24.20.0)，发行包包含完整 LICENSE 及第三方许可 |
| ws | 8.21.3 | [MIT](https://github.com/websockets/ws)，`npm ci` 固定版本，部署包保留 LICENSE |
| coturn | 4.18.0 | [BSD-3-Clause](https://github.com/coturn/coturn/tree/4.18.0)，部署包包含完整源码及 LICENSE |
| FFmpeg / FFprobe | 9.0.1 | [LGPL-2.1-or-later](https://ffmpeg.org/legal.html)，最小 FFprobe 未启用外部编解码器或 GPL 选项，完整对应源码包含在包中 |
| MediaMTX | v1.20.1-tsns-rewind16m | [MIT](https://github.com/bluenviron/mediamtx)，沿用当前 Relink 兼容二进制，保留上游许可证 |

MediaMTX 的 Relink 兼容二进制由官网提供，锁定摘要见 components.lock.json。本仓库公开安装器、节点代理及控制代码，并未声称包含该定制二进制的全部构建源码；上游源码可从上述链接取得。

FFprobe 构建命令（Linux x64 / glibc 2.28）：

```bash
./configure --disable-everything --disable-autodetect --enable-ffprobe --enable-network --enable-protocol=tcp,udp,rtp --enable-demuxer=rtsp,rtp,sdp,mpegts,h264 --enable-parser=h264,aac --enable-decoder=h264,aac --disable-doc --disable-debug --disable-x86asm --disable-ffmpeg --disable-ffplay --enable-small
make -j1 ffprobe
```

coturn 在目标机从随包源码编译，禁用 MySQL、PostgreSQL、Redis、SQLite 后端。自有代码 MIT 授权不包括 Relink 名称、图标的商标权，也不授予官方服务的无授权接入权限。
