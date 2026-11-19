import math
import random

from PIL import Image, ImageDraw

SS = 2
INK = (17, 17, 19, 255)
OUT = 9.0
KINDS = ("sedan", "pickup", "van", "motorbike", "saleng")
CONDS = ("good", "old", "wreck")
ACTIONS = ("park", "drive_in", "drive_out", "pass", "hood_open", "ride")
KIND_TH = {"sedan": "รถเก๋ง", "pickup": "กระบะ", "van": "รถตู้", "motorbike": "มอเตอร์ไซค์", "saleng": "ซาเล้ง"}
COND_TH = {"good": "สภาพดี", "old": "เก่า", "wreck": "เละ"}
SIZE = {"sedan": (1180, 560), "pickup": (1260, 600), "van": (1220, 700), "motorbike": (640, 520), "saleng": (900, 560)}
WHEEL = {"sedan": 118, "pickup": 126, "van": 120, "motorbike": 92, "saleng": 92}


def _rgb(c, dv=(176, 64, 52)):
    c = str(c or "").lstrip("#")
    try:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except Exception:
        return dv


def _mix(a, b, w):
    return tuple(int(a[i] + (b[i] - a[i]) * w) for i in range(3))


def _rot(p, c, deg):
    a = math.radians(deg)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(a) - y * math.sin(a), c[1] + x * math.sin(a) + y * math.cos(a))


def _round(pts, r, n=5):
    out = []
    m = len(pts)
    for i in range(m):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % m]
        d1 = math.dist(p0, p1) or 1
        d2 = math.dist(p1, p2) or 1
        rr = min(r, d1 / 2.2, d2 / 2.2)
        a = (p1[0] + (p0[0] - p1[0]) * rr / d1, p1[1] + (p0[1] - p1[1]) * rr / d1)
        b = (p1[0] + (p2[0] - p1[0]) * rr / d2, p1[1] + (p2[1] - p1[1]) * rr / d2)
        for k in range(n + 1):
            u = k / n
            out.append(((1 - u) ** 2 * a[0] + 2 * (1 - u) * u * p1[0] + u * u * b[0], (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * p1[1] + u * u * b[1]))
    return out


class Canvas:
    def __init__(self, w_units, h_units, scale):
        self.k = scale * SS
        self.x0, self.y0 = -w_units / 2, -h_units
        self.w, self.h = int(w_units * self.k), int((h_units + 40) * self.k)
        self.im = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def P(self, p):
        return ((p[0] - self.x0) * self.k, (p[1] - self.y0) * self.k)

    def poly(self, pts, fill, w=OUT, col=INK):
        q = [self.P(p) for p in pts]
        self.d.polygon(q, fill=fill)
        if w:
            self.line(pts + [pts[0]], w, col)

    def line(self, pts, w, col=INK):
        q = [self.P(p) for p in pts]
        ww = max(1, int(w * self.k))
        self.d.line(q, fill=col, width=ww, joint="curve")
        for p in (q[0], q[-1]):
            r = ww / 2
            self.d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col)

    def circle(self, c, r, fill, w=OUT, col=INK, ry=None):
        c = self.P(c)
        rx, ry = r * self.k, (ry if ry is not None else r) * self.k
        self.d.ellipse([c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry], fill=fill, outline=col if w else None, width=max(1, int(w * self.k)) if w else 0)

    def done(self, flip):
        im = self.im.convert("RGBa").resize((self.w // SS, self.h // SS), Image.BOX).convert("RGBA")
        ax = (0 - self.x0) * self.k / SS
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
            ax = im.width - ax
        return im, (ax, (0 - self.y0) * self.k / SS)


def wheel(cv, c, r, ang, cond, rng):
    flat = cond == "wreck" and rng.random() < 0.5
    cv.circle((c[0], c[1] + (8 if flat else 0)), r, (34, 34, 38, 255), ry=r * (0.86 if flat else 1.0))
    rim = (196, 200, 208, 255) if cond == "good" else ((150, 140, 128, 255) if cond == "old" else (120, 92, 70, 255))
    cv.circle(c, r * 0.56, rim, w=5)
    for k in range(5):
        a = ang + k * 2 * math.pi / 5
        cv.line([c, (c[0] + math.cos(a) * r * 0.48, c[1] + math.sin(a) * r * 0.48)], 6, (90, 92, 98, 255) if cond != "wreck" else (80, 60, 46, 255))
    cv.circle(c, r * 0.14, (70, 72, 78, 255), w=4)
    if cond == "good":
        cv.line([(c[0] - r * 0.3, c[1] - r * 0.38), (c[0] - r * 0.05, c[1] - r * 0.5)], 5, (255, 255, 255, 170))


def _windows(cv, pts, cond, rng, tint=(150, 196, 226, 255)):
    if cond == "wreck":
        tint = (124, 150, 160, 255)
    elif cond == "old":
        tint = (138, 170, 186, 255)
    cv.poly(pts, tint, w=6)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if cond == "good":
        x, y = min(xs) + (max(xs) - min(xs)) * 0.25, min(ys) + (max(ys) - min(ys)) * 0.2
        cv.line([(x, y + 60), (x + 50, y)], 9, (235, 246, 255, 200))
    if cond == "wreck":
        cx, cy = min(xs) + (max(xs) - min(xs)) * rng.uniform(0.3, 0.7), min(ys) + (max(ys) - min(ys)) * 0.5
        for k in range(6):
            a = k * math.pi / 3 + rng.uniform(-0.3, 0.3)
            ln = rng.uniform(30, 70)
            cv.line([(cx, cy), (cx + math.cos(a) * ln, cy + math.sin(a) * ln * 0.7)], 3, (240, 245, 250, 230))
        if rng.random() < 0.6:
            cv.line([(min(xs) + 20, min(ys) + 18), (max(xs) - 20, max(ys) - 12)], 14, (214, 200, 150, 235))


def _rust(cv, x, y, s, rng, col=(128, 70, 38, 255)):
    pts = []
    for k in range(9):
        a = k * 2 * math.pi / 9
        rr = s * rng.uniform(0.55, 1.0)
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr * 0.7))
    cv.poly(pts, col, w=0)
    for k in range(3):
        cv.circle((x + rng.uniform(-s, s), y + rng.uniform(-s, s) * 0.6), s * 0.18, (96, 50, 26, 255), w=0)


def _dent(cv, x, y, s, base):
    cv.circle((x, y), s, _mix(base, (0, 0, 0), 0.25) + (255,), w=0, ry=s * 0.6)
    cv.line([(x - s * 0.7, y - s * 0.35), (x + s * 0.5, y - s * 0.5)], 4, _mix(base, (255, 255, 255), 0.4) + (255,))


def _smoke(cv, x, y, t, dirn):
    for k in range(4):
        u = (t * 1.3 + k * 0.25) % 1.0
        r = 22 + 60 * u
        cv.circle((x - dirn * (40 + 220 * u), y - 30 - 90 * u), r, (120, 120, 124, int(170 * (1 - u))), w=0)


def car(kind, color, cond, scale, ang, t, hood=False, seed=0, moving=False):
    rng = random.Random(seed)
    L, Hh = SIZE[kind]
    cv = Canvas(L + 520, Hh + 260, scale)
    base = _rgb(color)
    if cond == "old":
        base = _mix(base, (150, 140, 128), 0.35)
    elif cond == "wreck":
        base = _mix(base, (120, 100, 84), 0.3)
    body = base + (255,)
    r = WHEEL[kind]
    wy = -r
    hl, hr = -L / 2, L / 2
    bounce = (3 * math.sin(t * 20) if moving else 0) + (5 * math.sin(t * 31) if moving and cond == "wreck" else 0)
    tilt = (-2.5 if cond == "wreck" and rng.random() < 0.5 else 0)
    if kind == "sedan":
        lower = [(hl, -100), (hl, -270), (hl + 70, -300), (hr - 90, -300), (hr, -250), (hr, -100)]
        cab = [(hl + 230, -300), (hl + 390, -500), (hr - 400, -500), (hr - 230, -300)]
        wins = [[(hl + 270, -310), (hl + 400, -470), (-10, -470), (-10, -310)], [(10, -310), (10, -470), (hr - 410, -470), (hr - 270, -310)]]
        wpos = [hl + 250, hr - 250]
    elif kind == "pickup":
        lower = [(hl, -110), (hl, -300), (hl + 40, -320), (hr - 80, -320), (hr, -270), (hr, -110)]
        cab = [(hl + 520, -320), (hl + 570, -560), (hr - 330, -560), (hr - 180, -320)]
        wins = [[(hl + 590, -340), (hl + 620, -530), (hr - 350, -530), (hr - 220, -340)]]
        wpos = [hl + 270, hr - 250]
    else:
        lower = [(hl, -110), (hl, -620), (hl + 40, -650), (hr - 300, -650), (hr - 60, -400), (hr, -330), (hr, -110)]
        cab = []
        wins = [[(hl + 60, -420), (hl + 60, -600), (hl + 380, -600), (hl + 380, -420)], [(hl + 420, -420), (hl + 420, -600), (hr - 320, -600), (hr - 320, -420)],
                [(hr - 290, -420), (hr - 290, -600), (hr - 120, -420)]]
        wpos = [hl + 260, hr - 250]
    off = (0, bounce)
    sh = lambda pts: [_rot((p[0] + off[0], p[1] + off[1]), (0, -200), tilt) for p in pts]
    for x in wpos:
        cv.circle((x, wy + 10), r * 1.12, (22, 22, 24, 255), w=0, ry=r * 0.9)
    if cab:
        cv.poly(sh(_round(cab, 60)), body)
    cv.poly(sh(_round(lower, 50)), body)
    if kind == "pickup":
        cv.line(sh([(hl + 20, -300), (hl + 500, -300)]), 8, _mix(base, (0, 0, 0), 0.35) + (255,))
    for w in wins:
        _windows(cv, sh(w), cond, rng)
    door = sh([(hl + 440, -310), (hl + 440, -130)]) if kind != "van" else sh([(hl + 400, -400), (hl + 400, -130)])
    cv.line(door, 5, _mix(base, (0, 0, 0), 0.4) + (255,))
    cv.line(sh([(hl + 470, -260), (hl + 530, -260)]), 9, (60, 60, 64, 255))
    cv.poly(sh(_round([(hr - 50, -270), (hr + 6, -268), (hr + 6, -205), (hr - 50, -210)], 16)), (255, 236, 150, 255) if cond != "wreck" else (190, 180, 140, 255), w=5)
    cv.poly(sh([(hl - 6, -270), (hl + 30, -270), (hl + 30, -205), (hl - 6, -205)]), (210, 50, 44, 255), w=5)
    bum = sh(_round([(hr - 30, -150), (hr + 30, -150), (hr + 30, -100), (hr - 30, -100)], 14))
    cv.poly(bum, (70, 72, 78, 255) if cond != "good" else (190, 194, 200, 255), w=5)
    rb = [(hl - 30, -150), (hl + 30, -150), (hl + 30, -100), (hl - 30, -100)]
    if cond == "wreck":
        rb = [_rot(p, (hl + 30, -150), 24) for p in rb]
    cv.poly(sh(_round(rb, 14)), (70, 72, 78, 255), w=5)
    if cond == "good":
        cv.line(sh([(hl + 60, -250), (hr - 120, -250)]), 10, _mix(base, (255, 255, 255), 0.45) + (200,))
    if cond in ("old", "wreck"):
        for k in range(2 if cond == "old" else 5):
            _rust(cv, *sh([(rng.uniform(hl + 80, hr - 80), rng.uniform(-260, -140))])[0], rng.uniform(22, 48), rng)
    if cond == "wreck":
        _dent(cv, *sh([(rng.uniform(hl + 120, hr - 160), -220)])[0], 70, base)
        _dent(cv, *sh([(rng.uniform(hl + 120, hr - 160), -170)])[0], 50, base)
        pd = sh([(hl + 440, -300), (hl + 440, -130), (hl + 700 if kind != "van" else hl + 680, -130), (hl + 700 if kind != "van" else hl + 680, -300)])
        cv.poly(pd, (150, 152, 150, 255), w=5)
        cv.line(sh([(hr - 220, -310), (hr - 120, -220)]), 12, (214, 200, 150, 235))
        cv.line(sh([(hr - 140, -310), (hr - 200, -230)]), 12, (214, 200, 150, 235))
    if hood and kind in ("sedan", "pickup"):
        hx0 = hr - (230 if kind == "sedan" else 180)
        hp = [(hx0, -310), (hr - 10, -300)]
        hp = [_rot(p, (hx0, -310), -48) for p in hp]
        cv.line(sh([hp[0], hp[1]]), 26, body)
        cv.line(sh([hp[0], hp[1]]), 6)
        cv.circle(sh([(hr - 120, -330)])[0], 46, (60, 60, 66, 255), w=5, ry=24)
    for x in wpos:
        wheel(cv, (x, wy), r, ang + x * 0.01, cond, rng)
    if cond == "wreck" and moving:
        _smoke(cv, *sh([(hl - 10, -120)])[0], t, 1)
    return cv, (hl + 120, -400)


def bike(kind, color, cond, scale, ang, t, seed=0, moving=False, layer="all"):
    rng = random.Random(seed)
    L, Hh = SIZE[kind]
    cv = Canvas(L + 640, Hh + 300, scale)
    base = _rgb(color, (44, 96, 170))
    if cond == "old":
        base = _mix(base, (150, 140, 128), 0.35)
    elif cond == "wreck":
        base = _mix(base, (120, 100, 84), 0.35)
    body = base + (255,)
    r = WHEEL[kind]
    bounce = (2.5 * math.sin(t * 22) if moving else 0) + (4 * math.sin(t * 33) if moving and cond == "wreck" else 0)
    sh = lambda pts: [(p[0], p[1] + bounce) for p in pts]
    fx, bx = 230, -230
    if kind == "saleng" and layer != "front":
        lift = -46
        cx0, cx1 = bx - 90, fx - 30
        cv.circle((-20, -r * 0.85 + lift), r * 0.85, (34, 34, 38, 255), w=OUT)
        cv.circle((-20, -r * 0.85 + lift), r * 0.45, (110, 112, 118, 255), w=4)
        deck = (110, 112, 118, 255) if cond == "good" else ((128, 120, 108, 255) if cond == "old" else (118, 86, 58, 255))
        rail = (80, 82, 88, 255) if cond == "good" else ((110, 96, 80, 255) if cond == "old" else (126, 78, 44, 255))
        top = -300 + lift
        cv.poly(sh([(cx0, top + 70), (cx1, top + 70), (cx1, top), (cx0, top)]), deck, w=7)
        piles = [((132, 100, 70), cx0 + 10, 150, 140), ((214, 196, 150), cx0 + 140, 130, 190), ((238, 238, 232), cx0 + 250, 110, 120), ((70, 120, 170), cx0 + 330, 100, 90)]
        if cond == "good":
            piles = piles[:2]
        elif cond == "wreck":
            piles += [((90, 70, 50), cx0 + 60, 120, 230), ((180, 60, 50), cx0 + 200, 90, 260)]
        for col, x, w_, h_ in piles:
            cv.poly(sh(_round([(x, top), (x - 6, top - h_), (x + w_ * 0.6, top - h_ - rng.uniform(0, 20)), (x + w_, top - h_ * 0.85), (x + w_, top)], 22)), col + (255,), w=6)
        for x in range(int(cx0), int(cx1) + 1, 120):
            cv.line(sh([(x, top), (x, top - 120)]), 7, rail)
        cv.line(sh([(cx0, top - 120), (cx1, top - 120)]), 8, rail)
        if cond == "wreck":
            _rust(cv, *sh([(cx0 + 120, top + 35)])[0], 30, rng)
            cv.line(sh([(cx1 - 40, top - 120), (cx1 + 30, top - 60)]), 8, rail)
    if layer == "back":
        return cv, sh([(-40, -380)])[0]
    cv.line(sh([(fx, -r), (fx - 70, -420)]), 14, (70, 72, 78, 255))
    shell = [(bx - 40, -230), (bx + 10, -330), (40, -330), (90, -230), (170, -230), (fx - 50, -440), (fx - 10, -460), (fx + 30, -360), (fx - 10, -230), (60, -150), (bx + 10, -150)]
    cv.poly(sh(_round(shell, 40)), body)
    cv.poly(sh(_round([(bx - 30, -330), (bx - 10, -380), (70, -380), (90, -330)], 26)), (34, 34, 38, 255), w=7)
    cv.line(sh([(fx - 90, -470), (fx - 20, -480)]), 12)
    cv.poly(sh(_round([(fx + 4, -410), (fx + 40, -405), (fx + 36, -360), (fx + 4, -365)], 10)), (255, 236, 150, 255) if cond != "wreck" else (180, 170, 130, 255), w=5)
    cv.line(sh([(fx - 60, -480), (fx - 40, -540)]), 6)
    cv.circle(sh([(fx - 40, -555)])[0], 18, (190, 200, 210, 255) if cond != "wreck" else (90, 90, 90, 255), w=5)
    cv.line(sh([(bx - 30, -200), (bx - 120, -190)]), 14, (120, 124, 130, 255))
    if cond == "good":
        cv.line(sh([(bx + 40, -300), (50, -300)]), 8, _mix(base, (255, 255, 255), 0.5) + (210,))
    if cond in ("old", "wreck"):
        for k in range(1 if cond == "old" else 3):
            _rust(cv, *sh([(rng.uniform(bx + 20, 100), rng.uniform(-300, -190))])[0], rng.uniform(16, 30), rng)
    if cond == "wreck":
        cv.line(sh([(bx + 10, -360), (60, -350)]), 16, (214, 200, 150, 235))
        cv.poly(sh([(20, -230), (110, -230), (80, -170), (30, -170)]), (60, 62, 66, 255), w=5)
        if moving:
            _smoke(cv, *sh([(bx - 120, -190)])[0], t, 1)
    for x in (bx, fx):
        wheel(cv, (x, -r), r, ang, cond, rng)
    seat = sh([(-40, -380)])[0]
    return cv, seat


def draw(kind, color="#b0403a", cond="good", scale=1.0, dist=0.0, t=0.0, hood=False, seed=0, moving=False, flip=False, layer="all"):
    kind = kind if kind in KINDS else "sedan"
    cond = cond if cond in CONDS else "good"
    ang = dist / max(1, WHEEL[kind])
    if kind in ("motorbike", "saleng"):
        cv, seat = bike(kind, color, cond, scale, ang, t, seed, moving, layer)
    else:
        cv, seat = car(kind, color, cond, scale, ang, t, hood, seed, moving)
    im, anchor = cv.done(flip)
    sx = (seat[0] - cv.x0) * cv.k / SS
    if flip:
        sx = im.width - sx
    return im, anchor, (sx, (seat[1] - cv.y0) * cv.k / SS)


def path_x(action, u, target, w, start_side=None):
    e = lambda v: 1 - (1 - max(0.0, min(1.0, v))) ** 3
    side = start_side or ("left" if target >= w / 2 else "right")
    off = -w * 0.75 if side == "left" else w * 1.75
    if action == "drive_in":
        return off + (target - off) * e(u / 0.6), u < 0.6
    if action == "drive_out":
        far = w * 1.75 if target >= w / 2 else -w * 0.75
        v = max(0.0, (u - 0.3) / 0.7)
        return target + (far - target) * v * v, u > 0.3
    if action == "pass":
        a, b = (-w * 0.75, w * 1.75) if side == "left" else (w * 1.75, -w * 0.75)
        return a + (b - a) * u, True
    if action == "ride":
        return target, True
    return target, False
