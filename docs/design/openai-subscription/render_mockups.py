"""Render static design proposals only; no account access or device operations."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BG = '#10171b'
PANEL = '#182227'
FG = '#edf3ed'
MUTED = '#9dadab'
GREEN = '#b6e7bb'
LINE = '#344247'
AMBER = '#edc586'
FONT = ROOT / 'web/fonts/Manrope.ttf'
ZH = Path('C:/Windows/Fonts/msyh.ttc')
ZHB = Path('C:/Windows/Fonts/msyhbd.ttc')


class Canvas:
    def __init__(self, w=1280, h=720):
        self.im = Image.new('RGBA', (w, h), BG)
        self.d = ImageDraw.Draw(self.im)
        self.w, self.h = w, h

    def text(self, x, y, value, size=28, color=FG, bold=False, right=False):
        source = ZHB if bold else ZH
        if all(ord(c) < 128 for c in value):
            source = FONT
        font = ImageFont.truetype(str(source), size)
        if source == FONT:
            font.set_variation_by_axes([600 if bold else 500])
        self.d.text((x, y), value, font=font, fill=color, anchor='rt' if right else 'lt')

    def line(self, y, x=44, end=None):
        self.d.line((x, y, end or self.w - 44, y), fill=LINE, width=1)

    def bar(self, x, y, w, fraction, color=GREEN):
        self.d.rounded_rectangle((x, y, x+w, y+14), radius=3, fill=LINE)
        self.d.rounded_rectangle((x, y, x+w*fraction, y+14), radius=3, fill=color)

    def header(self, title, portrait=False):
        self.text(44, 37, title, 32, bold=True)
        self.text(self.w-44, 43, '设计稿 · 演示数据', 23, AMBER, right=True)
        self.line(101)

    def footer(self, page, portrait=False, stale=False):
        y = self.h - 66
        self.line(y-19)
        self.text(44, y, '已过期 · 最后同步 14:20' if stale else '同步时间 14:32:08 · 示例', 23, AMBER if stale else MUTED)
        self.text(self.w-44, y, f'{page} / 3', 23, MUTED, right=True)

    def save(self, name):
        self.im.save(OUT / name)


def overview(portrait=False, stale=False):
    c = Canvas(720, 1280) if portrait else Canvas()
    c.header('OpenAI 订阅', portrait)
    if portrait:
        c.text(44, 134, 'ChatGPT Plus', 35)
        c.text(676, 142, '个人账户', 24, MUTED, right=True)
        c.text(44, 192, 'Codex 额度', 27, MUTED)
        c.line(245)
        quota(c, 44, 284, 632, '短周期剩余', '68', '2 小时 18 分后重置', '今日 16:50', 0.68)
        c.line(575)
        quota(c, 44, 620, 632, '周窗口剩余', '32', '3 天 06 小时后重置', '11 月 16 日 20:32', 0.32)
        c.line(925)
        c.text(44, 962, '下次续费', 26, MUTED)
        c.text(676, 962, '待接入', 28, right=True)
        c.text(44, 1025, '额外额度', 26, MUTED)
        c.text(676, 1025, '待接入', 28, right=True)
        c.text(44, 1111, '窗口与限制以账户返回信息为准', 23, MUTED)
    else:
        c.text(44, 132, 'ChatGPT Plus', 35)
        c.text(359, 143, '个人账户', 24, MUTED)
        c.text(1236, 143, '已过期 · 上次读取' if stale else 'Codex 额度', 27, AMBER if stale else GREEN, right=True)
        c.line(207)
        c.d.line((640, 240, 640, 533), fill=LINE, width=1)
        quota(c, 44, 245, 548, '短周期剩余', '68', '2 小时 18 分后重置', '今日 16:50', 0.68, stale)
        quota(c, 688, 245, 548, '周窗口剩余', '32', '3 天 06 小时后重置', '11 月 16 日 20:32', 0.32, stale)
        c.line(561)
        c.text(44, 589, '下次续费', 25, MUTED)
        c.text(195, 589, '待接入', 25)
        c.text(688, 589, '额外额度', 25, MUTED)
        c.text(839, 589, '待接入', 25)
    c.footer(1, portrait, stale)
    return c


def quota(c, x, y, w, label, value, reset, date, fraction, stale=False):
    c.text(x, y, label, 30)
    c.text(x+w, y+5, '上次读取剩余' if stale else '剩余 / 总额度', 22, AMBER if stale else MUTED, right=True)
    c.text(x-5, y+43, value, 120, MUTED if stale else GREEN)
    c.text(x+158, y+110, '%', 42, MUTED if stale else GREEN)
    c.bar(x, y+184, w, fraction, MUTED if stale else GREEN)
    c.text(x, y+224, '重置时间待重新确认' if stale else reset, 29, MUTED if stale else FG)
    c.text(x+w, y+266, date, 23, MUTED, right=True)


def billing():
    c = Canvas()
    c.header('套餐与账单')
    c.text(44, 137, 'ChatGPT Plus', 58)
    c.text(44, 228, '个人订阅', 28, MUTED)
    c.text(44, 288, '账户  m•••@example.com', 26, MUTED)
    c.d.rounded_rectangle((44, 371, 493, 538), radius=4, fill=PANEL)
    c.text(68, 394, '订阅状态', 24, MUTED)
    c.text(68, 444, '待接入账单来源', 32)
    c.d.line((554, 137, 554, 580), fill=LINE, width=1)
    for i, (label, value) in enumerate([
        ('当前账期', '待接入'), ('下次续费', '待接入'),
        ('续费金额 / 币种', '待接入'), ('自动续费', '待确认'),
        ('最近账单', '待接入'),
    ]):
        y = 144 + i*89
        c.text(603, y, label, 28, MUTED)
        c.text(1236, y, value, 29, right=True)
        c.line(y+62, 603)
    c.text(44, 588, '金额、税费与续费日期以实际账单为准', 24, MUTED)
    c.footer(2)
    return c


def entitlements():
    c = Canvas()
    c.header('权益与额度明细')
    c.text(44, 139, 'ChatGPT', 35)
    c.text(1236, 149, '仅展示账户实际提供的权益', 24, MUTED, right=True)
    c.line(206)
    c.text(44, 230, '功能', 24, MUTED)
    c.text(650, 230, '可用状态', 24, MUTED)
    c.text(1236, 230, '额度 / 重置时间', 24, MUTED, right=True)
    rows = [('模型访问', '待查询', '未提供'), ('深度研究', '待查询', '未提供'),
            ('图像生成', '待查询', '未提供'), ('语音', '待查询', '未提供')]
    for i, (label, status, remaining) in enumerate(rows):
        y = 288 + 74*i
        c.text(44, y, label, 29)
        c.text(650, y, status, 27, MUTED)
        c.text(1236, y, remaining, 27, MUTED, right=True)
        c.line(y+55)
    c.text(44, 595, '未提供额度的权益，不推算剩余次数', 24, MUTED)
    c.footer(3)
    return c


def disconnected():
    c = Canvas()
    c.header('OpenAI 订阅')
    c.text(44, 164, '等待连接账户', 60)
    c.text(44, 267, '连接后，这里将显示套餐与可获取的剩余额度。', 30, MUTED)
    c.line(350)
    c.text(44, 395, '套餐', 27, MUTED)
    c.text(44, 449, '—', 64)
    c.text(460, 395, '剩余额度', 27, MUTED)
    c.text(460, 449, '—', 64)
    c.text(900, 395, '重置时间', 27, MUTED)
    c.text(900, 449, '—', 64)
    c.text(44, 589, '请在电脑控制台连接账户', 28, GREEN)
    c.line(635)
    c.text(44, 654, '未连接 · 尚无账户数据', 23, MUTED)
    c.text(1236, 654, '1 / 3', 23, MUTED, right=True)
    return c


def main():
    for filename, canvas in [
        ('overview-landscape.png', overview()),
        ('overview-portrait.png', overview(True)),
        ('subscription-landscape.png', billing()),
        ('entitlements-landscape.png', entitlements()),
        ('disconnected-landscape.png', disconnected()),
        ('stale-landscape.png', overview(stale=True)),
    ]:
        canvas.save(filename)
    # A presentation sheet, separate from device-resolution designs.
    board = Image.new('RGB', (1968, 1460), '#f1f1ec')
    d = ImageDraw.Draw(board)
    def bt(x, y, s, size=24, color='#242c2b'):
        d.text((x, y), s, font=ImageFont.truetype(str(ZH), size), fill=color, anchor='lt')
    bt(48, 38, 'OpenAI 订阅 · 副屏 UI 提案', 38)
    bt(48, 99, '额度优先 / 详情分页 / 横竖重排', 24, '#5c685d')
    board.paste(Image.open(OUT/'overview-landscape.png').convert('RGB'), (48, 161))
    bt(48, 906, '横屏 1280 × 720 · 常驻总览', 25)
    portrait = Image.open(OUT/'overview-portrait.png').convert('RGB')
    portrait.thumbnail((540, 960), Image.Resampling.LANCZOS)
    board.paste(portrait, (1380, 161))
    bt(1380, 1148, '竖屏 720 × 1280', 25)
    for x, filename, label in [(48, 'subscription-landscape.png', '套餐与账单'),
                               (712, 'entitlements-landscape.png', '权益与额度明细')]:
        preview = Image.open(OUT/filename).convert('RGB').resize((616, 347), Image.Resampling.LANCZOS)
        board.paste(preview, (x, 960))
        bt(x, 1330, label, 25)
    bt(48, 1401, '全部为静态设计示例，尚未读取真实账户。所有操作留在电脑控制台。', 23, '#5c685d')
    board.save(OUT/'design-board.png')


if __name__ == '__main__':
    main()
