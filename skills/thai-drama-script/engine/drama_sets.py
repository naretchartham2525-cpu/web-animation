import math

import cv2
import numpy as np

W, H = 1350, 2400


def rng(seed):
    return np.random.default_rng(seed)


def noise(h, w, seed, scale=64, octaves=4):
    r = rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        s = max(2, int(scale / (2 ** o)))
        g = r.random((h // s + 2, w // s + 2)).astype(np.float32)
        out += cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC) * amp
        tot += amp
        amp *= 0.5
    return np.clip(out / tot, 0, 1)


def col(c):
    c = c.lstrip("#")
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def tex_concrete(w, h, base, seed, stains=0.35, cracks=6):
    n = noise(h, w, seed, 40)
    f = noise(h, w, seed + 1, 6, 2)
    t = col(base)[None, None] * (0.86 + 0.18 * n[..., None] + 0.14 * (f[..., None] - 0.5))
    st = np.clip((noise(h, w, seed + 2, 120, 3) - 0.6) * 4, 0, 1)
    t *= 1 - stains * st[..., None]
    r = rng(seed + 3)
    for _ in range(cracks):
        x, y = r.uniform(0, w), r.uniform(0, h)
        pts = []
        for k in range(8):
            x += r.uniform(-30, 30)
            y += r.uniform(10, 50)
            pts.append((int(x), int(y)))
        cv2.polylines(t, [np.int32(pts)], False, (col(base) * 0.45).tolist(), 2, cv2.LINE_AA)
    return t


def tex_ribs(w, h, base, seed, step=26, vertical=False, dirt=0.4):
    t = np.zeros((h, w, 3), np.float32) + col(base)
    a = np.arange(w if vertical else h, dtype=np.float32)
    band = 0.82 + 0.25 * (0.5 + 0.5 * np.sin(a / step * 2 * math.pi)) ** 3
    t *= (band[None, :, None] if vertical else band[:, None, None])
    n = noise(h, w, seed, 120)
    streak = noise(h, w, seed + 1, 40, 2)
    if not vertical:
        streak = cv2.resize(noise(h // 8 + 1, w, seed + 2, 30, 2), (w, h))
    t *= (1 - dirt * np.clip(n - 0.4, 0, 1)[..., None]) * (0.92 + 0.1 * streak[..., None])
    return t


def tex_tiles(w, h, base, base2, seed, size=90, grout="#3a3a3a"):
    t = np.zeros((h, w, 3), np.float32)
    r = rng(seed)
    for y in range(0, h, size):
        for x in range(0, w, size):
            c = col(base if ((x // size + y // size) % 2 == 0) else base2) * r.uniform(0.9, 1.08)
            t[y:y + size, x:x + size] = c
    g = col(grout)
    for y in range(0, h, size):
        t[y:y + 3] = g
    for x in range(0, w, size):
        t[:, x:x + 3] = g
    t *= (0.85 + 0.25 * noise(h, w, seed + 1, 80))[..., None]
    return t


def tex_plaster(w, h, top, bottom, seed, split=0.55):
    t = tex_concrete(w, h, top, seed, 0.45, 3)
    b = tex_concrete(w, h, bottom, seed + 9, 0.3, 2)
    m = np.zeros((h, w), np.float32)
    edge = (split + 0.02 * (noise(1, w, seed + 4, 30, 2)[0] - 0.5)) * h
    m[np.arange(h)[:, None] > edge[None, :]] = 1
    m = cv2.GaussianBlur(m, (0, 0), 2)[..., None]
    t = t * (1 - m) + b * m
    peel = np.clip((noise(h, w, seed + 5, 60, 3) - 0.68) * 6, 0, 1)[..., None]
    return t * (1 - 0.35 * peel)


def tex_wood(w, h, base, seed, plank=70):
    t = np.zeros((h, w, 3), np.float32) + col(base)
    grain = noise(h, w * 1, seed, 8, 2)
    grain = cv2.resize(cv2.resize(grain, (w // 12 + 1, h)), (w, h))
    t *= (0.8 + 0.3 * grain[..., None])
    for y in range(0, h, plank):
        t[y:y + 3] *= 0.5
    return t


def warp(canvas, mask, tex, quad):
    h, w = tex.shape[:2]
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), np.float32(quad))
    t = cv2.warpPerspective(tex, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    m = cv2.warpPerspective(np.ones((h, w), np.float32), M, (W, H), flags=cv2.INTER_LINEAR)
    canvas[:] = canvas * (1 - m[..., None]) + t * m[..., None]
    mask[:] = np.maximum(mask, m)
    return M


def poly(canvas, pts, c, alpha=1.0, blur=0):
    m = np.zeros((H, W), np.float32)
    cv2.fillPoly(m, [np.int32(pts)], 1.0, cv2.LINE_AA)
    if blur:
        m = cv2.GaussianBlur(m, (0, 0), blur)
    m = m[..., None] * alpha
    canvas[:] = canvas * (1 - m) + col(c) * m if isinstance(c, str) else canvas * (1 - m) + np.float32(c) * m


def ellipse(canvas, c, axes, color, alpha=1.0, blur=0, angle=0, a0=0, a1=360):
    m = np.zeros((H, W), np.float32)
    cv2.ellipse(m, (int(c[0]), int(c[1])), (int(axes[0]), int(axes[1])), angle, a0, a1, 1.0, -1, cv2.LINE_AA)
    if blur:
        m = cv2.GaussianBlur(m, (0, 0), blur)
    m = m[..., None] * alpha
    canvas[:] = canvas * (1 - m) + col(color) * m


def glow(light, c, r, strength, color="#ffd9a0"):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    g = np.exp(-((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / (2 * r * r)) * strength
    light += g[..., None] * (col(color) / 255.0)


def cone(light, top, w0, w1, bottom_y, strength, color="#ffe6b0"):
    m = np.zeros((H, W), np.float32)
    cv2.fillPoly(m, [np.int32([(top[0] - w0, top[1]), (top[0] + w0, top[1]), (top[0] + w1, bottom_y), (top[0] - w1, bottom_y)])], 1.0)
    m = cv2.GaussianBlur(m, (0, 0), 40)
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    fade = np.clip(1 - (yy * H - top[1]) / max(1, bottom_y - top[1]), 0, 1) ** 0.7
    light += (m * fade * strength)[..., None] * (col(color) / 255.0)


def cyl(canvas, x0, x1, y0, y1, base, rim=None, top=None):
    w = x1 - x0
    xs = np.linspace(-1, 1, max(2, int(w)), dtype=np.float32)
    shade = (0.55 + 0.6 * np.clip(1 - (xs + 0.35) ** 2, 0, 1)) [None, :, None]
    patch = col(base)[None, None] * shade * np.ones((max(1, int(y1 - y0)), 1, 1), np.float32)
    ys, xs0 = int(y0), int(x0)
    ph, pw = patch.shape[:2]
    sy0, sx0 = max(0, ys), max(0, xs0)
    sy1, sx1 = min(H, ys + ph), min(W, xs0 + pw)
    if sy1 > sy0 and sx1 > sx0:
        canvas[sy0:sy1, sx0:sx1] = patch[sy0 - ys:sy1 - ys, sx0 - xs0:sx1 - xs0]
    if top:
        ellipse(canvas, ((x0 + x1) / 2, y0), (w / 2, w * 0.12), top)
    if rim:
        for yy in (y0 + (y1 - y0) * 0.3, y0 + (y1 - y0) * 0.7):
            ellipse(canvas, ((x0 + x1) / 2, yy), (w / 2, w * 0.1), rim, 0.9, a0=0, a1=180)


def tire(canvas, cx, cy, r):
    ellipse(canvas, (cx, cy), (r, r * 0.42), "#1c1c1f")
    ellipse(canvas, (cx, cy - r * 0.05), (r * 0.98, r * 0.36), "#2b2b30")
    ellipse(canvas, (cx, cy - r * 0.08), (r * 0.52, r * 0.2), "#0e0e10")
    ellipse(canvas, (cx - r * 0.35, cy - r * 0.18), (r * 0.35, r * 0.06), "#4a4a52", 0.6, blur=3)


def tire_stack(canvas, cx, base_y, r, n):
    for k in range(n):
        y = base_y - k * r * 0.38
        ellipse(canvas, (cx, y + r * 0.06), (r, r * 0.42), "#151518")
        poly(canvas, [(cx - r, y - r * 0.02), (cx + r, y - r * 0.02), (cx + r, y + r * 0.2), (cx - r, y + r * 0.2)], "#202024")
        tire(canvas, cx, y - r * 0.02, r)


class Room:
    def __init__(self, vp, back, seed):
        self.vp = np.float32(vp)
        self.back = back
        self.seed = seed
        self.img = np.zeros((H, W, 3), np.float32)
        self.mask = np.zeros((H, W), np.float32)
        self.light = np.zeros((H, W, 3), np.float32)
        x0, y0, x1, y1 = back
        f = (x1 - x0) / (W * 1.9)
        self.f = f
        out = [self.vp + (np.float32(p) - self.vp) / f for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        self.out = out
        self.depth = np.zeros((H, W), np.float32)

    def quads(self):
        x0, y0, x1, y1 = self.back
        o = self.out
        return {"back": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                "floor": [(x0, y1), (x1, y1), tuple(o[2]), tuple(o[3])],
                "ceil": [tuple(o[0]), tuple(o[1]), (x1, y0), (x0, y0)],
                "left": [tuple(o[0]), (x0, y0), (x0, y1), tuple(o[3])],
                "right": [(x1, y0), tuple(o[1]), tuple(o[2]), (x1, y1)]}

    def surface(self, name, tex):
        return warp(self.img, self.mask, tex, self.quads()[name])

    def floor_y(self, d):
        x0, y0, x1, y1 = self.back
        return y1 + (self.out[3][1] - y1) * d

    def scale_at(self, y):
        return max(0.05, (y - self.vp[1]) / (2050 - self.vp[1]))

    def person(self, y):
        return 1225 * self.scale_at(y)

    def ao(self, strength=0.55):
        q = self.quads()
        m = np.zeros((H, W), np.float32)
        x0, y0, x1, y1 = self.back
        for a, b in ((q["back"][3], q["back"][2]), (q["back"][0], q["back"][3]), (q["back"][1], q["back"][2]), (q["floor"][0], q["floor"][3]), (q["floor"][1], q["floor"][2])):
            cv2.line(m, tuple(np.int32(a)), tuple(np.int32(b)), 1.0, 30, cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), 45)
        self.img *= (1 - strength * np.clip(m, 0, 1))[..., None]

    def build_depth(self):
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        x0, y0, x1, y1 = self.back
        d = np.full((H, W), 0.08, np.float32)
        floor = yy > y1
        d[floor] = 0.15 + 0.85 * np.clip((yy[floor] - y1) / (H - y1), 0, 1)
        side = (xx < x0) | (xx > x1)
        ds = np.clip(np.maximum((x0 - xx) / max(1, x0), (xx - x1) / max(1, W - x1)), 0, 1)
        d = np.where(side & ~floor, 0.15 + 0.7 * ds, d)
        self.depth = d

    def finish(self, ambient=0.62, tint="#9aa3b5", haze=0.25, wet=0.0, grade=(1.0, 1.0, 1.0), paint=True, vignette=0.45):
        img = self.img * (ambient * col(tint) / 255.0 + self.light)
        x0, y0, x1, y1 = self.back
        yy = np.arange(H, dtype=np.float32)[:, None]
        hz = np.exp(-((yy - (y0 + y1) / 2) / (H * 0.25)) ** 2)[..., None] * haze
        img = img * (1 - hz) + col(tint) * 0.55 * hz
        if wet:
            fy = int(y1)
            up = img[max(0, 2 * fy - H):fy][::-1]
            refl = np.zeros_like(img)
            refl[fy:fy + up.shape[0]] = up
            refl = cv2.GaussianBlur(refl, (0, 0), 5)
            pud = np.clip((noise(H, W, self.seed + 77, 260, 3) - 0.42) * 2.4, 0, 1)
            pud[:fy] = 0
            pud *= np.clip((yy[:, 0] - fy) / 300, 0, 1)[:, None]
            img = img * (1 - wet * pud[..., None]) + refl * wet * pud[..., None] * 0.95
        img = img * np.float32(grade)
        if vignette:
            yy2, xx2 = np.mgrid[0:H, 0:W].astype(np.float32)
            v = np.clip(np.hypot((xx2 - W / 2) / W, (yy2 - H / 2) / H) * 1.5 - 0.2, 0, 1)
            img *= (1 - vignette * v)[..., None]
        img = np.clip(img, 0, 255).astype(np.uint8)
        if paint:
            img = cv2.edgePreservingFilter(img, flags=1, sigma_s=12, sigma_r=0.18)
            img = cv2.addWeighted(img, 1.5, cv2.GaussianBlur(img, (0, 0), 3), -0.5, 0)
        g = (rng(self.seed + 5).normal(0, 3.5, (H, W, 1))).astype(np.float32)
        img = np.clip(img.astype(np.float32) + g, 0, 255).astype(np.uint8)
        self.build_depth()
        return img


def lamp_hanging(room, x, y, cord_top=0, color="#ffd8a0", strength=1.2, r=220):
    cv2.line(room.img, (int(x), int(cord_top)), (int(x), int(y - 30)), (25, 25, 28), 4, cv2.LINE_AA)
    poly(room.img, [(x - 70, y), (x + 70, y), (x + 40, y - 40), (x - 40, y - 40)], "#2a2d33")
    ellipse(room.img, (x, y + 4), (40, 14), "#fff4d6")
    glow(room.light, (x, y + 10), r, strength, color)
    cone(room.light, (x, y), 60, 520, y + 1400, 0.35, color)


def tube_light(room, x, y, w=260, strength=0.9):
    poly(room.img, [(x - w / 2, y - 10), (x + w / 2, y - 10), (x + w / 2, y + 12), (x - w / 2, y + 12)], "#f2f6ff")
    glow(room.light, (x, y + 20), 300, strength, "#dce8ff")


def garage(seed=11, time="overcast", rain=True):
    room = Room((675, 1150), (300, 520, 1050, 1560), seed)
    back = tex_ribs(900, 1260, "#7f858c", seed, 30, dirt=0.5)
    for k in range(2):
        cx = 220 + k * 460
        back[150:1200, cx - 170:cx + 170] = tex_ribs(340, 1050, "#8c9198", seed + 10 + k, 22)[:, :, :]
        back[130:150, cx - 190:cx + 190] = col("#3a3d42")
    room.surface("back", back)
    room.surface("floor", tex_concrete(900, 1500, "#55585e", seed + 2, 0.5, 10))
    side = tex_ribs(1200, 900, "#6e747b", seed + 3, 34, vertical=True, dirt=0.55)
    room.surface("left", side)
    room.surface("right", tex_ribs(1200, 900, "#737981", seed + 4, 34, vertical=True, dirt=0.55))
    ceil = tex_ribs(900, 900, "#3b3f45", seed + 5, 40, vertical=True)
    room.surface("ceil", ceil)
    q = room.quads()
    for k in range(5):
        y = 560 + k * 70
        x = 300 + 40
        poly(room.img, [(x + k * 0, y), (x + 260, y), (x + 260, y + 14), (x, y + 14)], "#4c3a2a")
    pegx, pegy = 640, 760
    poly(room.img, [(pegx, pegy), (pegx + 330, pegy), (pegx + 330, pegy + 220), (pegx, pegy + 220)], "#6a5a46")
    for k in range(7):
        cv2.line(room.img, (pegx + 30 + k * 44, pegy + 30), (pegx + 30 + k * 44, pegy + 120 + (k % 3) * 30), (60, 62, 68), 7, cv2.LINE_AA)
    poly(room.img, [(330, 1250), (620, 1250), (620, 1270), (330, 1270)], "#5a4632")
    for xx in (345, 600):
        poly(room.img, [(xx, 1270), (xx + 14, 1270), (xx + 14, 1480), (xx, 1480)], "#3f3226")
    cyl(room.img, 360, 470, 1110, 1250, "#2f5d8a", rim="#244a6e", top="#3b6fa2")
    cyl(room.img, 480, 580, 1130, 1250, "#8a3030", rim="#6e2424", top="#a03a3a")
    tire_stack(room.img, 1130, 1620, 120, 4)
    tire_stack(room.img, 200, 2050, 170, 3)
    ellipse(room.img, (760, 1780), (220, 50), "#202226", 0.55, blur=6)
    ellipse(room.img, (430, 1950), (150, 30), "#1b1d20", 0.5, blur=6)
    tube_light(room, 520, 470, 280, 0.6)
    tube_light(room, 860, 470, 280, 0.6)
    room.ao(0.5)
    img = room.finish(ambient=0.85, tint="#a7afbd", haze=0.05, wet=0.45 if rain else 0.15, grade=(0.95, 0.98, 1.04))
    return img, room.depth


def market(seed=21, time="day"):
    room = Room((675, 1100), (250, 600, 1100, 1500), seed)
    room.surface("back", tex_plaster(900, 1000, "#9a8f7c", "#6c6355", seed, 0.62))
    room.surface("floor", tex_tiles(900, 1500, "#8c8578", "#7a7366", seed + 1, 110))
    room.surface("left", tex_plaster(1200, 900, "#8f8574", "#655c4f", seed + 2, 0.6))
    room.surface("right", tex_plaster(1200, 900, "#938a79", "#686052", seed + 3, 0.6))
    room.surface("ceil", tex_ribs(900, 900, "#4a4a48", seed + 4, 50, vertical=True))
    r = rng(seed)
    canopy = ["#b8322f", "#2f6db8", "#d6a02a", "#2f8a5a", "#b8322f", "#2f6db8"]
    stalls = [(330, 1540, 0), (1020, 1540, 1), (-260, 2000, 2), (1610, 2000, 3)]
    for cx, by, k in sorted(stalls, key=lambda q: q[1]):
        p = room.person(by) * 0.8
        w = p * 0.5
        top = by - p * 1.35
        for i in range(6):
            c = col(canopy[k]) * (1.0 if i % 2 == 0 else 0.8)
            x_a, x_b = cx - w * 1.1 + i * w * 2.2 / 6, cx - w * 1.1 + (i + 1) * w * 2.2 / 6
            poly(room.img, [(x_a, top), (x_b, top), (x_b + p * 0.02, top + p * 0.14), (x_a + p * 0.02, top + p * 0.14)], c)
            ellipse(room.img, ((x_a + x_b) / 2, top + p * 0.14), ((x_b - x_a) / 2, p * 0.03), c * 0.9 if False else "#00000000", 0)
        poly(room.img, [(cx - w * 1.1, top + p * 0.14), (cx + w * 1.1, top + p * 0.14), (cx + w * 1.1, top + p * 0.17), (cx - w * 1.1, top + p * 0.17)], "#1e1e22", 0.5, blur=3)
        for xx in (cx - w, cx + w):
            poly(room.img, [(xx - p * 0.012, top), (xx + p * 0.012, top), (xx + p * 0.012, by), (xx - p * 0.012, by)], "#3a3a3e")
        poly(room.img, [(cx - w, by - p * 0.5), (cx + w, by - p * 0.5), (cx + w, by), (cx - w, by)], "#6e5c46")
        for j in range(5):
            poly(room.img, [(cx - w, by - p * (0.45 - j * 0.09)), (cx + w, by - p * (0.45 - j * 0.09)), (cx + w, by - p * (0.44 - j * 0.09)), (cx - w, by - p * (0.44 - j * 0.09))], "#4e4032")
        poly(room.img, [(cx - w - p * 0.03, by - p * 0.53), (cx + w + p * 0.03, by - p * 0.53), (cx + w, by - p * 0.48), (cx - w, by - p * 0.48)], "#a8987e")
        n = 7
        for row in range(2):
            for j in range(n):
                px = cx - w + p * 0.06 + j * (2 * w - p * 0.12) / (n - 1)
                py = by - p * (0.56 + row * 0.07)
                pc = r.choice(["#d84a2a", "#e8b030", "#6aa040", "#f08a30", "#c8c040", "#a03a6a", "#e86a5a"])
                ellipse(room.img, (px, py), (p * 0.05, p * 0.035), pc)
                ellipse(room.img, (px - p * 0.012, py - p * 0.012), (p * 0.016, p * 0.008), "#ffffff", 0.4, blur=2)
        for b in range(3):
            bx = cx - w * 0.6 + b * w * 0.6
            cv2.line(room.img, (int(bx), int(top + p * 0.17)), (int(bx), int(top + p * 0.3)), (30, 30, 30), 2)
            ellipse(room.img, (bx, top + p * 0.32), (p * 0.025, p * 0.032), "#fff2c8")
            glow(room.light, (bx, top + p * 0.33), p * 0.22, 0.55, "#ffcf8a")
    for k in range(4):
        ellipse(room.img, (300 + k * 260, 2150 - (k % 2) * 150), (120, 26), "#2a2824", 0.35, blur=8)
    if time in ("day", "golden"):
        cone(room.light, (675, 600), 300, 800, 2300, 0.35, "#ffe2b0")
    room.ao(0.45)
    img = room.finish(ambient=0.85, tint="#c2b49c", haze=0.05, wet=0.2, grade=(1.03, 1.0, 0.94))
    return img, room.depth


def rented_room(seed=31, time="night"):
    room = Room((675, 1180), (330, 560, 1020, 1520), seed)
    back = tex_plaster(700, 960, "#5e6a6c", "#2f4447", seed, 0.6)
    wx0, wy0, wx1, wy1 = 120, 120, 580, 470
    out = np.zeros((wy1 - wy0, wx1 - wx0, 3), np.float32)
    out[:] = col("#0d1830")
    yy = np.linspace(0, 1, wy1 - wy0, dtype=np.float32)[:, None, None]
    out = out * (1 - yy) + col("#24304a") * yy
    r = rng(seed)
    for k in range(5):
        bx = int(r.uniform(0, wx1 - wx0 - 80))
        bh = int(r.uniform(90, 260))
        out[(wy1 - wy0) - bh:, bx:bx + int(r.uniform(60, 140))] = col("#151c2c")
        for _ in range(6):
            lx, ly = bx + int(r.uniform(8, 50)), (wy1 - wy0) - int(r.uniform(20, bh - 10))
            out[ly:ly + 12, lx:lx + 10] = col("#e8c070")
    back[wy0:wy1, wx0:wx1] = out
    cv2.rectangle(back, (wx0, wy0), (wx1, wy1), col("#3a2a1c").tolist(), 16)
    cv2.line(back, ((wx0 + wx1) // 2, wy0), ((wx0 + wx1) // 2, wy1), col("#3a2a1c").tolist(), 8)
    cv2.rectangle(back, (wx0 - 20, wy1), (wx1 + 20, wy1 + 22), col("#4a3624").tolist(), -1)
    for sx in (wx0 - 60, wx1 + 10):
        cv2.rectangle(back, (sx, wy0 - 20), (sx + 50, wy1 + 40), col("#7a3a3a").tolist(), -1)
    room.surface("back", back)
    room.surface("floor", tex_concrete(800, 1400, "#3b3d3e", seed + 1, 0.45, 6))
    room.surface("left", tex_plaster(1100, 900, "#56605f", "#2b3c3e", seed + 2, 0.6))
    room.surface("right", tex_plaster(1100, 900, "#5a6463", "#2e3f41", seed + 3, 0.6))
    room.surface("ceil", tex_concrete(800, 800, "#3a3c3e", seed + 4, 0.3, 2))
    mx0, my, mx1 = 40, 1950, 520
    poly(room.img, [(mx0, my - 120), (mx1, my - 120), (mx1 + 40, my), (mx0 - 40, my)], "#c8c0b0")
    poly(room.img, [(mx0 - 40, my), (mx1 + 40, my), (mx1 + 40, my + 50), (mx0 - 40, my + 50)], "#8a8274")
    ellipse(room.img, (150, my - 140), (90, 34), "#e8e2d4")
    poly(room.img, [(200, my - 110), (500, my - 110), (520, my - 20), (180, my - 20)], "#4a6a8a", 0.9)
    tx, ty = 820, 1700
    poly(room.img, [(tx - 170, ty - 260), (tx + 170, ty - 260), (tx + 190, ty - 230), (tx - 190, ty - 230)], "#6a4a2e")
    for xx in (tx - 170, tx + 160):
        poly(room.img, [(xx, ty - 230), (xx + 14, ty - 230), (xx + 14, ty), (xx, ty)], "#4a3220")
    cyl(room.img, tx - 120, tx - 96, ty - 340, ty - 262, "#2f6a3a")
    ellipse(room.img, (tx + 60, ty - 262), (50, 12), "#e8e8e0")
    fx, fy = 1150, 1500
    cv2.line(room.img, (fx, fy), (fx, fy + 260), (40, 40, 44), 10, cv2.LINE_AA)
    ellipse(room.img, (fx, fy), (70, 70), "#5a7a9a")
    ellipse(room.img, (fx, fy), (58, 58), "#cfd8e0", 0.6)
    ellipse(room.img, (fx, fy + 270), (60, 16), "#2a2a2e")
    poly(room.img, [(1040, 980), (1300, 900), (1300, 1000), (1040, 1060)], "#3a3a3e", 0.0)
    for k, c in enumerate(("#c8a040", "#3a5a8a", "#8a3a3a")):
        poly(room.img, [(1060 + k * 70, 1000 - k * 22), (1110 + k * 70, 985 - k * 22), (1120 + k * 70, 1150 - k * 22), (1070 + k * 70, 1170 - k * 22)], c, 0.85)
    lamp_hanging(room, 675, 640, 520, "#ffe1b0", 1.1, 240)
    room.ao(0.6)
    img = room.finish(ambient=0.62, tint="#8494ad", haze=0.03, wet=0.08, grade=(0.95, 1.0, 1.08))
    return img, room.depth


SETS = {"garage": ("อู่ซ่อมรถ", garage), "market": ("ตลาดสด", market), "rented_room": ("ห้องเช่า", rented_room)}


def render(key, out, seed=None, **kw):
    fn = SETS[key][1]
    img, depth = fn(**({"seed": seed} if seed is not None else {}), **kw)
    cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    return depth
