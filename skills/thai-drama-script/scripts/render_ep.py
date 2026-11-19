import argparse
import asyncio
import hashlib
import importlib.util
import json
import math
import random
import re
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import cv2
import numpy as np
from PIL import Image, ImageDraw

import drama_rig as G
import matcher as M
import phone_ui as P
import scene_kit as SK
import textkit as T

W, H = 1080, 1920
SR = 24000
FRAMES = {"wide": (0.74, 1560), "medium": (0.98, 1640), "close": (1.62, 1950), "ots": (1.08, 1700)}
POS_X = {"left": 300, "center": 540, "right": 780}
FACE_MAP = {"happy": "smile", "scared": "shock", "tired": "sad", "disgust": "angry", "confused": "worried", "sly": "smug"}
VOICES = {"man": ("th-TH-NiwatNeural", "+0Hz", "+0%"), "oldman": ("th-TH-NiwatNeural", "-12Hz", "-10%"), "boy": ("th-TH-NiwatNeural", "+22Hz", "+8%"),
          "woman": ("th-TH-PremwadeeNeural", "+0Hz", "+0%"), "oldwoman": ("th-TH-PremwadeeNeural", "-10Hz", "-6%"), "girl": ("th-TH-PremwadeeNeural", "+18Hz", "+8%"),
          "system": ("th-TH-NiwatNeural", "+6Hz", "+12%")}
GAP, TAIL, MIN_SHOT = 0.16, 0.35, 1.8


def ffmpeg_bin():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit("ffmpeg not found: run scripts/doctor.py --install")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def clean_tts(t):
    t = re.sub(r"[“”\"'`*_#\[\]]", "", str(t or ""))
    return re.sub(r"\s+", " ", t.replace("…", " ").replace("...", " ")).strip()


class Cast:
    def __init__(self, series):
        self.by = {c["id"]: c for c in series.get("cast") or [] if "id" in c}
        self.looks, used = {}, set()
        for cid, c in self.by.items():
            rig = c.get("rig") if isinstance(c.get("rig"), dict) else {}
            seed = int(hashlib.md5(cid.encode()).hexdigest(), 16) % 10 ** 8
            look = G.random_look(random.Random(seed), used, female=str(c.get("sex", "")).lower().startswith("f"))
            look.update({k: v for k, v in rig.items() if k != "outfit" and v not in (None, "")})
            if rig.get("outfit") in G.OUTFITS:
                look = G.apply_outfit(look, rig["outfit"])
            used.add(G.signature(look))
            self.looks[cid] = look
        if "hero" not in self.looks:
            self.looks["hero"] = G.random_look(random.Random(7), used, female=False)

    def name(self, cid):
        if cid in ("hero", "narration"):
            return "ผม"
        return (self.by.get(cid) or {}).get("name") or cid

    def voice(self, cid):
        if cid == "system":
            return VOICES["system"]
        if cid in ("narration", "hero"):
            v = VOICES.get((self.by.get("hero") or {}).get("voice"), VOICES["man"])
            return (v[0], v[1], "-3%") if cid == "narration" else v
        c = self.by.get(cid)
        if c:
            return VOICES.get(c.get("voice"), VOICES["woman" if str(c.get("sex", "")).startswith("f") else "man"])
        k = int(hashlib.md5(str(cid).encode()).hexdigest(), 16)
        return VOICES[("woman", "man", "girl", "oldman", "boy", "oldwoman")[k % 6]]


def segments(shot, cast, idx):
    t, ui, d = shot.get("type"), shot.get("ui"), shot.get("data") or {}
    out = []

    def add(who, text, sub=True, reveal=None):
        if str(text or "").strip():
            out.append({"who": who, "text": str(text).strip(), "sub": sub, "reveal": reveal})
    if t == "scene":
        add(shot.get("say") or "narration", shot.get("line"))
    elif t == "card":
        add("narration", shot.get("line"))
    elif t == "phone":
        if ui == "chat":
            add("narration", shot.get("line"), reveal=0)
            for k, m in enumerate(d.get("msgs") or []):
                add("hero" if m.get("me") else (m.get("from") or m.get("name") or "other"), m.get("text"), False, k + 1)
        elif ui == "post":
            add("narration", shot.get("line"), reveal=0)
            add(d.get("author") or "other", d.get("text"), False, 0)
            for k, c in enumerate(d.get("comments") or []):
                add(c.get("name") or "other", c.get("text"), False, k + 1)
        elif ui == "forum":
            add("narration", shot.get("line"), reveal=0)
            add("hero" if d.get("me") else (d.get("author") or "other"), d.get("text"), False, 0)
            for k, a in enumerate(d.get("answers") or []):
                add(a.get("name") or "other", a.get("text"), False, k + 1)
        elif ui == "live":
            add(d.get("host") or "narration", shot.get("line"))
        elif ui == "system":
            add("system", shot.get("line"))
        else:
            add("narration", shot.get("line"))
    for s in out:
        s["shot"] = idx
    return out


async def _synth_all(items, outdir):
    import edge_tts
    sem = asyncio.Semaphore(4)

    async def one(it):
        p = outdir / f"{it['key']}.mp3"
        if p.exists() and p.stat().st_size > 800:
            return
        async with sem:
            for k in range(4):
                try:
                    await edge_tts.Communicate(it["tts"], it["voice"], rate=it["rate"], pitch=it["pitch"]).save(str(p))
                    if p.exists() and p.stat().st_size > 800:
                        return
                except Exception as ex:
                    err = ex
                await asyncio.sleep(1.5 * (k + 1))
            raise RuntimeError(f"edge-tts failed for: {it['tts'][:40]} ({err})")
    await asyncio.gather(*(one(it) for it in items))


def decode(ff, path):
    r = subprocess.run([ff, "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0
    nz = np.nonzero(np.abs(a) > 0.01)[0]
    if len(nz):
        a = a[max(0, nz[0] - int(0.03 * SR)):min(len(a), nz[-1] + int(0.08 * SR))]
    return a


def voice_track(segs, cast, work, ff, mute, log):
    items = []
    for k, s in enumerate(segs):
        v, pitch, rate = cast.voice(s["who"])
        tts = clean_tts(s["text"])
        key = hashlib.md5(f"{v}|{pitch}|{rate}|{tts}".encode()).hexdigest()[:16]
        s["key"] = key
        items.append({"key": key, "tts": tts, "voice": v, "pitch": pitch, "rate": rate})
    audio = {}
    if not mute:
        try:
            work.mkdir(parents=True, exist_ok=True)
            uniq = list({it["key"]: it for it in items}.values())
            log(f"voice: {len(uniq)} lines with edge-tts")
            asyncio.run(_synth_all(uniq, work))
            for it in uniq:
                audio[it["key"]] = decode(ff, work / f"{it['key']}.mp3")
        except Exception as ex:
            log(f"WARNING voice failed, rendering silent with estimated timing: {str(ex)[:200]}")
            audio = {}
    for s in segs:
        a = audio.get(s["key"])
        if a is None or len(a) < SR * 0.2:
            a = np.zeros(int(SR * max(1.0, len(s["text"]) / 12.0)), np.float32)
            s["silent"] = True
        s["pcm"] = a
        s["dur"] = len(a) / SR


def mouth_levels(s, fps):
    a = s["pcm"]
    n = max(1, int(s["dur"] * fps))
    if s.get("silent"):
        return [1 + (k // 3) % 2 if (k // 2) % 3 else 0 for k in range(n)]
    hop = len(a) / n
    rms = np.array([float(np.sqrt(np.mean(a[int(k * hop):int((k + 1) * hop)] ** 2) + 1e-9)) for k in range(n)])
    peak = max(1e-4, float(np.percentile(rms, 95)))
    r = rms / peak
    return [2 if v > 0.62 else (1 if v > 0.22 else 0) for v in r]


def build_bg(place, sdir, log):
    bgdir = sdir / "bg"
    png, py = bgdir / f"{place['id']}.png", bgdir / f"{place['id']}.py"
    if png.exists() and (not py.exists() or png.stat().st_mtime >= py.stat().st_mtime):
        return png
    img = None
    if py.exists():
        spec = importlib.util.spec_from_file_location(f"bg_{place['id']}", py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        img = mod.draw()
        if isinstance(img, tuple):
            img = img[0]
        log(f"background {place['id']}: drawn from {py.name}")
    else:
        txt = f"{place.get('id', '')} {place.get('name', '')} {place.get('image_prompt', '')}".lower()
        key = "garage" if any(k in txt for k in ("garage", "อู่", "repair", "mechanic", "workshop")) else (
            "rented_room" if any(k in txt for k in ("room", "ห้อง", "home", "บ้าน", "bedroom", "condo", "apartment", "house")) and not any(k in txt for k in ("market", "ตลาด")) else "market")
        img = SK.PRESETS[key](seed=int(hashlib.md5(place["id"].encode()).hexdigest(), 16) % 997)[0]
        log(f"background {place['id']}: no bg/{place['id']}.png or .py, used preset '{key}' (draw a custom one for a better look)")
    img = np.asarray(img)
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
    bgdir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(png)
    return png


def blend(fr, im, x, y, light=1.0):
    bb = im.getchannel("A").getbbox()
    if not bb:
        return
    im = im.crop(bb)
    x, y = x + bb[0], y + bb[1]
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    x0, y0 = int(round(x)), int(round(y))
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    sub = a[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    al = sub[..., 3:4] / 255.0
    rgb = sub[..., :3] * light
    dst = fr[fy0:fy1, fx0:fx1].astype(np.float32)
    fr[fy0:fy1, fx0:fx1] = (dst * (1 - al) + rgb * al).astype(np.uint8)


def layout(chars, sc):
    out = [dict(c) for c in chars]
    gap = 330 * sc
    for c in out:
        c["x"] = float(POS_X.get(c.get("pos"), 540))
    order = sorted(range(len(out)), key=lambda k: out[k]["x"])
    xs = [out[k]["x"] for k in order]
    for j in range(1, len(xs)):
        xs[j] = max(xs[j], xs[j - 1] + gap)
    if xs:
        sh = sum(out[k]["x"] for k in order) / len(xs) - sum(xs) / len(xs)
        sh = max(140 - xs[0], min(W - 140 - xs[-1], sh))
        xs = [x + sh for x in xs]
    for k, x in zip(order, xs):
        out[k]["x"] = x
    return out


def pick_pose(c):
    for v in (c.get("pose"), c.get("action")):
        if v and str(v) in G.POSES:
            return str(v)
    for v in (c.get("pose"), c.get("action")):
        if v:
            p = M.near(v, G.POSES, "")
            if p:
                return p
    return "stand"


def pick_prop(c):
    v = c.get("prop")
    if not v or v == "none":
        return None
    return v if v in G.PROPS else (M.near(v, G.PROPS, None))


LOCO = {"walk": "walk", "march": "walk", "limp": "walk", "skip": "walk", "jog": "run", "run": "run", "run_scared": "run"}


def pick_then(c):
    v = c.get("then")
    if not v or v == "none":
        return ""
    return str(v) if str(v) in G.POSES else M.near(v, G.POSES, "")


def glide(f):
    f = max(0.0, min(1.0, f))
    return f / 0.9 if f < 0.8 else 0.8 / 0.9 + (0.1 / 0.9) * (1 - (1 - (f - 0.8) / 0.2) ** 2)


def ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


class Renderer:
    def __init__(self, series, ep, sdir, cast, fps, log):
        self.series, self.ep, self.sdir, self.cast, self.fps, self.log = series, ep, sdir, cast, fps, log
        self.places = {p["id"]: p for p in series.get("places") or []}
        self.bgs = {}
        self.last_scene = None
        self.last_pose = {}
        self.seed = {cid: (int(hashlib.md5(cid.encode()).hexdigest(), 16) % 1000) / 100 for cid in list(cast.looks)}

    def bg(self, pid):
        if pid not in self.bgs:
            place = self.places.get(pid) or {"id": pid or "place", "name": pid or ""}
            img = cv2.cvtColor(cv2.imread(str(build_bg(place, self.sdir, self.log))), cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
            luma = float(img.reshape(-1, 3).mean(axis=0) @ [0.299, 0.587, 0.114])
            self.bgs[pid] = (img, max(0.74, min(1.0, 0.55 + luma / 255 * 0.75)))
        return self.bgs[pid]

    def motion(self, shot, chars):
        place = shot.get("place")
        solo = shot.get("frame") in ("close", "ots")
        for c in chars:
            key = (place, c["id"])
            was = self.last_pose.get(key)
            pose, then = c["_pose"], c["_then"]
            m, mt = LOCO.get(pose), LOCO.get(then)
            c["_enter"] = c.get("enter") if c.get("enter") in ("left", "right") else ""
            c["_enter_d"], c["_exit"], c["_exit_run"], c["_exit_u"] = 0.0, "", False, 0.5
            if m and solo:
                c["_pose"] = "stand" if m == "walk" else pose
            elif m == "run" or mt == "run":
                c["_exit"] = "left" if c["x"] < 540 else "right"
                c["_exit_run"], c["_exit_u"] = True, (0.3 if m == "run" else 0.55)
                c["_pose"], c["_then"], c["_enter"] = ("shock" if m == "run" else pose), "", ""
            elif m == "walk":
                if not c["_enter"]:
                    c["_enter"] = "left" if c["x"] <= 540 else "right"
                    c["_enter_d"] = 0.0 if was is None else 330.0
                c["_pose"], c["_then"] = (then or "stand"), ""
            elif mt == "walk":
                c["_exit"], c["_exit_u"], c["_then"] = ("left" if c["x"] < 540 else "right"), 0.55, ""
            c["_fallen"] = c["_pose"] in G.FALLS and was in G.FALLS
            self.last_pose[key] = "gone" if c["_exit"] else (c["_then"] or c["_pose"])

    def person(self, fr, c, t, u, dur, z, cy, sc, ground, light, mouth, talking, lk, yaw_flip):
        cid = c["id"]
        look = self.cast.looks.get(cid) or self.cast.looks["hero"]
        pose, prev, since, x, cad = c["_pose"], None, 99.0, c["x"], 1.0
        if talking and pose == "stand":
            pose = "talk2" if c["x"] > 540 else "talk"
        gait = False
        if c["_enter"]:
            sgn = -1 if c["_enter"] == "left" else 1
            start = x + sgn * c["_enter_d"] * sc if c["_enter_d"] else (-260 if sgn < 0 else W + 260)
            dist = abs(x - start)
            te = max(0.6, min(2.2, 0.62 * dur, dist / (0.95 * G.STRIDE * sc)))
            if t < te:
                x = start + (x - start) * glide(t / te)
                pose, cad, gait = "walk_side", max(0.55, min(1.6, dist / te / (G.STRIDE * sc))), True
                yaw_flip = sgn > 0
            else:
                prev, since = "walk", t - te
        if c["_then"] and u >= 0.55:
            prev, since, pose = pose, (u - 0.55) * dur, c["_then"]
        if pose in G.FALLS and not prev and not c["_fallen"]:
            prev, since = "stand", t - 0.15
        if c["_exit"] and u >= c["_exit_u"]:
            te = (u - c["_exit_u"]) * dur
            cad = 1.55 if c["_exit_run"] else 0.95
            v = cad * (G.RUN_STRIDE if c["_exit_run"] else G.STRIDE) * sc
            d = v * te * te / 0.44 if te < 0.22 else v * (te - 0.11)
            x += -d if c["_exit"] == "left" else d
            pose, prev, since, gait = ("run_side" if c["_exit_run"] else "walk_side"), None, 99.0, True
            yaw_flip = c["_exit"] == "left"
            if abs(540 + z * (x - 540) - 540) > 540 + 300 * sc * z:
                return
        seed = self.seed.get(cid, 1.0)
        tt = t if talking or gait or since < G.FALL_END else round(t * 12) / 12
        p, bob = G.animate(pose, tt * cad if gait else tt, talking, None, seed, prev, since)
        flip = False
        if gait:
            flip = bool(yaw_flip)
        elif yaw_flip is not None and pose not in ("point_r", "point_l"):
            p["yaw"], flip, lk = 0.35, yaw_flip, abs(lk)
        if pose in G.FALLS:
            fc = -1 if flip else 1
            pose = c.setdefault("_fall_" + pose, G.fall_fit(pose, x, sc, (540 * z - 540) / z, (540 * z + 540) / z, fc))
            if pose != c["_pose"] and pose == "fall_sit":
                p, bob = G.animate(pose, tt, talking, None, seed, prev, since)
                if not gait and yaw_flip is not None:
                    p["yaw"] = 0.35
            x += G.fall_slide(pose, since if prev else 99.0) * sc * fc * G.fall_room(pose, x, sc, (540 * z - 540) / z, (540 * z + 540) / z, fc)
        face = FACE_MAP.get(c.get("face"), c.get("face") or "neutral")
        if face not in G.FACES:
            face = "neutral"
        fx = c.get("fx") if c.get("fx") in G.FX else None
        im, foot = G.draw(look, p, face, mouth if talking else 0, sc * z, lk, prop=c.get("_prop"), blink=G.blinking(t, seed), flip=flip, fx=fx, t=t)
        X, Y = 540 + z * (x - 540), cy + z * (ground - cy)
        sh = Image.new("L", (int(260 * sc * z), int(46 * sc * z)), 0)
        ImageDraw.Draw(sh).ellipse((0, 0, sh.width - 1, sh.height - 1), fill=110)
        sha = Image.merge("RGBA", (sh.point(lambda v: 0), sh.point(lambda v: 0), sh.point(lambda v: 0), sh))
        blend(fr, sha, X - sha.width / 2, Y - sha.height / 2)
        blend(fr, im, X - foot[0], Y - foot[1] - bob * sc * z, light)

    def scene(self, shot, segs, n, t0):
        frame = shot.get("frame") if shot.get("frame") in FRAMES else "medium"
        sc, ground = FRAMES[frame]
        bg, light = self.bg(shot.get("place"))
        if shot.get("cctv"):
            bg = cv2.cvtColor(cv2.cvtColor(bg, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
        chars = layout(shot.get("chars") or [], sc)
        for c in chars:
            c["_pose"], c["_prop"], c["_then"] = pick_pose(c), pick_prop(c), pick_then(c)
        self.motion(shot, chars)
        say = shot.get("say") or "narration"
        xs = {c["id"]: c["x"] for c in chars}
        cy = 900 if frame == "close" else 960
        seg = segs[0] if segs else None
        mouth = mouth_levels(seg, self.fps) if seg and say in xs else []
        for i in range(n):
            t = i / self.fps
            u = i / max(1, n - 1)
            z = 1.0 + 0.05 * ease(u)
            Mx = np.float32([[z, 0, 540 - 540 * z], [0, z, cy - cy * z]])
            fr = cv2.warpAffine(bg, Mx, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            for c in sorted(chars, key=lambda q: q["id"] == say):
                talking = c["id"] == say
                lk, yf = 0.0, None
                others = [x for k, x in xs.items() if k != c["id"]]
                if others:
                    tx = xs.get(say) if not talking and say in xs else min(others, key=lambda v: abs(v - c["x"]))
                    if tx is not None and abs(tx - c["x"]) > 30:
                        lk = 0.45 if tx > c["x"] else -0.45
                        yf = lk < 0
                ml = mouth[i] if talking and i < len(mouth) else 0
                self.person(fr, c, t, u, n / self.fps, z, cy, sc, ground, light, ml, talking, lk, yf)
            yield fr
        self.last_scene = fr

    def phone(self, shot, segs, n, t0):
        ui, d = shot.get("ui"), shot.get("data") or {}
        names = {cid: self.cast.name(cid) for cid in self.cast.looks}
        cache = {}
        starts = [(s["t0"] - t0, s.get("reveal")) for s in segs]
        host_mouth = mouth_levels(segs[0], self.fps) if ui == "live" and segs else []
        for i in range(n):
            t = i / self.fps
            u = i / max(1, n - 1)
            shown = 0
            for st, rv in starts:
                if rv is not None and t >= st - 0.05:
                    shown = max(shown, rv)
            key = (ui, shown if ui in ("chat", "post", "forum") else 0)
            if ui == "live":
                fr = self.live_frame(d, names, t, host_mouth[i] if i < len(host_mouth) else 0)
            else:
                if key not in cache:
                    if ui == "chat":
                        im = P.chat(d, max(1, shown), names)
                    elif ui == "post":
                        im = P.post(d, shown)
                    elif ui == "forum":
                        im = P.forum(d, shown)
                    elif ui == "review":
                        im = P.review(d)
                    elif ui == "doc":
                        im = P.doc(d)
                    elif ui == "system":
                        base = self.last_scene if self.last_scene is not None else np.full((H, W, 3), 30, np.uint8)
                        b = Image.fromarray((base.astype(np.float32) * 0.55).astype(np.uint8)).convert("RGBA")
                        b.alpha_composite(P.system(d))
                        im = b.convert("RGB")
                    else:
                        im = P.card(shot.get("line", ""))
                    cache[key] = np.asarray(im)
                z = 1.0 + 0.03 * ease(u)
                Mx = np.float32([[z, 0, 540 - 540 * z], [0, z, 960 - 960 * z]])
                fr = cv2.warpAffine(cache[key], Mx, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            yield fr

    def live_frame(self, d, names, t, mouth):
        fr = np.asarray(P.live_frame(d, names)).copy()
        screen = np.zeros((1724, 904, 3), np.float32)
        yy = np.linspace(0, 1, 1724, dtype=np.float32)[:, None, None]
        screen[:] = np.float32([96, 84, 74]) * (1 - yy) + np.float32([52, 46, 42]) * yy
        fr[98:1822, 88:992] = screen.astype(np.uint8)
        host = d.get("host") or "hero"
        look = self.cast.looks.get(host) or self.cast.looks["hero"]
        p, bob = G.animate("talk", t, True, None, self.seed.get(host, 1.0))
        im, foot = G.draw(look, p, "smile", mouth, 1.25, 0.0, prop="phone", blink=G.blinking(t, 1.0), t=t)
        blend(fr, im, 540 - foot[0], 1880 - foot[1] - bob * 1.25)
        ov = Image.fromarray(fr).convert("RGBA")
        ov.alpha_composite(P.live_overlay(d, names))
        return np.asarray(ov.convert("RGB")).copy()

    def card(self, text, sub, n, fade=True):
        base = np.asarray(P.card(text, sub))
        for i in range(n):
            k = min(1.0, i / 8.0) if fade else 1.0
            yield (base.astype(np.float32) * k).astype(np.uint8)


def subtitle_for(segs, t):
    for s in segs:
        if s["sub"] and s["t0"] - 0.02 <= t < s["t0"] + s["dur"] + GAP:
            return s["text"]
    return ""


def main():
    ap = argparse.ArgumentParser(description="Render a Thai drama episode JSON to a vertical mp4")
    ap.add_argument("episode")
    ap.add_argument("--out", default="")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--mute", action="store_true", help="skip voices (estimated timing, silent audio)")
    ap.add_argument("--still", type=int, default=0, help="only save a PNG of shot N (1-based) to check the look")
    ap.add_argument("--bg-only", action="store_true", help="only build the background PNGs")
    a = ap.parse_args()
    t_start = time.time()
    log = lambda m: print(m, flush=True)
    ep_path = Path(a.episode)
    ep, sdir = load(ep_path), ep_path.parent
    series = load(sdir / "series.json")
    cast = Cast(series)
    ff = ffmpeg_bin()
    fps = a.fps
    rnd = Renderer(series, ep, sdir, cast, fps, log)
    if a.bg_only:
        for pid in rnd.places:
            rnd.bg(pid)
        log("backgrounds ready in " + str(sdir / "bg"))
        return
    shots = ep.get("shots") or []
    all_segs = []
    per_shot = []
    for k, s in enumerate(shots):
        sg = segments(s, cast, k)
        per_shot.append(sg)
        all_segs += sg
    end_segs = []
    if ep.get("ask"):
        end_segs = [{"who": "narration", "text": ep["ask"], "sub": True, "reveal": None, "shot": len(shots)}]
    work = sdir / ".voice_cache"
    voice_track(all_segs + end_segs, cast, work, ff, a.mute or bool(a.still), log)
    t, plan = 0.0, []
    for k, s in enumerate(shots):
        sg = per_shot[k]
        t0 = t
        cur = t + 0.12
        for x in sg:
            x["t0"] = cur
            cur += x["dur"] + GAP
        dur = max(MIN_SHOT, cur - t0 + TAIL - GAP)
        plan.append((s, sg, t0, dur))
        t = t0 + dur
    cur = t + 0.3
    for x in end_segs:
        x["t0"] = cur
        cur += x["dur"] + GAP
    end_dur = max(3.0, cur - t + 0.8)
    total = t + end_dur
    if a.still:
        s, sg, t0, dur = plan[min(len(plan), a.still) - 1]
        n = max(2, int(dur * fps))
        gen = rnd.scene(s, sg, n, t0) if s.get("type") == "scene" else (rnd.phone(s, sg, n, t0) if s.get("type") == "phone" else rnd.card(s.get("text", ""), "", n))
        fr = None
        for i, fr in enumerate(gen):
            if i >= n // 2:
                break
        img = Image.fromarray(fr)
        txt = subtitle_for(sg, sg[0]["t0"] - t0 + 0.1) if sg else ""
        if txt:
            img = img.copy()
            T.subtitle(img, sg[0]["text"])
        out = sdir / f"still_ep{int(ep.get('ep', 0)):02d}_shot{a.still:02d}.png"
        img.save(out)
        log(f"still saved: {out}")
        return
    pcm = np.zeros(int(total * SR) + SR, np.float32)
    for x in all_segs + end_segs:
        o = int(x["t0"] * SR)
        pcm[o:o + len(x["pcm"])] += x["pcm"] * 0.95
    pcm = np.clip(pcm, -1, 1)
    wav = sdir / f".ep{int(ep.get('ep', 0)):02d}_voice.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((pcm * 32767).astype(np.int16).tobytes())
    out = Path(a.out) if a.out else sdir / f"ep{int(ep.get('ep', 0)):02d}.mp4"
    enc = subprocess.Popen([ff, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-i", str(wav),
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
                            "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    done = 0
    for k, (s, sg, t0, dur) in enumerate(plan):
        n0, n1 = int(round(t0 * fps)), int(round((t0 + dur) * fps))
        n = max(1, n1 - n0)
        typ = s.get("type")
        gen = rnd.scene(s, sg, n, t0) if typ == "scene" else (rnd.phone(s, sg, n, t0) if typ == "phone" else rnd.card(s.get("text", ""), "", n))
        for i, fr in enumerate(gen):
            tt = t0 + i / fps
            txt = subtitle_for(sg, tt)
            if txt:
                img = Image.fromarray(fr)
                T.subtitle(img, txt, y=1500 if typ == "scene" else 1700)
                fr = np.asarray(img)
            enc.stdin.write(np.ascontiguousarray(fr).tobytes())
        done += 1
        log(f"shot {done}/{len(plan)} ({typ}) {dur:.1f}s")
    n_end = int(round(end_dur * fps))
    nxt = f"EP{int(ep.get('ep', 0)) + 1} ตอนต่อไป" if ep.get("teaser") else ""
    for i, fr in enumerate(rnd.card(ep.get("teaser") or ep.get("title", ""), nxt, n_end)):
        txt = subtitle_for(end_segs, t + i / fps)
        if txt:
            img = Image.fromarray(fr)
            T.subtitle(img, txt, y=1560)
            fr = np.asarray(img)
        enc.stdin.write(np.ascontiguousarray(fr).tobytes())
    enc.stdin.close()
    enc.wait()
    wav.unlink(missing_ok=True)
    log(f"DONE {out} · {total:.1f}s video · rendered in {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
