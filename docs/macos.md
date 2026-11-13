# macOS 运行与 USB 连接

TURZX Studio 在 macOS 使用 PyUSB 与 libusb 连接 `1CBE:0050` 屏幕。Windows 继续使用原生 WinUSB。页面渲染继续使用 Google Chrome。

## 安装与启动

安装 Python 3.10+、Node.js 18+ 和 Google Chrome，然后执行：

```sh
brew install libusb
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
.venv/bin/python server.py
```

打开 `http://127.0.0.1:8765/`。连接屏幕后，选择页面和方向，点击开始投屏。此启动命令不创建登录启动项。

macOS 的屏幕有时以 USB 配置 `0` 接入。配置 `0` 表示尚未选择接口。本程序仅在这种情况下选择设备唯一声明的配置。此操作是当前 USB 连接的配置选择，不写入屏幕持久设置，不刷固件。设备已有配置时，本程序保留该配置。

程序不重置 USB 设备，不卸载内核驱动，不结束其他屏幕软件。接口被占用时，停止占用程序后重新连接。检测到多块同型号屏幕时，程序拒绝自动选择。

## 帧格式与所有权

原生传输帧为 `720×1280 RGBA PNG`，全页 alpha 为 `255`。横屏页面按控制台选择的角度旋转后传输。完整 PNG 不超过 `1 MiB`。

本机通过六排列色块校准，用户确认 E 行正确；在控制台「显示 → 颜色修正」使用「循环修正 · BRG」。该设置只修正副屏输出，并保存到本机；预览和图片资源保持原色。其他设备应单独核验，不直接沿用本机设置。详见 [颜色通道校准](hardware-and-protocol.md#颜色通道校准)。

每个连接串行执行命令。写入超时为 `2000 ms`，读取 ACK 的总时限为 `2000 ms`。空 USB 包最多跳过两次，不重发命令。传输失败使该连接失效；必须关闭并重新连接。关闭操作只释放该连接拥有的接口。

服务拥有 USB 接口。运行独立 USB 探针前必须停止服务投屏。收到 ACK 只证明协议响应成功，不能证明屏幕上的画面正确。

## 验证记录

2026-11-13 在 macOS 上检测到 `1CBE:0050`。接口 `0` 提供 bulk IN `0x81` 和 bulk OUT `0x01`，最大包长均为 `512`。从配置 `0` 选择唯一配置 `1` 后成功打开接口。

本次发送一张静态校准帧。原生帧尺寸为 `720×1280`，模式为 RGBA，全部 alpha 为 `255`，文件大小为 `45,484` 字节。同步命令与 PNG 绘制命令均收到状态 `0xC8`。连接与发送总用时为 `0.146` 秒。发送后已关闭 USB 连接。

校准图包含四角标签、RGB 色条和灰阶。证据保存在本机 `runtime/macos-calibration-landscape.png`、`runtime/macos-calibration-native.png`、`runtime/macos-calibration-result.json`。这些文件不进入 Git。

用户已确认校准图画面完整、方向正确。随后通过工作台连续发送 Claude 与 cswap 两个页面，共 39 帧，实测约 2 帧/秒，没有传输错误。Claude 页完整帧为 500,847 字节，cswap 空态页完整帧为 141,411 字节；均小于 1 MiB。该次传输在 20 秒后正常停止。

执行无需硬件的传输回归：

```sh
.venv/bin/python -m unittest discover -s tests -p test_libusb.py -v
.venv/bin/python -m py_compile turzx_libusb.py
```

测试覆盖只读枚举、保留已有配置、未配置设备的唯一配置选择、空包处理、短写入、读取超时、无效 ACK、失效连接保护和重复关闭。

macOS 的 GPU、风扇、温度和实体网卡识别未在本次 USB 适配中新增。未提供的数据保留为空。
