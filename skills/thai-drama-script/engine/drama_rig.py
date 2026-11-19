import math
import random
import re

from PIL import Image, ImageDraw

import drama_items as IT
import drama_poses as PZ
import drama_outfits as OF

SS = 2
X0, X1, Y0, Y1 = -430, 430, -980, 40
HIP_Y, NECK_Y, HEAD_Y, R = -300.0, -560.0, -690.0, 150.0
BODY_W = 90.0
SHO = (78.0, -528.0)
HIPX = 40.0
UP, FORE = 128.0, 118.0
THIGH, SHIN = 152.0, 150.0
ARM_W, LEG_W, OUT = 15.0, 17.0, 9.0
INK = (17, 17, 19, 255)
WHITE = (250, 250, 250, 255)
GOLD = (226, 178, 52, 255)
GOLD_D = (168, 122, 24, 255)

LIMITS = {"la": (-70, 178), "ra": (-70, 178), "le": (-160, 160), "re": (-160, 160), "ll": (-100, 110), "rl": (-100, 110),
          "lk": (-5, 165), "rk": (-5, 165), "lean": (-40, 70), "head": (-26, 26)}
BODY = ("roll", "drop", "lift")
UNDER = ("under_car",)
BASE = {"la": 9, "le": -8, "ra": 9, "re": -8, "ll": 5, "lk": 0, "rl": 5, "rk": 0, "lean": 0, "head": 0}

POSES = {
    "stand": {},
    "talk": {"ra": 24, "re": 72, "gesture": "r"},
    "talk2": {"la": 24, "le": 72, "gesture": "l"},
    "point_r": {"ra": 92, "re": 4, "lean": 3, "head": 3},
    "point_l": {"la": 92, "le": 4, "lean": -3, "head": -3},
    "hips": {"rh": (104, -350), "lh": (-104, -350), "lean": -2},
    "cross": {"la": 20, "le": 142, "ra": 26, "re": 140, "head": -4},
    "shrug": {"la": 52, "le": -78, "ra": 52, "re": -78, "head": 7},
    "phone": {"rh": (6, -548), "head": -6, "prop": "phone"},
    "phone_show": {"rh": (250, -560), "head": 4, "prop": "phone"},
    "selfie": {"rh": (175, -700), "prop": "selfie", "head": 5},
    "facepalm": {"rh": (118, -742), "over": "r", "head": -9, "lean": 2},
    "think": {"rh": (-20, -585), "la": 30, "le": 112, "head": 7},
    "shock": {"la": 148, "le": 22, "ra": 148, "re": 22, "lean": -4, "head": 0},
    "hold": {"rh": (36, -462), "lh": (-36, -462)},
    "wave": {"ra": 140, "re": -28, "gesture": "w"},
    "fist": {"rh": (112, -400), "lh": (-112, -400), "hands": {"r": "fist", "l": "fist"}, "lean": 4, "shake": 1},
    "sad": {"la": 8, "le": -4, "ra": 8, "re": -4, "head": -10, "lean": 3},
    "yell": {"ra": 70, "re": 40, "la": 30, "le": 110, "lean": 6, "head": 4, "gesture": "r"},
    "walk": {"walk": 1},
    "bow": {"la": 14, "le": -12, "ra": 14, "re": -12, "head": -12, "lean": 8},
    "lean_desk": {"rh": (70, -430), "lh": (-70, -430), "lean": 5, "head": -3},
    "wai": {"ra": 10, "re": 142, "la": 10, "le": 142, "head": -9, "lean": 4, "palms": 1},
    "salute": {"rh": (172, -735), "la": 6, "le": -6, "head": 2},
    "give": {"rh": (230, -470), "head": 3, "lean": 3},
    "cast": {"rh": (215, -800), "lh": (60, -470), "prop": "rod", "head": 6, "lean": -3},
    "row": {"ra": 62, "re": -150, "la": 58, "le": 90, "prop": "paddle", "lean": -4, "head": -2},
    "pull": {"rh": (190, -470), "lh": (120, -470), "prop": "net", "lean": -9, "head": 4},
    "ride_r": {"ra": 52, "re": 28, "la": -22, "le": -78, "ll": 24, "lk": 50, "rl": 24, "rk": 50, "lean": 4},
    "ride_l": {"la": 52, "le": 28, "ra": -22, "re": -78, "ll": 24, "lk": 50, "rl": 24, "rk": 50, "lean": -4},
}
POSE_TH = {"stand": "ยืน", "talk": "พูด", "talk2": "พูด (มือซ้าย)", "point_r": "ชี้ขวา", "point_l": "ชี้ซ้าย", "hips": "เท้าสะเอว",
           "cross": "กอดอก", "shrug": "ยักไหล่", "phone": "ดูมือถือ", "phone_show": "ยื่นมือถือให้ดู", "selfie": "ไลฟ์ไม้เซลฟี่",
           "facepalm": "กุมหัว", "think": "เท้าคาง", "shock": "ตกใจยกมือ", "hold": "ถือของ", "wave": "โบกมือ", "fist": "กำหมัดโกรธ",
           "sad": "คอตก", "yell": "ตะโกน", "walk": "เดิน", "bow": "ก้มหัวขอโทษ", "lean_desk": "เท้าโต๊ะ", "ride_r": "ขี่รถ", "ride_l": "ขี่รถ",
           "wai": "ไหว้", "salute": "ตะเบ๊ะ", "give": "ยื่นของให้", "cast": "เหวี่ยงเบ็ด", "row": "พายเรือ", "pull": "ลากอวน"}
FACES = ("neutral", "smug", "smile", "angry", "shock", "sad", "worried", "yell", "cry")
HAIRS = ("short", "messy", "spiky", "side", "mohawk", "bob", "ponytail", "twintail", "long", "wavy", "bun", "curly", "afro", "bald", "bald_side")
HATS = ("none", "cap", "bucket", "beanie", "straw", "police", "helmet", "chef", "ngob", "fire", "nurse", "peaked", "beret",
        "hardhat", "crown", "cowboy", "grad", "santa", "hijab", "party", "visor", "bandana", "tophat", "headscarf", "wreath", "hazmat", "furhood")
GLASSES = ("none", "pixel", "round", "square", "sun", "cateye")
SHIRTS = ("tee", "hoodie", "collar", "suit", "dress", "tank", "jacket", "uniform", "coat", "robe", "vest", "overalls", "thai", "sabai", "firecoat", "student",
          "polo", "scrubs", "raincoat", "jersey", "kimono", "cardigan", "hawaii", "tracksuit", "gown", "monk")
PATTERNS = ("none", "stripe", "dots", "floral", "check")
MOUTHS = ("normal", "small", "wide", "lips", "buck", "gold", "thin", "pout", "gap")
BROWS = ("normal", "thick", "thin", "bushy", "unibrow", "arched", "sharp", "short")
EYES = ("oval", "dot", "round", "narrow", "sleepy", "sharp", "big", "lashes")
NOSES = ("none", "dot", "line", "round", "big", "hook")
EXTRAS = ("apron", "gold_chain", "necklace", "earrings", "bracelet", "watch", "tie", "scarf", "headband", "flower", "beard", "mustache",
          "mole", "blush", "lipstick", "freckles", "bandaid", "gold_ring", "acne", "scar", "eyebags", "wrinkles", "stethoscope", "badge", "reflect", "lanyard", "belt", "epaulette", "nametag", "gasmask", "face_cloth", "goggles", "soot")
BUILDS = ("normal", "fat", "thin")
PANTS = ("long", "shorts", "none")
PANTS_PAL = ("#2b3550", "#3a3a40", "#4a3a2a", "#5a6070", "#2a4a6a", "#6a5a48", "#1f2a3a")
SKIRTS = ("dress", "gown", "kimono")
SHORTS_OUTFITS = ("lifeguard", "swimmer", "boxer", "muay_thai", "football_red", "football_blue", "basketball", "runner", "summer_beach", "tank_shorts",
                  "kid_student", "scout", "tourist", "backpacker", "farang_expat", "homeless", "beggar", "poor_worn", "tennis", "cyclist")
PANTS_C = {"security_mall": "#1f2a3a", "parking_guard": "#1f2a3a", "chef_head": "#2a2a2e", "waiter": "#1a1a1e", "butler": "#1a1a1e", "zombie": "#4a4a52",
           "food_rider_pink": "#2a2a30", "food_rider_orange": "#2a2a30", "mechanic_dirty": "#2a3a5a", "construction": "#3a4a6a", "university_m": "#1a1a20",
           "teacher_m": "#3a3a40", "ceo": "#1a1a20", "hazmat": "#e8c020", "rad_suit": "#b8bcc4", "arctic_parka": "#3a3a40",
           "desert_nomad": "#b89868", "scavenger": "#4a4a3a", "survivor": "#3a3f4a", "toxic_survivor": "#3a4a2a", "soldier_wasteland": "#4a5a3a", "hiso_young": "#e8e4da", "rich_uncle": "#e8e4da", "nouveau_riche": "#d8c8a0", "gamer": "#3a3a40"}
BUILD_W = {"normal": (1.0, 1.0, 1.0), "fat": (1.3, 1.7, 1.4), "thin": (0.76, 0.76, 0.8)}
FACE_EXTRAS = ("gold_chain", "necklace", "earrings", "bracelet", "watch", "scarf", "headband", "flower", "beard", "mustache", "mole", "blush", "lipstick",
               "freckles", "bandaid", "gold_ring", "acne", "scar", "eyebags", "wrinkles")
OUTFITS = {
    "police": ("ตำรวจ", {"shirt": "uniform", "shirt_c": "#7a4a32", "hat": "police", "hat_c": "#4a2c1e", "extras": ["badge", "belt", "epaulette"]}),
    "soldier": ("ทหาร", {"shirt": "uniform", "shirt_c": "#4d5a32", "pattern": "check", "pat_c": "#39432a", "hat": "beret", "hat_c": "#2f3a22", "extras": ["belt", "nametag"]}),
    "firefighter": ("นักดับเพลิง", {"shirt": "firecoat", "shirt_c": "#2c2f36", "hat": "fire", "hat_c": "#d8a020", "extras": ["reflect"]}),
    "doctor": ("หมอ", {"shirt": "coat", "shirt_c": "#f4f4f2", "hat": "none", "extras": ["stethoscope", "nametag"]}),
    "nurse": ("พยาบาล", {"shirt": "dress", "shirt_c": "#f6f6f4", "hat": "nurse", "extras": ["nametag"]}),
    "guard": ("รปภ.", {"shirt": "uniform", "shirt_c": "#2a3550", "hat": "peaked", "hat_c": "#1c2438", "extras": ["badge", "belt"]}),
    "rider": ("ไรเดอร์", {"shirt": "jacket", "shirt_c": "#1f9a52", "hat": "helmet", "hat_c": "#1f9a52", "extras": ["reflect"]}),
    "motortaxi": ("วินมอเตอร์ไซค์", {"shirt": "vest", "shirt_c": "#e8742a", "hat": "none", "extras": ["nametag"]}),
    "mechanic": ("ช่างซ่อมรถ", {"shirt": "overalls", "shirt_c": "#2f5f9a", "hat": "cap", "hat_c": "#2f5f9a", "extras": ["nametag"]}),
    "farmer": ("ชาวนา", {"shirt": "collar", "shirt_c": "#273a6a", "hat": "ngob", "extras": ["scarf"], "acc_c": "#c0392b"}),
    "vendor": ("แม่ค้า", {"shirt": "tee", "shirt_c": "#c0504d", "pattern": "floral", "hat": "none", "extras": ["apron"]}),
    "cook": ("พ่อครัว", {"shirt": "collar", "shirt_c": "#f4f4f2", "hat": "chef", "extras": ["apron"]}),
    "civil": ("ข้าราชการชุดขาว", {"shirt": "uniform", "shirt_c": "#f2f2ee", "hat": "peaked", "hat_c": "#f2f2ee", "extras": ["epaulette", "nametag"]}),
    "village": ("กำนัน/ผู้ใหญ่บ้าน", {"shirt": "uniform", "shirt_c": "#a08a5a", "hat": "none", "extras": ["epaulette", "badge"]}),
    "student": ("นักเรียน", {"shirt": "student", "shirt_c": "#f6f6f4", "hat": "none", "extras": ["nametag"]}),
    "lawyer": ("ทนาย/ผู้พิพากษา", {"shirt": "robe", "shirt_c": "#1a1a1e", "hat": "none", "extras": ["tie"]}),
    "office": ("พนักงานออฟฟิศ", {"shirt": "collar", "shirt_c": "#9fb6d6", "hat": "none", "extras": ["lanyard", "tie"]}),
    "boss": ("เสี่ย", {"shirt": "collar", "shirt_c": "#c04040", "pattern": "floral", "hat": "none", "extras": ["gold_chain", "watch", "gold_ring"]}),
    "thai_m": ("ชุดไทยชาย", {"shirt": "thai", "shirt_c": "#e9e2cf", "hat": "none", "extras": []}),
    "thai_f": ("ชุดไทยหญิง", {"shirt": "sabai", "shirt_c": "#b0306a", "hat": "none", "extras": ["necklace", "earrings"]}),
    "funeral": ("ชุดดำงานศพ", {"shirt": "collar", "shirt_c": "#1c1c1f", "hat": "none", "extras": []}),
    "fisher": ("ชาวประมง", {"shirt": "tank", "shirt_c": "#3a6a8a", "hat": "straw", "extras": ["scarf"], "acc_c": "#e8b04a"}),
    "monkish_white": ("ชุดขาวถือศีล", {"shirt": "collar", "shirt_c": "#f6f6f4", "hat": "none", "extras": []}),
}


for _k, (_th, _cat, _o) in OF.OUTFITS.items():
    OUTFITS.setdefault(_k, (_th, _o))


def apply_outfit(look, key):
    o = OUTFITS.get(str(key or ""))
    if not o:
        return look
    l = dict(look or {})
    for k, v in o[1].items():
        if k == "extras":
            l["extras"] = list(dict.fromkeys(list(v) + [x for x in l.get("extras") or [] if x in ("beard", "mustache", "mole", "blush", "lipstick", "freckles", "earrings", "gold_chain")]))[:6]
        else:
            l[k] = v
    if key in SHORTS_OUTFITS:
        l["pants"] = "shorts"
    elif key in PANTS_C:
        l["pants"], l["pants_c"] = "long", PANTS_C[key]
    return l
PROPS = ("phone", "plate", "ladle", "paper", "box", "selfie", "bag", "money", "cup", "knife", "rod", "paddle", "net", "fish", "envelope")
PROPS = PROPS + tuple(k for k in IT.ITEMS if k not in PROPS)
for _k, (_th, _cat, _p) in PZ.POSES.items():
    if _k not in POSES:
        POSES[_k] = _p
        POSE_TH[_k] = _th
HAIR_TH = {"short": "สั้น", "messy": "ยุ่ง", "spiky": "ตั้งแหลม", "side": "แสกข้าง", "mohawk": "โมฮอว์ก", "bob": "บ๊อบ", "ponytail": "หางม้า",
           "twintail": "แกละสองข้าง", "long": "ยาวตรง", "wavy": "ยาวลอน", "bun": "มวย", "curly": "ดัดลอน", "afro": "แอฟโฟร", "bald": "หัวล้าน",
           "bald_side": "ล้านกลาง"}


def clamp(v, a, b):
    return max(a, min(b, v))


def _dir(side, ang):
    r = math.radians(ang)
    s = 1.0 if side == "r" else -1.0
    return (s * math.sin(r), math.cos(r))


def _ang(side, v):
    s = 1.0 if side == "r" else -1.0
    return math.degrees(math.atan2(s * v[0], v[1]))


def ik(side, sho, target, bend=1.0):
    dx, dy = target[0] - sho[0], target[1] - sho[1]
    d = clamp(math.hypot(dx, dy), abs(UP - FORE) + 1, UP + FORE - 0.5)
    base = math.atan2(dy, dx)
    c = clamp((UP * UP + d * d - FORE * FORE) / (2 * UP * d), -1, 1)
    off = math.acos(c) * (1 if side == "r" else -1) * bend
    el = (sho[0] + UP * math.cos(base + off), sho[1] + UP * math.sin(base + off))
    a = _ang(side, (el[0] - sho[0], el[1] - sho[1]))
    f = _ang(side, (target[0] - el[0], target[1] - el[1]))
    e = a - f
    while e > 180:
        e -= 360
    while e < -180:
        e += 360
    return a, e


def _fk(side, sho, a, e):
    d1 = _dir(side, a)
    el = (sho[0] + d1[0] * UP, sho[1] + d1[1] * UP)
    d2 = _dir(side, a - e)
    return el, (el[0] + d2[0] * FORE, el[1] + d2[1] * FORE)


def _wrap_clamp(v, lo, hi):
    best = None
    for k in (-360.0, 0.0, 360.0):
        w = v + k
        c = clamp(w, lo, hi)
        if best is None or abs(c - w) < best[0]:
            best = (abs(c - w), c)
    return best[1]


def ik_best(side, sho, target):
    (alo, ahi), (elo, ehi) = LIMITS[side + "a"], LIMITS[side + "e"]
    best = None
    for bend in (1.0, -1.0):
        a, e = ik(side, sho, target, bend)
        ca = _wrap_clamp(a, alo, ahi)
        if ca != a:
            el, _ = _fk(side, sho, ca, 0.0)
            e = ca - _ang(side, (target[0] - el[0], target[1] - el[1]))
            while e > 180:
                e -= 360
            while e < -180:
                e += 360
        ce = _wrap_clamp(e, elo, ehi)
        el, hd = _fk(side, sho, ca, ce)
        err = math.hypot(hd[0] - target[0], hd[1] - target[1]) + (0.0 if bend > 0 else 0.5)
        cross = (target[0] * (1 if side == "r" else -1)) < 20
        if not cross and abs(el[0]) < abs(sho[0]) - 10:
            err += 30.0
        if target[1] < sho[1] - 60 and not cross and abs(el[0]) < abs(sho[0]) + 70:
            err += 25.0
        if best is None or err < best[0]:
            best = (err, ca, ce)
    return best[1], best[2]


def resolve(name, extra=None):
    p = dict(BASE)
    src = dict(POSES.get(name) or {})
    src.update(extra or {})
    for k, v in src.items():
        if k in LIMITS:
            p[k] = v
    for side, key in (("r", "rh"), ("l", "lh")):
        if key in src:
            sx = SHO[0] if side == "r" else -SHO[0]
            tx, ty = src[key]
            if side not in str(src.get("over") or "") and ty < SHO[1] - 60:
                sg = 1 if side == "r" else -1
                if abs(tx) < 178 and math.hypot(tx, ty - HEAD_Y) < R + 60:
                    tx = sg * 178 if tx * sg > -40 else tx
                ty = max(ty, SHO[1] - 0.92 * (UP + FORE))
                src[key] = (tx, ty)
                src.setdefault("_raise", "")
                src["_raise"] += side
            p[side + "a"], p[side + "e"] = ik_best(side, (sx, SHO[1]), src[key])
    for k, (a, b) in LIMITS.items():
        p[k] = clamp(float(p[k]), a, b)
    for k in ("gesture", "over", "prop", "prop_rot", "walk", "shake", "palms", "side", "yaw", "roll", "drop", "lift", "seat", "osc", "hop", "hands", "legs_only", "lz", "rz", "ls", "rs", "back_arms", "pocket"):
        if k in src:
            p[k] = src[k]
    return p


def spring(t, dur=0.42):
    if t >= dur * 1.6:
        return 1.0
    x = max(0.0, t) / dur
    return 1.0 - math.exp(-5.2 * x) * math.cos(7.0 * x)


def blend(a, b, w, head_w=None):
    w = clamp(w, 0.0, 1.12)
    out = dict(b if w >= 0.5 else a)
    for k in LIMITS:
        ww = head_w if (k == "head" and head_w is not None) else w
        out[k] = clamp(a[k] + (b[k] - a[k]) * ww, *LIMITS[k])
    for k in BODY + ("lz", "rz", "ls", "rs"):
        if k in a or k in b:
            out[k] = float(a.get(k, 0.0)) + (float(b.get(k, 0.0)) - float(a.get(k, 0.0))) * w
    return out


def _rot(pt, c, deg):
    r = math.radians(deg)
    x, y = pt[0] - c[0], pt[1] - c[1]
    return (c[0] + x * math.cos(r) - y * math.sin(r), c[1] + x * math.sin(r) + y * math.cos(r))


def skeleton(p):
    hip = (0.0, HIP_Y)
    lean = p["lean"]
    yaw = float(p.get("yaw") or 0.0)
    side = bool(p.get("side"))
    sw = (1 - 0.62 * yaw) * float(p.get("_sw") or 1.0)
    sho = {s: _rot(((1 if s == "r" else -1) * SHO[0] * sw, SHO[1]), hip, lean) for s in "lr"}
    head = _rot((0.0, HEAD_Y), hip, lean)
    j = {"hip": hip, "head": head, "tilt": lean + p["head"]}
    for s in "lr":
        a, e = p[s + "a"], p[s + "e"]
        ds = "r" if side else s
        ln = lean if ds == "r" else -lean
        d1 = _dir(ds, a + ln)
        el = (sho[s][0] + d1[0] * UP, sho[s][1] + d1[1] * UP)
        d2 = _dir(ds, a - e + ln)
        hd = (el[0] + d2[0] * FORE, el[1] + d2[1] * FORE)
        j[s + "_sho"], j[s + "_el"], j[s + "_hand"] = sho[s], el, hd
        j[s + "_fore"] = math.degrees(math.atan2(d2[1], d2[0]))
        j[s + "_fdir"] = d2
        hx = (HIPX if s == "r" else -HIPX) * (1 - 0.75 * yaw) * float(p.get("_hw") or 1.0)
        d3 = _dir(ds, p[s + "l"])
        th = THIGH * (1 - 0.85 * max(0.0, min(1.0, p.get(s + "z", 0.0))))
        kn = (hx + d3[0] * th, HIP_Y + d3[1] * th)
        d4 = _dir(ds, p[s + "l"] - p[s + "k"])
        sn = SHIN * (1 - 0.85 * max(0.0, min(1.0, p.get(s + "s", 0.0))))
        ft = (kn[0] + d4[0] * sn, kn[1] + d4[1] * sn)
        j[s + "_hip"], j[s + "_knee"], j[s + "_foot"] = (hx, HIP_Y), kn, ft
    return j


class Pen:
    def __init__(self, scale):
        self.k = scale * SS
        self.w = int((X1 - X0) * self.k)
        self.h = int((Y1 - Y0) * self.k)
        self.im = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def P(self, pt):
        return ((pt[0] - X0) * self.k, (pt[1] - Y0) * self.k)

    def _soft(self, col, d):
        return d is None and isinstance(col, tuple) and len(col) == 4 and col[3] < 255

    def _over(self, fn):
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        fn(ImageDraw.Draw(layer))
        self.im.alpha_composite(layer)
        self.d = ImageDraw.Draw(self.im)

    def line(self, pts, w, col=INK, d=None):
        if self._soft(col, d):
            return self._over(lambda dd: self.line(pts, w, col, dd))
        d = d or self.d
        q = [self.P(p) for p in pts]
        ww = max(1, int(w * self.k))
        d.line(q, fill=col, width=ww, joint="curve")
        for p in (q[0], q[-1]):
            r = ww / 2
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col)

    def dot(self, c, r, col=INK, d=None):
        if self._soft(col, d):
            return self._over(lambda dd: self.dot(c, r, col, dd))
        d = d or self.d
        c, r = self.P(c), r * self.k
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=col)

    def poly(self, pts, fill, outline=None, w=0, d=None):
        if self._soft(fill, d):
            self._over(lambda dd: dd.polygon([self.P(p) for p in pts], fill=fill))
            if outline and w:
                self.line(pts + [pts[0]], w, outline)
            return
        d = d or self.d
        d.polygon([self.P(p) for p in pts], fill=fill)
        if outline and w:
            self.line(pts + [pts[0]], w, outline, d)

    def masked(self, pts, paint):
        mask = Image.new("L", (self.w, self.h), 0)
        ImageDraw.Draw(mask).polygon([self.P(p) for p in pts], fill=255)
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        paint(ImageDraw.Draw(layer))
        layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", (self.w, self.h), 0), mask))
        self.im.alpha_composite(layer)
        self.d = ImageDraw.Draw(self.im)

    def done(self):
        im = self.im.convert("RGBa").resize((self.w // SS, self.h // SS), Image.BOX).convert("RGBA")
        foot = ((0 - X0) * self.k / SS, (0 - Y0) * self.k / SS)
        return im, foot


def _hex(c, a=255, dv=(60, 64, 72)):
    c = str(c or "").lstrip("#")
    try:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a)
    except Exception:
        return dv + (a,)


def _shade(col, f):
    return (int(clamp(col[0] * f, 0, 255)), int(clamp(col[1] * f, 0, 255)), int(clamp(col[2] * f, 0, 255)), col[3])


def _rrect(cx, top, bot, hw, r, n=7):
    pts = []
    for cx0, cy0, a0 in ((cx + hw - r, top + r, -90), (cx + hw - r, bot - r, 0), (cx - hw + r, bot - r, 90), (cx - hw + r, top + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx0 + r * math.cos(a), cy0 + r * math.sin(a)))
    return pts


def _ellipse(c, rx, ry, a0=0, a1=360, n=36):
    return [(c[0] + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), c[1] + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def norm_look(look):
    l = dict(look or {})
    sh = str(l.get("shirt") or "")
    if sh.startswith("#"):
        l["shirt_c"], l["shirt"] = sh, "tee"
    if l.get("hair") in ("cap", "police"):
        l["hat"], l["hair"] = l["hair"], "short"
    l["hair"] = l.get("hair") if l.get("hair") in HAIRS else "short"
    l["hat"] = l.get("hat") if l.get("hat") in HATS else "none"
    l["glasses"] = l.get("glasses") if l.get("glasses") in GLASSES else "none"
    l["shirt"] = l.get("shirt") if l.get("shirt") in SHIRTS else "tee"
    l["pattern"] = l.get("pattern") if l.get("pattern") in PATTERNS else "none"
    l["mouth"] = l.get("mouth") if l.get("mouth") in MOUTHS else "normal"
    l["brows"] = l.get("brows") if l.get("brows") in BROWS else "normal"
    l["eyes"] = l.get("eyes") if l.get("eyes") in EYES else "oval"
    l["nose"] = l.get("nose") if l.get("nose") in NOSES else "none"
    l["extras"] = [x for x in (l.get("extras") or []) if x in EXTRAS]
    l["build"] = l.get("build") if l.get("build") in BUILDS else "normal"
    l["pants"] = l.get("pants") if l.get("pants") in PANTS else "long"
    pc = str(l.get("pants_c") or "")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", pc):
        sc = str(l.get("shirt_c") or "")
        if l["shirt"] in ("suit", "uniform") and re.fullmatch(r"#[0-9a-fA-F]{6}", sc):
            pc = "#%02x%02x%02x" % tuple(int(sc[i:i + 2], 16) * 7 // 10 for i in (1, 3, 5))
        else:
            pc = PANTS_PAL[sum(map(ord, sc + l["shirt"])) % len(PANTS_PAL)]
    l["pants_c"] = pc
    return l


def _body_pts(lean, dress=False, yaw=0.0):
    hip = (0.0, HIP_Y)
    k = 1 - 0.3 * yaw
    if dress:
        r = 60
        pts = _ellipse((BODY_W - r, NECK_Y + r), r, r, -90, 0, 8) + [(BODY_W + 4, HIP_Y - 40), (BODY_W + 40, HIP_Y + 112),
                                                                      (-BODY_W - 40, HIP_Y + 112), (-BODY_W - 4, HIP_Y - 40)] + _ellipse((-BODY_W + r, NECK_Y + r), r, r, 180, 270, 8)
    else:
        pts = _rrect(0, NECK_Y, HIP_Y + 18, BODY_W, 64)
    return [_rot((x * k + 10 * yaw, y), hip, lean) for x, y in pts]


def _pattern(pen, look, pts, col):
    pat = look.get("pattern")
    if pat == "none":
        return
    pc = _hex(look.get("pat_c"), dv=_shade(col, 0.7)[:3]) if look.get("pat_c") else _shade(col, 0.72)
    if look.get("pat_c") is None and pat in ("dots", "floral"):
        pc = _shade(col, 1.35)
    k = pen.k

    def paint(d):
        if pat == "stripe":
            for y in range(int(NECK_Y), int(HIP_Y + 120), 26):
                d.rectangle([0, (y - Y0) * k, pen.w, (y + 11 - Y0) * k], fill=pc)
        elif pat == "check":
            for y in range(int(NECK_Y), int(HIP_Y + 120), 40):
                d.rectangle([0, (y - Y0) * k, pen.w, (y + 14 - Y0) * k], fill=pc[:3] + (150,))
            for x in range(-140, 141, 40):
                d.rectangle([(x - X0) * k, 0, (x + 14 - X0) * k, pen.h], fill=pc[:3] + (150,))
        else:
            rng = random.Random(7)
            for y in range(int(NECK_Y) + 20, int(HIP_Y + 110), 36):
                for x in range(-120, 121, 36):
                    cx, cy = x + (18 if (y // 36) % 2 else 0) + rng.uniform(-3, 3), y
                    if pat == "dots":
                        r = 7 * k
                        d.ellipse([(cx - X0) * k - r, (cy - Y0) * k - r, (cx - X0) * k + r, (cy - Y0) * k + r], fill=pc)
                    else:
                        for a in range(0, 360, 72):
                            px, py = cx + 7 * math.cos(math.radians(a)), cy + 7 * math.sin(math.radians(a))
                            r = 5 * k
                            d.ellipse([(px - X0) * k - r, (py - Y0) * k - r, (px - X0) * k + r, (py - Y0) * k + r], fill=pc)
                        r = 3.5 * k
                        d.ellipse([(cx - X0) * k - r, (cy - Y0) * k - r, (cx - X0) * k + r, (cy - Y0) * k + r], fill=(250, 220, 90, 255))
    pen.masked(pts, paint)


def _wide_pen(pen, lean, top, bot):
    hip = (0.0, HIP_Y)
    base = type(pen)

    def P(self, pt):
        x, y = _rot(pt, hip, -lean)
        t = clamp((y - NECK_Y) / (HIP_Y - NECK_Y), 0.0, 1.0)
        return base.P(self, _rot((x * (top + (bot - top) * t), y), hip, lean))

    cls = type("WidePen", (base,), {"P": P})
    wp = cls.__new__(cls)
    wp.__dict__ = pen.__dict__
    return wp


def _body(pen, look, lean):
    bw = BUILD_W[look.get("build") or "normal"]
    if bw[0] != 1.0 or bw[1] != 1.0:
        pen = _wide_pen(pen, lean, bw[0], bw[1])
    hip = (0.0, HIP_Y)
    rt = lambda pts: [_rot(p, hip, lean) for p in pts]
    col = _hex(look.get("shirt_c"))
    kind = look["shirt"]
    pts = _body_pts(lean, kind in ("dress", "gown", "kimono"), float(look.get("_yaw") or 0.0))
    pen.poly(pts, col)
    _pattern(pen, look, pts, col)
    pen.masked(pts, lambda d: d.rectangle([pen.P((40, 0))[0], 0, pen.w, pen.h], fill=(0, 0, 0, 34)))
    pen.line(pts + [pts[0]], OUT)
    dk = _shade(col, 0.6)
    if kind == "hoodie":
        pen.line(rt(_ellipse((0, NECK_Y + 6), 46, 22, 10, 170, 12)), 6, dk)
        pen.line(rt([(-16, NECK_Y + 22), (-20, NECK_Y + 80)]), 4, dk)
        pen.line(rt([(16, NECK_Y + 22), (20, NECK_Y + 80)]), 4, dk)
        pen.line(rt(_ellipse((0, HIP_Y - 60), 46, 18, 0, 180, 10)), 4, dk)
    elif kind in ("collar", "uniform"):
        pen.poly(rt([(0, NECK_Y + 30), (-36, NECK_Y + 2), (-12, NECK_Y - 2)]), WHITE if kind == "collar" else _shade(col, 1.2), INK, 4)
        pen.poly(rt([(0, NECK_Y + 30), (36, NECK_Y + 2), (12, NECK_Y - 2)]), WHITE if kind == "collar" else _shade(col, 1.2), INK, 4)
        for k in range(3):
            pen.dot(_rot((0, NECK_Y + 60 + k * 55), hip, lean), 5, dk)
        if kind == "uniform":
            pen.poly(rt(_rrect(-46, NECK_Y + 70, NECK_Y + 110, 22, 4)), dk, INK, 3)
            pen.dot(_rot((50, NECK_Y + 76), hip, lean), 10, GOLD)
    elif kind in ("suit", "jacket"):
        pen.poly(rt([(-20, NECK_Y + 4), (20, NECK_Y + 4), (8, NECK_Y + 120), (-8, NECK_Y + 120)]), WHITE if kind == "suit" else _shade(col, 1.45))
        pen.line(rt([(-22, NECK_Y + 2), (-6, NECK_Y + 130), (-40, HIP_Y + 10)]), 5)
        pen.line(rt([(22, NECK_Y + 2), (6, NECK_Y + 130), (40, HIP_Y + 10)]), 5)
        if kind == "suit":
            pen.poly(rt([(0, NECK_Y + 10), (10, NECK_Y + 26), (6, NECK_Y + 110), (0, NECK_Y + 122), (-6, NECK_Y + 110), (-10, NECK_Y + 26)]), (140, 30, 40, 255), INK, 3)
        else:
            pen.line(rt([(0, NECK_Y + 130), (0, HIP_Y + 10)]), 4, dk)
    elif kind == "tank":
        pen.line(rt(_ellipse((0, NECK_Y + 4), 40, 30, 10, 170, 12)), 5, dk)
    elif kind in ("coat", "robe"):
        lap = WHITE if kind == "robe" else _shade(col, 0.88)
        pen.poly(rt([(-24, NECK_Y + 2), (24, NECK_Y + 2), (10, NECK_Y + 150), (-10, NECK_Y + 150)]), (120, 160, 200, 255) if kind == "coat" else WHITE)
        pen.line(rt([(-26, NECK_Y), (-4, NECK_Y + 160), (-30, HIP_Y + 18)]), 5)
        pen.line(rt([(26, NECK_Y), (4, NECK_Y + 160), (30, HIP_Y + 18)]), 5)
        pen.poly(rt([(-BODY_W + 4, HIP_Y - 10), (-BODY_W - 18, HIP_Y + 150), (-26, HIP_Y + 150), (-30, HIP_Y + 10)]), col, INK, 5)
        pen.poly(rt([(BODY_W - 4, HIP_Y - 10), (BODY_W + 18, HIP_Y + 150), (26, HIP_Y + 150), (30, HIP_Y + 10)]), col, INK, 5)
        pen.poly(rt(_rrect(50, HIP_Y - 70, HIP_Y - 30, 26, 4)), lap, INK, 3)
    elif kind == "vest":
        pen.poly(rt([(-BODY_W + 8, NECK_Y + 30), (-30, NECK_Y + 10), (-20, HIP_Y + 18), (-BODY_W + 8, HIP_Y + 18)]), _shade(col, 1.0), INK, 4)
        pen.poly(rt([(BODY_W - 8, NECK_Y + 30), (30, NECK_Y + 10), (20, HIP_Y + 18), (BODY_W - 8, HIP_Y + 18)]), _shade(col, 1.0), INK, 4)
        pen.poly(rt([(-20, NECK_Y + 10), (20, NECK_Y + 10), (20, HIP_Y + 18), (-20, HIP_Y + 18)]), (240, 240, 236, 255))
        pen.poly(rt(_rrect(-55, NECK_Y + 90, NECK_Y + 150, 24, 6)), WHITE, INK, 3)
    elif kind == "overalls":
        pen.poly(rt([(-48, NECK_Y + 90), (48, NECK_Y + 90), (52, HIP_Y + 18), (-52, HIP_Y + 18)]), _shade(col, 0.85), INK, 4)
        pen.line(rt([(-40, NECK_Y + 92), (-60, NECK_Y + 4)]), 10, _shade(col, 0.7))
        pen.line(rt([(40, NECK_Y + 92), (60, NECK_Y + 4)]), 10, _shade(col, 0.7))
        pen.poly(rt(_rrect(0, NECK_Y + 120, NECK_Y + 170, 26, 4)), _shade(col, 0.7), INK, 3)
        for k2 in range(5):
            pen.dot(_rot((-40 + k2 * 22, HIP_Y - 40 + (k2 % 2) * 14), hip, lean), 6, (60, 50, 40, 160))
    elif kind == "thai":
        pen.poly(rt(_rrect(0, NECK_Y - 6, NECK_Y + 18, 34, 6)), col, INK, 4)
        pen.line(rt([(0, NECK_Y + 18), (0, HIP_Y + 18)]), 4, dk)
        for k2 in range(5):
            pen.dot(_rot((10, NECK_Y + 50 + k2 * 42), hip, lean), 7, GOLD)
        pen.line(rt([(-BODY_W + 4, HIP_Y - 30), (BODY_W - 4, HIP_Y - 30)]), 6, GOLD_D)
    elif kind == "sabai":
        pen.poly(rt([(-BODY_W + 2, NECK_Y + 40), (-BODY_W + 2, NECK_Y + 4), (BODY_W - 2, NECK_Y + 170), (BODY_W - 2, NECK_Y + 214)]), _shade(col, 1.25), INK, 4)
        pen.line(rt([(-BODY_W + 6, NECK_Y + 22), (BODY_W - 6, NECK_Y + 192)]), 4, GOLD)
        pen.line(rt([(-BODY_W + 4, HIP_Y - 20), (BODY_W - 4, HIP_Y - 20)]), 8, GOLD)
    elif kind == "firecoat":
        pen.poly(rt([(-12, NECK_Y + 2), (12, NECK_Y + 2), (12, HIP_Y + 16), (-12, HIP_Y + 16)]), _shade(col, 0.7))
        for yy in (NECK_Y + 150, HIP_Y - 40):
            pen.poly(rt(_rrect(0, yy - 12, yy + 12, BODY_W - 6, 2)), (230, 220, 60, 255))
            pen.line(rt([(-BODY_W + 8, yy), (BODY_W - 8, yy)]), 6, (225, 230, 235, 255))
    elif kind == "student":
        pen.poly(rt([(0, NECK_Y + 30), (-36, NECK_Y + 2), (-12, NECK_Y - 2)]), WHITE, INK, 4)
        pen.poly(rt([(0, NECK_Y + 30), (36, NECK_Y + 2), (12, NECK_Y - 2)]), WHITE, INK, 4)
        for k2 in range(3):
            pen.dot(_rot((0, NECK_Y + 60 + k2 * 55), hip, lean), 5, dk)
        pen.poly(rt(_rrect(0, HIP_Y - 14, HIP_Y + 18, BODY_W, 6)), (32, 44, 86, 255), INK, 4)
    elif kind == "polo":
        pen.poly(rt([(0, NECK_Y + 26), (-34, NECK_Y + 2), (-10, NECK_Y - 2)]), _shade(col, 1.2), INK, 4)
        pen.poly(rt([(0, NECK_Y + 26), (34, NECK_Y + 2), (10, NECK_Y - 2)]), _shade(col, 1.2), INK, 4)
        for k2 in range(2):
            pen.dot(_rot((0, NECK_Y + 44 + k2 * 26), hip, lean), 5, dk)
    elif kind == "scrubs":
        pen.poly(rt([(-30, NECK_Y + 2), (0, NECK_Y + 60), (30, NECK_Y + 2)]), _shade(col, 0.8), INK, 4)
        pen.poly(rt(_rrect(-44, NECK_Y + 90, NECK_Y + 130, 22, 4)), _shade(col, 0.85), INK, 3)
    elif kind == "raincoat":
        pen.poly(rt([(-12, NECK_Y + 2), (12, NECK_Y + 2), (12, HIP_Y + 30), (-12, HIP_Y + 30)]), _shade(col, 0.85))
        pen.line(rt(_ellipse((0, NECK_Y - 4), 70, 44, 190, 350, 14)), 8, _shade(col, 0.8))
        for k2 in range(4):
            pen.dot(_rot((0, NECK_Y + 40 + k2 * 50), hip, lean), 6, WHITE)
    elif kind == "jersey":
        pen.line(rt(_ellipse((0, NECK_Y + 4), 38, 24, 10, 170, 12)), 7, WHITE)
        pen.poly(rt(_rrect(0, NECK_Y + 70, NECK_Y + 150, 34, 6)), WHITE, None, 0)
        pen.line(rt([(-16, NECK_Y + 84), (16, NECK_Y + 84), (-6, NECK_Y + 140)]), 7, col)
    elif kind == "kimono":
        pen.poly(rt([(-BODY_W + 4, NECK_Y + 6), (-6, NECK_Y + 6), (BODY_W - 10, HIP_Y - 60), (BODY_W - 10, HIP_Y - 30)]), _shade(col, 1.25), INK, 4)
        pen.poly(rt(_rrect(0, HIP_Y - 120, HIP_Y - 60, BODY_W, 4)), (200, 60, 70, 255), INK, 4)
    elif kind == "cardigan":
        pen.poly(rt([(-16, NECK_Y + 2), (16, NECK_Y + 2), (12, HIP_Y + 16), (-12, HIP_Y + 16)]), WHITE)
        for k2 in range(4):
            pen.dot(_rot((-20, NECK_Y + 40 + k2 * 50), hip, lean), 6, _shade(col, 0.6))
    elif kind == "hawaii":
        for k2 in range(7):
            pen.dot(_rot(((-50 + (k2 % 3) * 50), NECK_Y + 40 + k2 * 30), hip, lean), 14, (240, 200, 60, 230))
            pen.dot(_rot(((-50 + (k2 % 3) * 50) + 10, NECK_Y + 46 + k2 * 30), hip, lean), 8, (230, 90, 110, 230))
        pen.poly(rt([(0, NECK_Y + 30), (-36, NECK_Y + 2), (-12, NECK_Y - 2)]), _shade(col, 1.2), INK, 4)
        pen.poly(rt([(0, NECK_Y + 30), (36, NECK_Y + 2), (12, NECK_Y - 2)]), _shade(col, 1.2), INK, 4)
    elif kind == "tracksuit":
        pen.line(rt([(0, NECK_Y + 4), (0, HIP_Y + 16)]), 5, _shade(col, 0.6))
        for sx in (-1, 1):
            pen.line(rt([(sx * (BODY_W - 10), NECK_Y + 30), (sx * (BODY_W - 6), HIP_Y + 10)]), 8, WHITE)
    elif kind == "gown":
        pen.line(rt(_ellipse((0, NECK_Y + 4), 52, 30, 10, 170, 14)), 6, _shade(col, 0.7))
        for k2 in range(6):
            pen.dot(_rot((-40 + k2 * 16, NECK_Y + 30 + (k2 % 2) * 6), hip, lean), 6, (230, 230, 240, 255))
    elif kind == "monk":
        pen.poly(rt([(-BODY_W + 2, NECK_Y + 10), (BODY_W - 2, NECK_Y + 180), (BODY_W - 2, HIP_Y + 20), (-BODY_W + 2, HIP_Y + 20)]), _shade(col, 0.85), INK, 4)
        pen.line(rt([(-BODY_W + 6, NECK_Y + 30), (BODY_W - 6, NECK_Y + 200)]), 5, _shade(col, 0.6))
    elif kind == "dress":
        pen.line(rt(_ellipse((0, NECK_Y + 4), 40, 24, 10, 170, 12)), 5, dk)
        pen.line(rt([(-BODY_W + 6, HIP_Y - 40), (BODY_W - 6, HIP_Y - 40)]), 5, dk)
    else:
        pen.line(rt(_ellipse((0, NECK_Y + 2), 34, 18, 10, 170, 10)), 5, dk)
    ex = set(look["extras"])
    if "apron" in ex:
        pen.poly(rt([(-62, -470), (62, -470), (70, -292), (-70, -292)]), (236, 236, 228, 255), INK, 6)
        pen.poly(rt(_rrect(0, -400, -350, 28, 6)), (220, 220, 210, 255), INK, 3)
        pen.line(rt([(-58, -470), (-30, NECK_Y + 4)]), 5)
        pen.line(rt([(58, -470), (30, NECK_Y + 4)]), 5)
    if "tie" in ex and kind != "suit":
        pen.poly(rt([(0, NECK_Y + 4), (14, NECK_Y + 30), (8, NECK_Y + 140), (0, NECK_Y + 160), (-8, NECK_Y + 140), (-14, NECK_Y + 30)]), (150, 30, 40, 255), INK, 4)
    if "scarf" in ex:
        sc = _hex(look.get("acc_c") or "#c0392b")
        pen.poly(rt(_rrect(0, NECK_Y - 18, NECK_Y + 22, BODY_W - 6, 18)), sc, INK, 5)
        pen.poly(rt([(30, NECK_Y + 10), (58, NECK_Y + 10), (64, NECK_Y + 110), (36, NECK_Y + 110)]), sc, INK, 5)
    if "reflect" in ex and kind != "firecoat":
        for yy in (NECK_Y + 130, HIP_Y - 50):
            pen.poly(rt(_rrect(0, yy - 10, yy + 10, BODY_W - 6, 2)), (226, 232, 90, 255))
    if "lanyard" in ex:
        pen.line(rt([(-30, NECK_Y + 6), (0, NECK_Y + 120), (30, NECK_Y + 6)]), 5, (40, 80, 160, 255))
        pen.poly(rt(_rrect(0, NECK_Y + 118, NECK_Y + 176, 26, 4)), WHITE, INK, 3)
    if "belt" in ex:
        pen.poly(rt(_rrect(0, HIP_Y - 8, HIP_Y + 14, BODY_W - 2, 3)), (40, 30, 24, 255), INK, 3)
        pen.poly(rt(_rrect(0, HIP_Y - 10, HIP_Y + 16, 16, 3)), GOLD, INK, 3)
    if "badge" in ex:
        c = _rot((-48, NECK_Y + 84), hip, lean)
        pen.poly([(c[0] + 22 * math.cos(math.radians(a)) * (1 if k2 % 2 == 0 else 0.45), c[1] + 22 * math.sin(math.radians(a)) * (1 if k2 % 2 == 0 else 0.45))
                  for k2, a in enumerate(range(-90, 270, 36))], GOLD, INK, 3)
    if "nametag" in ex:
        pen.poly(rt(_rrect(46, NECK_Y + 74, NECK_Y + 96, 26, 3)), WHITE, INK, 3)
    if "epaulette" in ex:
        for sx in (-1, 1):
            pen.poly(rt(_rrect(sx * (BODY_W - 26), NECK_Y + 4, NECK_Y + 22, 24, 4)), _shade(col, 0.6), INK, 3)
            pen.dot(_rot((sx * (BODY_W - 26), NECK_Y + 13), hip, lean), 5, GOLD)
    if "stethoscope" in ex:
        pen.line(rt(_ellipse((0, NECK_Y + 10), 44, 70, 10, 170, 14)), 6, (40, 40, 44, 255))
        pen.line(rt([(-30, NECK_Y + 70), (-24, NECK_Y + 150)]), 6, (40, 40, 44, 255))
        pen.dot(_rot((-24, NECK_Y + 156), hip, lean), 12, (180, 184, 190, 255))
    if "necklace" in ex:
        pen.line(rt(_ellipse((0, NECK_Y + 4), 52, 36, 20, 160, 14)), 5, GOLD)
    if "gold_chain" in ex:
        for i, p in enumerate(rt(_ellipse((0, NECK_Y + 2), 58, 52, 15, 165, 16))):
            pen.dot(p, 9 if i % 2 else 7, GOLD)
            pen.dot(p, 3, GOLD_D)
        pen.poly(rt(_rrect(0, NECK_Y + 50, NECK_Y + 84, 16, 5)), GOLD, GOLD_D, 3)


def _limb(pen, a, b, c, w):
    pen.line([a, b, c], w)


def _pants(pen, look, j, far=None):
    kind = look.get("pants") or "long"
    if kind == "none" or look["shirt"] in SKIRTS:
        return
    pw = 40 * BUILD_W[look.get("build") or "normal"][2]
    col = _hex(look.get("pants_c"), dv=(43, 53, 80))
    legs = {}
    for s in "lr":
        hp, kn, ft = j[s + "_hip"], j[s + "_knee"], j[s + "_foot"]
        u = 0.18 if kind == "shorts" else 0.86
        end = (kn[0] + (ft[0] - kn[0]) * u, kn[1] + (ft[1] - kn[1]) * u)
        legs[s] = [(hp[0], hp[1] - 20), kn, end]
    hx = max(abs(j["r_hip"][0]), abs(j["l_hip"][0]))
    seat = _rrect(0, HIP_Y - 40, HIP_Y + 34, hx + pw / 2, 14)
    for s in legs:
        pen.line(legs[s], pw + OUT * 1.4)
    pen.poly(seat, INK, INK, OUT * 1.1)
    for s in legs:
        pen.line(legs[s], pw, _shade(col, 0.82) if s == far else col)
    pen.poly(seat, col)
    pen.line([(0, HIP_Y + 10), (0, HIP_Y + 34)], 4, _shade(col, 0.6))


def _sleeve(pen, look, j, s):
    if look["shirt"] not in ("tee", "uniform", "collar", "hoodie", "suit", "jacket", "coat", "robe", "thai", "firecoat", "student"):
        return
    sho, el = j[s + "_sho"], j[s + "_el"]
    col = _hex(look.get("shirt_c"))
    f = 0.42 if look["shirt"] in ("tee", "uniform", "student") else 0.92
    tip = (sho[0] + (el[0] - sho[0]) * f, sho[1] + (el[1] - sho[1]) * f)
    if look["shirt"] in ("hoodie", "suit", "jacket", "collar", "coat", "robe", "thai", "firecoat"):
        pen.line([sho, el], ARM_W + 18)
        pen.line([sho, el], ARM_W + 8, col)
        hd = j[s + "_hand"]
        cuff = (el[0] + (hd[0] - el[0]) * 0.72, el[1] + (hd[1] - el[1]) * 0.72)
        pen.line([el, cuff], ARM_W + 16)
        pen.line([el, cuff], ARM_W + 6, col)
    else:
        pen.line([sho, tip], ARM_W + 22)
        pen.line([sho, tip], ARM_W + 12, col)


def _arm_extras(pen, look, j, s):
    ex = set(look["extras"])
    el, hd = j[s + "_el"], j[s + "_hand"]
    at = (el[0] + (hd[0] - el[0]) * 0.82, el[1] + (hd[1] - el[1]) * 0.82)
    if s == "l" and "watch" in ex:
        pen.dot(at, 13, INK)
        pen.dot(at, 8, (220, 220, 225, 255))
    if s == "r" and "bracelet" in ex:
        pen.dot(at, 12, GOLD)
        pen.dot(at, 6, INK)
    if s == "r" and "gold_ring" in ex:
        pen.dot(hd, 6, GOLD)


def _hand(pen, h):
    pen.dot(h, ARM_W * 1.05)


def _hair_back(pen, look, hc, tilt):
    hair = look["hair"]
    col = _hex(look.get("hair_c") or "#1b1b1e")
    rt = lambda pts: [_rot(p, hc, tilt) for p in pts]
    cx, cy = hc
    if hair in ("long", "wavy"):
        pts = [(cx - R * 1.1, cy - R * 0.2), (cx + R * 1.1, cy - R * 0.2), (cx + R * 1.02, cy + R * 1.3), (cx - R * 1.02, cy + R * 1.3)]
        if hair == "wavy":
            side = [(cx + R * (1.05 + 0.12 * math.sin(i * 1.4)), cy - R * 0.2 + i * R * 0.25) for i in range(7)]
            pts = side + [(cx - p[0] + cx, p[1]) for p in side[::-1]]
        pen.poly(rt(pts), col, INK, 6)
    elif hair == "bob":
        pen.poly(rt(_rrect(cx, cy - R * 0.9, cy + R * 0.62, R * 1.14, R * 0.6)), col, INK, 6)
    elif hair == "ponytail":
        tail = [(cx + R * 0.7, cy - R * 0.7), (cx + R * 1.45, cy - R * 0.2), (cx + R * 1.38, cy + R * 0.7), (cx + R * 1.05, cy + R * 0.1)]
        pen.poly(rt(tail), col, INK, 6)
    elif hair == "twintail":
        for s in (-1, 1):
            pen.poly(rt([(cx + s * R * 0.85, cy - R * 0.5), (cx + s * R * 1.5, cy - R * 0.1), (cx + s * R * 1.42, cy + R * 0.85), (cx + s * R * 1.0, cy + R * 0.05)]), col, INK, 6)
            pen.dot(_rot((cx + s * R * 0.95, cy - R * 0.5), hc, tilt), R * 0.1, _hex(look.get("acc_c") or "#e84a7a"))
    elif hair == "bun":
        pen.dot(_rot((cx, cy - R * 1.08), hc, tilt), R * 0.36, INK)
        pen.dot(_rot((cx, cy - R * 1.08), hc, tilt), R * 0.36 - 6, col)
    elif hair == "afro":
        ring = [(hc[0] + R * 1.08 * math.cos(math.radians(a)), hc[1] - R * 0.12 + R * 1.02 * math.sin(math.radians(a))) for a in range(0, 360, 24)]
        for c_ in ring:
            pen.dot(c_, R * 0.4 + 6, INK)
        pen.dot((hc[0], hc[1] - R * 0.12), R * 1.08, INK)
        for c_ in ring:
            pen.dot(c_, R * 0.4, col)
        pen.dot((hc[0], hc[1] - R * 0.12), R * 1.08 - 6, col)
        for c_ in ring[::2]:
            pen.line(_ellipse(c_, R * 0.16, R * 0.12, 200, 470, 10), 4, _shade(col, 0.6))


def _hair_front(pen, look, hc, tilt, lk):
    hair = look["hair"]
    col = _hex(look.get("hair_c") or "#1b1b1e")
    rt = lambda pts: [_rot(p, hc, tilt) for p in pts]
    cx, cy = hc
    if hair in ("bald", "afro") or (look["hat"] != "none" and hair in ("short", "messy", "spiky", "side", "mohawk")):
        if hair == "afro" and look["hat"] == "none":
            for i in range(9):
                a = math.radians(190 + i * 20)
                pen.dot(_rot((cx + R * 0.9 * math.cos(a), cy - R * 0.25 + R * 0.75 * math.sin(a)), hc, tilt), R * 0.22, col)
        return
    if hair == "bald_side":
        for s in (-1, 1):
            pen.poly(rt(_ellipse((cx + s * R * 0.92, cy - R * 0.05), R * 0.18, R * 0.34)), col, INK, 4)
        return
    if hair == "mohawk":
        pts = [(cx - R * 0.2, cy - R * 0.85)] + [(cx + (i - 3) * R * 0.08, cy - R * (1.5 if i % 2 else 1.15)) for i in range(7)] + [(cx + R * 0.2, cy - R * 0.85)]
        pen.poly(rt(pts), col, INK, 5)
        return
    if hair in ("bun", "curly"):
        top = _ellipse((cx, cy - R * 0.22), R * 1.04, R * 0.86, 180, 360, 26)
        edge = [(cx + R * 1.0 - i * R * 2.0 / 8, cy - R * (0.3 if i % 2 else 0.18)) for i in range(9)]
        pen.poly(rt(top + edge), col, INK, 5)
        n = 11 if hair == "curly" else 7
        for i in range(n):
            a = math.radians(185 + i * 170 / (n - 1))
            c = _rot((cx + R * 1.0 * math.cos(a), cy - R * 0.2 + R * 0.86 * math.sin(a)), hc, tilt)
            r = R * (0.19 if hair == "curly" else 0.13)
            pen.dot(c, r, INK)
            pen.dot(c, r - 5, col)
        return
    top = _ellipse((cx, cy - R * 0.12), R * 1.05, R * 0.93, 185, 355, 22)
    if hair == "spiky":
        fr = [(cx + R * 1.02 - i * R * 2.04 / 8, cy - R * (0.95 if i % 2 else 0.35)) for i in range(9)]
        top = [(cx + R * 1.04 - i * R * 2.08 / 10, cy - R * (1.25 if i % 2 else 0.95)) for i in range(11)]
        pen.poly(rt(top + fr[::-1][::-1]), col, INK, 5)
        return
    if hair == "side":
        fr = [(cx - R * 0.95, cy - R * 0.22), (cx - R * 0.4, cy - R * 0.52), (cx + R * 0.15, cy - R * 0.62), (cx + R * 0.95, cy - R * 0.2)]
    elif hair in ("long", "wavy", "bob", "ponytail", "twintail"):
        fr = [(cx + R * 0.98, cy - R * 0.05), (cx + R * 0.55, cy - R * 0.45), (cx, cy - R * 0.5), (cx - R * 0.55, cy - R * 0.45), (cx - R * 0.98, cy - R * 0.05)]
    else:
        n = 7
        fr = [(cx + R * 0.95 - i * (R * 1.9 / n) + lk * R * 0.1, cy - R * (0.38 if i % 2 else 0.2) - (R * 0.06 if hair == "messy" else 0)) for i in range(n + 1)]
    pen.poly(rt(top + fr), col, INK, 5)


def _hat(pen, look, hc, tilt, lk):
    hat = look["hat"]
    rt = lambda pts: [_rot(p, hc, tilt) for p in pts]
    cx, cy = hc
    hcol = _hex(look.get("hat_c") or {"cap": "#18181b", "bucket": "#5b6b4a", "beanie": "#7a2f3a", "straw": "#d8b56a", "police": "#1e2c56",
                                       "helmet": "#f2c230", "chef": "#f6f6f2", "ngob": "#cfa860", "fire": "#d8a020", "nurse": "#f6f6f2",
                                       "peaked": "#1e2c56", "beret": "#7a1f2a"}.get(hat, "#222"))
    if hat == "cap":
        pen.poly(rt(_ellipse((cx, cy - R * 0.3), R * 1.0, R * 0.8, 180, 360, 30)), hcol, INK, 5)
        for a0 in (-0.42, 0.42):
            pen.line(rt([(cx + a0 * R * 0.2, cy - R * 1.06), (cx + a0 * R, cy - R * 0.36)]), 3, _shade(hcol, 2.2))
        pen.poly(rt(_ellipse((cx + lk * R * 0.3, cy - R * 0.27), R * 1.14, R * 0.16)), _shade(hcol, 0.6), INK, 4)
        pen.line(rt(_ellipse((cx + lk * R * 0.3, cy - R * 0.29), R * 0.95, R * 0.09, 195, 345, 12)), 3, _shade(hcol, 2.6))
        pen.dot(_rot((cx, cy - R * 1.1), hc, tilt), R * 0.07, _shade(hcol, 1.6))
    elif hat == "bucket":
        pen.poly(rt(_rrect(cx, cy - R * 1.08, cy - R * 0.32, R * 0.86, R * 0.3)), hcol, INK, 5)
        pen.poly(rt(_ellipse((cx, cy - R * 0.3), R * 1.25, R * 0.17)), _shade(hcol, 0.85), INK, 5)
    elif hat == "beanie":
        pen.poly(rt(_ellipse((cx, cy - R * 0.32), R * 1.02, R * 0.85, 180, 360, 28)), hcol, INK, 5)
        pen.poly(rt(_rrect(cx, cy - R * 0.46, cy - R * 0.22, R * 1.04, R * 0.1)), _shade(hcol, 0.8), INK, 5)
        pen.dot(_rot((cx, cy - R * 1.18), hc, tilt), R * 0.16, _shade(hcol, 1.3))
    elif hat == "straw":
        pen.poly(rt(_ellipse((cx, cy - R * 0.36), R * 1.6, R * 0.22)), hcol, INK, 5)
        pen.poly(rt(_ellipse((cx, cy - R * 0.42), R * 0.8, R * 0.62, 180, 360, 22)), hcol, INK, 5)
        pen.line(rt(_ellipse((cx, cy - R * 0.5), R * 0.8, R * 0.1, 0, 180, 10)), 8, (150, 40, 40, 255))
    elif hat == "police":
        pen.poly(rt(_ellipse((cx, cy - R * 0.32), R * 1.08, R * 0.75, 180, 360, 28)), hcol, INK, 5)
        pen.poly(rt(_ellipse((cx, cy - R * 0.3), R * 1.0, R * 0.13)), (14, 16, 22, 255), INK, 4)
        pen.dot(_rot((cx, cy - R * 0.68), hc, tilt), R * 0.13, GOLD)
    elif hat == "helmet":
        pen.poly(rt(_ellipse((cx, cy - R * 0.25), R * 1.1, R * 0.95, 180, 360, 30)), hcol, INK, 5)
        pen.poly(rt(_ellipse((cx, cy - R * 0.24), R * 1.25, R * 0.12)), _shade(hcol, 0.85), INK, 4)
        pen.line(rt([(cx, cy - R * 1.18), (cx, cy - R * 0.36)]), 10, _shade(hcol, 0.8))
    elif hat == "ngob":
        pen.poly(rt([(cx - R * 1.75, cy - R * 0.32), (cx, cy - R * 1.32), (cx + R * 1.75, cy - R * 0.32), (cx, cy - R * 0.2)]), hcol, INK, 5)
        for dx in (-0.9, -0.45, 0.45, 0.9):
            pen.line(rt([(cx, cy - R * 1.28), (cx + dx * R * 1.75, cy - R * 0.36)]), 3, _shade(hcol, 0.7))
    elif hat == "fire":
        pen.poly(rt(_ellipse((cx, cy - R * 0.28), R * 1.1, R * 0.98, 180, 360, 30)), hcol, INK, 5)
        pen.poly(rt(_ellipse((cx, cy - R * 0.22), R * 1.5, R * 0.16)), _shade(hcol, 0.8), INK, 5)
        pen.poly(rt(_rrect(cx, cy - R * 0.98, cy - R * 0.5, R * 0.22, R * 0.04)), (240, 240, 236, 255), INK, 4)
        pen.line(rt([(cx - R * 0.6, cy - R * 0.98), (cx + R * 0.6, cy - R * 0.98)]), 6, _shade(hcol, 0.7))
    elif hat == "nurse":
        pen.poly(rt([(cx - R * 0.6, cy - R * 0.72), (cx - R * 0.5, cy - R * 1.08), (cx + R * 0.5, cy - R * 1.08), (cx + R * 0.6, cy - R * 0.72)]), hcol, INK, 5)
        pen.line(rt([(cx - R * 0.5, cy - R * 0.98), (cx + R * 0.5, cy - R * 0.98)]), 5, (40, 60, 120, 255))
    elif hat == "peaked":
        pen.poly(rt(_ellipse((cx, cy - R * 0.5), R * 1.12, R * 0.42, 180, 360, 26)), hcol, INK, 5)
        pen.poly(rt(_rrect(cx, cy - R * 0.62, cy - R * 0.32, R * 1.0, R * 0.06)), _shade(hcol, 0.75), INK, 4)
        pen.poly(rt(_ellipse((cx + lk * R * 0.3, cy - R * 0.3), R * 1.0, R * 0.12, 0, 180, 16)), (14, 16, 22, 255), INK, 4)
        pen.dot(_rot((cx, cy - R * 0.62), hc, tilt), R * 0.11, GOLD)
    elif hat == "beret":
        pen.poly(rt(_ellipse((cx + R * 0.12, cy - R * 0.62), R * 1.08, R * 0.4)), hcol, INK, 5)
        pen.poly(rt(_rrect(cx, cy - R * 0.42, cy - R * 0.28, R * 0.98, R * 0.05)), _shade(hcol, 0.7), INK, 4)
        pen.dot(_rot((cx - R * 0.45, cy - R * 0.55), hc, tilt), R * 0.1, GOLD)
    elif hat == "hardhat":
        c = _hex(look.get("hat_c") or "#f2c230")
        pen.poly(rt(_ellipse((cx, cy - R * 0.36), R * 1.04, R * 0.9, 180, 360, 30)), c, INK, 5)
        pen.poly(rt(_rrect(cx, cy - R * 0.4, cy - R * 0.26, R * 1.3, R * 0.06)), _shade(c, 0.8), INK, 4)
        pen.line(rt([(cx, cy - R * 1.24), (cx, cy - R * 0.45)]), 7, _shade(c, 0.75))
    elif hat == "crown":
        pts = [(cx - R * 0.8, cy - R * 0.55), (cx - R * 0.8, cy - R * 1.15), (cx - R * 0.4, cy - R * 0.85), (cx, cy - R * 1.3), (cx + R * 0.4, cy - R * 0.85),
               (cx + R * 0.8, cy - R * 1.15), (cx + R * 0.8, cy - R * 0.55)]
        pen.poly(rt(pts), GOLD, INK, 5)
        for dx in (-0.4, 0, 0.4):
            pen.dot(_rot((cx + dx * R, cy - R * 0.68), hc, tilt), R * 0.08, (200, 30, 50, 255))
    elif hat == "cowboy":
        c = _hex(look.get("hat_c") or "#8a5a2a")
        pen.poly(rt(_ellipse((cx, cy - R * 0.5), R * 1.7, R * 0.22)), _shade(c, 0.85), INK, 5)
        pen.poly(rt([(cx - R * 0.75, cy - R * 0.55), (cx - R * 0.7, cy - R * 1.2), (cx, cy - R * 1.05), (cx + R * 0.7, cy - R * 1.2), (cx + R * 0.75, cy - R * 0.55)]), c, INK, 5)
        pen.line(rt([(cx - R * 0.72, cy - R * 0.68), (cx + R * 0.72, cy - R * 0.68)]), 8, _shade(c, 0.5))
    elif hat == "grad":
        pen.poly(rt(_rrect(cx, cy - R * 0.85, cy - R * 0.45, R * 0.8, R * 0.06)), (24, 24, 28, 255), INK, 4)
        pen.poly(rt([(cx - R * 1.3, cy - R * 0.98), (cx, cy - R * 1.28), (cx + R * 1.3, cy - R * 0.98), (cx, cy - R * 0.7)]), (24, 24, 28, 255), INK, 4)
        pen.line(rt([(cx, cy - R * 1.0), (cx + R * 1.0, cy - R * 0.9), (cx + R * 1.05, cy - R * 0.4)]), 5, GOLD)
    elif hat == "santa":
        pen.poly(rt([(cx - R * 0.95, cy - R * 0.5), (cx + R * 0.95, cy - R * 0.5), (cx + R * 1.3, cy - R * 0.9), (cx + R * 0.2, cy - R * 1.45)]), (200, 30, 40, 255), INK, 5)
        pen.poly(rt(_rrect(cx, cy - R * 0.62, cy - R * 0.36, R * 1.02, R * 0.12)), WHITE, INK, 4)
        pen.dot(_rot((cx + R * 1.32, cy - R * 0.86), hc, tilt), R * 0.16, WHITE)
    elif hat in ("hazmat", "furhood"):
        c = _hex(look.get("hat_c") or ("#e8c020" if hat == "hazmat" else "#7a4a2a"))
        ring = _ellipse((cx, cy + R * 0.02), R * 1.02, R * 1.04, 0, 360, 36)
        pen.line(rt(ring), R * 0.42, INK)
        pen.line(rt(ring), R * 0.36, c)
        if hat == "hazmat":
            pen.line(rt(_rrect(cx + lk * R * 0.2, cy - R * 0.62, cy + R * 0.7, R * 0.82, R * 0.3)) + rt(_rrect(cx + lk * R * 0.2, cy - R * 0.62, cy + R * 0.7, R * 0.82, R * 0.3))[:1], 6, (70, 90, 110, 255))
            pen.line(rt([(cx - R * 0.55, cy - R * 0.4), (cx - R * 0.25, cy - R * 0.55)]), 6, (255, 255, 255, 200))
        else:
            for k in range(22):
                a = math.radians(k * 360 / 22)
                pen.dot(rt([(cx + math.cos(a) * R * 0.86, cy + R * 0.02 + math.sin(a) * R * 0.88)])[0], R * 0.13, (242, 238, 228, 255))
    elif hat in ("hijab", "headscarf"):
        c = _hex(look.get("hat_c") or ("#3a4a6a" if hat == "hijab" else "#c0504d"))
        if hat == "hijab":
            for sx in (-1, 1):
                pen.poly(rt([(cx + sx * R * 0.78, cy + R * 0.2), (cx + sx * R * 1.08, cy + R * 0.1), (cx + sx * R * 1.15, cy + R * 1.15), (cx + sx * R * 0.55, cy + R * 1.1)]), c, INK, 4)
            pen.line(rt(_ellipse((cx, cy + R * 0.02), R * 0.98, R * 1.0, 150, 390, 30)), R * 0.36, INK)
            pen.line(rt(_ellipse((cx, cy + R * 0.02), R * 0.98, R * 1.0, 150, 390, 30)), R * 0.3, c)
        else:
            pen.poly(rt(_ellipse((cx, cy - R * 0.25), R * 1.06, R * 0.86, 180, 360, 30)), c, INK, 5)
            pen.poly(rt([(cx + R * 0.9, cy - R * 0.3), (cx + R * 1.25, cy - R * 0.05), (cx + R * 1.05, cy + R * 0.1)]), c, INK, 4)
    elif hat == "party":
        pen.poly(rt([(cx - R * 0.5, cy - R * 0.75), (cx + R * 0.5, cy - R * 0.75), (cx + R * 0.05, cy - R * 1.6)]), (60, 140, 220, 255), INK, 5)
        for k in range(3):
            pen.dot(_rot((cx - R * 0.2 + k * R * 0.2, cy - R * (0.95 + 0.15 * k)), hc, tilt), R * 0.06, (240, 200, 40, 255))
        pen.dot(_rot((cx + R * 0.05, cy - R * 1.62), hc, tilt), R * 0.12, (230, 60, 90, 255))
    elif hat == "visor":
        c = _hex(look.get("hat_c") or "#f2f2f2")
        pen.poly(rt(_rrect(cx, cy - R * 0.62, cy - R * 0.44, R * 1.0, R * 0.06)), c, INK, 4)
        pen.poly(rt(_ellipse((cx + lk * R * 0.3, cy - R * 0.44), R * 1.05, R * 0.16, 0, 180, 16)), _shade(c, 0.8), INK, 4)
    elif hat == "bandana":
        c = _hex(look.get("hat_c") or "#c0392b")
        pen.poly(rt(_ellipse((cx, cy - R * 0.32), R * 1.02, R * 0.78, 180, 360, 28)), c, INK, 5)
        for dx in (-0.5, 0, 0.5):
            pen.dot(_rot((cx + dx * R, cy - R * 0.72), hc, tilt), R * 0.06, WHITE)
        pen.poly(rt([(cx - R * 0.95, cy - R * 0.35), (cx - R * 1.35, cy - R * 0.1), (cx - R * 1.2, cy - R * 0.45)]), c, INK, 4)
    elif hat == "tophat":
        pen.poly(rt(_rrect(cx, cy - R * 1.6, cy - R * 0.5, R * 0.68, R * 0.06)), (24, 24, 28, 255), INK, 5)
        pen.poly(rt(_ellipse((cx, cy - R * 0.5), R * 1.18, R * 0.14)), (24, 24, 28, 255), INK, 4)
        pen.line(rt([(cx - R * 0.68, cy - R * 0.68), (cx + R * 0.68, cy - R * 0.68)]), 9, (150, 30, 40, 255))
    elif hat == "wreath":
        for k in range(9):
            a = math.radians(190 + k * 20)
            pen.dot(_rot((cx + math.cos(a) * R * 0.95, cy - R * 0.2 + math.sin(a) * R * 0.75), hc, tilt), R * 0.14, (90, 150, 70, 255))
            pen.dot(_rot((cx + math.cos(a) * R * 0.95, cy - R * 0.2 + math.sin(a) * R * 0.75), hc, tilt), R * 0.06, (230, 120, 160, 255))
    elif hat == "chef":
        pen.poly(rt(_rrect(cx, cy - R * 0.62, cy - R * 0.26, R * 0.9, R * 0.08)), hcol, INK, 5)
        for dx in (-0.55, 0, 0.55):
            pen.dot(_rot((cx + dx * R, cy - R * 0.98), hc, tilt), R * 0.45, INK)
        for dx in (-0.55, 0, 0.55):
            pen.dot(_rot((cx + dx * R, cy - R * 0.98), hc, tilt), R * 0.45 - 6, hcol)
        pen.poly(rt(_rrect(cx, cy - R * 0.95, cy - R * 0.55, R * 0.9, R * 0.08)), hcol)


def _glasses(pen, look, hc, tilt, lk):
    g = look["glasses"]
    cx, cy = hc[0] + lk * R * 0.22, hc[1] + R * 0.04
    rt = lambda p: _rot(p, hc, tilt)
    if g == "pixel":
        px = R * 0.1
        rows = ["XXXXXXXXXXXXXXXX", ".XWXXXX..XWXXXX.", "..XWXX....XWXX.."]
        x0 = cx - 8 * px
        cy2 = cy + R * 0.02
        for r_, row in enumerate(rows):
            for c_, ch in enumerate(row):
                if ch == ".":
                    continue
                col = WHITE if ch == "W" else (10, 10, 12, 255)
                x, y = x0 + c_ * px, cy2 - 1.5 * px + r_ * px
                e = px * 0.04
                pen.poly([rt((x - e, y - e)), rt((x + px + e, y - e)), rt((x + px + e, y + px + e)), rt((x - e, y + px + e))], col)
        return True
    if g == "sun":
        for s in (-1, 1):
            pen.poly([rt(p) for p in _rrect(cx + s * R * 0.34, cy - R * 0.16, cy + R * 0.16, R * 0.27, R * 0.1)], (16, 16, 20, 255), INK, 4)
            pen.line([rt((cx + s * R * 0.24, cy - R * 0.08)), rt((cx + s * R * 0.38, cy - R * 0.08))], 4, (120, 120, 130, 255))
        pen.line([rt((cx - R * 0.08, cy - R * 0.06)), rt((cx + R * 0.08, cy - R * 0.06))], 5)
        return True
    if g == "round":
        for s in (-1, 1):
            pen.line([rt(p) for p in _ellipse((cx + s * R * 0.33, cy), R * 0.24, R * 0.22)], 5)
        pen.line([rt((cx - R * 0.09, cy)), rt((cx + R * 0.09, cy))], 5)
    elif g == "square":
        for s in (-1, 1):
            pen.line([rt(p) for p in _rrect(cx + s * R * 0.33, cy - R * 0.18, cy + R * 0.18, R * 0.24, R * 0.05)] + [rt((cx + s * R * 0.57, cy - R * 0.13))], 6)
        pen.line([rt((cx - R * 0.09, cy - R * 0.04)), rt((cx + R * 0.09, cy - R * 0.04))], 5)
    elif g == "cateye":
        for s in (-1, 1):
            pts = [(cx + s * R * 0.1, cy - R * 0.08), (cx + s * R * 0.62, cy - R * 0.22), (cx + s * R * 0.55, cy + R * 0.12), (cx + s * R * 0.14, cy + R * 0.14)]
            pen.line([rt(p) for p in pts + [pts[0]]], 6, (120, 30, 60, 255))
    return False


def _face(pen, look, hc, tilt, lk, face, mouth, hide_eyes, blink):
    yaw = float(look.get("_yaw") or 0.0)
    cx, cy = hc[0] + lk * R * 0.22 + yaw * R * 0.3, hc[1]
    rt = lambda p: _rot(p, hc, tilt)
    ex = set(look["extras"])
    if not hide_eyes:
        ey = cy - R * 0.02
        for s in (-1, 1):
            ex_ = cx + s * R * 0.32 * (1 - 0.42 * yaw) - (R * 0.05 * yaw if s < 0 else 0)
            if blink or face in ("cry",):
                pen.line([rt((ex_ - R * 0.08, ey + R * 0.02)), rt((ex_ + R * 0.08, ey + R * 0.02))], 6)
            elif face == "shock":
                pen.dot(rt((ex_, ey)), R * 0.11, WHITE)
                pen.line([rt(p) for p in _ellipse((ex_, ey), R * 0.11, R * 0.11)], 4)
                pen.dot(rt((ex_ + lk * R * 0.03, ey)), R * 0.05, INK)
            else:
                _eye(pen, look, rt, ex_ + lk * R * 0.02, ey, s, face)
        by = cy - R * 0.25
        tilt_b = {"angry": 0.11, "yell": 0.12, "sad": -0.09, "worried": -0.08, "cry": -0.1, "shock": 0, "smug": 0.04}.get(face, 0.0)
        lift = R * 0.08 if face == "shock" else 0
        _brows(pen, look, rt, cx, by, tilt_b, lift, face)
    elif face in ("angry", "yell"):
        vx, vy = hc[0] + R * 0.62, hc[1] - R * 0.62
        for a in (0, 90, 180, 270):
            p1 = _rot((vx + R * 0.05, vy - R * 0.12), (vx, vy), a)
            p2 = _rot((vx + R * 0.05, vy - R * 0.03), (vx, vy), a)
            p3 = _rot((vx + R * 0.13, vy - R * 0.05), (vx, vy), a)
            pen.line([rt(p1), rt(p2), rt(p3)], 6, (210, 30, 40, 255))
    if "freckles" in ex:
        for s in (-1, 1):
            for dx, dy in ((0, 0), (0.07, 0.05), (-0.06, 0.06)):
                pen.dot(rt((cx + s * R * (0.45 + dx), cy + R * (0.2 + dy))), R * 0.018, (170, 110, 80, 255))
    if "mole" in ex:
        pen.dot(rt((cx + R * 0.3, cy + R * 0.5)), R * 0.03, INK)
    if "bandaid" in ex:
        pen.poly([rt(p) for p in _rrect(cx - R * 0.5, cy + R * 0.18, cy + R * 0.3, R * 0.14, R * 0.05)], (236, 196, 150, 255), INK, 3)
    _nose(pen, look, rt, cx, cy, lk)
    _marks(pen, look, rt, cx, cy, ex)
    my = cy + R * 0.45
    style = look["mouth"]
    mc = (196, 40, 52, 255) if ("lipstick" in ex or style == "lips") else INK
    wide = {"small": 0.7, "wide": 1.45}.get(style, 1.0)
    if "mustache" in ex:
        pen.poly([rt(p) for p in [(cx - R * 0.28, my - R * 0.08), (cx - R * 0.1, my - R * 0.17), (cx, my - R * 0.12), (cx + R * 0.1, my - R * 0.17),
                                  (cx + R * 0.28, my - R * 0.08), (cx, my - R * 0.06)]], INK)
    if "beard" in ex:
        bc = _hex(look.get("hair_c") or "#1b1b1e")
        outer = _ellipse((cx, my - R * 0.12), R * 0.62, R * 0.5, 15, 165, 16)
        inner = _ellipse((cx, my - R * 0.02), R * 0.3, R * 0.2, 165, 15, 12)
        pen.poly([rt(p) for p in outer + inner], bc, INK, 4)
    if "blush" in ex or face in ("angry", "yell"):
        for s in (-1, 1):
            pen.dot(rt((cx + s * R * 0.52, cy + R * 0.28)), R * 0.1, (238, 140, 140, 140 if face in ("angry", "yell") else 110))
    big = face in ("shock", "yell")
    lvl = max(int(mouth or 0), 2 if big else 0)
    if lvl:
        rx = R * 0.1 * wide * (1.2 if face == "yell" else 1.0)
        ry = R * (0.06 if lvl == 1 else (0.17 if big else 0.11))
        pen.poly([rt(p) for p in _ellipse((cx, my + ry * 0.3), rx, ry, n=20)], (52, 14, 20, 255), mc, 5)
        if lvl == 2 and not big:
            pen.poly([rt(p) for p in _ellipse((cx, my + ry * 0.75), rx * 0.6, ry * 0.35, 0, 180, 8)], (210, 90, 100, 255))
        if style == "buck":
            pen.poly([rt(p) for p in _rrect(cx, my + ry * 0.3 - ry + 2, my + ry * 0.3 - ry + R * 0.08, R * 0.05, 2)], WHITE, INK, 2)
    elif face == "smile" or style == "gold" and face not in ("angry", "sad", "cry", "worried"):
        pts = [rt(p) for p in _ellipse((cx, my - R * 0.06), R * 0.18 * wide, R * 0.13, 15, 165, 12)]
        if style in ("gold", "buck") or face == "smile":
            pen.poly(pts, WHITE, mc, 5)
            if style == "gold":
                pen.poly([rt(p) for p in _rrect(cx + R * 0.06, my - R * 0.02, my + R * 0.05, R * 0.035, 2)], GOLD, GOLD_D, 2)
            if style == "buck":
                pen.line([rt((cx, my - R * 0.02)), rt((cx, my + R * 0.06))], 3)
            if style == "gap":
                pen.poly([rt(p) for p in _rrect(cx - R * 0.03, my - R * 0.04, my + R * 0.03, R * 0.03, 2)], INK)
        else:
            pen.line(pts, 7, mc)
    elif face == "smug":
        pen.line([rt((cx - R * 0.15 * wide, my + R * 0.02)), rt((cx + R * 0.05, my + R * 0.01)), rt((cx + R * 0.2 * wide, my - R * 0.08))], 7, mc)
    elif face in ("angry", "sad", "cry"):
        pen.line([rt(p) for p in _ellipse((cx, my + R * 0.1), R * 0.16 * wide, R * 0.1, 200, 340, 12)], 7, mc)
    elif face == "worried":
        pen.line([rt((cx - R * 0.16 * wide, my)), rt((cx - R * 0.06, my - R * 0.04)), rt((cx + R * 0.05, my + R * 0.02)), rt((cx + R * 0.16 * wide, my - R * 0.02))], 6, mc)
    else:
        if style == "lips":
            pen.poly([rt(p) for p in _ellipse((cx, my), R * 0.15, R * 0.06)], mc, INK, 3)
        elif style == "pout":
            pen.poly([rt(p) for p in _ellipse((cx, my), R * 0.07, R * 0.06)], (196, 70, 80, 255), INK, 4)
        elif style == "thin":
            pen.line([rt((cx - R * 0.09, my)), rt((cx + R * 0.09, my))], 4, mc)
        else:
            pen.line([rt((cx - R * 0.13 * wide, my)), rt((cx + R * 0.13 * wide, my))], 7, mc)
    if face == "worried":
        d = (hc[0] - R * 0.75, hc[1] - R * 0.3)
        pen.poly([rt(p) for p in [(d[0], d[1] - R * 0.16)] + _ellipse((d[0], d[1]), R * 0.08, R * 0.09, -20, 200, 10)], (120, 190, 240, 255), INK, 3)
    if face == "cry":
        for s in (-1, 1):
            x = cx + s * R * 0.32
            pen.line([rt((x, cy + R * 0.08)), rt((x + s * R * 0.03, cy + R * 0.42))], 7, (110, 180, 240, 255))


def _eye(pen, look, rt, x, y, s, face):
    kind = look.get("eyes") or "oval"
    rx, ry = {"dot": (0.05, 0.05), "round": (0.095, 0.095), "narrow": (0.09, 0.038), "sleepy": (0.08, 0.09), "sharp": (0.09, 0.06), "big": (0.1, 0.14),
              "lashes": (0.075, 0.105)}.get(kind, (0.072, 0.105))
    if face == "smug":
        ry = min(ry, 0.075)
    if kind == "round":
        pen.poly([rt(p) for p in _ellipse((x, y), R * 0.12, R * 0.12, n=18)], WHITE, INK, 4)
        pen.poly([rt(p) for p in _ellipse((x, y + R * 0.01), R * 0.06, R * 0.065, n=14)], INK)
    elif kind == "sharp":
        pts = [(x - s * R * 0.1, y + R * 0.02), (x, y - R * 0.05), (x + s * R * 0.11, y - R * 0.05), (x + s * R * 0.04, y + R * 0.05)]
        pen.poly([rt(p) for p in pts], INK)
    else:
        pen.poly([rt(p) for p in _ellipse((x, y), R * rx, R * ry, n=16)], INK)
    if kind not in ("dot", "narrow"):
        pen.dot(rt((x - R * 0.025, y - R * 0.04)), R * (0.035 if kind == "big" else 0.022), WHITE)
    if kind == "big":
        pen.dot(rt((x + R * 0.03, y + R * 0.04)), R * 0.015, WHITE)
    if kind == "sleepy":
        skin = _hex(look.get("skin") or "#F2F2EE")
        pen.poly([rt(p) for p in _rrect(x, y - R * 0.12, y - R * 0.01, R * 0.11, 2)], skin)
        pen.line([rt((x - R * 0.1, y - R * 0.01)), rt((x + R * 0.1, y - R * 0.01))], 5)
    if kind == "lashes":
        for k in range(3):
            bx = x + s * R * (0.03 + 0.03 * k)
            pen.line([rt((bx, y - R * 0.09)), rt((bx + s * R * 0.05, y - R * 0.15))], 4)


def _brows(pen, look, rt, cx, by, tilt_b, lift, face):
    kind = look.get("brows") or "normal"
    col = _shade(_hex(look.get("hair_c") or "#1b1b1e"), 0.7)
    w = {"thick": 12, "thin": 4, "bushy": 15, "unibrow": 10}.get(kind, 7)
    tb = tilt_b + (0.07 if kind == "sharp" else 0.0)
    pts = []
    for s in (-1, 1):
        inner, outer = (cx + s * R * 0.16, by + tb * R - lift), (cx + s * R * (0.36 if kind == "short" else 0.46), by - tb * R - lift)
        if face == "smug" and s == 1:
            inner, outer = (inner[0], inner[1] - R * 0.08), (outer[0], outer[1] - R * 0.1)
        if kind == "arched":
            mid = ((inner[0] + outer[0]) / 2, min(inner[1], outer[1]) - R * 0.07)
            pen.line([rt(inner), rt(mid), rt(outer)], 6, col)
        elif kind == "bushy":
            pen.line([rt(inner), rt(outer)], w, col)
            for k in range(4):
                u = (k + 0.5) / 4
                p = (inner[0] + (outer[0] - inner[0]) * u, inner[1] + (outer[1] - inner[1]) * u - R * 0.05)
                pen.dot(rt(p), R * 0.035, col)
        else:
            pen.line([rt(inner), rt(outer)], w, col)
        pts.append(inner)
    if kind == "unibrow":
        pen.line([rt(pts[0]), rt(((pts[0][0] + pts[1][0]) / 2, min(pts[0][1], pts[1][1]) + R * 0.02)), rt(pts[1])], w, col)


def _nose(pen, look, rt, cx, cy, lk):
    kind = look.get("nose") or "none"
    x, y = cx + lk * R * 0.12, cy + R * 0.22
    if kind == "dot":
        pen.dot(rt((x, y)), R * 0.03, (60, 50, 50, 255))
    elif kind == "line":
        pen.line([rt((x, y - R * 0.12)), rt((x + R * 0.04, y)), rt((x - R * 0.02, y + R * 0.02))], 4)
    elif kind == "round":
        pen.line([rt(p) for p in _ellipse((x, y), R * 0.07, R * 0.06, 20, 160, 10)], 4)
    elif kind == "big":
        pen.poly([rt(p) for p in _ellipse((x, y - R * 0.01), R * 0.1, R * 0.08, n=16)], _shade(_hex(look.get("skin") or "#F2F2EE"), 0.9), INK, 4)
    elif kind == "hook":
        pen.line([rt((x - R * 0.02, y - R * 0.15)), rt((x + R * 0.08, y + R * 0.01)), rt((x - R * 0.03, y + R * 0.03))], 5)


def _marks(pen, look, rt, cx, cy, ex):
    if "acne" in ex:
        rng = random.Random(len(look.get("hair") or "") * 7 + 3)
        for _ in range(6):
            s = rng.choice((-1, 1))
            pen.dot(rt((cx + s * R * rng.uniform(0.3, 0.6), cy + R * rng.uniform(0.05, 0.35))), R * 0.028, (205, 80, 80, 255))
        pen.dot(rt((cx + R * 0.1, cy - R * 0.5)), R * 0.03, (205, 80, 80, 255))
    if "scar" in ex:
        a, b = (cx + R * 0.18, cy - R * 0.32), (cx + R * 0.48, cy + R * 0.08)
        pen.line([rt(a), rt(b)], 5, (150, 70, 70, 255))
        for k in range(1, 4):
            u = k / 4
            m = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
            pen.line([rt((m[0] - R * 0.04, m[1] + R * 0.03)), rt((m[0] + R * 0.04, m[1] - R * 0.03))], 3, (150, 70, 70, 255))
    if "eyebags" in ex:
        for s in (-1, 1):
            pen.line([rt(p) for p in _ellipse((cx + s * R * 0.32, cy + R * 0.08), R * 0.09, R * 0.05, 20, 160, 8)], 3, (120, 110, 120, 255))
    if "wrinkles" in ex:
        for k in range(2):
            pen.line([rt((cx - R * 0.28, cy - R * (0.5 + k * 0.09))), rt((cx + R * 0.28, cy - R * (0.5 + k * 0.09)))], 3, (150, 140, 140, 255))
        for s in (-1, 1):
            pen.line([rt((cx + s * R * 0.5, cy - R * 0.04)), rt((cx + s * R * 0.6, cy - R * 0.09))], 3, (150, 140, 140, 255))


def _head_extras(pen, look, hc, tilt, lk=0.0):
    ex = set(look["extras"])
    rt = lambda p: _rot(p, hc, tilt)
    fx = hc[0] + lk * R * 0.22 + float(look.get("_yaw") or 0.0) * R * 0.3
    if look.get("_back"):
        ex -= {"soot", "goggles", "gasmask", "face_cloth"}
    if "soot" in ex:
        for dx, dy, r in ((-0.5, 0.3, 0.12), (0.45, -0.4, 0.09), (0.2, 0.55, 0.08)):
            pen.dot(rt((fx + dx * R, hc[1] + dy * R)), R * r, (60, 56, 52, 120))
    if "goggles" in ex or "gasmask" in ex:
        pen.line([rt((fx - R * 0.98, hc[1] - R * 0.05)), rt((fx + R * 0.98, hc[1] - R * 0.05))], 10, (40, 40, 44, 255))
        for s in (-1, 1):
            pen.line([rt(p) for p in _ellipse((fx + s * R * 0.32, hc[1] - R * 0.03), R * 0.2, R * 0.18)], 9, (60, 64, 70, 255))
            pen.line([rt(p) for p in _ellipse((fx + s * R * 0.25, hc[1] - R * 0.1), R * 0.06, R * 0.04, 200, 280, 4)], 3, (255, 255, 255, 230))
    if "gasmask" in ex:
        pen.poly([rt(p) for p in _ellipse((fx, hc[1] + R * 0.45), R * 0.48, R * 0.36)], (58, 62, 68, 255), INK, 5)
        for s in (-1, 1):
            c = rt((fx + s * R * 0.5, hc[1] + R * 0.58))
            pen.dot(c, R * 0.2, INK)
            pen.dot(c, R * 0.15, (110, 116, 124, 255))
            pen.dot(c, R * 0.06, (60, 64, 70, 255))
        pen.dot(rt((fx, hc[1] + R * 0.5)), R * 0.1, (30, 30, 34, 255))
    elif "face_cloth" in ex:
        cc = _hex(look.get("acc_c") or "#b08a5a")
        pen.poly([rt(p) for p in [(fx - R * 0.85, hc[1] + R * 0.15), (fx + R * 0.85, hc[1] + R * 0.15), (fx + R * 0.6, hc[1] + R * 0.78), (fx, hc[1] + R * 0.98), (fx - R * 0.6, hc[1] + R * 0.78)]], cc, INK, 5)
        pen.line([rt((fx - R * 0.5, hc[1] + R * 0.45)), rt((fx + R * 0.5, hc[1] + R * 0.45))], 4, _shade(cc, 0.7))
    if "earrings" in ex:
        for s in (-1, 1):
            pen.dot(rt((hc[0] + s * R * 0.98, hc[1] + R * 0.28)), R * 0.07, GOLD)
            pen.dot(rt((hc[0] + s * R * 0.98, hc[1] + R * 0.28)), R * 0.03, GOLD_D)
    if "headband" in ex and look["hat"] == "none":
        pen.line([rt(p) for p in _ellipse(hc, R * 0.99, R * 0.99, 200, 340, 16)], 14, _hex(look.get("acc_c") or "#e84a7a"))
    if "flower" in ex and look["hat"] == "none":
        c = rt((hc[0] + R * 0.62, hc[1] - R * 0.62))
        for a in range(0, 360, 60):
            pen.dot((c[0] + R * 0.1 * math.cos(math.radians(a)), c[1] + R * 0.1 * math.sin(math.radians(a))), R * 0.08, (240, 110, 150, 255))
        pen.dot(c, R * 0.06, (250, 220, 90, 255))


def _prop(pen, kind, j, side, turn=0):
    h = j[side + "_hand"]
    ang = j[side + "_fore"]
    rt = lambda p, a=ang - 90: _rot(p, h, a)
    if kind == "phone":
        c = (h[0], h[1] - 34)
        pen.poly(_rrect(c[0], c[1] - 48, c[1] + 48, 28, 8), (16, 16, 18, 255), INK, 4)
        pen.poly(_rrect(c[0], c[1] - 40, c[1] + 38, 22, 5), (120, 170, 230, 255))
    elif kind == "selfie":
        tip = (h[0] + 30, h[1] - 150)
        pen.line([h, tip], 8, (70, 70, 74, 255))
        pen.poly(_rrect(tip[0], tip[1] - 50, tip[1] + 30, 26, 7), (16, 16, 18, 255), INK, 4)
        pen.dot((tip[0] + 10, tip[1] - 36), 5, (240, 60, 60, 255))
    elif kind == "plate":
        c = (h[0], h[1] - 10)
        pen.poly(_ellipse(c, 70, 20), WHITE, INK, 4)
        pen.poly(_ellipse((c[0], c[1] - 14), 44, 18, 180, 360, 16), (236, 214, 150, 255), INK, 3)
        pen.poly(_rrect(c[0] + 8, c[1] - 30, c[1] - 12, 26, 6), (240, 196, 130, 255), INK, 3)
    elif kind == "ladle":
        tip = rt((0, -120))
        pen.line([h, tip], 7, (150, 150, 156, 255))
        pen.poly(_ellipse(tip, 22, 16), (190, 190, 196, 255), INK, 4)
    elif kind == "knife":
        tip = rt((0, -110))
        pen.line([h, rt((0, -30))], 12, (90, 60, 40, 255))
        pen.poly([rt((-10, -30)), rt((10, -30)), tip], (210, 214, 220, 255), INK, 3)
    elif kind == "cup":
        c = (h[0], h[1] - 26)
        pen.poly(_rrect(c[0], c[1] - 34, c[1] + 30, 26, 6), WHITE, INK, 4)
        pen.line(_ellipse((c[0] + 28, c[1]), 12, 16, -90, 90, 8), 5)
    elif kind == "paper":
        pen.poly([rt(p, ang - 80) for p in [(h[0] - 40, h[1] - 120), (h[0] + 40, h[1] - 120), (h[0] + 40, h[1] - 6), (h[0] - 40, h[1] - 6)]],
                 (248, 246, 236, 255), INK, 4)
        for k in range(4):
            y = h[1] - 100 + k * 22
            pen.line([rt((h[0] - 26, y), ang - 80), rt((h[0] + 26, y), ang - 80)], 3, (150, 150, 150, 255))
    elif kind == "box":
        c = (h[0], h[1] - 30)
        pen.poly(_rrect(c[0], c[1] - 60, c[1] + 50, 80, 6), (200, 160, 100, 255), INK, 5)
        pen.line([(c[0] - 80, c[1] - 20), (c[0] + 80, c[1] - 20)], 4, (150, 110, 60, 255))
    elif kind == "bag":
        c = (h[0], h[1] + 70)
        pen.poly(_rrect(c[0], c[1] - 50, c[1] + 50, 46, 10), (230, 230, 225, 255), INK, 4)
        pen.line([(c[0] - 20, c[1] - 50), (h[0], h[1]), (c[0] + 20, c[1] - 50)], 4)
    elif kind == "rod":
        tip = (h[0] + 330, h[1] - 360)
        pen.line([h, tip], 7, (110, 80, 50, 255))
        pen.line([tip, (tip[0] + 40, tip[1] + 420)], 2, (230, 230, 230, 255))
        pen.dot((h[0] + 20, h[1] - 18), 14, (60, 60, 64, 255))
    elif kind == "net":
        top = [(h[0] - 70, h[1]), (h[0] + 70, h[1])]
        bot = [(h[0] + 110, h[1] + 260), (h[0] - 110, h[1] + 260)]
        pen.poly(top + bot, (90, 120, 110, 90), INK, 3)
        for k in range(1, 6):
            u = k / 6
            pen.line([(h[0] - 70 - 40 * u, h[1] + 260 * u), (h[0] + 70 + 40 * u, h[1] + 260 * u)], 2, (60, 80, 70, 255))
            pen.line([(h[0] - 70 + 140 * u, h[1]), (h[0] - 110 + 220 * u, h[1] + 260)], 2, (60, 80, 70, 255))
    elif kind == "fish":
        c = (h[0] + 10, h[1] + 70)
        pen.poly(_ellipse(c, 34, 80), (150, 170, 190, 255), INK, 4)
        pen.poly([(c[0], c[1] + 70), (c[0] - 34, c[1] + 120), (c[0] + 34, c[1] + 120)], (150, 170, 190, 255), INK, 4)
        pen.dot((c[0] + 8, c[1] - 50), 6, INK)
    elif kind == "envelope":
        pen.poly([rt(p, ang - 90) for p in [(h[0] - 60, h[1] - 40), (h[0] + 60, h[1] - 40), (h[0] + 60, h[1] + 36), (h[0] - 60, h[1] + 36)]], (238, 226, 196, 255), INK, 4)
        pen.line([rt((h[0] - 60, h[1] - 40), ang - 90), rt((h[0], h[1]), ang - 90), rt((h[0] + 60, h[1] - 40), ang - 90)], 3)
    elif kind not in ("money",) and IT.draw(pen, kind, h, turn):
        pass
    elif kind == "money":
        for k in range(3):
            pen.poly([rt(p, ang - 90 + k * 12) for p in [(h[0] - 50, h[1] - 30), (h[0] + 50, h[1] - 30), (h[0] + 50, h[1] + 20), (h[0] - 50, h[1] + 20)]],
                     (120, 180, 110, 255), INK, 3)


FX = ("vein", "sweat", "tears", "gloom", "sparkle")
FACE_FX = {"yell": "vein", "cry": "tears", "worried": "sweat"}


def _fx(pen, kind, look, hc, tilt, lk, t):
    rt = lambda p: _rot(p, hc, tilt)
    yaw = float(look.get("_yaw") or 0.0)
    cx, cy = hc[0] + lk * R * 0.22 + yaw * R * 0.3, hc[1]
    if kind == "vein":
        k = 1.5 * (1 + 0.18 * max(0.0, math.sin(t * 10)))
        vx, vy = hc[0] + R * 0.72, hc[1] - R * 0.74
        for a in (0, 90, 180, 270):
            p1 = _rot((vx + R * 0.05 * k, vy - R * 0.12 * k), (vx, vy), a)
            p2 = _rot((vx + R * 0.05 * k, vy - R * 0.03 * k), (vx, vy), a)
            p3 = _rot((vx + R * 0.13 * k, vy - R * 0.05 * k), (vx, vy), a)
            pen.line([rt(p1), rt(p2), rt(p3)], 9, (214, 28, 40, 255))
    elif kind == "sweat":
        side = -1 if lk >= 0 else 1
        sx, sy = hc[0] + side * R * 0.98, hc[1] - R * 0.42 + (t * 70) % (R * 0.55)
        pts = [(sx, sy - R * 0.3)] + [(sx + math.cos(math.pi * (-0.18 + 1.36 * j / 14)) * R * 0.13, sy + math.sin(math.pi * (-0.18 + 1.36 * j / 14)) * R * 0.13) for j in range(15)]
        pen.poly([rt(p) for p in pts], (156, 210, 255, 255), INK, 4)
        pen.dot(rt((sx - R * 0.04, sy - R * 0.02)), R * 0.03, WHITE)
    elif kind == "tears":
        ey = cy - R * 0.02 + R * 0.07
        for s_ in (-1, 1):
            ex_ = cx + s_ * R * 0.32 * (1 - 0.42 * yaw)
            pts = [(ex_ + s_ * R * 0.02 * math.sin(t * 9 + j * 0.9) + s_ * j * R * 0.012, ey + j * R * 0.11) for j in range(9)]
            pen.line([rt(p) for p in pts], 14, (110, 180, 245, 235))
            for j in range(2):
                ph = (t * 1.6 + j * 0.5 + (0.25 if s_ > 0 else 0)) % 1.0
                pen.dot(rt((ex_ + s_ * R * (0.15 + ph * 0.6), ey + R * (0.05 + ph * ph * 0.9))), R * 0.05 * (1 - ph * 0.5), (130, 195, 250, 220))
    elif kind == "gloom":
        def paint(d):
            top, bot = pen.P((0, hc[1] - R * 1.05))[1], pen.P((0, hc[1] + R * 0.05))[1]
            d.rectangle([0, top, pen.w, bot], fill=(30, 22, 60, 95))
            for j in range(-5, 6):
                x = pen.P((hc[0] + j * R * 0.18, 0))[0]
                ln = R * (0.55 + 0.25 * math.sin(t * 3 + j * 1.7))
                d.line([(x, top), (x, pen.P((0, hc[1] - R * 1.05 + ln))[1])], fill=(25, 18, 50, 210), width=max(1, int(5 * pen.k)))
        pen.masked(_ellipse(hc, R - OUT, R - OUT), paint)
    elif kind == "sparkle":
        for j, (dx, dy) in enumerate(((1.15, -0.95), (-1.2, -0.55), (1.3, 0.05))):
            tw = 0.35 + 0.65 * abs(math.sin(t * 5 + j * 2.1))
            px, py, r = hc[0] + dx * R, hc[1] + dy * R, R * 0.22 * tw
            star = [(px + math.cos(a * math.pi / 4) * (r if a % 2 == 0 else r * 0.28), py + math.sin(a * math.pi / 4) * (r if a % 2 == 0 else r * 0.28)) for a in range(8)]
            pen.poly(star, (255, 232, 110, 255), (196, 150, 20, 255), 3)
            pen.dot((px, py), r * 0.18, WHITE)


OPEN_HATS = ("none", "visor", "wreath", "crown", "party", "nurse")


def draw(look, pose, face="neutral", mouth=0, scale=1.0, lk=0.0, prop=None, prop_side="r", blink=False, flip=False, back=False, fx=None, t=0.0):
    look = norm_look(look)
    if look.get("hat") not in OPEN_HATS:
        look["hair"] = "bald"
    emote = fx
    yaw = float(pose.get("yaw") or 0.0)
    look["_yaw"] = yaw
    lk = clamp(lk + 0.8 * yaw, -1.25, 1.25)
    if mouth is True:
        mouth = 1
    bw = BUILD_W[look["build"]]
    j = skeleton(dict(pose, _sw=bw[0], _hw=bw[2]))
    pen = Pen(scale)
    hc, tilt = j["head"], j["tilt"]
    far = "r" if yaw > 0.3 else None
    _hair_back(pen, look, hc, tilt)
    if pose.get("seat"):
        _seat(pen, pose["seat"], j)
    for s in ("r", "l") if far else "lr":
        _limb(pen, j[s + "_hip"], j[s + "_knee"], j[s + "_foot"], LEG_W)
        f = j[s + "_foot"]
        fx = 18 if (pose.get("side") or s == "r") else -12
        pen.poly(_ellipse((f[0] + fx, f[1] - 4), 30 if pose.get("side") else 26, 11), INK)
        if s == far:
            _limb(pen, j[s + "_hip"], j[s + "_knee"], j[s + "_foot"], LEG_W - 7)
            pen.line([j[s + "_hip"], j[s + "_knee"], j[s + "_foot"]], LEG_W - 9, (88, 88, 94, 255))
    _pants(pen, look, j, far)
    if far:
        _sleeve(pen, look, j, far)
        _limb(pen, j[far + "_sho"], j[far + "_el"], j[far + "_hand"], ARM_W)
        pen.line([j[far + "_sho"], j[far + "_el"], j[far + "_hand"]], ARM_W - 8, (88, 88, 94, 255))
        _hand(pen, j[far + "_hand"])
    back_arms = str(pose.get("back_arms") or "")
    for s in back_arms:
        if s in "lr" and s != far:
            _sleeve(pen, look, j, s)
            _limb(pen, j[s + "_sho"], j[s + "_el"], j[s + "_hand"], ARM_W)
            _hand(pen, j[s + "_hand"])
    _body(pen, look, pose["lean"])
    over = pose.get("over")
    for s in "lr":
        if s == far or s in back_arms:
            continue
        if s not in (over or ""):
            _sleeve(pen, look, j, s)
            _limb(pen, j[s + "_sho"], j[s + "_el"], j[s + "_hand"], ARM_W)
            if look["shirt"] in ("hoodie", "suit", "jacket", "collar", "coat", "robe", "thai", "firecoat"):
                _sleeve(pen, look, j, s)
            if not pose.get("pocket"):
                _hand(pen, j[s + "_hand"])
            _arm_extras(pen, look, j, s)
    pen.dot(hc, R, INK)
    pen.dot(hc, R - OUT, _hex(look.get("skin") or "#F2F2EE"))
    pen.masked(_ellipse(hc, R - OUT, R - OUT), lambda d: d.ellipse([pen.P((hc[0] + R * 0.35, 0))[0], pen.P((0, hc[1] - R * 1.4))[1],
                                                                       pen.P((hc[0] + R * 2.2, 0))[0], pen.P((0, hc[1] + R * 1.4))[1]], fill=(0, 0, 0, 22)))
    if back:
        if look["hair"] not in ("bald",):
            hcol = _hex(look.get("hair_c") or "#1b1b1e")
            pen.masked(_ellipse(hc, R - OUT, R - OUT), lambda d: d.ellipse([pen.P((hc[0] - R * 1.2, 0))[0], pen.P((0, hc[1] - R * 1.3))[1],
                                                                             pen.P((hc[0] + R * 1.2, 0))[0], pen.P((0, hc[1] + R * 0.55))[1]], fill=hcol))
    else:
        hide = _glasses(pen, look, hc, tilt, lk) if look["glasses"] in ("pixel", "sun") else False
        _face(pen, look, hc, tilt, lk, face, mouth, hide, blink)
        if look["glasses"] in ("round", "square", "cateye"):
            _glasses(pen, look, hc, tilt, lk)
        _hair_front(pen, look, hc, tilt, lk)
    _hat(pen, look, hc, tilt, lk)
    look["_back"] = back
    _head_extras(pen, look, hc, tilt, lk)
    kind = emote if emote in FX else (None if emote == "none" else FACE_FX.get(face))
    if kind and not back:
        _fx(pen, kind, look, hc, tilt, lk, t)
    for ov in [x for x in "lr" if x in (over or "") and x != far]:
        _sleeve(pen, look, j, ov)
        _limb(pen, j[ov + "_sho"], j[ov + "_el"], j[ov + "_hand"], ARM_W)
        if look["shirt"] in ("hoodie", "suit", "jacket", "collar", "coat", "robe", "thai", "firecoat"):
            _sleeve(pen, look, j, ov)
        _hand(pen, j[ov + "_hand"])
    if pose.get("palms"):
        _palms(pen, j)
    for s, g in (pose.get("hands") or {}).items():
        if s in "lr" and s + "_hand" in j:
            _glyph(pen, j, s, g)
    pk = prop or pose.get("prop")
    if pk == "paddle":
        _paddle(pen, j)
    elif pk in PROPS:
        _prop(pen, pk, j, prop_side if pose.get("prop") is None else "r", float(pose.get("prop_rot") or 0))
    im, foot = pen.done()
    if pose.get("legs_only"):
        cut = max(0, int((HIP_Y + 20 - Y0) * scale))
        a = im.getchannel("A")
        a.paste(0, (0, 0, im.width, cut))
        im.putalpha(a)
    roll, drop, lift = (float(pose.get(k) or 0.0) for k in BODY)
    if not roll and not pose.get("walk") and any(pose.get(k) for k in ("drop", "lz", "rz", "ls", "rs")):
        ground = max(j["l_foot"][1], j["r_foot"][1], j["l_knee"][1] - 4, j["r_knee"][1] - 4) + 4
        drop = max(0.0, -ground)
    if roll or drop or lift:
        im, foot = _body_move(im, foot, roll, (drop - lift) * scale, ((0 - X0) * scale, (HIP_Y - Y0) * scale), lift * scale)
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
        foot = (im.width - foot[0], foot[1])
    return im, foot


def _body_move(im, foot, roll, down, hip, lift):
    fx, fy = foot
    if not roll:
        return im, (fx, fy - down)
    cx0, cy0 = im.width / 2, im.height / 2
    im = im.rotate(-roll, resample=Image.BICUBIC, expand=True)
    r = math.radians(roll)
    dx, dy = hip[0] - cx0, hip[1] - cy0
    hx = im.width / 2 + dx * math.cos(r) - dy * math.sin(r)
    bb = im.getchannel("A").getbbox() or (0, 0, im.width, im.height)
    return im, (hx, bb[3] + lift)


def _seat(pen, kind, j):
    hx = (j["l_hip"][0] + j["r_hip"][0]) / 2
    top = HIP_Y + 18
    base = max(j["l_foot"][1], j["r_foot"][1]) + 6
    wood, dark = (150, 104, 62, 255), (110, 74, 42, 255)
    if kind == "stool":
        pen.poly(_rrect(hx, top, top + 26, 95, 8), wood, INK, 5)
        for dx in (-70, 70):
            pen.line([(hx + dx, top + 22), (hx + dx * 1.15, base)], 12, dark)
        return
    if kind == "sofa":
        pen.poly(_rrect(hx, top - 210, top + 40, 230, 40), (150, 60, 60, 255), INK, 5)
        pen.poly(_rrect(hx, top - 10, top + 70, 260, 24), (170, 72, 72, 255), INK, 5)
        for dx in (-210, 210):
            pen.line([(hx + dx, top + 64), (hx + dx, base)], 14, dark)
        return
    if kind == "throne":
        pen.poly(_rrect(hx, top - 330, top + 30, 200, 30), (200, 160, 50, 255), INK, 6)
        pen.poly(_rrect(hx, top - 310, top - 10, 160, 22), (150, 30, 40, 255), INK, 4)
        pen.poly(_rrect(hx, top, top + 50, 220, 12), (200, 160, 50, 255), INK, 5)
        for dx in (-90, 90):
            pen.line([(hx + dx, top + 44), (hx + dx, base)], 16, (170, 130, 40, 255))
        return
    pen.poly(_rrect(hx, top - 260, top + 10, 150, 14), wood, INK, 5)
    pen.poly(_rrect(hx, top, top + 30, 190, 8), wood, INK, 5)
    for dx in (-80, 80):
        pen.line([(hx + dx, top + 26), (hx + dx, base)], 12, dark)


def _glyph(pen, j, s, g):
    h = j[s + "_hand"]
    d = j[s + "_fdir"]
    sx = 1 if s == "r" else -1
    if g == "thumb":
        pen.line([h, (h[0], h[1] - 42)], 13)
        pen.line([h, (h[0], h[1] - 40)], 7, WHITE)
    elif g == "down":
        pen.line([h, (h[0], h[1] + 42)], 13)
        pen.line([h, (h[0], h[1] + 40)], 7, WHITE)
    elif g == "peace":
        for a in (-14, 14):
            tip = (h[0] + math.sin(math.radians(a)) * 46, h[1] - math.cos(math.radians(a)) * 46)
            pen.line([h, tip], 12)
            pen.line([h, tip], 6, WHITE)
    elif g == "point":
        tip = (h[0] + d[0] * 48, h[1] + d[1] * 48)
        pen.line([h, tip], 12)
        pen.line([h, tip], 6, WHITE)
    elif g == "open":
        for a in (-50, -20, 10, 40, 75):
            tip = (h[0] + sx * math.sin(math.radians(a)) * 34 + d[0] * 10, h[1] - math.cos(math.radians(a)) * 34)
            pen.line([h, tip], 9)
    elif g == "ok":
        pen.line(_ellipse((h[0] + sx * 16, h[1] - 22), 16, 16), 8)
        for a in (10, 35, 60):
            pen.line([h, (h[0] + sx * math.sin(math.radians(a)) * 44, h[1] - math.cos(math.radians(a)) * 44)], 8)
    elif g == "heart":
        pen.poly([(h[0], h[1] - 4), (h[0] - 24, h[1] - 30), (h[0] - 12, h[1] - 44), (h[0], h[1] - 34), (h[0] + 12, h[1] - 44), (h[0] + 24, h[1] - 30)], (220, 40, 70, 255), INK, 3)
    elif g == "fist":
        pen.dot(h, ARM_W * 1.6)


def _palms(pen, j):
    a, b = j["r_hand"], j["l_hand"]
    c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 8)
    pts = [(c[0] - 30, c[1] + 26), (c[0] - 26, c[1] - 50), (c[0], c[1] - 110), (c[0] + 26, c[1] - 50), (c[0] + 30, c[1] + 26)]
    pen.poly(pts, WHITE, INK, 6)
    pen.line([(c[0], c[1] - 80), (c[0], c[1] + 18)], 3)


def _paddle(pen, j):
    up, lo = sorted((j["l_hand"], j["r_hand"]), key=lambda h: h[1])
    dx, dy = lo[0] - up[0], lo[1] - up[1]
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    top = (up[0] - ux * 60, up[1] - uy * 60)
    neck = (lo[0] + ux * 230, lo[1] + uy * 230)
    tip = (neck[0] + ux * 190, neck[1] + uy * 190)
    wood, dark = (176, 128, 74, 255), (120, 84, 46, 255)
    pen.line([top, neck], 13, INK)
    pen.line([top, neck], 7, wood)
    px, py = -uy, ux
    blade = [(neck[0] + px * 22, neck[1] + py * 22), (neck[0] + px * 44 + ux * 40, neck[1] + py * 44 + uy * 40), (tip[0] + px * 40, tip[1] + py * 40),
             (tip[0] + ux * 22, tip[1] + uy * 22), (tip[0] - px * 40, tip[1] - py * 40), (neck[0] - px * 44 + ux * 40, neck[1] - py * 44 + uy * 40),
             (neck[0] - px * 22, neck[1] - py * 22)]
    pen.poly(blade, wood, INK, 6)
    pen.line([(neck[0] + ux * 30, neck[1] + uy * 30), (tip[0] - ux * 10, tip[1] - uy * 10)], 4, dark)
    for h in (up, lo):
        _hand(pen, h)


def item_image(kind, scale):
    pen = Pen(scale)
    _prop(pen, kind, {"r_hand": (0.0, -40.0), "r_fore": 90.0}, "r")
    return pen.done()


def blinking(t, seed):
    period = 3.4 + (seed * 7.3) % 1.9
    ph = (t + seed * 1.37) % period
    return ph < 0.11


def walk_side(t, seed=0.0, talking=False):
    ph = 2 * math.pi * t + seed * 2.1
    sn, cs = math.sin(ph), math.cos(ph)
    th = 23 * sn
    p = resolve("stand")
    p.update({"side": 1, "yaw": 1.0, "rl": th, "ll": -th, "rk": 4 + 34 * max(0.0, cs) ** 1.5, "lk": 4 + 34 * max(0.0, -cs) ** 1.5,
              "ra": -22 * sn, "la": 22 * sn, "re": -18 - 8 * max(0.0, sn), "le": -18 - 8 * max(0.0, -sn), "lean": 4 + 1.5 * abs(cs),
              "head": clamp(-2 + 2 * abs(cs) + (1.3 * math.sin(2 * math.pi * t * 1.7) if talking else 0), -16, 16)})
    return p, 7 * abs(cs)


STRIDE = 520.0
RUN_STRIDE = 640.0
GAITS = ("walk_side", "run_side")
FALLS = {"fall_back": -1, "slip": -1, "knocked_out": -1, "fall_forward": 1, "trip": 1, "fall_sit": -1}
FALL_REACH = {"fall_sit": 300.0}
FALL_A, FALL_B, FALL_END = 0.34, 0.5, 1.3


def run_side(t, seed=0.0, talking=False):
    ph = 2 * math.pi * t + seed * 2.1
    sn, cs = math.sin(ph), math.cos(ph)
    th = 34 * sn
    p = resolve("stand")
    p.update({"side": 1, "yaw": 1.0, "rl": th, "ll": -th, "rk": 10 + 75 * max(0.0, cs) ** 1.3, "lk": 10 + 75 * max(0.0, -cs) ** 1.3,
              "ra": -38 * sn, "la": 38 * sn, "re": -78 - 10 * max(0.0, sn), "le": -78 - 10 * max(0.0, -sn), "lean": 13 + 2 * abs(cs),
              "head": clamp(-5 + 3 * abs(cs) + (1.3 * math.sin(2 * math.pi * t * 1.7) if talking else 0), -16, 16)})
    return p, 14 * abs(cs)


def fall_slide(name, since):
    d = FALLS.get(name)
    if not d or since >= FALL_END or since <= 0:
        return 0.0 if not d or since <= 0 else d * 200.0
    s = clamp(since / (FALL_A + FALL_B), 0.0, 1.0)
    return d * 200.0 * (1 - (1 - s) ** 2)


def fall_fit(name, x, unit, lo, hi, facing):
    if name in ("fall_back", "slip", "knocked_out") and fall_room(name, x, unit, lo, hi, facing) < 0.35:
        return "fall_sit"
    return name


def fall_room(name, x, unit, lo, hi, facing):
    d = FALLS.get(name)
    if not d:
        return 1.0
    dirn = d * facing
    reach = FALL_REACH.get(name, 780.0) * unit
    room = (x - lo - reach) if dirn < 0 else (hi - x - reach)
    return clamp(room / (200.0 * unit), 0.0, 1.0)


def _fall(pose_name, extra, prev, since, seed):
    d = FALLS[pose_name]
    a, b = resolve(prev), resolve(pose_name, extra)
    s = max(0.0, since)
    w = 2 * math.pi * s
    stag = blend(a, resolve("stand"), 0.7)
    stag.update({"lean": 16.0 * d, "head": clamp(-14.0 * d, *LIMITS["head"]),
                 "ra": clamp(118 + 34 * math.sin(w * 3.1), *LIMITS["ra"]), "la": clamp(140 + 30 * math.sin(w * 3.1 + 1.7), *LIMITS["la"]),
                 "re": 30 + 25 * math.sin(w * 2.7), "le": 20 - 25 * math.sin(w * 2.9), "rl": 20 * math.sin(w * 2.6), "ll": -20 * math.sin(w * 2.6),
                 "rk": 14 + 12 * max(0.0, math.sin(w * 2.6)), "lk": 14 + 12 * max(0.0, -math.sin(w * 2.6)), "roll": 0.0, "drop": 0.0, "lift": 0.0})
    for k in ("rh", "lh", "hands", "gesture", "seat", "back_arms", "pocket"):
        stag.pop(k, None)
    bob = 0.0
    if s < FALL_A:
        k = s / FALL_A
        p = blend(a, stag, 1 - (1 - k) ** 3)
        bob = 10 * math.sin(math.pi * k)
    elif s < FALL_A + FALL_B:
        k = ((s - FALL_A) / FALL_B) ** 2
        p = blend(stag, b, k)
        p["roll"] = float(b.get("roll") or 0.0) * k
    else:
        e = s - FALL_A - FALL_B
        p = dict(b)
        damp = math.exp(-8.0 * e)
        p["roll"] = float(b.get("roll") or 0.0) * (1 + 0.07 * damp * math.cos(24 * e))
        for k2, ph in (("ra", 0.0), ("la", 1.3), ("rl", 0.6), ("ll", 2.0)):
            p[k2] = clamp(p[k2] + 16 * damp * math.sin(26 * e + ph), *LIMITS[k2])
        p["head"] = clamp(p["head"] + 8 * damp * math.sin(30 * e), *LIMITS["head"])
        bob = 16 * math.exp(-11.0 * e) * abs(math.sin(19 * e))
    return p, bob


def animate(pose_name, t, talking=False, extra=None, seed=0.0, prev=None, since=99.0):
    if pose_name == "walk_side":
        return walk_side(t, seed, talking)
    if pose_name == "run_side":
        return run_side(t, seed, talking)
    if pose_name in FALLS and prev and prev != pose_name and since < FALL_END:
        return _fall(pose_name, extra, prev, since, seed)
    if pose_name == "row":
        w = math.sin(2 * math.pi * t * 0.55 + seed)
        extra = dict({"ra": 62 - 30 * w, "re": -150, "la": 58 - 20 * w, "le": 90 - 6 * w, "lean": -4 + 3 * w}, **(extra or {}))
    p = resolve(pose_name, extra)
    dip = 0.0
    if prev and prev != pose_name and since < 0.7:
        p = blend(resolve(prev), p, spring(since), spring(since - 0.09))
        dip = 7.0 * math.sin(math.pi * clamp(since / 0.28, 0.0, 1.0))
    ph = seed * 1.7
    br = math.sin(2 * math.pi * t / 3.6 + ph)
    p["head"] = clamp(p["head"] + 1.2 * math.sin(2 * math.pi * t / 5.1 + ph) + (1.3 * math.sin(2 * math.pi * t * 1.7) if talking else 0), *LIMITS["head"])
    p["lean"] = clamp(p["lean"] + 0.6 * br, *LIMITS["lean"])
    for s in "lr":
        p[s + "a"] = clamp(p[s + "a"] + 1.3 * math.sin(2 * math.pi * t / 3.3 + ph + (0.9 if s == "l" else 0)), *LIMITS[s + "a"])
    g = p.get("gesture")
    if talking and g in ("r", "l"):
        p[g + "e"] = clamp(p[g + "e"] + 10 * math.sin(2 * math.pi * t * 1.05), *LIMITS[g + "e"])
        p[g + "a"] = clamp(p[g + "a"] + 4 * math.sin(2 * math.pi * t * 0.55), *LIMITS[g + "a"])
    if g == "w":
        p["re"] = clamp(p["re"] + 20 * math.sin(2 * math.pi * t * 1.6), *LIMITS["re"])
    if p.get("shake"):
        p["lean"] = clamp(p["lean"] + 1.8 * math.sin(2 * math.pi * t * 6), *LIMITS["lean"])
    for k, amp, hz, ph0 in p.get("osc") or ():
        v = amp * math.sin(2 * math.pi * (t * hz + ph0))
        if k in LIMITS:
            p[k] = clamp(p[k] + v, *LIMITS[k])
        else:
            p[k] = float(p.get(k) or 0.0) + v
    if not (p.get("walk") or p.get("seat") or p.get("drop") or p.get("lz") or p.get("side")):
        ws = math.sin(2 * math.pi * t / 4.7 + ph * 1.3)
        p["lean"] = clamp(p["lean"] + 1.4 * ws, *LIMITS["lean"])
        bend = "lk" if ws > 0 else "rk"
        p[bend] = clamp(p[bend] + 6.0 * abs(ws) ** 2, *LIMITS[bend])
    bob = 2.5 * br - dip
    if p.get("hop"):
        bob += float(p["hop"]) * abs(math.sin(2 * math.pi * t * 1.4 + ph))
    if p.get("walk"):
        ph2 = 2 * math.pi * t * 1.7 + ph * 2.1
        w = math.sin(ph2)
        up_l, up_r = max(0.0, w) ** 1.4, max(0.0, -w) ** 1.4
        p["ll"], p["rl"] = clamp(4 + 4 * up_l, -12, 40), clamp(4 + 4 * up_r, -12, 40)
        p["lk"], p["rk"] = clamp(10 * up_l, -5, 60), clamp(10 * up_r, -5, 60)
        p["lz"], p["rz"] = 0.6 * up_l, 0.6 * up_r
        p["la"], p["ra"] = clamp(8 + 3 * up_r, -40, 178), clamp(8 + 3 * up_l, -40, 178)
        p["le"], p["re"] = -10 - 16 * up_r, -10 - 16 * up_l
        p["lean"] = clamp(p["lean"] + 2.2 * w, -14, 14)
        p["head"] = clamp(p["head"] - 1.5 * w, -16, 16)
        bob = 6 * (1 - abs(math.cos(ph2)))
    return p, bob


PALETTE = ("#b0563f", "#3f6fb0", "#4f8a5a", "#9a7a3f", "#7a4f9a", "#c0392b", "#2e7d7a", "#d08a2e", "#5a5f6e", "#8a4a6a", "#e2c35a", "#6a8fc0",
           "#3a5a40", "#a4473f", "#e07a9a", "#f0efe8", "#2b2d42", "#8d99ae")


def random_look(rng, used=(), female=None):
    for _ in range(40):
        f = rng.random() < 0.5 if female is None else female
        hair = rng.choice(("bob", "ponytail", "twintail", "long", "wavy", "bun", "curly") if f else ("short", "messy", "spiky", "side", "mohawk", "bald", "bald_side", "afro", "curly"))
        l = {"hair": hair, "hair_c": rng.choice(("#1b1b1e", "#3a2a1c", "#5a3b22", "#7a7a80", "#c9a14a", "#8a2b2b", "#2c3e66")),
             "hat": rng.choice(("none",) * 9 + ("bucket", "beanie", "straw", "helmet", "chef")),
             "glasses": rng.choice(("none",) * 4 + ("round", "square", "sun", "cateye" if f else "square")),
             "shirt": rng.choice(("tee", "tee", "hoodie", "collar", "jacket", "tank") + (("dress", "dress") if f else ("suit",))),
             "shirt_c": rng.choice(PALETTE),
             "pattern": rng.choice(("none",) * 9 + ("stripe", "dots", "floral", "check")),
             "mouth": rng.choice(("normal", "normal", "small", "wide", "buck", "gold", "thin", "gap") + (("lips", "lips", "pout") if f else ())),
             "brows": rng.choice(BROWS), "eyes": rng.choice(EYES if f else tuple(x for x in EYES if x != "lashes")),
             "nose": rng.choice(("none", "none") + NOSES[1:]),
             "extras": rng.sample([x for x in FACE_EXTRAS if x not in ("beard", "mustache")] if f else [x for x in FACE_EXTRAS if x not in ("lipstick", "earrings", "flower", "headband")],
                                  rng.randint(0, 3))}
        l["build"] = rng.choice(("normal",) * 4 + ("fat", "fat", "thin", "thin"))
        l["pants"] = rng.choice(("long",) * 5 + ("shorts",))
        sig = signature(l)
        if sig not in used:
            return l
    return l


def signature(look):
    l = norm_look(look)
    return "|".join([l["hair"], l["hat"], l["glasses"], l["shirt"], str(l.get("shirt_c") or "")[:4], l["mouth"], l["brows"], l["eyes"], l["nose"]])
