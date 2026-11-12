# OpenAI 订阅副屏

状态：用户已确认原 UI、授权真实数据与投屏，随后指定 IT 风格、参考 VS Code 默认浅色，并进一步要求不能只展示 Codex。本轮已接入 ChatGPT 功能额度与订阅续费，三页及控制台通过独立代码与八图复审，结论为 ship；最终版本已部署并持续竖屏投送。本轮尚未用户目视确认，上一轮横屏确认不自动覆盖本轮。

## 目的与当前方向

模式为 Operate。用户一瞥可读 ChatGPT 深度研究、图像生成等实际功能剩余次数、Work / Codex 共享额度和真实续费状态。副屏只展示，电脑控制台承担刷新、切页、轮播与输出。

当前视觉依据为 `web/subscription.css`、`web/subscription-workbench.css` 和 `runtime/chatgpt-qa/*.jpg`。沿用 VS Code `2026 Light`（include `light_modern.json`）的白色主区、近白工具栏、深灰文字、蓝色数字与细分隔线；正文 Segoe UI / Microsoft YaHei，数字 Cascadia Code / Consolas。隔离 token 见 [DESIGN.md](../../../DESIGN.md)，其他场景与动画保持原样。

本目录深色 PNG、`design-board.png` 与 `render_mockups.py` 为历史静态提案，示例套餐、日期、比例和功能不代表账户事实。`runtime/openai/light-*.png` 记录上一轮浅色实现，也不替代本轮新增内容的验收。

## 信息架构

| 页面 | 当前实现 |
| --- | --- |
| 额度总览 | 套餐与脱敏账户，前两项实际 ChatGPT 功能剩余次数及重置时间，Work / Codex 共享窗口；底部续费时间、自动续费、credits、重置机会 |
| 套餐与续费 | 订阅状态、当前账期、下次续费、自动续费、周期、购买平台与币种；续费实扣金额明确未提供 |
| ChatGPT 额度明细 | 按实际功能/模型计数列表展示剩余次数与重置时间，每页四项、15 秒翻页 |

已从真实来源验证深度研究、图像生成的 `limits_progress` 剩余次数与 ISO `reset_after`；当前 `model_limits` 为空，不能理解为无限。普通聊天消息与语音独立计数、续费实扣金额仍未返回，不由套餐名称、标价或历史账单推断。

官方用量页说明 Work、Codex、agents、Excel 使用共享额度，普通 ChatGPT 聊天不计入该额度；独立功能次数不与共享百分比相加。所有窗口、次数、币种、日期与套餐按实际账户返回，不将本次私有值写成常量或公开示例。

## 数据源与凭据

- Codex app-server 提供 `account/read` 和 `account/rateLimits/read`，读取账户及共享额度。协议见 [Codex App Server](https://learn.chatgpt.com/docs/app-server)。
- ChatGPT 订阅读取使用固定 `GET https://chatgpt.com/backend-api/subscriptions?account_id=...`，功能额度使用 `POST https://chatgpt.com/backend-api/conversation/init`、body `{}`。初始化请求没有 prompt、messages 或推理任务，不兑换额度或修改订阅。
- 网页接口不是稳定的公共 API。字段变化或访问失败保留适用旧采样并标记错误，无旧值则显示空态，不补造数据。
- 新版读取器会读取当前 Codex `auth.json` 的 OAuth 凭据，在内存中使用；不会另存或输出凭据。邮箱与当前 Codex 账户做一致性检查，目标限定固定 `chatgpt.com` HTTPS，禁止重定向，错误不透传原始正文。旧版“不读取 auth.json”的声明已不适用。

账期使用 `active_start` / `active_until`；续费使用 `entitlement.renews_at`，不能以可能包含宽限期的 `expires_at` 替代。购买平台、`will_renew` 与 `billing_currency` 直接取自订阅响应，已与官方网页续费记录交叉核对。OpenAI API 用量与账单仍不在范围内。

## 布局与交互

- 横屏 1280×720、竖屏 720×1280。总览横屏三列、竖屏三行，每区保持自己的来源、单位与重置信息。共享窗口的单双布局只影响共享区；缺失时显示空态，不强制补齐。
- 套餐与续费页横屏左右分区、竖屏上下排；明细最多四项一页，竖屏将重置时间换行。控制台同时适配桌面和窄屏，只在 OpenAI 场景启用浅色主题。
- 控制台手动选页关闭三页轮播；可选 15 秒轮播三页。明细列表超过四项时独立按 15 秒分页。多个共享额度分组才显示分组选择；账户在 Codex 中切换。
- Codex 与 ChatGPT 功能额度正常每 60 秒读取，超过 180 秒过期；账单正常每 1800 秒读取，超过 3600 秒过期。手动刷新可强制更新全部来源，重复请求合并，两次尝试至少间隔 10 秒。
- 画面与倒计时刷新独立于网络读取。绝对时间为北京时间，倒计时归零显示等待额度更新，不自行补满。零值标记耗尽，实际 blocked 功能标记受限；本版不提供低额度阈值配置。
- 官方用量与订阅设置入口保留在电脑端，实体屏不放伪按钮。方向由用户控制。

## 状态与缺失处理

各来源保留独立成功时刻、错误与过期状态。一源失败不抹掉其他成功数据；综合页提示部分来源未同步，账单和明细页显示本来源状态。旧额度变灰并标明上次读取，保留旧重置时间并提示待确认；未曾读取成功时显示 — 或错误。

Codex 账户切换先清除旧账户全部来源的缓存，再读新账户。ChatGPT 每轮通过 `bind_account` 绑定 OAuth `account_id` 的私有哈希，识别同邮箱工作区变化，并在每次 HTTP 读取前再次校验。该检查早于缓存有效期判断：即使无手动强制刷新，身份失效也立即清除功能额度和账单两份 ChatGPT 缓存；工作区变化先清两份缓存再读取。私有哈希不进入页面。缺失、零值、不限额、未返回分别表达，禁止把空模型列表写成无限。

## 交付与验证

本轮通过 35 项 Python 测试及 `node tests/test_subscription_ui.cjs`，独立代码与八图复审结论为 ship。完整浏览器证据位于 `runtime/chatgpt-qa/`：`overview`、`billing`、`entitlements` 各自的 `-1280.jpg` / `-720.jpg`，以及 `controller-desktop.jpg`、`controller-narrow.jpg`；最终生产捕获为 `live-overview.jpg`。操作与复验命令见 [使用说明](../../openai-subscription.md)。

最终版本保留用户当前 `rotation=0` 竖屏方向，持续约 2 fps 投送，每帧约 135 KiB 以下。真实 ChatGPT 功能来源已跨 60 秒自动刷新，账单来源为 live；这些结果证明读取与传输持续运行，本轮实体观感仍待用户目视确认。

上一轮用户口头确认横屏“显示正常，方向和文字都正确”，没有照片，只覆盖当时版本。本轮新增布局不沿用该结论。实体输出继续经服务端图像转换为 720×1280 RGBA、全不透明且小于 1 MiB；浏览器横屏图不能直接作为原生帧发送。既有 `.impeccable/design.json` 过期，本次不修复。
