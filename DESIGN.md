---
name: TURZX Studio
description: USB 副屏的八场景展示与本地控制台
colors:
  workbench-bg: "#f1f1ec"
  workbench-panel: "#f8f8f3"
  workbench-text: "#242c2b"
  workbench-muted: "#5c685d"
  control-primary: "#2c5643"
  control-primary-hover: "#1e4232"
  control-on-primary: "#f3f7eb"
  control-secondary: "#edf0e7"
  control-secondary-text: "#3b5845"
  control-secondary-hover: "#e0e7d9"
  control-ghost: "#41634e"
  control-ghost-hover: "#163e2d"
  selection: "#dde6dc"
  selection-text: "#183d2b"
  field-bg: "#fdfdf9"
  field-text: "#3a503b"
  screen-bg: "#10171b"
  screen-text: "#edf3ed"
  screen-muted: "#9dadab"
  screen-accent: "#b6e7bb"
  network-bg: "#0e1b25"
  network-accent: "#9ed9f2"
  clock-bg: "#141c22"
  focus-bg: "#18231e"
  focus-accent: "#d9e8bc"
  ambient-bg: "#0b1421"
  media-bg: "#211c1a"
  media-accent: "#e4c5a7"
  guide-bg: "#161b25"
  openai-bg: "#ffffff"
  openai-panel: "#fafafd"
  openai-text: "#202020"
  openai-muted: "#606060"
  openai-border: "#e2e2e5"
  openai-accent: "#0069cc"
  openai-numeric: "#0550ae"
  openai-warning: "#895503"
typography:
  openai-body:
    fontFamily: "Segoe UI, Microsoft YaHei, sans-serif"
  openai-numeric:
    fontFamily: "Cascadia Code, Consolas, monospace"
    fontWeight: 400
  body:
    fontFamily: "Manrope, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "14px"
  headline:
    fontSize: "28px"
    fontWeight: 650
    letterSpacing: "-0.8px"
  label:
    fontSize: "12px"
    fontWeight: 600
  screen-body:
    fontSize: "28px"
    fontWeight: 450
  screen-title:
    fontSize: "31px"
    fontWeight: 550
    letterSpacing: "-0.5px"
  cpu-display:
    fontSize: "162px"
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: "-6px"
  clock-display:
    fontSize: "210px"
    fontWeight: 450
    lineHeight: 1.1
    letterSpacing: "-10px"
rounded:
  control: "4px"
  navigation: "5px"
  preview-stage: "8px"
  preview-shell: "9px"
spacing:
  control-gap: "8px"
  button: "10px 12px"
  navigation: "13px 12px"
  stage: "33px 34px 24px"
  screen-landscape: "39px 45px 30px"
  screen-portrait: "45px 40px 34px"
components:
  button-primary:
    backgroundColor: "{colors.control-primary}"
    textColor: "{colors.control-on-primary}"
    rounded: "{rounded.control}"
    padding: "{spacing.button}"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.control-primary-hover}"
  button-secondary:
    backgroundColor: "{colors.control-secondary}"
    textColor: "{colors.control-secondary-text}"
    rounded: "{rounded.control}"
    padding: "{spacing.button}"
  button-secondary-hover:
    backgroundColor: "{colors.control-secondary-hover}"
  button-ghost:
    textColor: "{colors.control-ghost}"
    padding: "7px 0"
    typography: "{typography.label}"
  navigation-selected:
    backgroundColor: "{colors.selection}"
    textColor: "{colors.selection-text}"
    rounded: "{rounded.navigation}"
    padding: "{spacing.navigation}"
  textarea:
    backgroundColor: "{colors.field-bg}"
    textColor: "{colors.field-text}"
    rounded: "{rounded.control}"
    padding: "10px"
---

# Design System: TURZX Studio

## Overview

**Creative North Star: "录音棚监听台"**

电脑上的浅色工作台承担选择与控制，副屏上的深色画面承担阅读与观看。页面导航借用通道列的秩序，中央预览始终代表同一块输出屏；右侧集中输出、方向、帧率与计时设置。

本记录从已完成的 HTML/CSS/canvas 提取，并依据 PRODUCT.md 与 work/design-brief.md。用户委托五个代理决定此次探索方案；code-first 仅是本次设备实验的实现选择，不是永久偏好。

**Key Characteristics:**

- 控制与展示分离，副屏不出现无法操作的按钮。
- 八个页面各有构图，保持清晰的状态和原生字号。
- 真实采样、旧数据、未接入和生成视觉各自标明。

## Colors

色值以文件开头的 token 为准；这里描述用途。

### Primary

控制台主按钮使用深林绿，浅绿选中背景用于当前页面；主按钮颜色不扩散到全部区域。性能页以浅薄荷绿标示采样和曲线。

### Secondary

网络使用冰蓝；专注使用暖绿；媒体空态使用棕褐与暖米色。不同场景色彩是这次多用途探索的组成部分，不代表所有新增页面都需要新增主题。

### Neutral

工作台用纸灰、近白面板和深墨文字。副屏使用偏蓝黑或场景深色背景，浅色文字与分隔线承担信息层级。校准页的纯 RGB、灰阶与白边是检查内容，不是品牌色板。

## Typography

字体栈为 Manrope、Noto Sans SC、Microsoft YaHei、sans-serif。Manrope 可变字体随项目自托管，许可证见 web/fonts/OFL-Manrope.txt；中文字体使用本机已有字体回退。数字采用等宽数字排布，未另引入等宽字体。

工作台正文为 body，页面标题为 headline；功能性小字最低为 11 px。副屏标题、正文和主数字分别使用 screen-title、screen-body 与对应 display 角色。CPU 横屏主数字为 cpu-display，竖屏改为 190 px；时钟横屏主数字为 clock-display，竖屏改为 165 px。专注计时横屏 210 px、竖屏 173 px。数据辅助说明通常 22–28 px；校准页额外包含 24/28/32/40 px 字样供实际观看比较。

大字号仅用于原生副屏画布，不照搬到控制台。长硬件名可省略，媒体文案和便签可断行；不要用缩小全部内容代替竖屏重排。

## Layout

工作台最大宽度 1900 px。默认三列为 218 px / 弹性预览 / 278 px；顶部栏高 78 px。1550 px 以上扩大侧列和间距；1180 px 以下收紧；930 px 以下设置区移至下方；620 px 以下变成纵向布局、横向场景导航和两列设置。手机仍保留紧凑的设备说明入口及来源链接。

实体展示横屏画布为 1280×720，原生竖屏为 720×1280；显示重排依据最大宽高比 1:1。外侧留白使用 screen-landscape / screen-portrait。控制台 iframe 只缩放预览，实体页在实际画布内重新布局。

| 页面 | 横屏 | 竖屏 |
|---|---|---|
| system | CPU 主区在左，内存/GPU/磁盘在右 | CPU 与历史曲线在上，其他指标在下 |
| network | 下载与上传并列，下方共享图表 | 下载、上传纵排，图表与图例各占独立空间 |
| clock | 大字时间、下方并排世界时钟 | 本地时间在上，世界时钟逐行排列 |
| focus | 居中倒计时、单条进度与便签 | 居中保留，便签容纳更多行 |
| ambient | 全幅原创轨道，角落标题与时间 | 按画布重新计算几何与留白 |
| media | 唱片图形在左，未接入说明在右 | 图形在上，说明在下 |
| guide | 三列区分可体验、待接入、待验证 | 三个区域纵排，每组列表双列 |
| calibrate | 色条、灰阶、文字与正圆 | 色条增高，样字和正圆上下排布 |

## Elevation & Depth

界面主要靠底色、分隔线和空白分层。预览外壳使用唯一结构性投影：0 16px 25px -19px #28342f99。媒体唱片的内凹描边属于图形内容。没有通用悬浮卡片体系。

## Shapes

按钮和输入框采用 control 圆角，页面导航采用 navigation 圆角。预览背景和外壳分别使用 preview-stage、preview-shell；内部画面保持矩形画布。小圆点标记状态，圆形只用于唱片和校准几何。图标来自项目内的同线宽 SVG 路径。

## Components

- **按钮**：主按钮深绿；次按钮浅绿并带边框；文字按钮无底色。悬停改变底色或文字颜色，键盘焦点为 3 px 实线轮廓，外偏移 3 px；禁用状态降低不透明度。
- **场景导航**：图标、中文名称与英文短名组成一行；选中项用浅绿底和深绿字。手机隐藏英文短名，保留所有八个场景的横向滚动。
- **输入**：便签 textarea 使用近白底、细边框和可见焦点；显示 160 字符上限。方向、帧率、停留时间采用原生 select；亮度为原生 range，未连接时禁用。
- **预览**：固定原生宽高的 iframe 按容器等比例缩放；横竖屏切换改变真实 viewport 尺寸。设备详情的“原生画布”读取 native_width/native_height，不使用横屏展示尺寸。
- **指标与图表**：值与单位分层；百分比和容量可用时才显示。历史曲线只使用真实采样；网络图例与页脚分别占位。容量使用 GiB，二进制吞吐使用 KiB/s、MiB/s。
- **状态**：工作台显示实际发送 fps、累计 MiB 与最新错误；副屏显示实时、过期或未接入。音乐一隅当前是明确空态；缓慢轨道是原创 canvas 生成视觉。
- **运动**：按钮颜色过渡 0.16 秒，开关位移 0.15 秒。氛围动画在普通预览中约每 200 ms 更新；离屏 renderer 按调用绘制。无闪烁或频闪，系统减少动态偏好会停用普通预览的连续动画循环。

## Do's and Don'ts

### Do:

- Do 让控制留在电脑端，副屏保留内容与状态。
- Do 按原生横竖画布重新排版，并保留清晰的缺失数据状态。
- Do 使用真实测量单位和实际发送速度。
- Do 从 web/studio.css、web/display.css 和对应 JS 核对记录；预览截图是项目渲染捕获，不是第三方素材。

### Don't:

- Don't 以随机数替代未接入数据，或把空态称为正在播放。
- Don't 将请求发送帧率当成面板刷新率。
- Don't 隐藏窄屏的设备说明与来源入口。
- Don't 把这次 code-first 选择写成用户的永久设计偏好。

## 动画实验室增量

沿用原有控制台和画布尺寸。四种Canvas作品以轨道、极光光带、流场曲线和透视星点区分，均为慢速连续运动，不使用闪烁或突然大幅缩放。播放参数由共享时间基准维护，浏览器预览约30 fps，实体帧率以控制台实测为准。切出动画页、隐藏标签和减少动态效果场景会停止连续绘制。控制区域复用现有下拉、滑块、开关与按钮，无新增图形库或远程素材。

## OpenAI 订阅场景增量

此节是 `openai` 场景的独立视觉规则。原有监听台、八个场景及动画实验室继续使用上文体系。用户在确认原订阅 UI 并要求接入真实数据后，将本场景方向明确改为 IT 风格、参考 VS Code 默认浅色；原深色订阅 PNG 仅为历史提案。

### 视觉来源与颜色

依据本机 VS Code 内置 `2026 Light` 主题提取：`C:/Softwares/Microsoft VS Code/04c0d99f4f/resources/app/extensions/theme-defaults/themes/2026-light.json`，其 include 为 `light_modern.json`。[VS Code 1.113 发布说明](https://code.visualstudio.com/updates/v1_113)记录了默认浅色与深色主题更新。实现以 `web/subscription.css` 和 `web/subscription-workbench.css` 为准。

`openai-*` token 只用于订阅展示页与选中 OpenAI 场景时的控制台。白色主画布、近白工具栏、细灰分隔线、深灰正文构成阅读秩序；蓝色用于活动状态、焦点、进度与关键数字；棕色用于来源异常和过期提醒。过期额度数字与进度转为辅助灰，并保留文字说明。不得把新增色板扩散至其他场景。

### 字体、布局与组件

正文采用 `openai-body`；额度数字、时间数值及额度附加值采用 `openai-numeric`，中文仍使用系统字体回退。订阅页标题 31–32 px，套餐 35 px，主要说明约 22–30 px。当前综合总览主数字横屏 88 px、竖屏 82 px；同一共享额度分组返回两个窗口时使用紧凑数字横屏 42 px、竖屏 38 px。只为原生画布使用大字号，不放大控制台文字。

展示保持 1280×720 横屏与 720×1280 竖屏，左右留白 44 px。综合总览横屏以三列并列 ChatGPT 功能额度前两项和 Work / Codex 共享额度；竖屏重排为三行，每行将数值与重置时间分置左右。底部承载续费时间、自动续费、credits 和重置机会。共享额度返回一个或两个窗口时只调整该区，不占用 ChatGPT 功能区。套餐与续费页横屏左右分区、竖屏上下重排；功能明细每页最多四项，每 15 秒分页，竖屏将重置时间另起一行。头尾工具栏固定分隔。进度轨道保持直角，控制台按钮与输入框为 3 px 小圆角，预览去除投影，以边框和底色分层。

控制台提供三页选择、15 秒详情轮播、实际返回的共享额度分组选择、手动刷新及官方入口。副屏只显示数据与状态。三页轮播、明细内部自动分页和场景轮播分别处理；固定订阅内容时关闭场景轮播，手动切换详情页会关闭三页轮播，明细超过四项时仍自动分页。焦点为可见蓝色轮廓，不依赖颜色单独传达数据状态。

### 数据与验证约束

设计表现遵循实际返回的功能次数、共享额度桶与窗口。ChatGPT 深度研究、图像生成等独立次数不与 Work / Codex 共享百分比相加；不画虚构的短周期额度，空模型列表不代表无限。credits、重置机会、次数与百分比保留各自单位。账期、续费时间、自动续费和平台使用 ChatGPT 账户接口的真实字段；权益到期不能代替续费时间，套餐标价不能代替实扣金额。尚未返回的普通聊天消息、语音独立计数和续费实扣金额明确标注，不推算。倒计时归零显示等待更新，不能自行补满。

ChatGPT 功能额度、共享额度与账单分别维护成功时间和过期状态；部分来源失败时保留其他来源的有效结果，并标记“部分来源未同步”。过期数值、灰色进度与来源提示共同表达旧采样，不以全局同步标签掩盖局部失败。操作、凭据读取与接口边界见 [订阅使用说明](docs/openai-subscription.md)。

新增 ChatGPT 功能额度与续费已完成三页横竖屏和桌面/窄屏控制台共八图复审，结论为 ship；证据位于 `runtime/chatgpt-qa/*.jpg`，最终生产捕获为 `live-overview.jpg`。最终版保留用户当前竖屏方向并持续投送，本轮尚未用户目视确认。`runtime/openai/light-*.png` 以及用户对横屏“显示正常，方向和文字都正确”的口头确认只对应上一轮以 Codex 为主的版本，不作为本轮实体屏验收。详细验证结果见订阅使用说明。既存 `.impeccable/design.json` 已发现过期，本次不修复或覆盖该 sidecar。
