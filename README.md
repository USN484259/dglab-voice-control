# DG-LAB Voice Control

郊狼语音控制客户端


## 使用说明

1. 下载[Vosk中文语音模型](https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip)，解压到同目录
2. 下载[qrcode.min.js](https://github.com/davidshimjs/qrcodejs/raw/refs/heads/master/qrcode.min.js)到client目录下
3. 运行 `python3 dglab_voice_control.py` 列出当前音频设备，记录要使用的设备序号
4. 编辑 *config.toml*，按照文件内提示进行配置
5. 运行 `python3 dglab_voice_control.py config.toml` 启动软件
6. 软件初始化完成后会自动打开网页，显示连接二维码
7. 手机和PC处于同一局域网中，郊狼App进入*SOCKET控制*，扫码连接
8. 等待App提示连接成功，网页中二维码消失，使用过程中请保持网页打开
9. 语音识别的结果和当前通道强度会在网页上显示


## 配置文件

配置文件规则详见 *config.toml* 中的注释


## 命令行参数

`dglab_voice_control.py [-v] [config]`

* -v, --verbose:	启用详细日志信息
* config:		配置文件路径，若不指定则列出当前音频设备后退出


## 依赖

* Python >= 3.8
* vosk
* sounddevice
* aiohttp
* toml (for Python < 3.11)


## 引用

+ [DG-LAB 开源](https://github.com/DG-LAB-OPENSOURCE/DG-LAB-OPENSOURCE)
+ [Vosk](https://alphacephei.com/vosk/) is a speech recognition toolkit.
+ [sounddevice](https://python-sounddevice.readthedocs.io): Play and Record Sound with Python.
+ [aiohttp](https://docs.aiohttp.org/): Asynchronous HTTP Client/Server for asyncio and Python.
+ [QRCode.js](https://github.com/davidshimjs/qrcodejs) is javascript library for making QRCode
+ [TOML](https://toml.io): A config file format for humans.

## LICENSE

MIT License

Copyright (c) 2025 USN484259
