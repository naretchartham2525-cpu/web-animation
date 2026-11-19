import hashlib

from PIL import Image, ImageDraw

import textkit as T

W, H = 1080, 1920
BG = (43, 42, 40)
COLS = ((231, 111, 81), (42, 157, 143), (69, 123, 157), (233, 196, 106), (155, 93, 229), (244, 162, 97), (38, 70, 83), (188, 71, 73))


def _col(name):
    return COLS[int(hashlib.md5(str(name).encode()).hexdigest(), 16) % len(COLS)]


def _phone(top_col=(38, 50, 74), title="", sub=""):
    img = T.canvas(W, H, BG)
    d = T.Draw(img)
    T.rounded(d, (70, 80, 1010, 1840), 70, (12, 12, 14))
    T.rounded(d, (88, 98, 992, 1822), 56, (245, 245, 247))
    d.rounded_rectangle((88, 98, 992, 290), 56, fill=top_col)
    d.rectangle((88, 200, 992, 290), fill=top_col)
    d.text((140, 150), "9:41", font=T.font(30, "SemiBold"), fill=(255, 255, 255))
    if title:
        d.text((140, 232), "‹  " + title, font=T.font(42, "Bold"), fill=(255, 255, 255), anchor="lm")
    if sub:
        d.text((950, 232), sub, font=T.font(30, "SemiBold"), fill=(220, 230, 240), anchor="rm")
    return img, d


def chat(data, shown=99, names=None):
    names = names or {}
    img, d = _phone((38, 50, 74), data.get("name", "แชต"))
    d.rectangle((88, 290, 992, 1822), fill=(142, 166, 198))
    d.rounded_rectangle((88, 1700, 992, 1822), 56, fill=(244, 244, 244))
    d.rectangle((88, 1700, 992, 1760), fill=(244, 244, 244))
    T.rounded(d, (120, 1722, 960, 1792), 35, (255, 255, 255), (220, 220, 220), 2)
    y = 330
    f = T.font(46, "Regular")
    fn = T.font(30, "SemiBold")
    for m in (data.get("msgs") or [])[:shown]:
        me = bool(m.get("me"))
        who = names.get(m.get("from"), m.get("from") or "")
        tw = min(640, max(T.width(ln, f) for ln in T.wrap(m.get("text", ""), f, 640)) + 4)
        th = T.measure(m.get("text", ""), f, 640)
        if me:
            x1 = 950
            T.rounded(d, (x1 - tw - 56, y, x1, y + th + 40), 34, (141, 224, 126))
            T.block(d, x1 - tw - 28, y + 18, m.get("text", ""), f, (20, 20, 20), 640)
            y += th + 70
        else:
            T.avatar(d, 160, y + 36, 38, who, _col(who))
            d.text((216, y - 6), who, font=fn, fill=(40, 48, 66))
            T.rounded(d, (216, y + 34, 216 + tw + 56, y + 34 + th + 40), 34, (255, 255, 255))
            T.block(d, 244, y + 52, m.get("text", ""), f, (20, 20, 20), 640)
            y += th + 110
    return img


def review(data, shown=99):
    img, d = _phone((214, 72, 56), data.get("shop", "รีวิว"))
    stars = float(data.get("stars") or 0)
    y = 340
    d.text((140, y), data.get("shop", ""), font=T.font(52, "Bold"), fill=(25, 25, 25))
    y += 90
    _stars(d, 140, y, stars, 52)
    d.text((140 + 6 * 60, y + 26), f"{stars:.1f}", font=T.font(46, "Bold"), fill=(25, 25, 25), anchor="lm")
    y += 110
    for r in (data.get("reviews") or [])[:shown]:
        T.rounded(d, (120, y, 960, y + 40 + T.measure(r.get("text", ""), T.font(42, "Regular"), 760) + 130), 30, (255, 255, 255), (225, 225, 228), 2)
        T.avatar(d, 186, y + 66, 36, r.get("name", ""), _col(r.get("name", "")))
        d.text((240, y + 40), r.get("name", ""), font=T.font(34, "SemiBold"), fill=(30, 30, 30))
        _stars(d, 240, y + 86, float(r.get("stars") or 0), 30)
        yy = T.block(d, 160, y + 140, r.get("text", ""), T.font(42, "Regular"), (40, 40, 40), 760)
        y = yy + 50
    return img


def _stars(d, x, y, v, s):
    for k in range(5):
        f = max(0.0, min(1.0, v - k))
        cx = x + k * (s + 8) + s // 2
        pts = _star(cx, y + s // 2, s // 2)
        d.polygon(pts, fill=(213, 213, 213))
        if f > 0:
            m = Image.new("L", (s + 4, s + 4), 0)
            ImageDraw.Draw(m).polygon([(px - cx + s // 2 + 2, py - y + 2) for px, py in pts], fill=255)
            m = m.crop((0, 0, int((s + 4) * f), s + 4))
            d.bitmap((cx - s // 2 - 2, y - 2), m, fill=(245, 180, 0))


def _star(cx, cy, r):
    import math
    out = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        out.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return out


def post(data, shown=99):
    img, d = _phone((24, 119, 242), data.get("group", "กลุ่ม"))
    d.rectangle((88, 290, 992, 1822), fill=(240, 242, 245))
    y = 330
    T.rounded(d, (110, y, 970, y + 200 + T.measure(data.get("text", ""), T.font(44, "Regular"), 780)), 26, (255, 255, 255))
    T.avatar(d, 176, y + 70, 42, data.get("author", ""), _col(data.get("author", "")))
    d.text((236, y + 36), data.get("author", ""), font=T.font(38, "Bold"), fill=(20, 20, 20))
    d.text((236, y + 86), "เมื่อสักครู่", font=T.font(28, "Regular"), fill=(110, 110, 110))
    yy = T.block(d, 140, y + 150, data.get("text", ""), T.font(44, "Regular"), (20, 20, 20), 780)
    d.text((140, yy + 10), f"ถูกใจ {data.get('likes', '')} คน", font=T.font(32, "SemiBold"), fill=(100, 100, 100))
    y = yy + 90
    for c in (data.get("comments") or [])[:shown]:
        T.avatar(d, 160, y + 40, 34, c.get("name", ""), _col(c.get("name", "")))
        h = T.measure(c.get("text", ""), T.font(38, "Regular"), 680)
        T.rounded(d, (210, y, 210 + 740, y + h + 80), 30, (255, 255, 255))
        d.text((236, y + 14), c.get("name", ""), font=T.font(30, "Bold"), fill=(20, 20, 20))
        T.block(d, 236, y + 56, c.get("text", ""), T.font(38, "Regular"), (30, 30, 30), 680)
        y += h + 110
    return img


def forum(data, shown=99, hero="ผม"):
    img, d = _phone((255, 69, 0), data.get("board", "กระทู้"))
    d.rectangle((88, 290, 992, 1822), fill=(246, 247, 248))
    y = 330
    who = hero if data.get("me") else data.get("author", "")
    d.text((130, y), f"u/{who} · ตั้งกระทู้", font=T.font(30, "SemiBold"), fill=(120, 120, 120))
    y = T.block(d, 130, y + 50, data.get("title", ""), T.font(50, "Bold"), (20, 20, 20), 800) + 10
    y = T.block(d, 130, y, data.get("text", ""), T.font(40, "Regular"), (40, 40, 40), 800) + 20
    d.text((130, y), f"โหวต {data.get('votes', '')} · {len(data.get('answers') or [])} คำตอบ", font=T.font(32, "SemiBold"), fill=(110, 110, 110))
    y += 70
    for a in (data.get("answers") or [])[:shown]:
        d.line((130, y, 130, y + 40 + T.measure(a.get("text", ""), T.font(38, "Regular"), 760) + 50), fill=(210, 210, 214), width=5)
        d.text((160, y), f"u/{a.get('name', '')}", font=T.font(30, "Bold"), fill=(30, 30, 30))
        yy = T.block(d, 160, y + 44, a.get("text", ""), T.font(38, "Regular"), (30, 30, 30), 760)
        d.text((160, yy + 4), f"+{a.get('votes', '')} โหวต", font=T.font(28, "SemiBold"), fill=(255, 69, 0))
        y = yy + 70
    return img


DOC_HEAD = {"court": ((28, 47, 85), "ศาล"), "police": ((47, 95, 143), "สถานีตำรวจ"), "slip": ((31, 111, 92), "ธนาคาร"), "medical": ((15, 125, 117), "โรงพยาบาล"),
            "notice": ((194, 29, 29), "แจ้งเตือน"), "bill": ((90, 90, 90), "ใบเสร็จรับเงิน"), "statement": ((59, 42, 143), "ธนาคาร")}


def doc(data):
    img = T.canvas(W, H, BG)
    d = T.Draw(img)
    kind = data.get("kind", "letter")
    head, org0 = DOC_HEAD.get(kind, ((107, 78, 22), ""))
    paper = (255, 254, 248) if kind != "note" else (255, 250, 214)
    lines = data.get("lines") or []
    f = T.font(40, "Regular")
    body_h = sum(T.measure(x, f, 760) + 16 for x in lines) + (110 if data.get("amount") else 0) + (150 if data.get("stamp") else 0)
    top = max(160, (H - (body_h + 480)) // 2)
    T.rounded(d, (100, top, 980, top + body_h + 480), 24, paper)
    d.rounded_rectangle((100, top, 980, top + 150), 24, fill=head)
    d.rectangle((100, top + 100, 980, top + 150), fill=head)
    d.text((150, top + 75), data.get("org") or org0, font=T.font(40, "Bold"), fill=(255, 255, 255), anchor="lm")
    y = T.block(d, 540, top + 200, data.get("title", ""), T.font(60, "Bold"), (20, 20, 20), 760, anchor="c") + 20
    d.line((160, y, 920, y), fill=(200, 196, 186), width=3)
    y += 30
    for x in lines:
        y = T.block(d, 160, y, x, f, (35, 35, 35), 760) + 16
    if data.get("amount"):
        T.rounded(d, (160, y + 10, 920, y + 100), 16, (240, 240, 232))
        d.text((540, y + 55), str(data["amount"]), font=T.font(52, "Bold"), fill=(20, 20, 20), anchor="mm")
        y += 120
    if data.get("stamp"):
        st = Image.new("RGBA", (520, 150), (0, 0, 0, 0))
        sd = T.Draw(st)
        sd.rounded_rectangle((6, 6, 514, 144), 20, outline=(200, 30, 30, 230), width=10)
        sd.text((260, 75), data["stamp"], font=T.font(64, "Bold"), fill=(200, 30, 30, 230), anchor="mm")
        st = st.rotate(-12, expand=True, resample=Image.BICUBIC)
        img.paste(st, (440, y + 10), st)
    return img


def system(data):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = T.Draw(img)
    lines = data.get("lines") or []
    f = T.font(44, "SemiBold")
    h = 260 + sum(T.measure(x, f, 760) for x in lines) + (90 if data.get("reward") else 0)
    top = 420
    d.rounded_rectangle((110, top, 970, top + h), 28, fill=(6, 18, 38, 225), outline=(90, 200, 255, 255), width=5)
    d.text((540, top + 40), "[ SYSTEM ]", font=T.font(30, "Bold"), fill=(120, 210, 255, 255), anchor="ma")
    y = T.block(d, 540, top + 90, data.get("title", ""), T.font(56, "Bold"), (255, 255, 255, 255), 760, anchor="c") + 16
    for x in lines:
        y = T.block(d, 540, y, "• " + x, f, (200, 235, 255, 255), 760, anchor="c")
    if data.get("reward"):
        T.rounded(d, (200, y + 14, 880, y + 84), 20, (255, 196, 64, 230))
        d.text((540, y + 49), "รางวัล: " + data["reward"], font=T.font(38, "Bold"), fill=(40, 30, 0, 255), anchor="mm")
    return img


def live_frame(data, names=None):
    names = names or {}
    img = T.canvas(W, H, (18, 18, 22))
    d = T.Draw(img)
    T.rounded(d, (70, 80, 1010, 1840), 70, (12, 12, 14))
    return img


def live_overlay(data, names=None, shown=99):
    names = names or {}
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = T.Draw(ov)
    host = names.get(data.get("host"), data.get("host", ""))
    T.rounded(d, (120, 140, 120 + 70 + T.width(host, T.font(36, "Bold")) + 40, 220), 40, (0, 0, 0, 140))
    T.avatar(d, 160, 180, 30, host, _col(host))
    d.text((200, 180), host, font=T.font(36, "Bold"), fill=(255, 255, 255, 255), anchor="lm")
    T.rounded(d, (770, 150, 860, 210), 12, (238, 29, 82, 255))
    d.text((815, 180), "LIVE", font=T.font(30, "Bold"), fill=(255, 255, 255, 255), anchor="mm")
    T.rounded(d, (870, 150, 975, 210), 12, (0, 0, 0, 140))
    d.text((922, 180), f"{data.get('viewers', '')} คน", font=T.font(26, "SemiBold"), fill=(255, 255, 255, 255), anchor="mm")
    if data.get("name"):
        T.rounded(d, (120, 240, 960, 310), 20, (0, 0, 0, 110))
        d.text((540, 275), data["name"], font=T.font(34, "SemiBold"), fill=(255, 255, 255, 255), anchor="mm")
    y = 1420
    for c in (data.get("comments") or [])[:shown]:
        txt = f"{c.get('name', '')}  {c.get('text', '')}"
        w = min(820, T.width(txt, T.font(36, "SemiBold")) + 50)
        T.rounded(d, (120, y, 120 + w, y + 68), 34, (0, 0, 0, 130))
        d.text((146, y + 34), c.get("name", ""), font=T.font(32, "Bold"), fill=(255, 220, 120, 255), anchor="lm")
        d.text((146 + T.width(c.get("name", "") + "  ", T.font(32, "Bold")), y + 34), c.get("text", ""), font=T.font(34, "SemiBold"), fill=(255, 255, 255, 255), anchor="lm")
        y += 84
    return ov


def card(text, sub=""):
    img = T.canvas(W, H, (12, 12, 14))
    d = T.Draw(img)
    y = T.block(d, 540, 820, text, T.font(84, "Bold"), (255, 255, 255), 900, anchor="c", lh=1.25)
    if sub:
        T.block(d, 540, y + 40, sub, T.font(46, "SemiBold"), (200, 255, 46), 900, anchor="c")
    return img
