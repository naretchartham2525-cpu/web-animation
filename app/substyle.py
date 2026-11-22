"""ซับของคลิป (ระบบเป็นคนใส่ทุกเทมเพลต) · ปรับขนาด/ตำแหน่ง/ภาษาซับของคลิปที่เสร็จแล้วได้โดยไม่ต้องเรนเดอร์ใหม่

ทุก EP เก็บไว้ 2 อย่าง:
  _clean.mp4  วิดีโอก่อนใส่ซับ (เอนจิน = raw.mp4 ของสกิล · เทมเพลตทั่วไป = ฉากต่อกันแล้ว ยังไม่มีซับ/เพลง)
  _subs.json  ข้อมูลซับ + เวลา + ค่าที่ใช้ export (ขนาดจอ ลายน้ำ เพลง ความคมชัด)
ปรับซับ = สร้างไฟล์ซับใหม่ แล้ว export จาก _clean.mp4 อีกครั้ง (ราวครึ่งนาที)

ค่าซับ (style) เป็นตัวเลขบนจอกว้าง 1080 px:
  sub_size   ขนาดซับหลัก          sub2_size  ขนาดคำแปล (บรรทัดล่าง)
  sub_y      เลื่อนซับหลัก (+ลง −ขึ้น)  sub2_y     เลื่อนคำแปล
"""
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from . import core, video

STYLE_KEYS = ("sub_size", "sub2_size", "sub_y", "sub2_y")
ENGINE_DEFAULT = {"sub_size": 66, "sub2_size": 56, "sub_y": 0, "sub2_y": 0}
SUB_Y = {"scene": 1500, "phone": 1700, "card": 1700, "end": 1560}   # ตำแหน่งซับของเอนจิน (บนจอ 1080x1920)
_running = {}


def clean_style(st):
    out = {}
    for k in STYLE_KEYS:
        try:
            v = int(float((st or {}).get(k)))
        except (TypeError, ValueError):
            continue
        out[k] = max(20, min(140, v)) if k.endswith("size") else max(-900, min(600, v))
    return out


def defaults(meta):
    if meta.get("kind") == "engine":
        return dict(ENGINE_DEFAULT)
    k = 1080 / max(1, meta["w"])
    main = round(video.default_sub_size(meta["w"], meta["h"]) * k)
    swap = meta.get("dub") == "en" and meta.get("mode") == "both"
    return {"sub_size": main, "sub2_size": round(main * (0.9 if swap else 0.78)), "sub_y": 0, "sub2_y": 0}


def style_of(meta):
    return {**defaults(meta), **clean_style(meta.get("style"))}


# ---------------- ซับของเทมเพลตที่มีเอนจิน ----------------
def _wrapper(skill_dir):
    """ตัดบรรทัดแบบเดียวกับเอนจิน (ภาษาไทยไม่มีเว้นวรรค ต้องตัดคำเอง)"""
    eng = str(Path(skill_dir) / "engine")
    if eng not in sys.path:
        sys.path.insert(0, eng)
    try:
        import textkit as T
        return lambda text, size, n=4: T.wrap(text, T.font(size, "Bold"), 900, n)
    except Exception:  # noqa: BLE001  ไม่มีไลบรารีของเอนจิน → ตัดตามจำนวนตัวอักษร
        return lambda text, size, n=4: video.split_chunks(text, max(8, int(900 / (size * 0.55))))[:n]


def _texts(x, mode, dub):
    """(ซับหลัก, คำแปล) ของแต่ละประโยค · x["th"] = ข้อความที่เอนจินพูด (ภาษาพากย์) · x["src"] = บทไทยต้นฉบับ · x["en"] = คำแปลอังกฤษ"""
    spoken = x.get("th") or ""
    if dub == "en":
        thai = x.get("src") or ""
        return {"en": (spoken, ""), "th": (thai, ""), "both": (spoken, thai)}.get(mode, ("", ""))
    return {"th": (spoken, ""), "en": (x.get("en") or spoken, ""), "both": (spoken, x.get("en") or "")}.get(mode, ("", ""))


def engine_ass(meta, st):
    wrap = _wrapper(meta["skill_dir"])
    s1, s2 = st["sub_size"], st["sub2_size"]
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: S1,IBM Plex Sans Thai,{s1},&H00FFFFFF,&H00FFFFFF,&H000C0A0A,&H00000000,-1,0,0,0,100,100,0,0,1,{max(4, round(s1 * 0.13))},0,5,60,60,0,1\n"
            f"Style: S2,IBM Plex Sans Thai,{s2},&H00FFFFFF,&H00FFFFFF,&H000C0A0A,&H00000000,-1,0,0,0,100,100,0,0,1,{max(3, round(s2 * 0.12))},0,8,60,60,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    esc = lambda t: str(t).replace("{", "(").replace("}", ")").replace("\n", " ")
    ev = []
    for x in meta["items"]:
        a, b = _t(x["t0"]), _t(x["t1"])
        t1, t2 = _texts(x, meta["mode"], meta.get("dub"))
        y = SUB_Y.get(x.get("typ"), 1700) + st["sub_y"]
        h1 = 0
        if t1.strip():
            lines = wrap(t1, s1)
            h1 = len(lines) * s1 * 1.3
            body = "\\N".join(esc(ln) for ln in lines)
            ev.append(f"Dialogue: 0,{a},{b},S1,,0,0,0,,{{\\an5\\pos(540,{int(y)})}}{body}")
        if t2.strip():
            lines = wrap(t2, s2, 3)
            y2 = (y + h1 / 2 + 14 if h1 else y) + st["sub2_y"]   # คำแปลอยู่ใต้ซับหลัก (เลื่อนตามซับหลัก) + เลื่อนเองได้
            body = "\\N".join(esc(ln) for ln in lines)
            ev.append(f"Dialogue: 1,{a},{b},S2,,0,0,0,,{{\\an8\\pos(540,{int(min(1900, y2))})}}{body}")
    return head + "\n".join(ev) + "\n"


def _t(sec):
    sec = max(0.0, float(sec))
    h, m, x = int(sec // 3600), int(sec % 3600 // 60), sec % 60
    return f"{h}:{m:02d}:{x:05.2f}"


# ---------------- ซับของเทมเพลตทั่วไป ----------------
def normal_ass(meta, st):
    w, h = meta["w"], meta["h"]
    s = {**(meta.get("s") or {}), "_style": st}
    items = [tuple(x) for x in meta["items"]]
    mode = meta["mode"]
    if meta.get("dub") == "en" and mode == "both":     # อังกฤษเป็นซับหลัก ไทยบรรทัดล่าง
        items = [(a, b, en or th, th) for a, b, th, en in items]
        s["subtitle_max_chars"] = s.get("subtitle_max_chars") or (30 if h > w else 52)
    elif meta.get("dub") == "en" and mode == "th":     # พากย์อังกฤษ ซับไทยอย่างเดียว
        mode = "th"
    ass, _, _ = video.build_subs(items, w, h, s, watermark=meta.get("wm") or "", total=meta.get("total") or 0, mode=mode)
    return ass


# ---------------- export ----------------
def export(edir, meta, log=print):
    """_clean.mp4 + ซับตามค่า → final.mp4 (เขียนทับอย่างปลอดภัย)"""
    edir = Path(edir)
    st = style_of(meta)
    work = core.WORK_DIR / f"subs-{core.safe_name(edir.parent.name)[:30]}-{edir.name}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        vf = []
        if meta["kind"] == "engine":
            vf.append(f"scale={meta['w']}:{meta['h']}:flags=lanczos")
            if meta.get("wm"):
                ass, _, _ = video.build_subs([], meta["w"], meta["h"], meta.get("s") or {}, watermark=meta["wm"], total=meta.get("total") or 0, mode="none")
                (work / "wm.ass").write_text(ass, encoding="utf-8")
                vf.append("ass=wm.ass")
            if meta["mode"] != "none" and meta["items"]:
                (work / "subs.ass").write_text(engine_ass(meta, st), encoding="utf-8")
                shutil.copytree(Path(meta["skill_dir"]) / "engine" / "fonts", work / "fonts", dirs_exist_ok=True)
                vf.append("ass=subs.ass:fontsdir=fonts")
        else:
            (work / "subs.ass").write_text(normal_ass(meta, st), encoding="utf-8")
            if (meta["mode"] != "none" and meta["items"]) or meta.get("wm"):
                if core.FONTS_DIR.exists() and any(core.FONTS_DIR.iterdir()):
                    shutil.copytree(core.FONTS_DIR, work / "fonts", dirs_exist_ok=True)
                    vf.append("ass=subs.ass:fontsdir=fonts")
                else:
                    vf.append("ass=subs.ass")
        vfs = ",".join(vf) or "null"
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(edir / "_clean.mp4")]
        bgm = meta.get("music")
        if bgm and Path(bgm).exists():
            cmd += ["-stream_loop", "-1", "-i", str(bgm), "-filter_complex",
                    f"[0:v]{vfs}[v];[1:a]volume={float(meta.get('bgm_volume') or 0.12)}[b];"
                    f"[0:a][b]amix=inputs=2:duration=first:dropout_transition=0,volume=2[a]", "-map", "[v]", "-map", "[a]"]
        else:
            cmd += ["-vf", vfs, "-map", "0:v", "-map", "0:a?"]
        cmd += ["-c:v", "libx264", "-preset", meta.get("preset") or "veryfast", "-crf", str(meta.get("crf") or 20),
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "final.mp4"]
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError((r.stderr or "ffmpeg ไม่สำเร็จ")[-300:])
        tmp = edir / "final.part.mp4"
        shutil.copyfile(work / "final.mp4", tmp)
        tmp.replace(edir / "final.mp4")
        _write_srt(edir, meta)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _write_srt(edir, meta):
    """ไฟล์ .srt ตามภาษาที่เลือก (subs.srt = ไทย · subs_en.srt = อังกฤษ)"""
    if meta["kind"] != "engine":
        return
    def srt(rows):
        f = lambda t: "%02d:%02d:%02d,%03d" % (int(t // 3600), int(t % 3600 // 60), int(t % 60), int(round(t % 1 * 1000)) % 1000)
        return "\n".join(f"{i}\n{f(a)} --> {f(b)}\n{t}\n" for i, (a, b, t) in enumerate(rows, 1))
    items = meta["items"]
    if meta.get("dub") == "en":
        th = [(x["t0"], x["t1"], x.get("src")) for x in items if x.get("src")]
        en = [(x["t0"], x["t1"], x.get("th")) for x in items if x.get("th")]
    else:
        th = [(x["t0"], x["t1"], x.get("th")) for x in items if x.get("th")]
        en = [(x["t0"], x["t1"], x.get("en")) for x in items if x.get("en")]
    if th:
        (Path(edir) / "subs.srt").write_text(srt(th), encoding="utf-8")
    if en:
        (Path(edir) / "subs_en.srt").write_text(srt(en), encoding="utf-8")


def save(edir, meta):
    core.write_json(Path(edir) / "_subs.json", meta)


def load(edir):
    return core.read_json(Path(edir) / "_subs.json")


def restyle(project, ep, style=None, mode=None):
    """ปรับซับของคลิปที่เสร็จแล้ว (เบื้องหลัง) · คืน False ถ้าคลิปนี้ไม่มีไฟล์ต้นฉบับก่อนใส่ซับ (ต้องทำคลิปใหม่)"""
    edir = core.project_dir(project) / f"ep{int(ep):02d}"
    meta = load(edir)
    if not meta or not (edir / "_clean.mp4").exists():
        return False
    if style is not None:
        meta["style"] = clean_style({**(meta.get("style") or {}), **style})
    if mode in ("th", "en", "both", "none"):
        meta["mode"] = mode
    save(edir, meta)
    p = core.get_project(project) or {}                  # จำไว้ใช้กับ EP ต่อไปของเรื่องนี้
    opts = dict(p.get("options") or {})
    opts["sub_style"] = meta.get("style") or {}
    if mode:
        opts["sub_lang"] = mode
    core.update_project(project, {"options": opts})
    key = (project, int(ep))

    def run():
        _running[key] = {"state": "running"}
        try:
            export(edir, meta)
            _running[key] = {"state": "done"}
        except Exception as e:  # noqa: BLE001
            _running[key] = {"state": "error", "error": str(e)[:300]}
    threading.Thread(target=run, daemon=True).start()
    return True


def status(project, ep):
    return _running.get((project, int(ep))) or {"state": "idle"}
