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

## 登录后自动启动

使用项目虚拟环境安装当前用户的 LaunchAgent：

```sh
.venv/bin/python autostart_macos.py
```

安装后立即启动服务。以后每次开机并登录此 macOS 用户，后台自动启动，不打开浏览器或终端。若 8765 端口已有服务，请在管理页关闭服务后再安装。重复安装不会启动第二个进程。

服务恢复 `runtime/display-preferences.json` 中的页面、方向、图片、颜色校准和背光亮度。每次重新连接设备时，在发送画面前恢复已保存的背光亮度；旧配置没有亮度值时不改动背光。此前正在投屏时会自动恢复；此前手动停止投屏时保持停止。USB 晚于服务接入也会自动恢复。异常退出后 launchd 重启服务；管理页正常关闭服务后，当次登录不会重启。

日志位于 `runtime/launchd.stdout.log`、`runtime/launchd.stderr.log` 和 `runtime/server.log`。这是登录后的用户服务，不是登录前的系统服务。移动项目或虚拟环境后，应取消并重新安装启动项。

取消启动项并停止它管理的服务：

```sh
.venv/bin/python autostart_macos.py --disable
```

## 帧格式与所有权

原生传输帧为 `720×1280 RGBA PNG`，全页 alpha 为 `255`。横屏页面按控制台选择的角度旋转后传输。完整 PNG 不超过 `1 MiB`。

本机最新静态复核结果为「0，A」：不偏移时顶部刻度为 0，RGB 标准色序正确。当前使用「标准颜色」和零位置补偿。此前确认过的 BRG 与 -60 像素补偿在本次连接中已不适用。用户实物反馈优先，其他设备应单独核验。详见 [颜色通道校准](hardware-and-protocol.md#颜色通道校准)。

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
