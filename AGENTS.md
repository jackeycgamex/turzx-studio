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

## Verification

Run Python compilation and JavaScript syntax checks for changed modules. Check affected pages at 1280×720 and 720×1280, and the controller at desktop and narrow widths. For USB changes, first transmit one static calibration frame and compare physically before running a bounded throughput test. User photo evidence outranks browser captures.

Do not commit, push or create PRs unless asked.
