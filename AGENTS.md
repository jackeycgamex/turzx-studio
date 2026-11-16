# TURZX Studio

Local Windows project for the USB-connected TURZX 5.2-inch screen, VID:PID `1CBE:0050`.

## Run

- `python -X utf8 server.py` starts preview/control at `http://127.0.0.1:8765/`.
- `启动.cmd` launches the hidden service and opens the controller; `停止.cmd` requests graceful shutdown.
- Reuse the installed Microsoft WinUSB driver. Do not install a replacement, flash firmware, save persistent panel settings or enable autostart as an incidental change.
- The service owns the USB handle. Stop streaming before running a direct hardware probe.

## Layout

- `web/`: controller and eight native-resolution views.
- `server.py`: local HTTP bridge, timer, USB ownership and rendering lifecycle.
- `renderer.cjs`: independent headless Chrome, restricted to this localhost page.
- `turzx_usb.py`: ctypes WinUSB transport and public protocol.
- `telemetry.py`: read-only psutil / DXGI / PDH telemetry.
- `runtime/`: descriptors, validation evidence and runtime logs.
- `research/`: five exploration reports and follow-up findings.

## Important behavior

- Physical PNG frames are **720×1280 RGBA**, color type 6. RGB PNGs can receive a successful ACK yet render as repeated strips over the stock background on this unit. Full pages require alpha 255 everywhere. Never infer visual success from ACK alone.
- Keep the complete PNG payload below 1 MiB. JPEG and PNG target different display layers; do not silently replace an opaque PNG with JPEG without testing overlay clearing.
- User-facing landscape is 1280×720, rotated 270° for native transfer. Portrait pages reflow at 720×1280. Rotation remains user-controlled.
- All transport transactions have bounded timeouts and serialize ownership. Old session requests must not close or write to a new session.
- Missing temperature, power, fan and realtime frequency values remain null. Never synthesize a plausible reading.
- Capacity fields ending `_gb` contain GiB; network `_bps` fields contain bytes per second. Label units accordingly.
- Bind only to loopback. Do not serve source, logs or arbitrary paths via the web root.

## Claude 两端同步更新

- 投屏页面与 macOS「Claude 账号面板」必须在同一轮同步更新。任一端修改共享布局、字体、背景图片、图片调节或账号数据展示时，必须同步另一端的源码和实际运行版本。
- 两端复用一致的 `web/claude.js`、`web/claude.css`、`web/design-tokens.css`、字体和 `web/assets/claude/` 资源。账号面板的点击切换和操作提示属于 App 专用交互，不要求投屏页面提供这些交互。
- 账号面板安装包内的页面和图片是构建时的副本。更新源码或同步背景参数不等于更新安装包。共享内容变更后，必须重建、验证并更新 `~/Applications/Claude 账号面板.app`，保留可恢复的旧包，打开新版确认生效。
- 核对正在投屏的服务所用目录、账号面板源码目录和已安装 App 的资源，不能只核对当前 worktree。涉及多个 checkout 时，将共享改动同步到对应源码，不覆盖无关改动。
- 使用相同数据验证两端在 1280×720 和 720×1280 下的账号画面一致，并检查 App 在 390×844 下的布局。运行账号面板源码中的 `tests/test_account_app_parity.cjs` 和 `tests/test_account_app_ui.cjs`；图像对比可隐藏 App 专用操作提示，测试不得切换真实账号。
- 交付前确认已安装 App 的背景选择、亮度、色彩浓度和淡化值与投屏服务一致。只更新一端或只更新源码，不算完成。

## Verification

Run Python compilation and JavaScript syntax checks for changed modules. Check affected pages at 1280×720 and 720×1280, and the controller at desktop and narrow widths. For USB changes, first transmit one static calibration frame and compare physically before running a bounded throughput test. User photo evidence outranks browser captures.

Do not commit, push or create PRs unless asked.
