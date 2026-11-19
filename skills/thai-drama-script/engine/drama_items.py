import math
from pathlib import Path

INK = (17, 17, 19, 255)
WHITE = (250, 250, 250, 255)
FONT = Path(__file__).resolve().parent / "web" / "story" / "fonts" / "Kanit-Bold.ttf"
_FONTS = {}


def C(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def rr(cx, cy, w, h, r=6, n=6):
    l, t, rg, b = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    r = min(r, w / 2, h / 2)
    pts = []
    for x0, y0, a0 in ((rg - r, t + r, -90), (rg - r, b - r, 0), (l + r, b - r, 90), (l + r, t + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((x0 + r * math.cos(a), y0 + r * math.sin(a)))
    return pts


def el(cx, cy, rx, ry, a0=0, a1=360, n=28):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def rot(pts, c, deg):
    r = math.radians(deg)
    return [(c[0] + (x - c[0]) * math.cos(r) - (y - c[1]) * math.sin(r), c[1] + (x - c[0]) * math.sin(r) + (y - c[1]) * math.cos(r)) for x, y in pts]


def text(pen, s, c, size, col=INK):
    from PIL import ImageFont
    k = int(size * pen.k)
    if k < 4 or not FONT.is_file():
        return
    if k not in _FONTS:
        _FONTS[k] = ImageFont.truetype(str(FONT), k)
    x, y = pen.P(c)
    pen.d.text((x, y), s, font=_FONTS[k], fill=col, anchor="mm")


def P(pen, pts, fill, w=4):
    pen.poly(pts, fill, INK if w else None, w)


def L(pen, pts, w, col=INK):
    pen.line(pts, w, col)


def D(pen, c, r, col):
    pen.dot(c, r, col)


def coin(pen, h, col="#e2b234", n=1, big=0):
    for k in range(n):
        c = (h[0] + k * 6, h[1] - 24 - k * 12)
        P(pen, el(c[0], c[1], 24 + big, 24 + big), C(col))
        P(pen, el(c[0], c[1], 16 + big * 0.7, 16 + big * 0.7), C(col), 3)
    text(pen, "฿", (h[0] + (n - 1) * 6, h[1] - 24 - (n - 1) * 12), 22 + big)


def note(pen, h, col="#7a9a5a", label="100", n=1):
    for k in range(n):
        q = rot(rr(h[0], h[1] - 34, 130, 66, 4), (h[0], h[1] - 34), -8 + k * 9)
        P(pen, q, C(col))
    P(pen, el(h[0] - 30, h[1] - 34, 16, 20), C(col), 3)
    text(pen, label, (h[0] + 26, h[1] - 34), 26)


def wad(pen, h, col="#c23b3b", bundle=True):
    for k in range(5):
        P(pen, rr(h[0], h[1] - 30 - k * 9, 140, 22, 3), C(col), 3)
    if bundle:
        P(pen, rr(h[0], h[1] - 48, 28, 64, 2), C("#f2e9c8"), 3)


def card(pen, h, col="#2b4c9a", stripe=None, chip=True, logo=None, photo=False, label=None):
    c = (h[0], h[1] - 44)
    P(pen, rr(c[0], c[1], 150, 94, 10), C(col))
    if stripe:
        P(pen, rr(c[0], c[1] - 20, 150, 18, 0), C(stripe), 0)
    if chip:
        P(pen, rr(c[0] - 40, c[1] + 4, 30, 24, 4), C("#d9b44a"), 3)
    if logo:
        D(pen, (c[0] + 44, c[1] + 26), 12, C(logo[0], 230))
        D(pen, (c[0] + 58, c[1] + 26), 12, C(logo[1], 230))
    if photo:
        P(pen, rr(c[0] - 44, c[1] + 6, 40, 52, 4), C("#c9d3e0"), 3)
        D(pen, (c[0] - 44, c[1] - 2), 11, C("#8a96a8"))
        for k in range(3):
            L(pen, [(c[0] - 10, c[1] - 10 + k * 16), (c[0] + 60, c[1] - 10 + k * 16)], 4, C("#7a7a80"))
    if label:
        text(pen, label, (c[0] + 20, c[1] + 26), 20, C("#ffffff"))


def paper(pen, h, w=110, hh=150, col="#fbfaf4", lines=5, zig=False, title=None, stamp=None, tilt=-6, grid=False, photo=False, total=False):
    c = (h[0] + 6, h[1] - hh / 2 + 10)
    pts = rr(c[0], c[1], w, hh, 3)
    if zig:
        t, b, l, r = c[1] - hh / 2, c[1] + hh / 2, c[0] - w / 2, c[0] + w / 2
        pts = [(l, t), (r, t)] + [(r - k * w / 8, b - (6 if k % 2 else 0)) for k in range(9)]
    P(pen, rot(pts, c, tilt), C(col))
    top = c[1] - hh / 2 + 22
    if title:
        L(pen, rot([(c[0] - w * 0.3, top), (c[0] + w * 0.3, top)], c, tilt), 7, C(title))
        top += 18
    if photo:
        P(pen, rot(rr(c[0], top + 26, w * 0.7, 50, 3), c, tilt), C("#a8c0d8"), 3)
        top += 62
    for k in range(lines):
        y = top + k * max(10, (hh - (top - c[1] + hh / 2) - 20) / max(1, lines))
        if y > c[1] + hh / 2 - 12:
            break
        L(pen, rot([(c[0] - w * 0.36, y), (c[0] + w * (0.2 if k % 3 == 2 else 0.36), y)], c, tilt), 3, C("#9a9a9a"))
    if grid:
        for k in range(1, 4):
            x = c[0] - w / 2 + k * w / 4
            L(pen, rot([(x, c[1] - hh / 2 + 8), (x, c[1] + hh / 2 - 8)], c, tilt), 2, C("#c0c0c0"))
    if total:
        L(pen, rot([(c[0] - w * 0.36, c[1] + hh / 2 - 22), (c[0] + w * 0.36, c[1] + hh / 2 - 22)], c, tilt), 6, INK)
    if stamp:
        P(pen, rot(el(c[0] + w * 0.22, c[1] + hh * 0.28, 20, 20), c, tilt), C(stamp, 120), 3)


def book(pen, h, col="#8a3a3a", w=100, hh=136, spine="#5a2020", label=None, rings=False):
    c = (h[0], h[1] - hh / 2 + 8)
    P(pen, rr(c[0], c[1], w, hh, 5), C(col))
    P(pen, rr(c[0] - w / 2 + 8, c[1], 14, hh, 2), C(spine), 3)
    if rings:
        for k in range(5):
            D(pen, (c[0] - w / 2, c[1] - hh / 2 + 16 + k * (hh - 32) / 4), 6, C("#c0c0c0"))
    if label:
        text(pen, label, (c[0] + 6, c[1] - 10), 24, C("#ffffff"))


def bottle(pen, h, col="#3d7a3d", cap="#d8d8d8", label="#f2e7c9", hh=190, w=52, neck=0.32, liquid=None, shape="std", alpha=255):
    b = h[1] + 20
    top = b - hh
    nk = top + hh * neck
    if shape == "flask":
        body = rr(h[0], b - (b - nk) / 2, w * 1.3, b - nk, 10)
    elif shape == "round":
        body = el(h[0], b - (b - nk) / 2 + 6, w * 0.7, (b - nk) / 2)
    else:
        body = rr(h[0], b - (b - nk) / 2, w, b - nk, 12)
    P(pen, rr(h[0], (top + nk) / 2 + 10, w * 0.36, nk - top + 20, 6), C(col, alpha))
    P(pen, body, C(col, alpha))
    if liquid:
        P(pen, rr(h[0], b - (b - nk) * 0.3, w - 10, (b - nk) * 0.55, 8), C(liquid), 0)
    if label:
        P(pen, rr(h[0], b - (b - nk) * 0.45, w * (1.25 if shape == "flask" else 0.98), (b - nk) * 0.36, 2), C(label), 3)
    P(pen, rr(h[0], top + 4, w * 0.42, 16, 3), C(cap), 3)


def can(pen, h, col="#c0392b", band="#f2f2f2", hh=110, w=62):
    c = (h[0], h[1] - hh / 2 + 16)
    P(pen, rr(c[0], c[1], w, hh, 8), C(col))
    P(pen, rr(c[0], c[1], w, hh * 0.28, 0), C(band), 0)
    L(pen, [(c[0] - w / 2 + 6, c[1] - hh / 2 + 8), (c[0] + w / 2 - 6, c[1] - hh / 2 + 8)], 3, C("#b0b0b0"))


def cup(pen, h, col="#ffffff", liquid="#6b3e26", hh=90, w=74, handle=False, straw=None, lid=None, boba=False, glass=False, stem=False, sleeve=None, steam=False):
    b = h[1] + 10
    top = b - hh
    if stem:
        L(pen, [(h[0], b), (h[0], b + 60)], 6, C("#d0e4f0"))
        P(pen, el(h[0], b + 60, 30, 8), C("#d0e4f0"), 3)
    body = [(h[0] - w / 2, top), (h[0] + w / 2, top), (h[0] + w * 0.36, b), (h[0] - w * 0.36, b)]
    if stem:
        body = el(h[0], top + hh * 0.35, w / 2, hh * 0.65, 0, 180) + [(h[0] - w / 2, top), (h[0] + w / 2, top)]
    P(pen, body, C(col, 140 if glass else 255))
    if liquid:
        lv = top + hh * 0.25
        liq = [(h[0] - w * 0.46, lv), (h[0] + w * 0.46, lv), (h[0] + w * 0.34, b - 4), (h[0] - w * 0.34, b - 4)] if not stem else el(h[0], top + hh * 0.35, w / 2 - 5, hh * 0.6, 0, 180)
        P(pen, liq, C(liquid, 220), 0)
    if boba:
        for k in range(7):
            D(pen, (h[0] - w * 0.28 + (k % 4) * w * 0.18, b - 12 - (k // 4) * 14), 7, C("#2a1a12"))
    if sleeve:
        P(pen, [(h[0] - w * 0.44, top + hh * 0.35), (h[0] + w * 0.44, top + hh * 0.35), (h[0] + w * 0.4, top + hh * 0.65), (h[0] - w * 0.4, top + hh * 0.65)], C(sleeve), 3)
    if lid:
        P(pen, rr(h[0], top - 6, w + 8, 16, 6), C(lid), 3)
    if straw:
        L(pen, [(h[0] + 8, top - 4), (h[0] + 20, top - 70)], 9, C(straw))
    if handle:
        L(pen, el(h[0] + w / 2 - 2, top + hh * 0.45, 18, 22, -90, 90, 10), 7)
    if steam:
        for k in (-1, 1):
            L(pen, [(h[0] + k * 14, top - 14), (h[0] + k * 14 + 8, top - 34), (h[0] + k * 14, top - 54)], 4, C("#d8d8d8", 200))


def bowl(pen, h, col="#f4f4f2", food="#e8c070", w=130, deep=50, top_items=None, chop=False):
    c = (h[0], h[1] - 30)
    P(pen, el(c[0], c[1] - deep / 2, w / 2 - 6, 14), C(food))
    for k, (dx, dy, r, fc) in enumerate(top_items or []):
        D(pen, (c[0] + dx, c[1] - deep / 2 + dy - 6), r, C(fc))
    P(pen, el(c[0], c[1] - deep / 2, w / 2, deep, 0, 180, 18) + [(c[0] - w / 2, c[1] - deep / 2)], C(col))
    if chop:
        L(pen, [(c[0] - 20, c[1] - deep), (c[0] + 50, c[1] - deep - 80)], 5, C("#c89a5a"))
        L(pen, [(c[0] - 6, c[1] - deep), (c[0] + 64, c[1] - deep - 74)], 5, C("#c89a5a"))


def plate(pen, h, food="#f2f0e6", mound=None, col="#ffffff", w=160, items=None):
    c = (h[0], h[1] - 18)
    P(pen, el(c[0], c[1], w / 2, 22), C(col))
    P(pen, el(c[0], c[1] - 2, w / 2 - 18, 14), C("#e9e9e4"), 2)
    if mound:
        P(pen, el(c[0] - 10, c[1] - 10, w * 0.26, 26, 180, 360, 16), C(mound))
    for dx, dy, r, fc in items or []:
        P(pen, el(c[0] + dx, c[1] - 10 + dy, r, r * 0.7), C(fc), 3)


def fruit(pen, h, col="#d23a3a", r=34, leaf="#4f8a3a", stem=True, shape="round", spots=None):
    c = (h[0], h[1] - r)
    if shape == "banana":
        P(pen, el(c[0], c[1] + 10, 70, 46, 200, 340, 14) + el(c[0], c[1] + 30, 56, 28, 340, 200, 14), C(col))
        L(pen, [(c[0] + 58, c[1] - 6), (c[0] + 70, c[1] - 16)], 7, C("#6a5a2a"))
        return
    if shape == "slice":
        P(pen, [(c[0] - 60, c[1] - 20), (c[0] + 60, c[1] - 20), (c[0], c[1] + 50)], C(col))
        P(pen, [(c[0] - 60, c[1] - 20), (c[0] + 60, c[1] - 20), (c[0] + 56, c[1] - 30), (c[0] - 56, c[1] - 30)], C(leaf))
        for k in range(4):
            D(pen, (c[0] - 24 + k * 16, c[1] - 2 + (k % 2) * 12), 4, INK)
        return
    if shape == "long":
        P(pen, el(c[0], c[1] - 10, r * 0.5, r * 1.3), C(col))
    elif shape == "oval":
        P(pen, el(c[0], c[1], r * 1.2, r * 0.85), C(col))
    else:
        P(pen, el(c[0], c[1], r, r), C(col))
    if spots:
        for k in range(6):
            a = k * 1.05
            D(pen, (c[0] + math.cos(a) * r * 0.55, c[1] + math.sin(a) * r * 0.55), 4, C(spots))
    if stem:
        L(pen, [(c[0], c[1] - r + 2), (c[0] + 4, c[1] - r - 14)], 5, C("#6a4a2a"))
    if leaf:
        P(pen, el(c[0] + 14, c[1] - r - 8, 14, 7), C(leaf), 3)


def skewer(pen, h, cols=("#9a5a2a",), n=4, r=16):
    L(pen, [(h[0], h[1] + 10), (h[0], h[1] - 40 - n * r * 1.9)], 5, C("#d8b886"))
    for k in range(n):
        P(pen, el(h[0], h[1] - 40 - k * r * 1.9, r * 1.1, r), C(cols[k % len(cols)]), 3)


def box(pen, h, col="#c8a064", w=120, hh=90, ribbon=None, lid=None, label=None, handle=False):
    c = (h[0], h[1] - hh / 2 + 6)
    P(pen, rr(c[0], c[1], w, hh, 5), C(col))
    if lid:
        P(pen, rr(c[0], c[1] - hh / 2 + 8, w + 10, 20, 4), C(lid), 3)
    if ribbon:
        P(pen, rr(c[0], c[1], 16, hh, 0), C(ribbon), 0)
        P(pen, rr(c[0], c[1], w, 16, 0), C(ribbon), 0)
        P(pen, el(c[0] - 14, c[1] - hh / 2 - 6, 16, 10), C(ribbon), 3)
        P(pen, el(c[0] + 14, c[1] - hh / 2 - 6, 16, 10), C(ribbon), 3)
    if handle:
        L(pen, el(c[0], c[1] - hh / 2, 24, 22, 180, 360, 10), 6)
    if label:
        text(pen, label, (c[0], c[1] + 4), 26, C("#ffffff"))


def bag(pen, h, col="#d8d4c8", w=110, hh=120, kind="tote", strap=None):
    c = (h[0], h[1] + hh / 2 + 20)
    if kind == "sack":
        P(pen, [(c[0] - w / 2, c[1] - hh / 2), (c[0] + w / 2, c[1] - hh / 2), (c[0] + w * 0.6, c[1] + hh / 2), (c[0] - w * 0.6, c[1] + hh / 2)], C(col))
        L(pen, [(c[0] - 20, c[1] - hh / 2), (h[0], h[1]), (c[0] + 20, c[1] - hh / 2)], 6, C("#8a6a3a"))
        return
    if kind == "plastic":
        P(pen, [(c[0] - w / 2, c[1] - hh / 2), (c[0] + w / 2, c[1] - hh / 2), (c[0] + w * 0.45, c[1] + hh / 2), (c[0] - w * 0.45, c[1] + hh / 2)], C(col, 200), 3)
        L(pen, [(c[0] - w / 2 + 10, c[1] - hh / 2), (h[0] - 12, h[1]), (h[0] + 12, h[1]), (c[0] + w / 2 - 10, c[1] - hh / 2)], 5, C(col))
        return
    P(pen, rr(c[0], c[1], w, hh, 12), C(col))
    if kind == "brief":
        P(pen, rr(c[0], c[1] - 6, w, 10, 0), C("#2a2a2a"), 0)
        L(pen, [(c[0] - 20, c[1] - hh / 2), (c[0] - 16, h[1]), (c[0] + 16, h[1]), (c[0] + 20, c[1] - hh / 2)], 6)
        return
    L(pen, [(c[0] - w * 0.25, c[1] - hh / 2), (h[0], h[1]), (c[0] + w * 0.25, c[1] - hh / 2)], 5, C(strap or "#5a5a5a"))
    if kind == "shop":
        text(pen, "SALE", (c[0], c[1] + 4), 24, C("#ffffff"))


def device(pen, h, kind="phone", col="#16161a", screen="#78aae6"):
    c = (h[0], h[1] - 50)
    if kind == "tablet":
        P(pen, rr(c[0], c[1] - 20, 130, 170, 10), C(col))
        P(pen, rr(c[0], c[1] - 20, 112, 150, 6), C(screen), 0)
    elif kind == "laptop":
        P(pen, rr(c[0], c[1] - 30, 200, 130, 8), C(col))
        P(pen, rr(c[0], c[1] - 32, 180, 110, 4), C(screen), 0)
        P(pen, [(c[0] - 110, c[1] + 36), (c[0] + 110, c[1] + 36), (c[0] + 124, c[1] + 54), (c[0] - 124, c[1] + 54)], C("#b8bcc4"))
    elif kind == "camera":
        P(pen, rr(c[0], c[1], 140, 90, 12), C(col))
        P(pen, el(c[0], c[1] + 4, 32, 32), C("#2a2a30"))
        P(pen, el(c[0], c[1] + 4, 18, 18), C(screen), 3)
        P(pen, rr(c[0] - 40, c[1] - 52, 34, 16, 3), C(col), 3)
    elif kind == "vcam":
        P(pen, rr(c[0], c[1], 150, 80, 10), C(col))
        P(pen, rr(c[0] + 90, c[1], 40, 50, 6), C("#2a2a30"))
        D(pen, (c[0] - 50, c[1] - 24), 8, C("#e03030"))
    elif kind == "mic":
        L(pen, [(h[0], h[1] + 10), (h[0], h[1] - 80)], 16, C("#2a2a2e"))
        P(pen, el(h[0], h[1] - 104, 30, 34), C("#9a9aa2"))
        for k in range(3):
            L(pen, [(h[0] - 22, h[1] - 118 + k * 12), (h[0] + 22, h[1] - 118 + k * 12)], 2, C("#6a6a72"))
    elif kind == "remote":
        P(pen, rr(h[0], h[1] - 50, 40, 130, 14), C(col))
        D(pen, (h[0], h[1] - 96), 8, C("#e03030"))
        for k in range(3):
            D(pen, (h[0] - 9, h[1] - 64 + k * 20), 5, C("#8a8a90"))
            D(pen, (h[0] + 9, h[1] - 64 + k * 20), 5, C("#8a8a90"))
    elif kind == "pad":
        P(pen, el(h[0] - 40, h[1] - 30, 40, 34) + el(h[0] + 40, h[1] - 30, 40, 34), C(col))
        P(pen, rr(h[0], h[1] - 40, 90, 50, 18), C(col), 0)
        D(pen, (h[0] - 44, h[1] - 34), 10, C("#8a8a90"))
        for dx, dy, cc in ((44, -46, "#e03030"), (56, -30, "#30a0e0"), (32, -30, "#e0c030")):
            D(pen, (h[0] + dx, h[1] + dy), 7, C(cc))
    elif kind == "calc":
        P(pen, rr(h[0], h[1] - 56, 90, 130, 10), C(col))
        P(pen, rr(h[0], h[1] - 100, 70, 26, 3), C("#b8c8a8"), 0)
        for r_ in range(3):
            for q in range(3):
                P(pen, rr(h[0] - 24 + q * 24, h[1] - 66 + r_ * 24, 16, 14, 3), C("#d8d8d8"), 0)
    elif kind == "radio":
        P(pen, rr(c[0], c[1], 150, 90, 10), C(col))
        P(pen, el(c[0] - 38, c[1] + 6, 26, 26), C("#3a3a3e"), 3)
        P(pen, rr(c[0] + 34, c[1] - 10, 56, 22, 3), C(screen), 3)
        L(pen, [(c[0] + 60, c[1] - 45), (c[0] + 90, c[1] - 110)], 4, C("#9a9aa2"))
    elif kind == "walkie":
        P(pen, rr(h[0], h[1] - 56, 54, 120, 10), C(col))
        L(pen, [(h[0] + 16, h[1] - 116), (h[0] + 16, h[1] - 170)], 8, C(col))
        P(pen, rr(h[0], h[1] - 70, 36, 30, 4), C(screen), 0)
    elif kind == "torch":
        P(pen, rr(h[0], h[1] - 40, 34, 110, 8), C(col))
        P(pen, [(h[0] - 24, h[1] - 96), (h[0] + 24, h[1] - 96), (h[0] + 17, h[1] - 80), (h[0] - 17, h[1] - 80)], C("#c8c8c8"))
        P(pen, [(h[0] - 24, h[1] - 100), (h[0] + 24, h[1] - 100), (h[0] + 60, h[1] - 200), (h[0] - 60, h[1] - 200)], C("#fff3a0", 90), 0)
    elif kind == "headset":
        L(pen, el(h[0], h[1] - 60, 50, 60, 180, 360, 14), 9, C(col))
        P(pen, rr(h[0] - 50, h[1] - 50, 30, 50, 10), C(col))
        P(pen, rr(h[0] + 50, h[1] - 50, 30, 50, 10), C(col))
    elif kind == "speaker":
        P(pen, rr(c[0], c[1], 90, 140, 12), C(col))
        P(pen, el(c[0], c[1] + 26, 30, 30), C("#3a3a40"), 3)
        P(pen, el(c[0], c[1] - 36, 16, 16), C("#3a3a40"), 3)
    elif kind == "drone":
        P(pen, rr(c[0], c[1], 70, 30, 8), C(col))
        for dx in (-70, 70):
            L(pen, [(c[0], c[1]), (c[0] + dx, c[1] - 20)], 6, C(col))
            P(pen, el(c[0] + dx, c[1] - 24, 30, 6), C("#9a9aa2", 200), 2)
    elif kind == "usb":
        P(pen, rr(h[0], h[1] - 30, 30, 60, 6), C(col))
        P(pen, rr(h[0], h[1] - 70, 20, 22, 2), C("#c8c8c8"), 3)
    elif kind == "bank":
        P(pen, rr(h[0], h[1] - 40, 70, 110, 10), C(col))
        D(pen, (h[0], h[1] - 80), 7, C("#60e080"))
    else:
        P(pen, rr(c[0], c[1] - 4, 58, 106, 10), C(col))
        P(pen, rr(c[0], c[1] - 4, 46, 88, 5), C(screen), 0)
        if kind == "cracked":
            L(pen, [(c[0] - 18, c[1] - 40), (c[0] + 4, c[1] - 6), (c[0] - 8, c[1] + 10), (c[0] + 16, c[1] + 36)], 3, C("#ffffff"))
        if kind == "watch":
            P(pen, rr(c[0], c[1] - 4, 58, 58, 16), C(col), 0)


def tool(pen, h, kind, col="#9aa0a8", handle="#7a4a2a"):
    x, y = h
    if kind == "hammer":
        L(pen, [(x, y + 30), (x, y - 120)], 12, C(handle))
        P(pen, rr(x, y - 130, 90, 34, 5), C(col))
    elif kind == "wrench":
        L(pen, [(x, y + 30), (x, y - 110)], 14, C(col))
        P(pen, el(x, y - 128, 26, 26), C(col))
        P(pen, rr(x, y - 140, 16, 26, 2), C("#ffffff", 0), 0)
        P(pen, el(x, y - 146, 10, 14), C("#ffffff", 255), 0)
    elif kind == "screwdriver":
        P(pen, rr(x, y - 20, 26, 70, 10), C(handle))
        L(pen, [(x, y - 56), (x, y - 140)], 6, C(col))
    elif kind == "saw":
        L(pen, [(x, y), (x, y - 40)], 18, C(handle))
        P(pen, [(x - 14, y - 40), (x + 14, y - 40), (x + 30, y - 220), (x - 4, y - 220)], C(col), 3)
    elif kind == "drill":
        P(pen, rr(x, y - 20, 30, 70, 8), C(col))
        P(pen, rr(x + 30, y - 70, 110, 44, 10), C(col))
        L(pen, [(x + 86, y - 70), (x + 140, y - 70)], 6, C("#c8c8c8"))
    elif kind == "pliers":
        L(pen, [(x - 10, y + 20), (x - 2, y - 60), (x + 10, y - 120)], 9, C(handle))
        L(pen, [(x + 10, y + 20), (x + 2, y - 60), (x - 10, y - 120)], 9, C(handle))
        D(pen, (x, y - 64), 8, C(col))
    elif kind == "tape":
        P(pen, rr(x, y - 40, 80, 76, 14), C("#e0c020"))
        D(pen, (x, y - 40), 12, C("#3a3a3a"))
        L(pen, [(x + 40, y - 10), (x + 90, y - 10)], 6, C("#e0c020"))
    elif kind == "brush":
        L(pen, [(x, y + 20), (x, y - 70)], 10, C(handle))
        P(pen, rr(x, y - 96, 50, 50, 4), C("#c8b07a"))
        P(pen, rr(x, y - 112, 46, 18, 2), C(col), 0)
    elif kind == "roller":
        L(pen, [(x, y + 20), (x, y - 70), (x + 40, y - 90)], 8, C("#7a7a80"))
        P(pen, rr(x + 40, y - 112, 110, 36, 14), C(col))
    elif kind in ("shovel", "hoe", "rake", "broom", "mop", "axe", "crowbar", "stick", "bat", "golf", "racket", "badminton", "oar"):
        top = y - 300
        L(pen, [(x, y + 120), (x, top)], 9, C(handle))
        if kind == "shovel":
            P(pen, [(x - 34, top), (x + 34, top), (x + 26, top - 70), (x, top - 90), (x - 26, top - 70)], C(col))
        elif kind == "hoe":
            P(pen, [(x, top), (x + 70, top + 6), (x + 70, top + 40), (x + 6, top + 26)], C(col))
        elif kind == "rake":
            L(pen, [(x - 60, top), (x + 60, top)], 8, C(col))
            for k in range(7):
                L(pen, [(x - 54 + k * 18, top), (x - 54 + k * 18, top - 30)], 4, C(col))
        elif kind == "broom":
            P(pen, [(x - 14, top), (x + 14, top), (x + 50, top - 110), (x - 50, top - 110)], C("#d8b060"))
        elif kind == "mop":
            for k in range(9):
                L(pen, [(x, top), (x - 40 + k * 10, top - 90 - (k % 2) * 10)], 5, C("#e8e8e0"))
        elif kind == "axe":
            P(pen, [(x, top + 10), (x + 70, top - 20), (x + 74, top + 60), (x, top + 50)], C(col))
        elif kind == "crowbar":
            L(pen, [(x, top), (x + 30, top - 30), (x + 50, top - 20)], 10, C("#b02020"))
        elif kind == "bat":
            L(pen, [(x, y + 40), (x, top + 40)], 12, C(handle))
            L(pen, [(x, top + 120), (x, top - 40)], 30, C(handle))
        elif kind == "golf":
            P(pen, rr(x + 14, top - 6, 50, 22, 6), C(col))
        elif kind == "racket":
            P(pen, el(x, top - 70, 56, 74), C(col, 40))
            for k in range(-3, 4):
                L(pen, [(x + k * 14, top - 140), (x + k * 14, top)], 2, C("#e8e8e8"))
                L(pen, [(x - 50, top - 70 + k * 18), (x + 50, top - 70 + k * 18)], 2, C("#e8e8e8"))
            L(pen, el(x, top - 70, 56, 74), 7, C(col))
        elif kind == "badminton":
            P(pen, el(x, top - 54, 40, 56), C(col, 30))
            L(pen, el(x, top - 54, 40, 56), 5, C(col))
        elif kind == "oar":
            P(pen, el(x, top - 60, 26, 70), C(col))
    elif kind == "bucket":
        P(pen, [(x - 60, y + 30), (x + 60, y + 30), (x + 46, y + 140), (x - 46, y + 140)], C(col))
        L(pen, el(x, y + 30, 60, 40, 180, 360, 12), 5)
    elif kind == "watering":
        P(pen, rr(x, y + 70, 100, 100, 14), C(col))
        L(pen, [(x + 50, y + 90), (x + 130, y + 20)], 12, C(col))
        L(pen, el(x, y + 20, 40, 30, 180, 360, 10), 7, C(col))
    elif kind == "toolbox":
        box(pen, (x, y + 110), "#c03030", 160, 90, handle=True)
    elif kind == "key":
        P(pen, el(x, y - 30, 22, 22), C("#d9b44a"))
        D(pen, (x, y - 30), 7, C("#ffffff", 0))
        L(pen, [(x, y - 52), (x, y - 120)], 8, C("#d9b44a"))
        L(pen, [(x, y - 104), (x + 16, y - 104)], 7, C("#d9b44a"))
        L(pen, [(x, y - 118), (x + 12, y - 118)], 7, C("#d9b44a"))
    elif kind == "keys":
        L(pen, el(x, y - 16, 20, 20), 4, C("#9a9aa2"))
        for k, cc in enumerate(("#d9b44a", "#c8c8d0", "#d9b44a")):
            L(pen, [(x - 20 + k * 20, y - 30), (x - 34 + k * 26, y - 100)], 8, C(cc))
    elif kind == "padlock":
        L(pen, el(x, y - 70, 26, 34, 180, 360, 12), 9, C("#9a9aa2"))
        P(pen, rr(x, y - 40, 76, 60, 8), C("#d9b44a"))
        D(pen, (x, y - 42), 7, INK)
    elif kind == "rope":
        for k in range(3):
            L(pen, el(x, y - 30, 40 - k * 6, 30 - k * 4), 7, C("#c8a060"))
        L(pen, [(x + 30, y), (x + 50, y + 120)], 7, C("#c8a060"))
    elif kind == "chain":
        for k in range(6):
            L(pen, el(x + (k % 2) * 4, y - 20 - k * 22, 10, 14), 5, C("#9a9aa2"))
    elif kind == "oilcan":
        P(pen, rr(x, y - 40, 70, 100, 8), C(col))
        L(pen, [(x + 20, y - 90), (x + 70, y - 150)], 8, C(col))
    elif kind == "jerry":
        P(pen, rr(x, y + 60, 110, 140, 12), C("#c03030"))
        P(pen, rr(x + 30, y - 18, 30, 24, 4), C("#c03030"))
        L(pen, [(x - 40, y - 10), (x - 10, y - 10)], 10, C("#c03030"))
    elif kind == "ladder":
        for dx in (-50, 50):
            L(pen, [(x + dx, y + 160), (x + dx, y - 360)], 10, C("#b8b8b8"))
        for k in range(8):
            L(pen, [(x - 50, y + 140 - k * 64), (x + 50, y + 140 - k * 64)], 8, C("#b8b8b8"))
    elif kind == "plug":
        P(pen, rr(x, y - 40, 50, 60, 8), C("#e8e8e8"))
        L(pen, [(x - 12, y - 70), (x - 12, y - 96)], 6, C("#c8a040"))
        L(pen, [(x + 12, y - 70), (x + 12, y - 96)], 6, C("#c8a040"))
        L(pen, [(x, y - 10), (x + 10, y + 80)], 6, C("#2a2a2a"))
    elif kind == "tire":
        P(pen, el(x, y - 70, 80, 80), C("#2a2a2e"))
        P(pen, el(x, y - 70, 38, 38), C("#9a9aa2"))


def kitchen(pen, h, kind, col="#9aa0a8"):
    x, y = h
    if kind == "spatula":
        L(pen, [(x, y + 20), (x, y - 110)], 9, C("#3a3a3a"))
        P(pen, rr(x, y - 140, 56, 50, 6), C(col))
    elif kind == "wok":
        P(pen, el(x + 90, y - 30, 90, 40, 0, 180, 18) + [(x, y - 30)], C("#2e2e32"))
        L(pen, [(x, y - 30), (x - 80, y - 10)], 12, C("#6a4a2a"))
    elif kind == "pan":
        P(pen, el(x + 100, y - 20, 80, 22), C("#2e2e32"))
        L(pen, [(x + 20, y - 20), (x - 50, y - 6)], 14, C("#2a2a2a"))
    elif kind == "pot":
        P(pen, rr(x, y - 50, 150, 100, 10), C(col))
        P(pen, rr(x, y - 104, 160, 16, 6), C(col), 3)
        L(pen, [(x - 90, y - 70), (x - 76, y - 70)], 10)
        L(pen, [(x + 76, y - 70), (x + 90, y - 70)], 10)
    elif kind == "board":
        P(pen, rr(x, y - 40, 170, 90, 14), C("#c89a5a"))
        D(pen, (x + 66, y - 66), 8, C("#8a6a3a"))
    elif kind == "rolling":
        L(pen, [(x - 110, y - 20), (x + 110, y - 20)], 30, C("#d8b07a"))
        L(pen, [(x - 140, y - 20), (x + 140, y - 20)], 12, C("#a07a4a"))
    elif kind == "whisk":
        L(pen, [(x, y + 20), (x, y - 50)], 12, C("#3a3a3a"))
        for k in (-1, 0, 1):
            L(pen, el(x, y - 100, 14 + abs(k) * 12, 50), 3, C(col))
    elif kind == "chopsticks":
        L(pen, [(x - 4, y + 20), (x + 10, y - 150)], 6, C("#c89a5a"))
        L(pen, [(x + 6, y + 20), (x + 24, y - 146)], 6, C("#c89a5a"))
    elif kind == "fork":
        L(pen, [(x, y + 20), (x, y - 80)], 8, C(col))
        for k in range(4):
            L(pen, [(x - 15 + k * 10, y - 80), (x - 15 + k * 10, y - 120)], 4, C(col))
        L(pen, [(x - 16, y - 80), (x + 16, y - 80)], 6, C(col))
    elif kind == "spoon":
        L(pen, [(x, y + 20), (x, y - 80)], 8, C(col))
        P(pen, el(x, y - 104, 18, 26), C(col))
    elif kind == "tongs":
        L(pen, [(x - 6, y + 10), (x - 22, y - 150)], 7, C(col))
        L(pen, [(x + 6, y + 10), (x + 22, y - 150)], 7, C(col))
    elif kind == "kettle":
        P(pen, el(x, y - 50, 70, 56), C(col))
        L(pen, el(x, y - 100, 40, 30, 180, 360, 10), 8)
        L(pen, [(x + 60, y - 50), (x + 110, y - 90)], 12, C(col))
    elif kind == "ricecooker":
        P(pen, rr(x, y - 60, 150, 110, 30), C("#f0f0ea"))
        P(pen, rr(x, y - 112, 130, 24, 12), C("#e06060"), 3)
        D(pen, (x, y - 40), 10, C("#e06060"))
    elif kind == "mortar":
        P(pen, el(x, y - 40, 70, 40, 0, 180, 16) + [(x - 70, y - 40)], C("#c89a6a"))
        L(pen, [(x + 10, y - 50), (x + 60, y - 150)], 16, C("#a07a4a"))
    elif kind == "grater":
        P(pen, [(x - 40, y), (x + 40, y), (x + 30, y - 130), (x - 30, y - 130)], C(col))
        for k in range(5):
            L(pen, [(x - 20, y - 20 - k * 22), (x + 20, y - 20 - k * 22)], 3, C("#5a5a60"))
    elif kind == "blender":
        P(pen, rr(x, y + 10, 90, 50, 8), C("#3a3a3e"))
        P(pen, [(x - 36, y - 16), (x + 36, y - 16), (x + 50, y - 150), (x - 50, y - 150)], C("#d0e4f0", 150))
        P(pen, [(x - 32, y - 16), (x + 32, y - 16), (x + 40, y - 90), (x - 40, y - 90)], C("#e05a7a", 200), 0)
    elif kind == "mitt":
        P(pen, rr(x, y - 50, 70, 110, 30), C("#d04040"))
        P(pen, el(x - 40, y - 60, 16, 30), C("#d04040"))
    elif kind == "tray":
        P(pen, rr(x, y - 10, 220, 24, 8), C(col))
    elif kind == "thermos":
        P(pen, rr(x, y - 60, 56, 150, 18), C("#3a7aaa"))
        P(pen, rr(x, y - 138, 46, 24, 6), C("#2a2a2e"), 3)
    elif kind == "ladle2":
        L(pen, [(x, y + 20), (x, y - 120)], 7, C(col))
        P(pen, el(x, y - 140, 26, 20), C(col))
    elif kind == "cleaver":
        L(pen, [(x, y + 20), (x, y - 30)], 14, C("#3a2a1a"))
        P(pen, rr(x + 20, y - 80, 80, 70, 4), C("#c8ccd2"))


def food(pen, h, kind):
    x, y = h
    if kind == "egg":
        P(pen, el(x, y - 34, 26, 34), C("#f6efe0"))
    elif kind == "friedegg":
        plate(pen, h, items=[(0, -2, 40, "#ffffff"), (0, -4, 14, "#f2b81c")])
    elif kind == "bread":
        P(pen, el(x, y - 40, 50, 40, 180, 360, 14) + [(x + 50, y - 40), (x + 46, y), (x - 46, y)], C("#d8a050"))
        P(pen, el(x, y - 30, 38, 30, 180, 360, 12) + [(x + 38, y - 30), (x + 36, y - 6), (x - 36, y - 6)], C("#f2deb0"), 0)
    elif kind == "sandwich":
        P(pen, [(x - 60, y), (x + 60, y), (x, y - 90)], C("#f2deb0"))
        L(pen, [(x - 46, y - 12), (x + 46, y - 12)], 8, C("#6ab04a"))
        L(pen, [(x - 40, y - 22), (x + 40, y - 22)], 6, C("#e05050"))
    elif kind == "burger":
        P(pen, el(x, y - 70, 60, 34, 180, 360, 14) + [(x + 60, y - 70), (x - 60, y - 70)], C("#d89040"))
        L(pen, [(x - 62, y - 62), (x + 62, y - 62)], 8, C("#6ab04a"))
        P(pen, rr(x, y - 46, 124, 24, 10), C("#6a3a1a"))
        P(pen, rr(x, y - 24, 118, 22, 10), C("#d89040"))
    elif kind == "pizza":
        P(pen, [(x - 50, y - 120), (x + 50, y - 120), (x, y + 10)], C("#f2c860"))
        P(pen, rr(x, y - 124, 106, 16, 8), C("#c88a3a"), 3)
        for dx, dy in ((-18, -96), (14, -84), (-2, -56)):
            D(pen, (x + dx, y + dy), 9, C("#c03030"))
    elif kind == "hotdog":
        P(pen, rr(x, y - 30, 150, 40, 20), C("#e0b060"))
        P(pen, rr(x, y - 38, 170, 22, 11), C("#c04a3a"), 3)
        L(pen, [(x - 60, y - 42), (x - 30, y - 34), (x, y - 42), (x + 30, y - 34), (x + 60, y - 42)], 4, C("#f2c020"))
    elif kind == "donut":
        P(pen, el(x, y - 50, 50, 50), C("#d89a50"))
        P(pen, el(x, y - 54, 44, 42), C("#f08ab0"), 0)
        D(pen, (x, y - 50), 16, C("#ffffff", 0))
        P(pen, el(x, y - 50, 16, 16), C("#ffffff", 0), 3)
    elif kind == "cake":
        P(pen, rr(x, y - 50, 150, 90, 8), C("#f6e0c0"))
        P(pen, rr(x, y - 90, 154, 22, 10), C("#f2a0b8"), 3)
        for k in range(3):
            L(pen, [(x - 40 + k * 40, y - 100), (x - 40 + k * 40, y - 140)], 7, C("#5ab0e0"))
            D(pen, (x - 40 + k * 40, y - 148), 7, C("#f6c020"))
    elif kind == "cupcake":
        P(pen, [(x - 34, y - 50), (x + 34, y - 50), (x + 26, y), (x - 26, y)], C("#e0a0c0"))
        P(pen, el(x, y - 60, 40, 30), C("#fff0f6"))
        D(pen, (x, y - 92), 8, C("#d02030"))
    elif kind == "icecream":
        P(pen, [(x - 30, y - 70), (x + 30, y - 70), (x, y + 10)], C("#d8a050"))
        P(pen, el(x, y - 90, 36, 32), C("#f6c0d8"))
        P(pen, el(x, y - 124, 30, 26), C("#a8e0c0"))
    elif kind == "cookie":
        P(pen, el(x, y - 40, 44, 44), C("#d8a050"))
        for dx, dy in ((-14, -50), (12, -30), (8, -60), (-10, -24)):
            D(pen, (x + dx, y + dy), 6, C("#4a2a1a"))
    elif kind == "candy":
        P(pen, el(x, y - 40, 30, 22), C("#e04a8a"))
        P(pen, [(x - 30, y - 40), (x - 60, y - 60), (x - 60, y - 20)], C("#e04a8a"), 3)
        P(pen, [(x + 30, y - 40), (x + 60, y - 60), (x + 60, y - 20)], C("#e04a8a"), 3)
    elif kind == "lollipop":
        L(pen, [(x, y + 20), (x, y - 80)], 6, C("#f0f0f0"))
        P(pen, el(x, y - 110, 36, 36), C("#f05a7a"))
        L(pen, el(x, y - 110, 20, 20, 0, 300, 12), 5, C("#ffffff"))
    elif kind == "chocolate":
        P(pen, rr(x, y - 50, 80, 120, 6), C("#5a2e1a"))
        P(pen, rr(x, y - 20, 84, 60, 4), C("#c03030"), 3)
    elif kind == "steak":
        plate(pen, h, items=[(0, -4, 50, "#8a3a2a")])
    elif kind == "sushi":
        for k in range(3):
            P(pen, rr(x - 44 + k * 44, y - 30, 38, 30, 8), C("#f6f6f0"), 3)
            P(pen, rr(x - 44 + k * 44, y - 50, 42, 14, 6), C("#f07a4a"), 3)
    elif kind == "dumpling":
        for k in range(3):
            P(pen, el(x - 40 + k * 40, y - 30, 22, 18, 180, 360, 10) + [(x - 18 + k * 40, y - 24), (x - 62 + k * 40, y - 24)], C("#f6f0e0"), 3)
    elif kind == "crab":
        P(pen, el(x, y - 40, 50, 32), C("#e05030"))
        for s in (-1, 1):
            P(pen, el(x + s * 70, y - 70, 18, 14), C("#e05030"), 3)
            D(pen, (x + s * 14, y - 70), 6, INK)
    elif kind == "shrimp":
        L(pen, el(x, y - 40, 40, 34, 200, 450, 14), 18, C("#f08a5a"))
    elif kind == "corn":
        P(pen, el(x, y - 70, 26, 74), C("#f2c830"))
        P(pen, [(x - 26, y - 20), (x - 40, y - 110), (x - 6, y - 40)], C("#7ab04a"), 3)
    elif kind == "carrot":
        P(pen, [(x - 18, y - 120), (x + 18, y - 120), (x, y + 10)], C("#f08a2a"))
        for k in (-1, 0, 1):
            L(pen, [(x, y - 120), (x + k * 14, y - 160)], 6, C("#5ab04a"))
    elif kind == "chili":
        L(pen, el(x, y - 30, 26, 70, 180, 300, 10), 16, C("#d02020"))
    elif kind == "riceplate":
        plate(pen, h, mound="#fbfaf2")
    elif kind == "friedrice":
        plate(pen, h, mound="#e8c070", items=[(30, -6, 10, "#5ab04a"), (-30, -6, 12, "#f2b81c")])
    elif kind == "basil":
        plate(pen, h, mound="#fbfaf2", items=[(36, -4, 30, "#7a4a2a"), (-34, -10, 18, "#f2b81c")])
    elif kind == "somtam":
        plate(pen, h, items=[(0, -4, 50, "#c8d870"), (20, -8, 8, "#d02020"), (-14, -12, 6, "#e06030")])
    elif kind == "grilledchicken":
        plate(pen, h, items=[(-10, -4, 46, "#b0602a"), (30, -14, 20, "#d08a3a")])
    elif kind == "noodle":
        bowl(pen, h, food="#e8d090", top_items=[(-20, 0, 10, "#e06050"), (20, 2, 8, "#5ab04a")], chop=True)
    elif kind == "tomyum":
        bowl(pen, h, food="#e86a2a", top_items=[(-20, 0, 12, "#f6a080"), (16, 0, 7, "#5ab04a")])
    elif kind == "congee":
        bowl(pen, h, food="#f6f2e2", top_items=[(0, 0, 9, "#f2b81c")])
    elif kind == "stickyrice":
        P(pen, rr(x, y - 50, 90, 90, 20), C("#c8a060"))
        L(pen, [(x - 40, y - 60), (x + 40, y - 60)], 3, C("#8a6a3a"))
        L(pen, el(x, y - 96, 30, 22, 180, 360, 10), 5, C("#8a6a3a"))
    elif kind == "lunchbox":
        for k in range(3):
            P(pen, rr(x, y - 30 - k * 46, 90, 44, 8), C("#c0c4ca"))
        L(pen, [(x - 50, y - 10), (x - 50, y - 170), (x + 50, y - 170), (x + 50, y - 10)], 5, C("#8a8a90"))
    elif kind == "takeaway":
        P(pen, [(x - 60, y - 80), (x + 60, y - 80), (x + 50, y), (x - 50, y)], C("#f6f2e6"))
        P(pen, [(x - 64, y - 80), (x + 64, y - 80), (x + 40, y - 110), (x - 40, y - 110)], C("#f6f2e6"), 3)
    elif kind == "waterbag":
        P(pen, el(x, y + 60, 44, 60), C("#d0e8f8", 180))
        P(pen, el(x, y + 76, 40, 40), C("#e0a040", 200), 0)
        L(pen, [(x, y + 10), (x, y - 10)], 6, C("#d02020"))
        L(pen, [(x + 6, y + 30), (x + 30, y - 40)], 6, C("#f2f2f2"))
    elif kind == "popcorn":
        P(pen, [(x - 50, y - 100), (x + 50, y - 100), (x + 36, y), (x - 36, y)], C("#f2f2f2"))
        for k in range(4):
            P(pen, rr(x - 36 + k * 24, y - 50, 12, 100, 0), C("#e03030"), 0)
        for k in range(6):
            D(pen, (x - 40 + k * 16, y - 108 - (k % 2) * 10), 13, C("#fff6d8"))
    elif kind == "rice_sack":
        bag(pen, (x, y - 40), "#e8e0c8", 120, 150, "sack")


def misc(pen, h, kind, col="#c03030"):
    x, y = h
    if kind == "umbrella":
        L(pen, [(x, y + 20), (x, y - 240)], 7, C("#3a3a3a"))
        P(pen, el(x, y - 240, 140, 80, 180, 360, 18) + [(x + 140, y - 240), (x - 140, y - 240)], C(col))
        L(pen, el(x, y + 20, 14, 16, 0, 180, 8), 6, C("#3a3a3a"))
    elif kind == "flowers":
        for k, cc in enumerate(("#e03050", "#f2c020", "#e070b0", "#ffffff", "#e03050")):
            a = -60 + k * 30
            tip = (x + math.sin(math.radians(a)) * 110, y - 60 - math.cos(math.radians(a)) * 110)
            L(pen, [(x, y), tip], 4, C("#4a8a3a"))
            for p in range(5):
                D(pen, (tip[0] + math.cos(p * 1.26) * 14, tip[1] + math.sin(p * 1.26) * 14), 11, C(cc))
            D(pen, tip, 8, C("#f2c020"))
        P(pen, [(x - 40, y - 60), (x + 40, y - 60), (x + 10, y + 30), (x - 10, y + 30)], C("#f0e6d0"))
    elif kind == "rose":
        L(pen, [(x, y + 20), (x + 6, y - 120)], 5, C("#3a7a2a"))
        P(pen, el(x + 6, y - 140, 24, 24), C("#c01a30"))
        L(pen, el(x + 6, y - 140, 12, 12, 0, 300, 8), 3, C("#7a0a18"))
    elif kind == "candle":
        P(pen, rr(x, y - 50, 30, 100, 4), C("#f6f0e0"))
        P(pen, el(x, y - 118, 10, 18), C("#f6a020"), 0)
    elif kind == "lantern":
        P(pen, el(x, y - 70, 50, 60), C("#d02020"))
        P(pen, rr(x, y - 132, 40, 12, 3), C("#f2c020"), 3)
        P(pen, rr(x, y - 8, 40, 12, 3), C("#f2c020"), 3)
        L(pen, [(x, y - 138), (x, y - 160)], 4)
    elif kind == "incense":
        for k in range(3):
            L(pen, [(x - 10 + k * 10, y + 10), (x - 16 + k * 16, y - 130)], 4, C("#c06040"))
            D(pen, (x - 16 + k * 16, y - 132), 4, C("#f05a20"))
    elif kind == "garland":
        L(pen, el(x, y + 40, 40, 70, 0, 360, 20), 14, C("#f6f2e6"))
        P(pen, el(x, y + 110, 20, 14), C("#d02020"), 3)
        L(pen, [(x, y + 120), (x, y + 170)], 6, C("#f2c020"))
    elif kind == "amulet":
        L(pen, el(x, y - 40, 36, 60, 180, 360, 12), 3, C("#d9b44a"))
        P(pen, rr(x, y - 10, 40, 54, 8), C("#d9b44a"))
        P(pen, el(x, y - 10, 12, 18), C("#8a6a2a"), 0)
    elif kind == "frame":
        P(pen, rr(x, y - 70, 120, 150, 4), C("#8a5a2a"))
        P(pen, rr(x, y - 70, 92, 120, 2), C("#c8d8e8"), 3)
        D(pen, (x, y - 90), 18, C("#7a8aa0"))
        P(pen, el(x, y - 40, 28, 18, 180, 360, 10), C("#7a8aa0"), 0)
    elif kind == "ringbox":
        P(pen, rr(x, y - 30, 70, 50, 8), C("#b02040"))
        P(pen, rr(x, y - 66, 70, 30, 8), C("#b02040"), 3)
        L(pen, el(x, y - 40, 12, 10), 4, C("#d9b44a"))
        D(pen, (x, y - 52), 6, C("#e0f4ff"))
    elif kind == "suitcase":
        P(pen, rr(x, y + 100, 150, 200, 14), C(col))
        L(pen, [(x - 30, y + 2), (x - 30, y - 20), (x + 30, y - 20), (x + 30, y + 2)], 8, C("#3a3a3a"))
        for dx in (-40, 40):
            L(pen, [(x + dx, y + 10), (x + dx, y + 190)], 4, C("#00000040"))
    elif kind == "backpack":
        P(pen, rr(x, y + 60, 110, 140, 30), C(col))
        P(pen, rr(x, y + 90, 80, 60, 12), C(col), 3)
        L(pen, [(x - 20, y), (x, y - 14), (x + 20, y)], 6)
    elif kind == "pillow":
        P(pen, rr(x, y - 50, 160, 100, 36), C("#f2f2ee"))
    elif kind == "blanket":
        P(pen, rr(x, y + 60, 160, 160, 10), C(col))
        for k in range(4):
            L(pen, [(x - 70, y + 4 + k * 36), (x + 70, y + 4 + k * 36)], 4, C("#ffffff", 120))
    elif kind == "towel":
        P(pen, rr(x, y + 70, 70, 150, 6), C(col))
        L(pen, [(x - 34, y + 120), (x + 34, y + 120)], 6, C("#ffffff"))
    elif kind == "handfan":
        P(pen, el(x, y - 40, 90, 90, 200, 340, 14) + [(x, y - 40)], C(col))
        for k in range(6):
            a = math.radians(200 + k * 28)
            L(pen, [(x, y - 40), (x + math.cos(a) * 90, y - 40 + math.sin(a) * 90)], 3, C("#ffffff"))
    elif kind == "tissue":
        P(pen, rr(x, y - 40, 120, 70, 6), C("#7ab0d8"))
        P(pen, [(x - 20, y - 76), (x + 20, y - 76), (x + 10, y - 120), (x - 14, y - 110)], C("#ffffff"), 3)
    elif kind == "toiletpaper":
        P(pen, rr(x, y - 50, 80, 90, 14), C("#ffffff"))
        P(pen, el(x, y - 95, 40, 12), C("#ececec"), 3)
        D(pen, (x, y - 95), 8, C("#c8a070"))
    elif kind == "soap":
        P(pen, rr(x, y - 30, 80, 50, 18), C("#f2a0c8"))
        for k in range(3):
            P(pen, el(x - 30 + k * 26, y - 70 - k * 8, 10, 10), C("#e0f4ff", 200), 2)
    elif kind == "trashbag":
        bag(pen, (x, y - 20), "#2a2a2e", 130, 150, "sack")
    elif kind == "sign":
        L(pen, [(x, y + 40), (x, y - 160)], 9, C("#a07a4a"))
        P(pen, rr(x, y - 200, 220, 120, 4), C("#e8d8b0"))
        for k in range(3):
            L(pen, [(x - 80, y - 230 + k * 26), (x + 80 - k * 30, y - 230 + k * 26)], 7, C("#2a2a2e"))
    elif kind == "megaphone":
        P(pen, [(x - 10, y - 40), (x + 30, y - 50), (x + 130, y - 100), (x + 130, y + 10), (x + 30, y - 10), (x - 10, y - 20)], C("#f0f0f0"))
        P(pen, el(x + 130, y - 45, 12, 55), C("#d02020"), 3)
    elif kind == "whistle":
        P(pen, rr(x, y - 30, 60, 34, 14), C("#d0d4da"))
        P(pen, rr(x - 36, y - 38, 30, 16, 4), C("#d0d4da"), 3)
    elif kind == "binoculars":
        for dx in (-30, 30):
            P(pen, rr(x + dx, y - 50, 44, 80, 12), C("#2a2a2e"))
            P(pen, el(x + dx, y - 92, 20, 8), C("#78aae6"), 3)
    elif kind == "magnifier":
        L(pen, [(x, y + 20), (x + 30, y - 50)], 14, C("#5a3a1a"))
        P(pen, el(x + 50, y - 100, 46, 46), C("#c8e8f8", 120))
        L(pen, el(x + 50, y - 100, 46, 46), 9, C("#2a2a2e"))
    elif kind == "giftbox":
        box(pen, h, "#d02040", 120, 100, ribbon="#f2c020")
    elif kind == "parcel":
        box(pen, h, "#c8a064", 140, 100)
        L(pen, [(x - 70, y - 40), (x + 70, y - 40)], 10, C("#a08050"))
    elif kind == "shoebox":
        box(pen, h, "#e8e8e0", 160, 70, lid="#d02020")
    elif kind == "teddy":
        P(pen, el(x, y - 50, 44, 50), C("#b07a4a"))
        P(pen, el(x, y - 120, 36, 34), C("#b07a4a"))
        for dx in (-26, 26):
            P(pen, el(x + dx, y - 150, 14, 14), C("#b07a4a"), 3)
            D(pen, (x + dx * 0.45, y - 124), 5, INK)
    elif kind == "balloon":
        L(pen, [(x, y + 20), (x + 10, y - 150)], 2, C("#5a5a5a"))
        P(pen, el(x + 10, y - 210, 50, 62), C(col))
    elif kind == "kite":
        P(pen, [(x + 60, y - 260), (x + 120, y - 180), (x + 60, y - 80), (x, y - 180)], C(col))
        L(pen, [(x, y), (x + 60, y - 80)], 2, C("#5a5a5a"))
    elif kind == "toycar":
        P(pen, rr(x, y - 30, 110, 40, 14), C(col))
        P(pen, rr(x - 6, y - 60, 60, 30, 10), C(col), 3)
        for dx in (-34, 34):
            D(pen, (x + dx, y - 8), 13, INK)
    elif kind == "rubik":
        for r_ in range(3):
            for q in range(3):
                P(pen, rr(x - 30 + q * 30, y - 90 + r_ * 30, 28, 28, 4), C(("#d02020", "#f2c020", "#2a7ad0", "#4ab04a", "#ffffff", "#f07a20")[(r_ * 3 + q) % 6]), 3)
    elif kind == "ball":
        P(pen, el(x, y - 54, 54, 54), C("#ffffff"))
        P(pen, [(x - 14, y - 70), (x + 14, y - 70), (x + 20, y - 46), (x, y - 32), (x - 20, y - 46)], INK, 0)
    elif kind == "basketball":
        P(pen, el(x, y - 54, 54, 54), C("#e07a2a"))
        L(pen, [(x - 54, y - 54), (x + 54, y - 54)], 4)
        L(pen, [(x, y - 108), (x, y)], 4)
        L(pen, el(x - 60, y - 54, 34, 50, -60, 60, 10), 4)
        L(pen, el(x + 60, y - 54, 34, 50, 120, 240, 10), 4)
    elif kind == "dumbbell":
        L(pen, [(x - 70, y - 20), (x + 70, y - 20)], 12, C("#7a7a80"))
        for dx in (-70, 70):
            P(pen, rr(x + dx, y - 20, 34, 70, 6), C("#2a2a2e"))
    elif kind == "jumprope":
        L(pen, el(x + 60, y + 60, 70, 100, 0, 180, 16), 4, C("#d02020"))
        P(pen, rr(x, y - 10, 18, 50, 8), C("#2a7ad0"))
    elif kind == "skateboard":
        P(pen, rr(x, y - 30, 240, 26, 13), C(col))
        for dx in (-70, 70):
            D(pen, (x + dx, y - 6), 12, C("#f2f2f2"))
    elif kind in ("guitar", "ukulele"):
        k = 1.0 if kind == "guitar" else 0.6
        P(pen, el(x, y + 40 * k, 70 * k, 60 * k), C("#c87a3a"))
        P(pen, el(x, y - 40 * k, 52 * k, 46 * k), C("#c87a3a"))
        D(pen, (x, y + 10 * k), 18 * k, C("#3a2a1a"))
        L(pen, [(x, y - 70 * k), (x, y - 300 * k)], 16 * k, C("#5a3a1a"))
        P(pen, rr(x, y - 310 * k, 30 * k, 40 * k, 4), C("#3a2a1a"), 3)
    elif kind == "violin":
        P(pen, el(x, y - 40, 34, 60), C("#a0501a"))
        L(pen, [(x, y - 90), (x, y - 190)], 10, C("#2a1a10"))
        L(pen, [(x - 60, y - 20), (x + 70, y - 150)], 3, C("#e8e0c8"))
    elif kind == "drum":
        P(pen, rr(x, y + 50, 140, 90, 6), C("#d02020"))
        P(pen, el(x, y + 5, 70, 16), C("#f2f2ea"))
        L(pen, [(x - 30, y - 20), (x - 10, y - 120)], 6, C("#d8b07a"))
    elif kind == "trophy":
        P(pen, el(x, y - 110, 50, 50, 0, 180, 14) + [(x - 50, y - 110), (x + 50, y - 110)], C("#e2b234"))
        P(pen, rr(x, y - 140, 104, 60, 4), C("#e2b234"), 0)
        L(pen, [(x, y - 60), (x, y - 20)], 14, C("#e2b234"))
        P(pen, rr(x, y - 10, 70, 22, 4), C("#7a4a2a"))
        L(pen, el(x - 56, y - 130, 16, 22, 90, 270, 8), 6, C("#e2b234"))
        L(pen, el(x + 56, y - 130, 16, 22, -90, 90, 8), 6, C("#e2b234"))
    elif kind == "medal":
        P(pen, [(x - 20, y - 130), (x, y - 70), (x + 20, y - 130)], C("#2a5ad0"))
        P(pen, el(x, y - 50, 30, 30), C("#e2b234"))
        P(pen, el(x, y - 50, 18, 18), C("#e2b234"), 3)
    elif kind == "slipper":
        P(pen, rr(x, y - 90, 70, 190, 34), C("#2a6ad0"))
        L(pen, [(x - 30, y - 140), (x, y - 120), (x + 30, y - 140)], 8, C("#f2f2f2"))
    elif kind == "rolledpaper":
        P(pen, rr(x, y - 80, 40, 200, 10), C("#e8e4d8"))
        for k in range(4):
            L(pen, [(x - 18, y - 150 + k * 40), (x + 18, y - 150 + k * 40)], 3, C("#9a9a9a"))
    elif kind == "mask":
        P(pen, rr(x, y - 40, 110, 60, 14), C("#a8d8f0"))
        L(pen, [(x - 55, y - 54), (x - 80, y - 70)], 3)
        L(pen, [(x + 55, y - 54), (x + 80, y - 70)], 3)
    elif kind == "pills":
        P(pen, rr(x, y - 50, 70, 100, 8), C("#f2a030"))
        P(pen, rr(x, y - 110, 76, 26, 6), C("#ffffff"), 3)
        P(pen, rr(x, y - 50, 70, 40, 0), C("#ffffff"), 0)
    elif kind == "pillstrip":
        P(pen, rr(x, y - 40, 110, 70, 6), C("#d8dce2"))
        for r_ in range(2):
            for q in range(4):
                P(pen, el(x - 39 + q * 26, y - 54 + r_ * 28, 9, 9), C("#f6f6f6"), 2)
    elif kind == "syringe":
        P(pen, rr(x, y - 70, 26, 110, 4), C("#e8f4fc"))
        P(pen, rr(x, y - 50, 18, 60, 2), C("#e05a5a", 180), 0)
        L(pen, [(x, y - 126), (x, y - 180)], 3, C("#b8b8c0"))
        L(pen, [(x, y - 14), (x, y + 30)], 8, C("#b8b8c0"))
    elif kind == "thermometer":
        L(pen, [(x, y), (x, y - 130)], 14, C("#f2f2f2"))
        L(pen, [(x, y - 4), (x, y - 70)], 6, C("#d02020"))
        D(pen, (x, y), 12, C("#d02020"))
    elif kind == "bandage":
        P(pen, rot(rr(x, y - 40, 140, 40, 18), (x, y - 40), -20), C("#e8b88a"))
        P(pen, rot(rr(x, y - 40, 44, 30, 6), (x, y - 40), -20), C("#f6dcc0"), 0)
    elif kind == "stethoscope":
        L(pen, el(x, y - 80, 50, 60, 180, 360, 14), 6, C("#2a2a2e"))
        L(pen, [(x, y - 20), (x + 10, y + 50)], 6, C("#2a2a2e"))
        P(pen, el(x + 10, y + 64, 18, 18), C("#c8ccd2"))
    elif kind == "lipstick":
        P(pen, rr(x, y - 30, 30, 60, 4), C("#2a2a2e"))
        P(pen, [(x - 12, y - 60), (x + 12, y - 60), (x + 12, y - 92), (x - 4, y - 104), (x - 12, y - 92)], C("#c01a40"))
    elif kind == "mirror":
        L(pen, [(x, y + 20), (x, y - 50)], 14, C("#e070a0"))
        P(pen, el(x, y - 100, 50, 56), C("#e070a0"))
        P(pen, el(x, y - 100, 40, 46), C("#d8eef8"), 0)
    elif kind == "comb":
        P(pen, rr(x, y - 60, 30, 150, 6), C("#2a2a2e"))
        for k in range(8):
            L(pen, [(x + 14, y - 124 + k * 16), (x + 34, y - 124 + k * 16)], 3, C("#2a2a2e"))
    elif kind == "hairdryer":
        P(pen, rr(x + 40, y - 90, 140, 60, 24), C(col))
        P(pen, rr(x, y - 30, 34, 90, 10), C(col))
    elif kind == "perfume":
        bottle(pen, h, "#f2a0c8", "#d9b44a", None, 110, 70, 0.3, shape="round", alpha=200)
    elif kind == "nailpolish":
        bottle(pen, h, "#d02060", "#2a2a2e", None, 90, 40, 0.45)
    elif kind == "pen":
        L(pen, [(x, y + 20), (x + 6, y - 120)], 10, C("#2a5ad0"))
        L(pen, [(x + 6, y - 120), (x + 7, y - 140)], 4, INK)
    elif kind == "pencil":
        L(pen, [(x, y + 20), (x + 6, y - 120)], 12, C("#f2c020"))
        P(pen, [(x, y - 120), (x + 12, y - 120), (x + 7, y - 150)], C("#e8c8a0"), 2)
        L(pen, [(x - 1, y + 20), (x - 1, y + 36)], 12, C("#f07090"))
    elif kind == "marker":
        P(pen, rr(x, y - 50, 30, 130, 10), C("#f2f2f2"))
        P(pen, rr(x, y - 104, 32, 30, 8), C(col), 3)
    elif kind == "ruler":
        P(pen, rr(x, y - 110, 30, 260, 2), C("#f2d860"))
        for k in range(12):
            L(pen, [(x - 15, y - 230 + k * 20), (x - 4 + (k % 2) * 6, y - 230 + k * 20)], 2)
    elif kind == "scissors":
        L(pen, [(x - 10, y - 30), (x + 20, y - 150)], 7, C("#c8ccd2"))
        L(pen, [(x + 10, y - 30), (x - 20, y - 150)], 7, C("#c8ccd2"))
        L(pen, el(x - 16, y - 16, 14, 14), 6, C("#d02020"))
        L(pen, el(x + 16, y - 16, 14, 14), 6, C("#d02020"))
    elif kind == "stapler":
        P(pen, rr(x, y - 30, 140, 30, 10), C("#2a2a2e"))
        P(pen, rr(x - 6, y - 52, 130, 22, 10), C("#d02020"), 3)
    elif kind == "rubberstamp":
        P(pen, rr(x, y - 70, 30, 70, 10), C("#7a4a2a"))
        P(pen, rr(x, y - 26, 80, 30, 4), C("#2a2a2e"))
        P(pen, rr(x, y - 6, 80, 10, 2), C("#c02020"), 0)
    elif kind == "tape_roll":
        P(pen, el(x, y - 40, 40, 40), C("#e8e0b8", 220))
        P(pen, el(x, y - 40, 22, 22), C("#c8a070"), 3)
    elif kind == "glue":
        P(pen, rr(x, y - 50, 40, 100, 10), C("#f2f2f2"))
        P(pen, rr(x, y - 110, 24, 24, 6), C("#f07a20"), 3)
    elif kind == "files":
        for k in range(4):
            P(pen, rr(x, y - 20 - k * 20, 150, 20, 2), C(("#f2c020", "#4a8ad0", "#e05a5a", "#5ab04a")[k]))
    elif kind == "clipboard":
        P(pen, rr(x, y - 70, 120, 160, 6), C("#a07a4a"))
        P(pen, rr(x, y - 64, 100, 136, 2), C("#fbfaf4"), 3)
        P(pen, rr(x, y - 146, 50, 20, 4), C("#c8ccd2"), 3)
        for k in range(5):
            L(pen, [(x - 38, y - 110 + k * 22), (x + 38, y - 110 + k * 22)], 3, C("#9a9a9a"))
    elif kind == "evidence":
        P(pen, rr(x, y - 60, 110, 130, 4), C("#e8f4fc", 170))
        P(pen, rr(x, y - 116, 110, 18, 2), C("#d02020"), 3)
        P(pen, el(x, y - 50, 24, 30), C("#5a5a60"), 3)
    elif kind == "cigarbox":
        box(pen, h, "#7a4a2a", 120, 60, lid="#5a2a1a")
    elif kind == "lighter":
        P(pen, rr(x, y - 40, 40, 70, 6), C(col))
        P(pen, el(x, y - 90, 9, 16), C("#f6a020"), 0)
    elif kind == "safe":
        box(pen, h, "#5a5f6e", 140, 140)
        P(pen, el(x, y - 60, 26, 26), C("#c8ccd2"), 3)
    elif kind == "piggy":
        P(pen, el(x, y - 50, 60, 46), C("#f2a0b8"))
        P(pen, el(x + 56, y - 56, 16, 18), C("#f2a0b8"), 3)
        L(pen, [(x - 10, y - 96), (x + 14, y - 96)], 6)
        D(pen, (x + 30, y - 66), 5, INK)
    elif kind == "goldbar":
        for k in range(2):
            P(pen, [(x - 60 + k * 10, y - 20 - k * 30), (x + 60 + k * 10, y - 20 - k * 30), (x + 44 + k * 10, y - 50 - k * 30), (x - 44 + k * 10, y - 50 - k * 30)], C("#e2b234"))
    elif kind == "moneybag":
        P(pen, el(x, y + 70, 70, 70), C("#c8a060"))
        P(pen, [(x - 24, y), (x + 24, y), (x + 34, y - 30), (x - 34, y - 30)], C("#c8a060"), 3)
        L(pen, [(x - 26, y + 4), (x + 26, y + 4)], 6, C("#7a4a2a"))
        text(pen, "฿", (x, y + 76), 54, C("#5a3a10"))
    elif kind == "wallet":
        P(pen, rr(x, y - 36, 130, 80, 10), C("#5a3a20"))
        P(pen, rr(x, y - 58, 120, 14, 4), C("#7ab06a"), 0)
        D(pen, (x + 50, y - 30), 7, C("#d9b44a"))
    elif kind == "purse":
        P(pen, rr(x, y + 60, 120, 80, 14), C("#d0507a"))
        L(pen, el(x, y + 20, 40, 34, 180, 360, 10), 6, C("#d9b44a"))
    elif kind == "handbag":
        P(pen, [(x - 70, y + 40), (x + 70, y + 40), (x + 80, y + 140), (x - 80, y + 140)], C(col))
        L(pen, el(x, y + 40, 44, 50, 180, 360, 12), 7, C("#3a2a1a"))
    elif kind == "laundry":
        P(pen, rr(x, y + 60, 150, 100, 14), C("#4a8ad0", 220))
        for k in range(3):
            D(pen, (x - 40 + k * 40, y + 6), 22, C(("#f2f2f2", "#e05a5a", "#f2c020")[k]))
    elif kind == "flag":
        L(pen, [(x, y + 20), (x, y - 220)], 6, C("#8a6a3a"))
        for k, cc in enumerate(("#d02020", "#f2f2f2", "#2a3a8a", "#f2f2f2", "#d02020")):
            P(pen, rr(x + 60, y - 210 + k * 14 + (8 if k > 2 else 0) * 0, 110, 14 if k != 2 else 28, 0), C(cc), 0)
    elif kind == "crystalball":
        P(pen, el(x, y - 80, 56, 56), C("#b8d8f8", 200))
        P(pen, rr(x, y - 14, 80, 24, 6), C("#7a4a2a"))
    elif kind == "dice":
        P(pen, rr(x, y - 40, 60, 60, 10), C("#f2f2f2"))
        for dx, dy in ((-14, -54), (0, -40), (14, -26)):
            D(pen, (x + dx, y + dy), 6, INK)
    elif kind == "cards":
        for k in range(3):
            P(pen, rot(rr(x, y - 60, 70, 100, 6), (x, y - 10), -20 + k * 20), C("#f6f6f6"))
        text(pen, "A", (x + 18, y - 70), 30, C("#d02020"))
    elif kind == "lottery":
        paper(pen, h, 150, 76, "#f2e8f6", 2, title="#7a3a9a", tilt=-4)
    elif kind == "newspaper":
        paper(pen, h, 150, 190, "#ecebe4", 7, title="#2a2a2e", photo=True, tilt=-3)
    elif kind == "magazine":
        book(pen, h, "#e05a8a", 110, 150, "#b03060")
        P(pen, rr(x, y - 66, 70, 70, 4), C("#f2d0a0"), 3)


def gear(pen, h, kind, col="#c03030", label=None):
    x, y = h
    if kind == "noodle_cup":
        P(pen, [(x - 44, y - 110), (x + 44, y - 110), (x + 32, y + 6), (x - 32, y + 6)], C("#f6f2e8"))
        P(pen, [(x - 41, y - 80), (x + 41, y - 80), (x + 38, y - 50), (x - 38, y - 50)], C(col), 3)
        text(pen, label or "บะหมี่", (x, y - 64), 18, WHITE)
        P(pen, rot(el(x + 6, y - 112, 48, 10), (x - 40, y - 112), -14), C("#e8e0cc"), 3)
        L(pen, [(x + 18, y - 104), (x + 40, y - 170)], 5, C("#c8ccd2"))
        for k in range(3):
            L(pen, [(x + 32 + k * 6, y - 170), (x + 36 + k * 6, y - 190)], 3, C("#c8ccd2"))
    elif kind == "aid_kit":
        P(pen, rr(x, y + 70, 150, 110, 12), C("#f6f6f4"))
        P(pen, rr(x, y + 70, 24, 70, 3), C("#d02a2a"), 0)
        P(pen, rr(x, y + 70, 70, 24, 3), C("#d02a2a"), 0)
        L(pen, [(x - 30, y + 16), (x - 30, y), (x + 30, y), (x + 30, y + 16)], 8, C("#3a3a3a"))
    elif kind == "extinguisher":
        P(pen, rr(x - 6, y + 120, 64, 190, 26), C("#d02a2a"))
        P(pen, rr(x - 6, y + 128, 50, 50, 4), C("#f2f2f2"), 3)
        P(pen, rr(x - 6, y + 14, 30, 22, 4), C("#3a3a3a"), 3)
        L(pen, [(x - 20, y), (x + 30, y - 6)], 8, C("#3a3a3a"))
        L(pen, [(x + 6, y + 18), (x + 50, y + 40), (x + 56, y + 150)], 7, C("#2a2a2e"))
        P(pen, rr(x + 56, y + 168, 16, 34, 4), C("#2a2a2e"), 3)
    elif kind == "gas_mask":
        P(pen, el(x, y - 70, 52, 62), C("#3a3f46"))
        for dx in (-22, 22):
            P(pen, el(x + dx, y - 90, 16, 14), C("#bcd8e8"), 3)
        P(pen, el(x, y - 30, 26, 22), C("#5a5f66"), 3)
        P(pen, el(x, y - 30, 12, 10), C("#2a2a2e"), 2)
        L(pen, [(x - 52, y - 70), (x - 70, y - 40)], 5, C("#2a2a2e"))
    elif kind == "flare":
        L(pen, [(x, y + 30), (x, y - 120)], 16, C("#d02a2a"))
        L(pen, [(x, y - 120), (x, y - 128)], 16, C("#f2f2f2"))
        P(pen, el(x, y - 150, 22, 28), C("#ffb020", 230), 0)
        P(pen, el(x, y - 146, 12, 16), C("#fff6c0"), 0)
        for k in range(6):
            a = math.radians(k * 60 + 15)
            D(pen, (x + math.cos(a) * 40, y - 150 + math.sin(a) * 40), 4, C("#ffd040"))
    elif kind == "car_battery":
        P(pen, rr(x, y + 90, 150, 120, 6), C("#2e3238"))
        P(pen, rr(x, y + 44, 150, 26, 4), C("#4a4f56"), 3)
        P(pen, rr(x - 46, y + 26, 18, 14, 2), C("#d02a2a"), 2)
        P(pen, rr(x + 46, y + 26, 18, 14, 2), C("#3a3a3a"), 2)
        P(pen, rr(x, y + 100, 90, 36, 4), C("#f2c020"), 3)
        text(pen, "12V", (x, y + 100), 22, INK)
        L(pen, [(x - 30, y + 34), (x - 20, y), (x + 20, y), (x + 30, y + 34)], 6, C("#1a1a1a"))
    elif kind == "water_jug":
        P(pen, rr(x + 10, y + 100, 120, 170, 22), C("#bfe0f4", 220))
        P(pen, rr(x + 10, y + 120, 112, 120, 18), C("#7ab8e8", 200), 0)
        P(pen, rr(x + 50, y + 14, 26, 24, 4), C("#2a6ad0"), 3)
        L(pen, [(x - 20, y + 20), (x - 20, y), (x + 30, y), (x + 30, y + 16)], 8, C("#bfe0f4"))
    elif kind == "spray_can":
        P(pen, rr(x, y - 50, 44, 120, 8), C(col))
        P(pen, rr(x, y - 70, 36, 30, 3), C("#f2f2f2"), 3)
        P(pen, el(x, y - 112, 22, 12, 180, 360, 10) + [(x + 22, y - 110), (x - 22, y - 110)], C("#c8ccd2"))
        P(pen, rr(x, y - 128, 14, 16, 3), C("#2a2a2e"), 3)
    elif kind == "pipe":
        L(pen, [(x, y + 50), (x, y - 190)], 16, C("#7a8088"))
        L(pen, [(x - 5, y + 40), (x - 5, y - 180)], 4, C("#b0b6be"))
        for yy in (y + 54, y - 194):
            L(pen, [(x - 12, yy), (x + 12, yy)], 8, C("#4a4f56"))
    elif kind == "plank":
        P(pen, rot(rr(x, y - 40, 40, 300, 4), (x, y - 40), 8), C("#b8864a"))
        for dy in (-120, 40):
            D(pen, rot([(x, y + dy)], (x, y - 40), 8)[0], 5, C("#5a3a1a"))
        L(pen, rot([(x - 6, y - 170), (x - 6, y + 80)], (x, y - 40), 8), 3, C("#8a5a2a"))
    elif kind == "generator":
        P(pen, rr(x, y + 100, 180, 130, 8), C("#e0a020"))
        L(pen, [(x - 90, y + 36), (x + 90, y + 36), (x + 90, y + 166), (x - 90, y + 166), (x - 90, y + 36)], 8, C("#2a2a2e"))
        P(pen, el(x - 30, y + 104, 30, 30), C("#4a4f56"), 3)
        P(pen, rr(x + 46, y + 92, 40, 50, 4), C("#2a2a2e"), 3)
        D(pen, (x + 46, y + 80), 5, C("#f05a20"))
        L(pen, [(x - 60, y + 36), (x - 40, y), (x + 40, y), (x + 60, y + 36)], 8, C("#2a2a2e"))
    elif kind == "qr_stand":
        P(pen, rr(x, y - 90, 120, 160, 10), C("#1f4fa0"))
        P(pen, rr(x, y - 100, 84, 84, 4), C("#ffffff"), 3)
        for i in range(5):
            for j in range(5):
                if (i * 7 + j * 3 + i * j) % 3 != 1 or (i in (0, 4) and j in (0, 4)):
                    P(pen, rr(x - 32 + i * 16, y - 132 + j * 16, 13, 13, 1), INK, 0)
        text(pen, label or "สแกนจ่าย", (x, y - 30), 18, WHITE)
        P(pen, rr(x, y + 0, 80, 12, 3), C("#c8ccd2"), 3)
    elif kind == "price_tag":
        P(pen, [(x - 20, y - 30), (x + 70, y - 30), (x + 100, y - 70), (x + 70, y - 110), (x - 20, y - 110)], C(col))
        D(pen, (x + 80, y - 70), 6, C("#ffffff"))
        text(pen, label or "฿99", (x + 20, y - 70), 26, WHITE)
        L(pen, [(x + 80, y - 70), (x + 6, y - 10)], 2, C("#3a3a3a"))
    elif kind == "sale_sign":
        L(pen, [(x, y + 30), (x, y - 120)], 8, C("#8a5a2a"))
        P(pen, rr(x, y - 180, 200, 110, 8), C(col))
        text(pen, label or "ลดราคา!", (x, y - 182), 34, WHITE)
    elif kind == "growth_chart":
        P(pen, rr(x, y - 90, 170, 150, 6), C("#ffffff"))
        L(pen, [(x - 70, y - 150), (x - 70, y - 30), (x + 74, y - 30)], 4, C("#3a3a3a"))
        pts = [(x - 62, y - 44), (x - 30, y - 60), (x - 6, y - 52), (x + 24, y - 96), (x + 62, y - 138)]
        L(pen, pts, 6, C("#2a9a4a"))
        P(pen, [(x + 66, y - 150), (x + 50, y - 132), (x + 72, y - 128)], C("#2a9a4a"), 0)
        text(pen, label or "ยอดขาย", (x - 20, y - 150), 18, C("#2a9a4a"))
    elif kind == "service_bell":
        P(pen, el(x, y - 40, 50, 46, 180, 360, 16) + [(x + 50, y - 40), (x - 50, y - 40)], C("#d9b44a"))
        L(pen, [(x - 30, y - 70), (x - 10, y - 80)], 5, C("#fff2b0"))
        P(pen, rr(x, y - 34, 120, 14, 4), C("#3a3a3a"))
        P(pen, rr(x, y - 92, 16, 14, 4), C("#b08a2a"), 3)
    elif kind == "name_badge":
        P(pen, rr(x, y - 50, 120, 64, 8), C(col))
        P(pen, rr(x, y - 44, 104, 30, 4), C("#ffffff"), 0)
        text(pen, label or "ผู้จัดการ", (x, y - 44), 18, INK)
        P(pen, rr(x, y - 80, 70, 8, 3), C("#3a3a3a"), 0)
    elif kind == "cloche":
        P(pen, el(x, y - 30, 100, 14), C("#c8ccd2"))
        P(pen, el(x, y - 34, 84, 70, 180, 360, 18) + [(x + 84, y - 34), (x - 84, y - 34)], C("#dfe3e8"))
        L(pen, [(x - 50, y - 70), (x - 20, y - 90)], 6, C("#ffffff"))
        D(pen, (x, y - 108), 12, C("#b0b6be"))
    elif kind == "room_key":
        P(pen, el(x, y - 26, 18, 18), C("#d9b44a"))
        L(pen, [(x, y - 44), (x, y - 110)], 8, C("#d9b44a"))
        L(pen, [(x, y - 96), (x + 16, y - 96)], 7, C("#d9b44a"))
        L(pen, [(x, y - 10), (x + 6, y + 20)], 3, C("#3a3a3a"))
        P(pen, rot(rr(x + 14, y + 66, 46, 90, 18), (x + 6, y + 22), -10), C(col))
        text(pen, label or "1208", (x + 18, y + 70), 18, WHITE)
    elif kind == "baton":
        L(pen, [(x, y + 40), (x, y - 220)], 20, C("#1a1a1c"))
        L(pen, [(x, y + 40), (x, y - 10)], 24, C("#3a3a3e"))
        L(pen, [(x - 4, y - 40), (x - 4, y - 200)], 4, C("#5a5a60"))
    elif kind == "helmet":
        P(pen, el(x, y - 60, 64, 62), C(col))
        P(pen, el(x + 18, y - 56, 40, 26, 0, 360, 18), C("#2a3a4a", 230), 3)
        L(pen, [(x + 0, y - 70), (x + 34, y - 74)], 4, C("#9ab8d0"))
        P(pen, rr(x - 10, y + 2, 90, 16, 6), C(col), 3)
    elif kind == "canteen":
        P(pen, el(x, y + 70, 56, 66), C("#6a7a4a"))
        P(pen, el(x, y + 70, 44, 54), C("#7a8a5a"), 0)
        P(pen, rr(x, y - 6, 22, 24, 4), C("#3a3a3a"), 3)
        L(pen, [(x - 50, y + 40), (x - 30, y - 30), (x + 30, y - 30), (x + 50, y + 40)], 5, C("#5a4a3a"))
    elif kind == "solar_panel":
        P(pen, rot(rr(x + 20, y - 80, 190, 130, 4), (x, y - 20), -8), C("#2a3a6a"))
        for k in (-1, 0, 1):
            L(pen, rot([(x + 20 + k * 48, y - 142), (x + 20 + k * 48, y - 18)], (x, y - 20), -8), 3, C("#8aa0d0"))
        L(pen, rot([(x - 72, y - 80), (x + 112, y - 80)], (x, y - 20), -8), 3, C("#8aa0d0"))
        L(pen, [(x, y - 14), (x, y + 30)], 6, C("#5a5f66"))
    elif kind == "water_filter":
        P(pen, rr(x, y - 70, 60, 150, 10), C("#3a7ab0"))
        P(pen, rr(x, y - 110, 44, 40, 6), C("#e8eef2"), 3)
        P(pen, rr(x, y - 40, 44, 60, 6), C("#bfe0f4", 200), 3)
        L(pen, [(x, y + 6), (x, y + 30)], 6, C("#2a2a2e"))
        D(pen, (x, y + 40), 6, C("#7ab8e8"))
    elif kind == "dead_plant":
        P(pen, [(x - 44, y - 70), (x + 44, y - 70), (x + 32, y + 10), (x - 32, y + 10)], C("#b0663a"))
        P(pen, rr(x, y - 74, 96, 16, 4), C("#c0763a"), 3)
        L(pen, [(x, y - 80), (x + 4, y - 150), (x + 30, y - 120)], 4, C("#7a6a3a"))
        L(pen, [(x + 4, y - 130), (x - 26, y - 160), (x - 40, y - 140)], 4, C("#7a6a3a"))
        P(pen, el(x + 34, y - 116, 10, 6), C("#a08a4a"), 2)
        P(pen, el(x - 42, y - 136, 10, 6), C("#a08a4a"), 2)
    elif kind == "crushed_bottle":
        P(pen, [(x - 20, y - 120), (x + 18, y - 116), (x + 26, y - 70), (x + 10, y - 50), (x + 24, y - 10), (x - 22, y - 4), (x - 10, y - 50), (x - 28, y - 76)], C("#cfe6f4", 200))
        P(pen, rr(x - 2, y - 130, 20, 16, 3), C("#3a7ad0"), 3)
        L(pen, [(x - 18, y - 70), (x + 16, y - 60)], 3, C("#8ab0c8"))
    elif kind == "firewood":
        for k, (dx, dy) in enumerate(((-30, 30), (30, 30), (0, -2), (-30, -34), (30, -34))):
            P(pen, rot(rr(x + dx * 0.2, y + dy, 150, 30, 14), (x, y), 8 - k * 4), C("#8a5a2a"))
            D(pen, rot([(x + dx * 0.2 + 70, y + dy)], (x, y), 8 - k * 4)[0], 11, C("#d8b080"))
        L(pen, [(x - 10, y - 60), (x - 10, y + 60)], 5, C("#c8a064"))
    elif kind == "ice_axe":
        L(pen, [(x, y + 40), (x, y - 190)], 10, C("#3a3f46"))
        P(pen, [(x - 70, y - 186), (x + 70, y - 200), (x + 70, y - 184), (x - 70, y - 172)], C("#c8ccd2"))
        P(pen, [(x - 70, y - 186), (x - 96, y - 160), (x - 70, y - 172)], C("#c8ccd2"))
        P(pen, rr(x, y + 24, 16, 40, 4), C("#d02a2a"), 3)
    elif kind == "gas_heater":
        P(pen, rr(x, y + 100, 120, 170, 12), C("#5a5f66"))
        P(pen, rr(x, y + 80, 90, 90, 6), C("#ff8030"), 3)
        for k in range(3):
            L(pen, [(x - 36, y + 50 + k * 30), (x + 36, y + 50 + k * 30)], 4, C("#ffd040"))
        L(pen, [(x - 30, y + 16), (x - 20, y), (x + 20, y), (x + 30, y + 16)], 7, C("#2a2a2e"))
    elif kind == "toxic_barrel":
        P(pen, rr(x, y + 110, 130, 190, 10), C("#e0b020"))
        for yy in (y + 50, y + 170):
            L(pen, [(x - 64, yy), (x + 64, yy)], 6, C("#9a7a10"))
        P(pen, [(x, y + 78), (x + 34, y + 136), (x - 34, y + 136)], C("#1a1a1c"), 0)
        D(pen, (x, y + 116), 9, C("#e0b020"))
        P(pen, el(x - 20, y + 20, 26, 8), C("#7ad040"), 0)
        L(pen, [(x - 30, y + 15), (x - 20, y)], 8, C("#2a2a2e"))
    elif kind == "vial":
        P(pen, rr(x, y - 60, 30, 110, 12), C("#e8f4f8", 210))
        P(pen, rr(x, y - 30, 24, 54, 10), C(col), 0)
        P(pen, rr(x, y - 122, 34, 18, 3), C("#3a3a3a"), 3)
        D(pen, (x - 4, y - 44), 4, C("#ffffff"))
    elif kind == "oxygen_tank":
        P(pen, rr(x, y + 100, 60, 200, 28), C("#2a8a5a"))
        P(pen, rr(x, y - 4, 30, 30, 6), C("#c8ccd2"), 3)
        L(pen, [(x + 14, y - 4), (x + 50, y - 30), (x + 70, y + 60)], 5, C("#3a3a3a"))
        P(pen, el(x + 74, y + 74, 18, 14), C("#e8eef2"), 3)
    elif kind in ("hazard_sign", "rad_sign"):
        L(pen, [(x, y + 30), (x, y - 100)], 8, C("#5a5f66"))
        P(pen, [(x, y - 250), (x + 100, y - 90), (x - 100, y - 90)], C("#f2c020"))
        if kind == "rad_sign":
            D(pen, (x, y - 140), 10, INK)
            for a in (90, 210, 330):
                P(pen, [(x, y - 140)] + el(x, y - 140, 46, 46, a - 30, a + 30, 6), INK, 0)
        else:
            text(pen, "!", (x, y - 140), 70, INK)
    elif kind == "geiger":
        P(pen, rr(x, y - 40, 110, 80, 10), C("#e0b020"))
        P(pen, rr(x - 14, y - 46, 56, 40, 4), C("#d8e8c8"), 3)
        L(pen, [(x - 32, y - 34), (x - 14, y - 58)], 3, C("#d02a2a"))
        D(pen, (x + 34, y - 52), 7, C("#d02a2a"))
        D(pen, (x + 34, y - 26), 7, C("#2a2a2e"))
        L(pen, [(x + 55, y - 40), (x + 90, y - 40), (x + 96, y + 30)], 5, C("#2a2a2e"))
        P(pen, rr(x + 96, y + 60, 22, 70, 8), C("#5a5f66"), 3)
    elif kind == "pill_box":
        P(pen, rr(x, y - 50, 100, 70, 6), C("#f6f6f4"))
        P(pen, rr(x, y - 70, 100, 18, 3), C(col), 0)
        text(pen, label or "KI", (x, y - 40), 24, C(col))
    elif kind == "lead_box":
        P(pen, rr(x, y - 50, 120, 90, 6), C("#6a6e76"))
        P(pen, rr(x, y - 98, 128, 20, 4), C("#7a7e86"), 3)
        D(pen, (x, y - 50), 18, C("#f2c020"))
        for a in (90, 210, 330):
            P(pen, [(x, y - 50)] + el(x, y - 50, 16, 16, a - 30, a + 30, 4), INK, 0)
    elif kind == "ration":
        P(pen, rr(x, y - 50, 90, 120, 8), C("#7a6a4a"))
        P(pen, rr(x, y - 50, 70, 40, 3), C("#e8dcc0"), 3)
        text(pen, label or "MRE", (x, y - 50), 20, INK)
        L(pen, [(x - 44, y - 104), (x + 44, y - 104)], 4, C("#5a4a2a"))
    elif kind == "seed_pack":
        P(pen, rr(x, y - 50, 80, 110, 6), C("#f2e2a0"))
        P(pen, el(x, y - 60, 22, 30), C("#4a9a3a"), 0)
        L(pen, [(x, y - 30), (x, y - 90)], 3, C("#2a6a2a"))
        L(pen, [(x - 36, y - 100), (x + 36, y - 100)], 3, C("#b08a4a"))
    elif kind == "compass":
        P(pen, el(x, y - 40, 40, 40), C("#c8a064"))
        P(pen, el(x, y - 40, 32, 32), C("#f2efe4"), 3)
        P(pen, [(x, y - 70), (x + 8, y - 40), (x - 8, y - 40)], C("#d02a2a"), 0)
        P(pen, [(x, y - 10), (x + 8, y - 40), (x - 8, y - 40)], C("#3a3a3a"), 0)
    elif kind == "delivery_box":
        P(pen, rr(x, y + 100, 170, 150, 14), C(col))
        P(pen, rr(x, y + 112, 120, 50, 8), C("#ffffff", 220), 0)
        text(pen, label or "DELIVERY", (x, y + 112), 20, C(col))
        L(pen, [(x - 50, y + 26), (x - 30, y), (x + 30, y), (x + 50, y + 26)], 8, C("#2a2a2e"))


ITEMS = {}


def _add(cat, key, th, fn, *a, **k):
    ITEMS[key] = (cat, th, fn, a, k)


for key, th, fn, a, k in [
    ("coin", "เหรียญ", coin, (), {}), ("coins", "กองเหรียญ", coin, (), {"n": 4}), ("coin_silver", "เหรียญเงิน", coin, ("#c8ccd2",), {}),
    ("bank20", "แบงก์ 20", note, ("#5aa05a", "20"), {}), ("bank50", "แบงก์ 50", note, ("#4a7ad0", "50"), {}), ("bank100", "แบงก์ 100", note, ("#d04a3a", "100"), {}),
    ("bank500", "แบงก์ 500", note, ("#8a5ab0", "500"), {}), ("bank1000", "แบงก์ 1000", note, ("#9a8a6a", "1000"), {}), ("banknotes", "ปึกแบงก์", note, ("#d04a3a", "100"), {"n": 3}),
    ("money_wad", "เงินปึกหนา", wad, (), {}), ("money_stack", "กองเงินมัดฟาง", wad, ("#9a8a6a",), {}), ("dollar", "ดอลลาร์", note, ("#6a9a6a", "$"), {}),
    ("credit_card", "บัตรเครดิต", card, ("#2b4c9a",), {"logo": ("#e04030", "#f2a020")}), ("gold_card", "บัตรทอง", card, ("#c8a040",), {"logo": ("#e04030", "#f2a020")}),
    ("black_card", "บัตรดำ", card, ("#1a1a1e",), {"logo": ("#c8c8c8", "#8a8a8a")}), ("atm_card", "บัตร ATM", card, ("#3a8a5a",), {}),
    ("id_card", "บัตรประชาชน", card, ("#c8dcf0",), {"chip": False, "photo": True}), ("driver_license", "ใบขับขี่", card, ("#f0e6c8",), {"chip": False, "photo": True}),
    ("keycard", "คีย์การ์ด", card, ("#f2f2f2",), {"chip": False, "stripe": "#2a2a2e"}), ("business_card", "นามบัตร", card, ("#fbfaf4",), {"chip": False, "stripe": "#c03030"}),
    ("member_card", "บัตรสมาชิก", card, ("#d0507a",), {"chip": False, "label": "VIP"}), ("gift_card", "บัตรของขวัญ", card, ("#e05a5a",), {"chip": False, "label": "GIFT"}),
    ("check", "เช็คเงินสด", paper, (170, 76, "#e8f4e8", 3), {"tilt": -3, "title": "#2a6a3a"}), ("coupon", "คูปอง", paper, (140, 70, "#fff2c8", 2), {"title": "#e05a20", "tilt": 5}),
    ("lottery", "ลอตเตอรี่", misc, ("lottery",), {}), ("goldbar", "ทองคำแท่ง", misc, ("goldbar",), {}), ("moneybag", "ถุงเงิน", misc, ("moneybag",), {}),
    ("wallet", "กระเป๋าสตางค์", misc, ("wallet",), {}), ("purse", "กระเป๋าใส่เหรียญ", misc, ("purse",), {}), ("piggy_bank", "กระปุกออมสิน", misc, ("piggy",), {}),
    ("safe", "ตู้เซฟเล็ก", misc, ("safe",), {}), ("bank_book", "สมุดบัญชี", book, ("#2a6a9a",), {"w": 90, "hh": 120, "spine": "#1a4a6a"}),
]:
    _add("money", key, th, fn, *a, **k)

for key, th, fn, a, k in [
    ("receipt", "ใบเสร็จ", paper, (80, 170, "#fbfaf4", 7), {"zig": True, "total": True, "tilt": -4}), ("long_receipt", "ใบเสร็จยาวเหยียด", paper, (80, 300, "#fbfaf4", 12), {"zig": True, "total": True, "tilt": -2}),
    ("bill", "บิลค่าน้ำค่าไฟ", paper, (120, 160, "#f2f8f2", 5), {"title": "#2a7a4a", "total": True}), ("invoice", "ใบแจ้งหนี้", paper, (120, 160, "#fbfaf4", 6), {"title": "#c03030", "total": True}),
    ("contract", "สัญญา", paper, (120, 170, "#fbfaf4", 7), {"title": "#2a2a2e", "stamp": "#c02020"}), ("letter", "จดหมาย", paper, (120, 150, "#fbfaf4", 6), {}),
    ("envelope_red", "ซองแดงอั่งเปา", box, ("#d02020",), {"w": 70, "hh": 110, "label": "福"}), ("envelope_brown", "ซองน้ำตาล", box, ("#c8a064",), {"w": 140, "hh": 100}),
    ("photo", "รูปถ่าย", paper, (110, 90, "#ffffff", 0), {"photo": True, "tilt": -8}), ("polaroid", "รูปโพลารอยด์", paper, (90, 110, "#ffffff", 0), {"photo": True, "tilt": 6}),
    ("map", "แผนที่", paper, (170, 130, "#f2e8c8", 3), {"grid": True, "tilt": -2}), ("newspaper", "หนังสือพิมพ์", misc, ("newspaper",), {}), ("magazine", "นิตยสาร", misc, ("magazine",), {}),
    ("book", "หนังสือ", book, ("#8a3a3a",), {}), ("notebook", "สมุดจด", book, ("#2a5ad0",), {"rings": True, "spine": "#1a3a8a"}), ("diary", "ไดอารี่", book, ("#c0608a",), {"spine": "#8a3060"}),
    ("folder", "แฟ้มเอกสาร", book, ("#f2c020",), {"w": 130, "hh": 160, "spine": "#c89a10"}), ("clipboard", "คลิปบอร์ด", misc, ("clipboard",), {}),
    ("certificate", "ใบประกาศ", paper, (160, 120, "#f6eed0", 3), {"title": "#8a6a2a", "stamp": "#c02020", "tilt": -3}), ("passport", "พาสปอร์ต", book, ("#7a1a2a",), {"w": 80, "hh": 110, "spine": "#5a1020"}),
    ("land_deed", "โฉนดที่ดิน", paper, (150, 180, "#f6f2e0", 7), {"title": "#c02020", "stamp": "#c02020"}), ("ticket", "ตั๋ว", paper, (150, 60, "#f2e0c0", 2), {"title": "#c03030", "tilt": 8}),
    ("boarding_pass", "บอร์ดดิ้งพาส", paper, (160, 70, "#e8f0fc", 3), {"title": "#2a5ad0", "tilt": 4}), ("poster", "โปสเตอร์", paper, (150, 200, "#2a3a6a", 3), {"title": "#f2c020", "photo": True}),
    ("sticky_note", "กระดาษโน้ต", paper, (80, 80, "#f8f080", 3), {"tilt": 6}), ("prescription", "ใบสั่งยา", paper, (110, 140, "#f2fcfc", 5), {"title": "#2a8a8a"}),
    ("report_card", "สมุดพก", book, ("#3a8a5a",), {"spine": "#2a6a3a"}), ("evidence_bag", "ถุงหลักฐาน", misc, ("evidence",), {}), ("rolled_paper", "กระดาษม้วน", misc, ("rolledpaper",), {}),
    ("debt_notice", "หนังสือทวงหนี้", paper, (120, 160, "#fff4f4", 6), {"title": "#c02020", "stamp": "#c02020"}), ("will", "พินัยกรรม", paper, (130, 180, "#f6eed8", 8), {"title": "#2a2a2e", "stamp": "#c02020"}),
    ("lab_result", "ผลตรวจแล็บ", paper, (120, 160, "#ffffff", 6), {"title": "#2a8a8a", "grid": True}), ("menu", "เมนูอาหาร", book, ("#2a2a2e",), {"w": 110, "hh": 160, "spine": "#c8a040", "label": "MENU"}),
]:
    _add("document", key, th, fn, *a, **k)

for key, kind, th, k in [
    ("smartphone", "phone", "สมาร์ตโฟน", {}), ("cracked_phone", "cracked", "มือถือจอแตก", {}), ("old_phone", "phone", "มือถือปุ่มกด", {"col": "#5a5f6e", "screen": "#b8c8a8"}),
    ("tablet", "tablet", "แท็บเล็ต", {}), ("laptop", "laptop", "โน้ตบุ๊ก", {"col": "#8a8f98"}), ("camera", "camera", "กล้องถ่ายรูป", {}), ("video_camera", "vcam", "กล้องวิดีโอ", {}),
    ("microphone", "mic", "ไมโครโฟน", {}), ("remote", "remote", "รีโมท", {}), ("game_controller", "pad", "จอยเกม", {}), ("calculator", "calc", "เครื่องคิดเลข", {"col": "#3a3a40"}),
    ("radio", "radio", "วิทยุ", {"col": "#8a5a3a", "screen": "#e8d890"}), ("walkie_talkie", "walkie", "วิทยุสื่อสาร", {}), ("flashlight", "torch", "ไฟฉาย", {"col": "#2a2a2e"}),
    ("headphones", "headset", "หูฟัง", {}), ("speaker", "speaker", "ลำโพง", {}), ("drone", "drone", "โดรน", {"col": "#e8e8e8"}), ("usb", "usb", "แฟลชไดรฟ์", {}),
    ("power_bank", "bank", "พาวเวอร์แบงก์", {"col": "#f2f2f2"}), ("smartwatch", "watch", "สมาร์ตวอทช์", {}),
]:
    _add("electronic", key, th, device, kind, **k)

for key, kind, th in [("hammer", "hammer", "ค้อน"), ("wrench", "wrench", "ประแจ"), ("screwdriver", "screwdriver", "ไขควง"), ("saw", "saw", "เลื่อย"), ("drill", "drill", "สว่าน"),
                      ("pliers", "pliers", "คีม"), ("tape_measure", "tape", "ตลับเมตร"), ("paint_brush", "brush", "แปรงทาสี"), ("paint_roller", "roller", "ลูกกลิ้งทาสี"),
                      ("shovel", "shovel", "พลั่ว"), ("hoe", "hoe", "จอบ"), ("rake", "rake", "คราด"), ("broom", "broom", "ไม้กวาด"), ("mop", "mop", "ไม้ถูพื้น"),
                      ("bucket", "bucket", "ถังน้ำ"), ("watering_can", "watering", "บัวรดน้ำ"), ("axe", "axe", "ขวาน"), ("crowbar", "crowbar", "ชะแลง"), ("toolbox", "toolbox", "กล่องเครื่องมือ"),
                      ("key", "key", "กุญแจ"), ("keys", "keys", "พวงกุญแจ"), ("padlock", "padlock", "แม่กุญแจ"), ("rope", "rope", "เชือก"), ("chain", "chain", "โซ่"),
                      ("oil_can", "oilcan", "กระป๋องน้ำมันเครื่อง"), ("jerrycan", "jerry", "แกลลอนน้ำมัน"), ("ladder", "ladder", "บันได"), ("plug", "plug", "ปลั๊กไฟ"), ("tire", "tire", "ยางรถ"),
                      ("stick", "stick", "ไม้"), ("oar", "oar", "ไม้พาย")]:
    _add("tool", key, th, tool, kind)

for key, kind, th in [("spatula", "spatula", "ตะหลิว"), ("wok", "wok", "กระทะจีน"), ("frying_pan", "pan", "กระทะ"), ("pot", "pot", "หม้อ"), ("cutting_board", "board", "เขียง"),
                      ("rolling_pin", "rolling", "ไม้นวดแป้ง"), ("whisk", "whisk", "ตะกร้อตีไข่"), ("chopsticks", "chopsticks", "ตะเกียบ"), ("fork", "fork", "ส้อม"), ("spoon", "spoon", "ช้อน"),
                      ("tongs", "tongs", "ที่คีบ"), ("kettle", "kettle", "กาต้มน้ำ"), ("rice_cooker", "ricecooker", "หม้อหุงข้าว"), ("mortar", "mortar", "ครกสาก"), ("grater", "grater", "ที่ขูด"),
                      ("blender", "blender", "เครื่องปั่น"), ("oven_mitt", "mitt", "ถุงมือจับหม้อ"), ("tray", "tray", "ถาด"), ("thermos", "thermos", "กระติกน้ำ"), ("ladle2", "ladle2", "กระบวย"),
                      ("cleaver", "cleaver", "มีดปังตอ")]:
    _add("kitchen", key, th, kitchen, kind)

for key, th, fn, a, k in [
    ("bowl", "ชาม", bowl, (), {"food": "#f6f6f2"}), ("mug", "แก้วมัค", cup, (), {"handle": True, "steam": True}), ("water_glass", "แก้วน้ำ", cup, ("#d0e4f0", "#bfe0f8"), {"glass": True}),
    ("wine_glass", "แก้วไวน์", cup, ("#d0e4f0", "#8a1a30"), {"glass": True, "stem": True, "hh": 70, "w": 70}), ("beer_glass", "แก้วเบียร์", cup, ("#d0e4f0", "#e8b030"), {"glass": True, "handle": True}),
    ("tea_cup", "ถ้วยชา", cup, ("#f2f2ea", "#b07a3a"), {"hh": 50, "w": 64, "handle": True}), ("coffee_cup", "แก้วกาแฟกระดาษ", cup, ("#f6f2e6", None), {"lid": "#2a2a2e", "sleeve": "#a07a4a"}),
    ("bubble_tea", "ชานมไข่มุก", cup, ("#e8f4fc", "#d8b088"), {"glass": True, "boba": True, "lid": "#e8f4fc", "straw": "#e05a8a", "hh": 130}),
    ("iced_coffee", "กาแฟเย็น", cup, ("#e8f4fc", "#7a4a2a"), {"glass": True, "lid": "#e8f4fc", "straw": "#2a7a4a", "hh": 130}),
    ("water_bottle", "ขวดน้ำ", bottle, ("#bfe0f8",), {"cap": "#2a7ad0", "label": "#2a7ad0", "w": 48, "alpha": 170}),
    ("beer_bottle", "ขวดเบียร์", bottle, ("#5a3a10",), {"cap": "#d9b44a", "label": "#f2e7c9"}), ("whisky", "ขวดเหล้า", bottle, ("#a0601a",), {"shape": "flask", "cap": "#2a2a2e"}),
    ("wine_bottle", "ขวดไวน์", bottle, ("#3a1020",), {"cap": "#8a1a30", "label": "#f2e7c9", "hh": 220}), ("soy_sauce", "ซีอิ๊ว", bottle, ("#2a1a10",), {"cap": "#d02020", "label": "#f2c020", "hh": 160}),
    ("fish_sauce", "น้ำปลา", bottle, ("#a06a20",), {"cap": "#d02020", "label": "#ffffff", "hh": 170}), ("medicine_bottle", "ขวดยา", bottle, ("#6a3a10",), {"cap": "#ffffff", "label": "#ffffff", "hh": 110, "neck": 0.25}),
    ("poison", "ขวดยาพิษ", bottle, ("#3a6a2a",), {"cap": "#2a2a2e", "label": "#f2f2f2", "hh": 120, "shape": "round"}), ("soda_can", "น้ำอัดลมกระป๋อง", can, ("#c0392b",), {}),
    ("beer_can", "เบียร์กระป๋อง", can, ("#2a5ad0",), {"band": "#f2c020"}), ("energy_drink", "เครื่องดื่มชูกำลัง", bottle, ("#f2c020",), {"cap": "#d02020", "label": "#d02020", "hh": 120, "neck": 0.25}),
    ("milk_carton", "กล่องนม", box, ("#f2f2f2",), {"w": 60, "hh": 110, "lid": "#2a7ad0"}), ("juice_box", "น้ำผลไม้กล่อง", box, ("#f2a020",), {"w": 56, "hh": 90}),
    ("jar", "โหลแก้ว", cup, ("#d0e4f0", "#e8a030"), {"glass": True, "lid": "#d02020", "w": 80, "hh": 100}), ("plate", "จาน", plate, (), {}),
    ("water_bag", "ถุงน้ำดื่ม", food, ("waterbag",), {}), ("takeaway_box", "กล่องข้าว", food, ("takeaway",), {}), ("lunchbox", "ปิ่นโต", food, ("lunchbox",), {}),
]:
    _add("dish", key, th, fn, *a, **k)

for key, th, fn, a, k in [
    ("rice_plate", "ข้าวสวย", food, ("riceplate",), {}), ("fried_rice", "ข้าวผัด", food, ("friedrice",), {}), ("basil_rice", "กะเพราไข่ดาว", food, ("basil",), {}),
    ("papaya_salad", "ส้มตำ", food, ("somtam",), {}), ("grilled_chicken", "ไก่ย่าง", food, ("grilledchicken",), {}), ("noodle_bowl", "ก๋วยเตี๋ยว", food, ("noodle",), {}),
    ("tom_yum", "ต้มยำ", food, ("tomyum",), {}), ("congee", "โจ๊ก", food, ("congee",), {}), ("sticky_rice", "ข้าวเหนียว", food, ("stickyrice",), {}),
    ("moo_ping", "หมูปิ้ง", skewer, (("#9a5a2a",),), {}), ("meatball", "ลูกชิ้นปิ้ง", skewer, (("#b07a5a",),), {"n": 5, "r": 13}), ("satay", "สะเต๊ะ", skewer, (("#c8802a",),), {"n": 3, "r": 18}),
    ("banana", "กล้วย", fruit, ("#f2d040",), {"shape": "banana"}), ("apple", "แอปเปิ้ล", fruit, ("#d23a3a",), {}), ("orange", "ส้ม", fruit, ("#f08a20",), {}),
    ("watermelon", "แตงโมชิ้น", fruit, ("#f05a6a",), {"shape": "slice", "leaf": "#3a8a3a"}), ("mango", "มะม่วง", fruit, ("#f2c030",), {"shape": "oval", "leaf": "#4f8a3a"}),
    ("durian", "ทุเรียน", fruit, ("#8a9a3a",), {"r": 50, "spots": "#5a6a2a", "leaf": None}), ("pineapple", "สับปะรด", fruit, ("#e8b030",), {"shape": "long", "spots": "#a07a20"}),
    ("coconut", "มะพร้าว", fruit, ("#6a8a3a",), {"r": 48, "leaf": None}), ("grapes", "องุ่น", fruit, ("#7a3a9a",), {"r": 30, "spots": "#5a2a7a"}), ("lemon", "มะนาว", fruit, ("#9ad040",), {"r": 24}),
    ("egg", "ไข่", food, ("egg",), {}), ("fried_egg", "ไข่ดาว", food, ("friedegg",), {}), ("bread", "ขนมปัง", food, ("bread",), {}), ("sandwich", "แซนด์วิช", food, ("sandwich",), {}),
    ("burger", "เบอร์เกอร์", food, ("burger",), {}), ("pizza", "พิซซ่า", food, ("pizza",), {}), ("hotdog", "ฮอตดอก", food, ("hotdog",), {}), ("donut", "โดนัท", food, ("donut",), {}),
    ("cake", "เค้ก", food, ("cake",), {}), ("cupcake", "คัพเค้ก", food, ("cupcake",), {}), ("ice_cream", "ไอศกรีม", food, ("icecream",), {}), ("cookie", "คุกกี้", food, ("cookie",), {}),
    ("candy", "ลูกอม", food, ("candy",), {}), ("lollipop", "อมยิ้ม", food, ("lollipop",), {}), ("chocolate", "ช็อกโกแลต", food, ("chocolate",), {}), ("steak", "สเต๊ก", food, ("steak",), {}),
    ("sushi", "ซูชิ", food, ("sushi",), {}), ("dumpling", "ขนมจีบ", food, ("dumpling",), {}), ("crab", "ปู", food, ("crab",), {}), ("shrimp", "กุ้ง", food, ("shrimp",), {}),
    ("corn", "ข้าวโพด", food, ("corn",), {}), ("carrot", "แครอท", food, ("carrot",), {}), ("chili", "พริก", food, ("chili",), {}), ("popcorn", "ป๊อปคอร์น", food, ("popcorn",), {}),
    ("rice_sack", "กระสอบข้าวสาร", food, ("rice_sack",), {}),
]:
    _add("food", key, th, fn, *a, **k)

for key, kind, th, col in [("pen", "pen", "ปากกา", None), ("pencil", "pencil", "ดินสอ", None), ("marker", "marker", "ปากกาเมจิก", "#2a5ad0"), ("ruler", "ruler", "ไม้บรรทัด", None),
                           ("scissors", "scissors", "กรรไกร", None), ("stapler", "stapler", "แม็กเย็บกระดาษ", None), ("rubber_stamp", "rubberstamp", "ตรายาง", None), ("tape_roll", "tape_roll", "เทปใส", None),
                           ("glue", "glue", "กาว", None), ("files_stack", "files", "กองแฟ้ม", None), ("briefcase", "brief", "กระเป๋าเอกสาร", None)]:
    if kind == "brief":
        _add("office", key, th, bag, "#3a2a1a", 140, 100, "brief")
    else:
        _add("office", key, th, misc, kind, *((col,) if col else ()))

for key, kind, th, col in [("pill_bottle", "pills", "กระปุกยา", None), ("pill_strip", "pillstrip", "แผงยา", None), ("syringe", "syringe", "เข็มฉีดยา", None), ("thermometer", "thermometer", "ปรอทวัดไข้", None),
                           ("bandage", "bandage", "พลาสเตอร์ยา", None), ("face_mask", "mask", "หน้ากากอนามัย", None), ("stethoscope", "stethoscope", "หูฟังหมอ", None), ("lipstick", "lipstick", "ลิปสติก", None),
                           ("mirror", "mirror", "กระจกส่องหน้า", None), ("comb", "comb", "หวี", None), ("hairdryer", "hairdryer", "ไดร์เป่าผม", "#e070a0"), ("perfume", "perfume", "น้ำหอม", None),
                           ("nail_polish", "nailpolish", "ยาทาเล็บ", None)]:
    _add("health", key, th, misc, kind, *((col,) if col else ()))

for key, kind, th, col in [("football", "ball", "ลูกฟุตบอล", None), ("basketball", "basketball", "ลูกบาส", None), ("tennis_racket", "racket", "ไม้เทนนิส", "#d02020"),
                           ("badminton_racket", "badminton", "ไม้แบด", "#2a5ad0"), ("golf_club", "golf", "ไม้กอล์ฟ", "#c8ccd2"), ("baseball_bat", "bat", "ไม้เบสบอล", None),
                           ("dumbbell", "dumbbell", "ดัมเบล", None), ("jump_rope", "jumprope", "เชือกกระโดด", None), ("skateboard", "skateboard", "สเก็ตบอร์ด", "#e05a20"),
                           ("guitar", "guitar", "กีตาร์", None), ("ukulele", "ukulele", "อูคูเลเล่", None), ("violin", "violin", "ไวโอลิน", None), ("drum", "drum", "กลอง", None),
                           ("trophy", "trophy", "ถ้วยรางวัล", None), ("medal", "medal", "เหรียญรางวัล", None), ("teddy_bear", "teddy", "ตุ๊กตาหมี", None), ("balloon", "balloon", "ลูกโป่ง", "#e04a6a"),
                           ("kite", "kite", "ว่าว", "#e05a20"), ("toy_car", "toycar", "รถของเล่น", "#2a7ad0"), ("rubik", "rubik", "รูบิก", None), ("dice", "dice", "ลูกเต๋า", None),
                           ("playing_cards", "cards", "ไพ่", None), ("crystal_ball", "crystalball", "ลูกแก้วหมอดู", None)]:
    if kind in ("racket", "badminton", "golf", "bat"):
        _add("sport", key, th, tool, kind, *((col,) if col else ()))
    else:
        _add("sport", key, th, misc, kind, *((col,) if col else ()))

for key, kind, th, col in [("umbrella", "umbrella", "ร่ม", "#2a5ad0"), ("flowers", "flowers", "ช่อดอกไม้", None), ("rose", "rose", "กุหลาบ", None), ("candle", "candle", "เทียน", None),
                           ("lantern", "lantern", "โคมไฟจีน", None), ("incense", "incense", "ธูป", None), ("garland", "garland", "พวงมาลัย", None), ("amulet", "amulet", "พระเครื่อง", None),
                           ("photo_frame", "frame", "กรอบรูป", None), ("ring_box", "ringbox", "กล่องแหวน", None), ("suitcase", "suitcase", "กระเป๋าเดินทาง", "#3a5a8a"),
                           ("backpack", "backpack", "กระเป๋าเป้", "#d04a3a"), ("handbag", "handbag", "กระเป๋าถือแบรนด์เนม", "#8a5a3a"), ("pillow", "pillow", "หมอน", None),
                           ("blanket", "blanket", "ผ้าห่ม", "#5a7ab0"), ("towel", "towel", "ผ้าขนหนู", "#e07a9a"), ("hand_fan", "handfan", "พัด", "#d02040"), ("tissue_box", "tissue", "กล่องทิชชู่", None),
                           ("toilet_paper", "toiletpaper", "ทิชชู่ม้วน", None), ("soap", "soap", "สบู่", None), ("trash_bag", "trashbag", "ถุงขยะ", None), ("sign_board", "sign", "ป้ายประท้วง", None),
                           ("megaphone", "megaphone", "โทรโข่ง", None), ("whistle", "whistle", "นกหวีด", None), ("binoculars", "binoculars", "กล้องส่องทางไกล", None),
                           ("magnifier", "magnifier", "แว่นขยาย", None), ("gift_box", "giftbox", "กล่องของขวัญ", None), ("parcel", "parcel", "กล่องพัสดุ", None), ("shoe_box", "shoebox", "กล่องรองเท้า", None),
                           ("slipper", "slipper", "รองเท้าแตะ", None), ("lighter", "lighter", "ไฟแช็ก", "#d02020"), ("laundry_basket", "laundry", "ตะกร้าผ้า", None), ("flag", "flag", "ธงชาติ", None)]:
    _add("misc", key, th, misc, kind, *((col,) if col else ()))

for key, th, a, k in [("shopping_bag", "ถุงช้อปปิ้ง", ("#e05a8a",), {"kind": "shop"}), ("plastic_bag", "ถุงพลาสติก", ("#f2f2f2",), {"kind": "plastic"}),
                      ("tote_bag", "ถุงผ้า", ("#d8d4c8",), {}), ("sack", "กระสอบ", ("#d8c89a",), {"kind": "sack", "w": 120, "hh": 150}),
                      ("cash_bag", "ถุงกระดาษใส่เงิน", ("#c8a064",), {"kind": "plastic"})]:
    _add("misc", key, th, bag, *a, **k)

for cat, key, kind, th, k in [
    ("food", "instant_noodle", "noodle_cup", "บะหมี่ถ้วย", {}), ("food", "canned_fish", None, "ปลากระป๋อง", {}), ("survival", "first_aid_kit", "aid_kit", "กล่องปฐมพยาบาล", {}),
    ("survival", "fire_extinguisher", "extinguisher", "ถังดับเพลิง", {}), ("survival", "gas_mask", "gas_mask", "หน้ากากกันแก๊ส", {}),
    ("survival", "flare", "flare", "พลุไฟสัญญาณ", {}), ("survival", "car_battery", "car_battery", "แบตเตอรี่รถ", {}),
    ("survival", "water_jug", "water_jug", "แกลลอนน้ำดื่ม", {}), ("tool", "spray_can", "spray_can", "สีสเปรย์", {"col": "#2a8ad0"}),
    ("survival", "iron_pipe", "pipe", "ท่อเหล็ก", {}), ("survival", "plank", "plank", "ไม้กระดาน", {}),
    ("survival", "generator", "generator", "เครื่องปั่นไฟ", {}), ("money", "qr_stand", "qr_stand", "ป้าย QR จ่ายเงิน", {}),
    ("money", "price_tag", "price_tag", "ป้ายราคา", {"col": "#d02a2a"}), ("money", "sale_sign", "sale_sign", "ป้ายลดราคา", {"col": "#d02a2a"}),
    ("document", "growth_chart", "growth_chart", "กราฟยอดขายพุ่ง", {}), ("misc", "service_bell", "service_bell", "กระดิ่งเคาน์เตอร์", {}),
    ("misc", "name_badge", "name_badge", "ป้ายชื่อพนักงาน", {"col": "#1f3f7a"}), ("dish", "champagne", None, "แชมเปญ", {}),
    ("dish", "cloche", "cloche", "ฝาครอบอาหารเงิน", {}), ("misc", "room_key", "room_key", "กุญแจห้องโรงแรม", {"col": "#8a2a3a"}),
    ("survival", "baton", "baton", "กระบองยาม", {}), ("misc", "moto_helmet", "helmet", "หมวกกันน็อก", {"col": "#2a2a2e"}),
    ("misc", "delivery_box", "delivery_box", "กล่องส่งอาหาร", {"col": "#e0602a"}),
    ("survival", "canteen", "canteen", "กระติกน้ำทหาร", {}), ("survival", "solar_panel", "solar_panel", "แผงโซลาร์พกพา", {}),
    ("survival", "water_filter", "water_filter", "เครื่องกรองน้ำพกพา", {}), ("survival", "dead_plant", "dead_plant", "ต้นไม้เหี่ยวตาย", {}),
    ("survival", "crushed_bottle", "crushed_bottle", "ขวดน้ำเปล่ายับ", {}), ("survival", "firewood", "firewood", "มัดฟืน", {}),
    ("survival", "ice_axe", "ice_axe", "ขวานน้ำแข็ง", {}), ("survival", "gas_heater", "gas_heater", "ฮีตเตอร์แก๊ส", {}),
    ("survival", "toxic_barrel", "toxic_barrel", "ถังสารพิษ", {}), ("survival", "antidote", "vial", "หลอดยาแก้พิษ", {"col": "#40c0e0"}),
    ("survival", "toxic_vial", "vial", "หลอดสารพิษเขียว", {"col": "#7ad040"}), ("survival", "oxygen_tank", "oxygen_tank", "ถังออกซิเจน", {}),
    ("survival", "hazard_sign", "hazard_sign", "ป้ายเตือนอันตราย", {}), ("survival", "radiation_sign", "rad_sign", "ป้ายเตือนรังสี", {}),
    ("survival", "geiger_counter", "geiger", "เครื่องวัดรังสี", {}), ("survival", "iodine_pills", "pill_box", "ยาเม็ดไอโอดีน", {"col": "#2a6ad0"}),
    ("survival", "lead_box", "lead_box", "กล่องตะกั่วเก็บของมีรังสี", {}), ("survival", "ration_pack", "ration", "อาหารยังชีพ", {}),
    ("survival", "seed_pack", "seed_pack", "ซองเมล็ดพันธุ์", {}), ("survival", "compass", "compass", "เข็มทิศ", {}),
]:
    if kind:
        _add(cat, key, th, gear, kind, **k)
    elif key == "canned_fish":
        _add(cat, key, th, can, "#d03a2a", "#f2e2a0", 70, 84)
    else:
        _add(cat, key, th, bottle, "#1f4a2a", "#d9b44a", "#f2e2a0", hh=210, w=56, neck=0.36)

CATS = {"money": "เงินและบัตร", "document": "เอกสาร", "electronic": "อุปกรณ์ไฟฟ้า", "tool": "เครื่องมือช่าง/ทำสวน", "kitchen": "เครื่องครัว",
        "dish": "ภาชนะ/เครื่องดื่ม", "food": "อาหาร", "office": "เครื่องเขียน", "health": "ยา/ความงาม", "sport": "กีฬา/ของเล่น/ดนตรี", "misc": "ของใช้/ของขวัญ/อื่นๆ",
        "survival": "เอาชีวิตรอด/ฉุกเฉิน"}
TH = {k: v[1] for k, v in ITEMS.items()}


def _rotpen(pen, c, deg):
    base = type(pen)
    cls = type("RotPen", (base,), {"P": lambda self, pt: base.P(self, rot([pt], c, deg)[0])})
    rp = cls.__new__(cls)
    rp.__dict__ = pen.__dict__
    return rp


def draw(pen, key, h, turn=0):
    it = ITEMS.get(key)
    if not it:
        return False
    _, _, fn, a, k = it
    fn(_rotpen(pen, h, turn) if turn else pen, h, *a, **k)
    return True


def by_cat():
    out = {}
    for k, v in ITEMS.items():
        out.setdefault(v[0], []).append(k)
    return out
