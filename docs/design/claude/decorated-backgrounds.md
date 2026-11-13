# 装饰背景

管理页「显示 → 背景图片」提供 9 张图和纯色背景。原来的站姿、凝思、相伴保留同一人物及构图，新增边缘花藤、蕾丝和星月装饰。新增三个人物场景为花庭信笺、星月花环、午后书房；三个非人物风格为植物水彩、剪纸山水、琉璃流光。

所有背景共用已有亮度、饱和度、淡化设置。选择背景不会覆盖这些参数，也不会改动屏幕色序、位置或背光。背景选择沿用 `claude_background` 保存，重启后恢复。新背景在横屏中保留整圈装饰，竖屏在卡片下方显示完整横幅；1–5 个账号继续使用现有数据布局。

## 资源与导出

生成原图保存在本目录的 `claude-v4-*-landscape-original.png`，原三款的装饰图保存在 `claude-v3-decorated-*-landscape-original.png`。此前无装饰原图和资源仍保留。

```sh
.venv/bin/python docs/design/claude/prepare_assets.py --collection-dir /path/to/装饰背景-六款
.venv/bin/python docs/design/claude/prepare_assets.py --originals-dir /path/to/原三款人物-装饰版
.venv/bin/python docs/design/claude/prepare_assets.py --version v4-floral
```

导出为 1280×720 RGBA 图片和 320×180 WebP 缩略图。副屏派生图按最小可用步长取整 RGB 色值，使单独的原生 PNG 不超过 850,000 字节，为文字和卡片留出空间。当前最大步长为 6，单通道误差最多 3/255。此处理不模糊线条、不调整色调曲线、不使用索引 PNG；原图不变。派生图并非与原图逐像素一致。

浏览器缩放和用户色彩调整仍会增加最终 PNG 体积。发送端先尝试 PNG 压缩级别 1 和 9；仍超 1 MiB 时，依次尝试 RGB 步长 2、3、4，单通道误差最多 2/255。若仍超限则拒绝发送。全部输出保持 720×1280、不透明 RGBA，统计与本地帧日志记录 `quantization_step`；1 表示未取整。

## 验证

```sh
node tests/test_claude_ui.cjs
node tests/test_designer_console.cjs
node tests/test_decorated_backgrounds.cjs
.venv/bin/python tests/verify_decorated_encoding.py
.venv/bin/python -m unittest discover -s tests -p test_panel_encoding.py
```

页面测试通过本地服务读取静态资源，使用示例账号数据，不更改真实账号或副屏。布局与编码覆盖 9 张图、0–5 个账号、横竖方向、原色以及深浅参数边界，共 324 张页面帧。管理页检查桌面和 390 像素窄屏选择及保存请求。编码回归检查尺寸、PNG color type 6、alpha=255、载荷上限，以及预算内原像素保持、超限取整误差与无法满足预算时的拒绝。

本次验收：324 张原生帧全部小于 1 MiB，最大 1,044,599 字节。最终发送端仅 10 张需要色值取整，其中 9 张使用步长 2，1 张使用步长 3。原图与副屏派生图对照输出为 `装饰背景-原图与副屏资源对照.png`。
