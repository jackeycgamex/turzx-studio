# OpenAI 订阅副屏使用说明

OpenAI 场景同时展示 ChatGPT 功能剩余次数、Work / Codex 共享额度，以及真实订阅周期与续费状态。额度正常每 60 秒同步，账单正常每 30 分钟同步；投屏与倒计时刷新不代表每帧都向 OpenAI 查询。

## 运行前提

- 本机已安装 Codex CLI，并在 Codex 中登录 ChatGPT 订阅账户。仅 API key 登录不提供此处所需的订阅信息。
- 服务能找到已安装的 `codex.exe`。默认检查 PATH 及常见 npm 安装目录；自定义位置可通过 `TURZX_CODEX_PATH` 指向实际 `.exe`，再启动服务。
- ChatGPT 网页读取器需要当前 Codex 的 OAuth 登录文件：优先使用 `CODEX_HOME/auth.json`，未设置时使用用户目录的 `.codex/auth.json`。邮箱须与 app-server 返回的 Codex 账户一致；缺失、无效或不一致时提示重新登录，不要求手工复制凭据。
- 沿用项目已有 Python、renderer/Chrome 环境。实体屏使用现有 WinUSB 驱动，不需要换驱动、刷固件或保存面板设置。

在项目目录执行 `python -X utf8 server.py`，或运行 `启动.cmd`，打开 [本地控制台](http://127.0.0.1:8765/)。已有服务时复用当前实例；`停止.cmd` 请求优雅退出。本功能不设置开机自启。

## 控制台操作

1. 选择 **OpenAI 订阅**，等待各来源读取。该场景启用 VS Code 浅色风格，其他场景保持原样。
2. 额度总览并列显示返回的前两项 ChatGPT 功能额度（当前已验证深度研究、图像生成）及选中分组的 Work / Codex 共享额度；底部展示续费、自动续费、credits 和重置机会。功能次数与共享百分比不相加。
3. 用“内容”切换总览、套餐与续费、ChatGPT 额度明细。手动选页关闭三页详情轮播；开启“详情轮播 · 15 秒”可轮换三页。功能明细独立按每页最多四项、每 15 秒自动翻页。固定订阅场景时同时关闭通用场景轮播。
4. 返回多个共享额度分组时才显示“额度分组”；单分组隐藏此控件。所有功能条目、额度桶与窗口按返回数据处理，不补造第二个窗口或无限额度。
5. “刷新订阅数据”提前请求 Codex 与 ChatGPT 两路来源，并强制重读 ChatGPT 功能额度和账单，不必等待账单正常周期。重复请求合并，两次读取尝试至少间隔 10 秒；成功以对应来源的同步时间为准。
6. 设置方向和发送帧率后点击投屏按钮。横屏为 1280×720，竖屏为 720×1280，内容重排。账户切换在 Codex 内完成，再刷新；官方用量和订阅设置链接用于核对记录，工作台没有登录、购买、续费修改或重置兑换入口。

## 两路数据来源

`subscription.py` 启动独立的 `codex.exe app-server --stdio`，初始化后调用 `account/read`（`refreshToken: false`）和 `account/rateLimits/read`，读取账户与共享额度。协议见 [Codex App Server](https://learn.chatgpt.com/docs/app-server)。

`chatgpt_account.py` 另行调用固定的 ChatGPT 网页账户接口：

| 请求 | 用途 |
| --- | --- |
| `GET https://chatgpt.com/backend-api/subscriptions?account_id=...` | 读取订阅状态、账期、续费时间、购买渠道和币种 |
| `POST https://chatgpt.com/backend-api/conversation/init`，body 为 `{}` | 初始化页面额度信息，读取 `limits_progress` 与可选 `model_limits` |

额度初始化不提交 prompt、messages 或推理任务，不创建内容或兑换额度。上述网页接口不是稳定、版本化的公共 API；字段或访问规则变化时可能失效。实现对响应格式、超时和体积设限，失败显示安全错误并保留适用的旧采样，不使用伪造数据补齐。

## 字段口径与缺失边界

| 数据 | 当前行为 |
| --- | --- |
| 套餐与账户 | 使用 Codex 账户套餐和后端脱敏邮箱 |
| ChatGPT 功能额度 | 从 `limits_progress` 的实际功能条目读取剩余次数与 ISO `reset_after`；已验证深度研究、图像生成 |
| 模型计数 | 只接收 `model_limits` 中明确返回的剩余计数；空列表不表示无限 |
| Work / Codex 共享额度 | 按实际分组展示存在的 primary / secondary 窗口；剩余百分比由已用百分比换算 |
| credits 与重置机会 | 保留来源余额、不限额标记及可用次数；只展示，不兑换、不折算现金或任务数 |
| 当前账期 | 使用 `active_start` / `active_until` |
| 下次续费 | 使用 `entitlement.renews_at`；`expires_at` 为权益到期，可能含宽限期，不能代替续费时间 |
| 自动续费、周期与渠道 | 使用 `will_renew`、`billing_period` 和购买平台；例如平台字段可映射为 Google Play、App Store 或网页 |
| 币种与续费金额 | 币种来自 `billing_currency`；本接口未返回下次实扣金额，套餐标价和历史账单均不能代替 |
| 普通 ChatGPT 聊天消息、语音独立计数 | 当前来源未返回，不推算次数或总上限 |
| OpenAI API 用量与账单 | 本版不接入；也不提供发票下载或支付记录列表 |

当前官方用量页将 Work、Codex、agents 和 Excel 计入共享额度，普通 ChatGPT 聊天不计入该共享额度；这与深度研究、图像生成等独立功能次数是不同口径。可通过控制台的 [官方用量](https://chatgpt.com/codex/settings/usage) 入口核对，实际账户限制以官方显示为准。

真实来源与 ChatGPT 网页的续费记录已交叉核对。用户套餐、日期、余额、次数与币种都由当前账户返回，不写入固定配置或公开示例。未知、零值、不限额和未返回分别处理；登录套餐本身不证明已支付或自动续费开启。

## 同步、过期与账户切换

| 来源 | 正常读取周期 | 过期阈值 |
| --- | --- | --- |
| Codex 共享额度 | 60 秒 | 180 秒 |
| ChatGPT 功能额度 | 60 秒 | 180 秒 |
| ChatGPT 订阅/续费 | 1800 秒 | 3600 秒 |

Codex 每个 RPC 请求超时为 20 秒，ChatGPT 网页请求超时为 8 秒。账单读取成功后按正常周期缓存，失败会在后续轮询重试。ChatGPT 功能额度与账单各自维护状态、采样时刻和错误；Codex 额度失败时仍可尝试读取 ChatGPT。账户身份无法确认时暂停该轮后续读取，避免混用账户。

一项来源失败不会把其他成功来源清空。综合页提示“部分来源未同步”，对应区域保留自己的状态；账单与明细页使用本来源状态和时间。有旧值时显示过期或上次读取提示，功能/共享额度数字及进度变灰，保留旧重置时刻；无旧值时显示空态。重置时刻已到只显示等待更新，不自行补满。

检测到 Codex 账户变化后，先清空旧账户的共享额度、功能额度、账单和采样时刻，再读新账户。ChatGPT 读取器还会在每轮读取前通过 `bind_account` 绑定 OAuth `account_id` 的私有 SHA-256 哈希，识别同邮箱下的工作区变化；该标识仅供本地比较，不输出到页面。每个 HTTP 请求前再次读取并校验身份，防止绑定后账户又发生切换。

身份检查先于缓存有效期判断。即使没有手动强制刷新，OAuth 文件不可用、邮箱不一致或请求前发现账户变化时，也立即清空 ChatGPT 功能额度和账单两份缓存，避免一份失败而另一份仍显示旧账户信息。正常工作区变化同样先清空两份 ChatGPT 缓存，再读取新工作区数据。

## 凭据与进程边界

新版 ChatGPT 读取器**会读取本机 Codex 的 `auth.json` OAuth 凭据**；此前“完全不读取凭据文件”的描述仅适用于旧版 app-server 单来源实现，已不适用。登录和 token 更新仍由 Codex 管理，读取器只在内存中使用现有 access token 和账户标识，不另存凭据、不输出到日志或页面。

发送目标固定为上述 `chatgpt.com` HTTPS 接口，禁止 HTTP 重定向，防止凭据随重定向外发。读取前将本地 ID token 中邮箱与 Codex 当前账户邮箱比较，作为本地防串号检查；服务器负责验证 access token。失败错误不透传原始响应正文。页面只接收脱敏账户摘要及规范化数据。

本地服务仅绑定 loopback。`GET /api/subscription` 与 `GET /api/state` 返回展示快照，不应公开到互联网。截图即使邮箱已脱敏，仍可能含套餐、额度与续费信息。

服务只清理自己启动的 app-server 及其子进程，不关闭 Codex 桌面应用。USB 句柄统一由服务持有，直接硬件探测前必须停止投屏。

## 故障恢复

| 现象 | 操作 |
| --- | --- |
| 未找到 Codex CLI | 检查 `codex.exe`，必要时设置 `TURZX_CODEX_PATH` 后重启服务 |
| OAuth 登录缺失、失效或账户不一致 | 在 Codex 中重新登录目标 ChatGPT 账户，再刷新；不要手工粘贴 token 到网页或配置 |
| 仅部分来源失败 | 查看对应来源的错误和同步时刻，检查网络与登录；可手动刷新全部来源 |
| 429 或读取超时 | 等待后续轮询，避免连续重复刷新 |
| 网页接口格式变化 | 保留错误与旧采样状态，等待适配；官方页面仍可用于核对，不生成替代数据 |
| 只有一个共享窗口或模型列表为空 | 按返回内容展示，不能推断第二个窗口或无限权限 |
| 普通聊天/语音次数或实扣金额未提供 | 属于当前缺失字段，使用官方页面核对；重复刷新不会补出不存在的字段 |
| 浏览器正常但实体画面异常 | 停止投屏，确认方向与设备连接，按项目校准流程目视核对；ACK 不等于显示正确 |

## 验证与设计依据

在项目根目录可执行：

```powershell
python -X utf8 -m py_compile chatgpt_account.py subscription.py server.py
python -X utf8 -m unittest discover -s tests -v
node --check web/subscription.js
node --check web/studio.js
node --check web/display.js
node tests/test_subscription_ui.cjs
```

本轮已通过 35 项 Python 测试及 `node tests/test_subscription_ui.cjs`，独立代码与八张界面图复审结论为 ship。`runtime/chatgpt-qa/` 包含 `overview`、`billing`、`entitlements` 各自的 `-1280.jpg` / `-720.jpg`，以及 `controller-desktop.jpg`、`controller-narrow.jpg`；最终生产总览捕获为 `live-overview.jpg`。

最终版本已部署，保留用户当前 `rotation=0` 竖屏方向，持续发送约 2 fps，实测每帧约 135 KiB 以下。真实 ChatGPT 功能数据已跨过 60 秒自动刷新，账单来源为 live。这些是运行与传输证据，本轮尚未获得用户目视确认。上一轮 `runtime/openai/light-*.png` 及用户对横屏“显示正常，方向和文字都正确”的确认仅覆盖当时版本，不作为本轮实体观感验收。

浅色主题来自本机 VS Code 内置 `2026 Light`（include `light_modern.json`），背景见 [VS Code 1.113 发布说明](https://code.visualstudio.com/updates/v1_113)。视觉规范见 [DESIGN.md](../DESIGN.md)，范围与历史稿见 [设计 brief](design/openai-subscription/brief.md)。

实体 PNG 必须为 720×1280 RGBA、alpha 全为 255，完整载荷小于 1 MiB。横屏经服务端既有图像转换路径旋转后发送，方向仍由用户控制。物理效果须独立观察或照片核对，不能用浏览器截图、发送帧率或 ACK 替代。
