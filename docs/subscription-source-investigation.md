# 聊天、语音与实扣金额：数据源补查

核查日期：2026-11-13。已接入语音状态、模型限制状态与官方套餐目录标价；普通聊天条数与语音分钟数仍未返回。

## 普通聊天

- 已登录 ChatGPT 的模型选择器未显示剩余消息次数。
- `POST /backend-api/conversation/init` 的 `model_limits` 返回空列表；当前 `limits_progress` 仍只有深度研究与图像生成。
- `GET /backend-api/models` 成功返回模型目录与能力描述。模型的 `max_tokens` 是上下文能力，不能解释为剩余额度。
- 官方账户用量页明确说明“聊天”模式的对话不计入 Work / Codex 等功能的共享额度。
- 进一步检查已安装官方客户端的打包源码：`model_limits` 通常包含模型、`resets_after` 和降级模型，而不是剩余消息数。已补充这种限制状态的解析。
- 使用模型目录实际返回的 Instant、Pro 模型分别初始化，仍返回空 `model_limits`；请求不含消息，不执行推理。

因此当前不能从共享百分比或模型能力反推聊天剩余次数，也不能由空列表认定无限。现有读取器继续保留明确返回模型计数时的接收能力。

## 语音

- 已登录网页的语音设置展示声音、语言、听写与最近录音，没有独立剩余时间。
- 当前聊天初始化响应未返回语音条目。
- 从官方客户端的 `getRealtimeVoiceStatus` 调用定位到 `POST https://chatgpt.com/realtime/status`，另验证 `POST /backend-api/conversation/voice/status`；二者均可读取状态。生产读取器使用前者，body 为 `{}`。
- 实测返回高级语音模式，`disabled_mode_metadata=null`、`resets_after=null`，表示本次状态查询未禁用该模式，但没有剩余分钟数。界面显示“可用 · 分钟数未提供”。
- 原始语音响应含临时 `chatreq_token` 等字段，规范化时全部丢弃，不缓存、不记录、不发送给屏幕。
- [官方定价文档](https://learn.chatgpt.com/docs/pricing)说明桌面 ChatGPT Voice 使用共享的 Codex 用量预算；这不提供独立的剩余分钟数，不能直接套用到其他语音入口。
- [官方语音说明](https://learn.chatgpt.com/docs/features/voice)用于核对桌面语音的适用范围。

本轮未启动语音会话、录音或推理任务来消耗额度试探上限。

## 续费与实际支付

- 移动端购买的订阅由相应购买渠道管理，实际支付须以当前订单或收据为依据。
- 较早套餐的已支付记录、已作废账单均不能证明当前套餐的实际扣款。
- 本功能使用官方套餐目录标价，不导入个人付款资料、订单记录或支付链接。
- 套餐标价、下次预计扣款、已支付订单金额与用户银行卡本币扣款是不同口径。未发生的下一次扣款没有“实扣”结果；历史支付不能直接填入 `renewal_amount`。

从客户端价格读取代码定位并验证 `GET /backend-api/checkout_pricing_config/configs/US`。读取器按订阅 `plan_code` 匹配该目录的月费，页面标为“套餐标价”及美元目录参考价，不当作实扣金额。生产匹配限定 USD 月付套餐；不使用年付项的月均数计算年扣款。

## 实施状态

生产修改位于 `chatgpt_account.py`、`subscription.py`、`web/subscription.js` 与控制台状态提示。新增来源单独缓存与过期，账户变化时一并清理；语音每 60 秒、目录标价每 30 分钟刷新。已通过 41 项 Python 回归检查和前端语义检查，并核对横竖屏与窄屏控制台。

探测脚本及源码片段仅保存在 Git 忽略的 `runtime/`；凭据只在内存中使用，原始账单、支付链接和个人付款信息不写入本文件。
