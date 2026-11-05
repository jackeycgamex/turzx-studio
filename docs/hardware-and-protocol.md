# 硬件、协议与实测说明

核对日期：2026-11-06。本文包含可复核的型号、协议和验证结论；原始 USB 序列号、系统拓扑、日志及私人照片不进入仓库。

## 设备身份

参考设备枚举为 `TURZX1.0`，VID/PID 为 `1CBE:0050`，使用 Microsoft WinUSB。此标识与上游 **Turing 5.2 英寸、720×1280 原生方向**对应，官方横屏规格为 **1280×720**，不能与旧款 800×480 串口 5 英寸屏混用。

| 项目 | 证据 |
|---|---|
| 型号与分辨率 | [固定版本型号表](https://github.com/mathoudebine/turing-smart-screen-python/blob/2b33ab4f00a096916dd6a1174441a53a7ec33b03/library/lcd/lcd_comm_turing_usb.py)与[作者实测发布记录](https://github.com/mathoudebine/turing-smart-screen-python/releases/tag/3.10.0) |
| 系列尺寸与接口 | [官方目录](https://www.turzx.com/)列 127×71 mm、USB-C / PH1.25、Windows 10/11 |
| USB 接口 | 实读 USB 2.0 High-speed、interface 0、bulk IN `0x81` / OUT `0x01`，最大包 512 B |
| 设备版本标识 | 同步返回原串 `turzx_0001_0015`，不改写成“v1.15” |
| 供电字段 | 描述符声明 120 mA；不是实测功耗 |
| 存储查询 | 查询成功但容量字段为零，不能据此认定没有存储硬件 |

“支持桌面模式”来自官网，当前图片路径仍是 WinUSB。切换模式、安装虚拟显示驱动和设备重启均不包含在应用流程中。

## 传输与 RGBA 兼容性

屏幕不执行网页。Chrome 渲染本地页面，主机旋转整图到 720×1280，再通过串行化 WinUSB 事务发送。

协议参考 [MIT 实现 ScreenDevice.cs](https://github.com/usausa/turing-smart-screen/blob/ade6bd871aa22430b0061eed890f2cd191c3d276/LcdDriver.TuringSmartScreen/ScreenDevice.cs)，许可声明已保留。500 字节命令体按公开格式填充、DES-CBC 编码并封装为 512 字节，图片数据随后发送。固定协议值不是用户凭据。核心命令为同步 10、PNG 102，亮度接口为 14；源码另保留 JPEG 101 方法，但正常画面路径只用 RGBA PNG。

事务检查写入长度、命令回显和 ACK，并设有限超时。服务单独持有设备句柄，旧会话请求不能写入或关闭新会话。停止保留最后一帧，不代表关屏。

参考设备接受 RGB PNG（color type 2）并返回 ACK，却出现重复条带和旧背景。改用 **RGBA PNG（color type 6）、alpha=255** 后，人工对照确认图像完整、方向正确。可以确认此设备存在 RGB PNG 显示兼容问题；内部是否使用错误像素步长仅属推测。此经验与上游 RGBA 画布一致，不能推断所有型号或固件都相同。

驱动现在主动拒绝 RGB PNG，无硬件测试覆盖 RGB 拒绝、RGBA 接受和尺寸检查。超过 1 MiB 时进一步压缩 PNG，仍超限则报错，不静默切到可能被旧覆盖层遮挡的 JPEG。

## 有限传输测试

以下为一台 Windows 11 主机的渲染链路与 USB 事务测量，不是面板刷新率或发光延迟。

| 场景 | 请求 fps | 成功帧数 | 时长 | 实际发送 fps | USB p50 / p95 |
|---|---:|---:|---:|---:|---:|
| 八页巡回 | 2 | 49 | 24.55 s | 2.00 | 86.97 / 114.75 ms |
| 混合场景 | 5 | 73 | 15.19 s | 4.80 | 70.75 / 109.37 ms |
| 生成氛围 | 10 | 74 | 15.22 s | 4.86 | 104.30 / 118.82 ms |

5 fps 区间发生页面切换，不是纯动画基准。三个区间共 196 帧通过 ACK 校验，停止后重新打开并发送通过；未测试长时间运行或真实拔插恢复。

八页均检查了 1280×720 和 720×1280 排版，控制台检查了桌面及窄窗口。人工实物确认覆盖横屏校准图，竖屏仅验证了软件重排。

## 能力边界

| 当前可用 | 仍需接入或验证 |
|---|---|
| CPU、内存、GPU、显存、磁盘、网卡 | 温度、风扇、功耗、实时 CPU 频率 |
| 时钟、倒计时、便签 | 天气、日历、播放器、训练任务数据 |
| 程序动画、图片推送 | H.264 直传、离线播放与存储 |
| 四向主机旋转、横竖重排 | 官方桌面模式和虚拟显示驱动 |
| 浏览器控制、原生尺寸校准 | 触控、音频、面板响应时间与色度指标 |

没有可靠依据的面板、主控、功耗与色域参数保持未知。更多一手资料：[Microsoft WinUSB](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/using-winusb-api-to-communicate-with-a-usb-device)、[psutil API](https://psutil.readthedocs.io/en/latest/)、[Windows GPU 指标说明](https://devblogs.microsoft.com/directx/gpus-in-the-task-manager/)。
