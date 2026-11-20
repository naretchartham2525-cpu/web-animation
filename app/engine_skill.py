"""รองรับสกิลที่มีเอนจินของตัวเอง (autoclip.json → "engine": "drama-json")
ระบบเรา: รับบท → ให้สกิลตรวจ/เรนเดอร์ → คุมเสียง ลายน้ำ ความคมชัด → เก็บลง Drive"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import core, video

CODE_DIR = Path(__file__).resolve().parent.parent


def manifest(skill):
    if not skill or not skill.get("dir"):
        return {}
    return core.read_json(Path(skill["dir"]) / "autoclip.json", {}) or {}


# ---------------- อ่านบทที่วางมา ----------------
def _json_objects(text):
    """ดึง JSON object ทุกก้อนจากข้อความ (ในหรือนอก ```json``` ก็ได้)"""
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth, j, in_str, esc = 0, i, False, False
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        chunk = text[i:j + 1]
        try:
            obj = json.loads(chunk)
            if isinstance(obj, dict):
                out.append(obj)
            i = j + 1
        except json.JSONDecodeError:
            i += 1
    return out


_BG = re.compile(r"```(?:python|py)?\s*\n#\s*bg[:/ ]\s*([A-Za-z0-9_\-]+)(?:\.py)?\s*\n(.*?)```", re.S)


def parse_paste(text):
    """คืน {"series": dict|None, "episodes": [dict], "bg": {place_id: code}}"""
    text = (text or "").replace("\r", "")
    series, eps = None, []
    for obj in _json_objects(text):
        if isinstance(obj.get("shots"), list):
            eps.append(obj)
        elif isinstance(obj.get("cast"), list) or "series_title" in obj:
            series = obj
    bg = {m.group(1): m.group(2).strip() + "\n" for m in _BG.finditer(text)}
    if not eps and not series:
        raise ValueError("ไม่พบบท JSON ของสกิล (ต้องมี epNN.json ที่มี \"shots\")")
    eps.sort(key=lambda e: int(e.get("ep") or 0))
    return {"series": series, "episodes": eps, "bg": bg}


def engine_dir(name):
    d = core.project_dir(name) / "engine"
    d.mkdir(parents=True, exist_ok=True)
    return d


def to_scenes(ep):
    """แปลงบทของสกิลเป็นรูปแบบของระบบ (ไว้แสดงในเว็บ/สรุปเรื่องย่อ)"""
    scenes = []
    for sh in ep.get("shots") or []:
        line = str(sh.get("line") or "").strip()
        if not line and sh.get("type") == "card":
            line = str(sh.get("text") or "").strip()
        if line:
            who = sh.get("say") or sh.get("type") or ""
            scenes.append({"narration": line, "subtitle": "", "image_prompt": f"{sh.get('type')} · {who}", "clip": ""})
    return {"title": ep.get("title") or "", "summary": ep.get("summary") or "", "scenes": scenes or
            [{"narration": "-", "subtitle": "", "image_prompt": "", "clip": ""}], "engine": True}


def save_paste(name, parsed, start_ep):
    """เก็บ series.json / bg / บทแต่ละ EP ลงโปรเจกต์ → คืนจำนวน EP"""
    sdir = engine_dir(name)
    if parsed["series"]:
        core.write_json(sdir / "series.json", parsed["series"])
    elif not (sdir / "series.json").exists():
        raise ValueError("ยังไม่มี series.json (ไบเบิลซีรีส์) วางมาพร้อม EP แรกด้วย")
    if parsed["bg"]:
        (sdir / "bg").mkdir(exist_ok=True)
        for pid, code in parsed["bg"].items():
            (sdir / "bg" / f"{core.safe_name(pid)}.py").write_text(code, encoding="utf-8")
    for i, ep in enumerate(parsed["episodes"]):
        n = start_ep + i
        ep = {**ep, "ep": n}
        d = core.ep_dir(name, n)
        if d.exists():
            d.rename(d.parent / f"_old_ep{n:02d}_{int(time.time())}")
        d.mkdir(parents=True)
        core.write_json(d / "engine_ep.json", ep)
        core.write_json(d / "script.json", to_scenes(ep))
    return len(parsed["episodes"])


def series_title(parsed, fallback):
    s = parsed.get("series") or {}
    return s.get("series_title") or (parsed["episodes"][0].get("title") if parsed["episodes"] else "") or fallback


# ---------------- คำสั่งให้ Claude เขียนบทของสกิล ----------------
def chat_prompt(skill, proj_name, start_ep, count, s, idea=""):
    m = manifest(skill)
    sdir = Path(skill["dir"])
    parts = [f"ใช้สกิล {skill['id']} (ไฟล์อ้างอิงด้านล่าง) เขียนบทละครสั้น "
             + (f"EP {start_ep}" if count == 1 else f"EP {start_ep} ถึง EP {start_ep + count - 1}")]
    series = None
    if proj_name:
        series = core.read_json(engine_dir(proj_name) / "series.json")
    if series:
        parts.append("series.json ปัจจุบัน (ห้ามเปลี่ยนตัวละคร ใช้ต่อเนื่อง):\n```json\n"
                     + json.dumps(series, ensure_ascii=False, indent=1) + "\n```")
    else:
        parts.append("ยังไม่มีซีรีส์: เขียน series.json ใหม่ก่อน แล้วตามด้วย EP")
    parts.append(f"หัวข้อ/เรื่อง: {idea}" if idea else "หัวข้อ/เรื่อง: (ผมจะกำหนดเอง ให้รอรับหัวข้อก่อนเขียน)")
    if s.get("_tweak_th"):
        parts.append(f"ปรับแต่งเพิ่มเติม: {s['_tweak_th']}")
    sec = int((series or {}).get("seconds") or s.get("target_seconds") or m.get("default_seconds") or 90)
    parts.append(f"""รูปแบบคำตอบ (ระบบอ่านอัตโนมัติ):
- ตอบเป็น code block ```json``` แยกก้อนละไฟล์: {'series.json แล้วตามด้วย ' if not series else ''}epNN.json ทีละ EP
- ความยาวตอนละประมาณ {sec} วินาที · ทุกคนในฉากต้องมี pose (และ prop ถ้าถือของ) · ตัวละครต้องมี rig
- ถ้ารันโค้ดได้ ให้รันตัวตรวจ drama_tool.py check จนผ่านก่อนส่ง
- ฉากหลัง: {'วาดทุกสถานที่ใน places ' if not series else 'วาดเฉพาะสถานที่ใหม่ที่ยังไม่เคยมี '}ตาม reference/scenes.md ส่งเป็น code block ```python``` ก้อนละสถานที่ บรรทัดแรก "# bg: <place_id>" (ไม่ส่ง = ระบบใช้ฉากสำเร็จรูปที่มักไม่ตรงเรื่อง)
{'- ซับอังกฤษ: ทุกช็อตเพิ่มฟิลด์ "line_en" (คำแปลอังกฤษสั้นๆ ของ line) และเพิ่ม "ask_en" ระดับตอน\n' if s.get("sub_lang") in ("en", "both") else ""}- ผู้พูดต้องถูกตัวทุกประโยค (ระบบแยกบทพากย์ตามตัวละครให้อัดเสียง): scene ใช้ "say" = id ตัวละคร หรือ narration · แชทใช้ "from" = id ตัวละคร · author/name ในโพสต์/ฟอรัม/คอมเมนต์ใช้ชื่อตามที่อยู่ใน cast ทุกตัวอักษร
- ไม่ต้องมีคำอธิบายอื่น""")
    for f in m.get("prompt_files") or ["reference/format.md"]:
        p = sdir / f
        if p.exists():
            parts.append(f"===== {f} =====\n" + p.read_text(encoding="utf-8", errors="replace").strip())
    for c in m.get("prompt_commands") or []:
        out = _cmd_output(sdir, c.get("cmd") or [])
        if out:
            parts.append(f"===== {c.get('title') or ' '.join(c.get('cmd'))} =====\n"
                         "ใช้เฉพาะค่าในรายการนี้เท่านั้น\n" + out)
    return "\n\n".join(parts)


_CMD_CACHE = {}


def _cmd_output(sdir, cmd):
    """รันคำสั่งของสกิล (เช่น assets.py poses) เพื่อแนบรายการค่าที่ใช้ได้ในคำสั่ง (แคชไว้)"""
    if not cmd or not str(cmd[0]).endswith(".py"):
        return ""
    key = (str(sdir), tuple(cmd))
    if key not in _CMD_CACHE:
        try:
            r = subprocess.run([sys.executable] + [str(x) for x in cmd], cwd=str(sdir),
                               capture_output=True, text=True, timeout=60)
            _CMD_CACHE[key] = r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            _CMD_CACHE[key] = ""
    return _CMD_CACHE[key]


# ---------------- ซับ (งานของระบบ ใช้ได้กับทุกเทมเพลต) ----------------
GAP_END = 0.16
SUB_Y = {"scene": 1500, "phone": 1700, "card": 1700, "end": 1560}   # ตำแหน่งซับไทยของเอนจิน (พิกัด 1080x1920)


def sub_mode(s):
    return (s.get("sub_lang") or "th") if s.get("subtitles", True) else "none"


def timeline_subs(ctx, ep, rawmp4, s):
    """ไทม์ไลน์เสียงจริงจากเอนจิน → [{t0, t1, th, en, typ}] · ขาดคำแปล → แปลด้วย AI ฟรี"""
    f = Path(rawmp4).with_suffix(".timeline.json")
    rows = core.read_json(f, []) or []
    shots = ep.get("shots") or []
    out = []
    for r in rows:
        if not r.get("sub") or not str(r.get("text") or "").strip():
            continue
        k = r.get("shot")
        sh = shots[k] if isinstance(k, int) and k < len(shots) else None
        en = (sh or {}).get("line_en") if sh else ep.get("ask_en")
        out.append({"t0": r["t0"], "t1": r["t0"] + r["dur"] + GAP_END, "th": r["text"], "en": str(en or "").strip(),
                    "typ": (sh or {}).get("type") or "end"})
    if out and sub_mode(s) in ("en", "both") and any(not x["en"] for x in out):
        from .pipeline import ensure_english
        sc = {"scenes": [{"narration": x["th"], "subtitle_en": x["en"]} for x in out]}
        try:
            ensure_english(ctx, sc, s)
            for x, y in zip(out, sc["scenes"]):
                x["en"] = y.get("subtitle_en") or x["en"]
        except Exception as e:
            ctx.log(f"แปลซับอังกฤษไม่สำเร็จ: {e}")
    return out


def _t(sec, ass=True):
    sec = max(0.0, sec)
    h, m, x = int(sec // 3600), int(sec % 3600 // 60), sec % 60
    return f"{h}:{m:02d}:{x:05.2f}" if ass else f"{h:02d}:{m:02d}:{int(x):02d},{int(round((x % 1) * 1000)) % 1000:03d}"


def _srt(items):
    return "\n".join(f"{i}\n{_t(a, False)} --> {_t(b, False)}\n{t}\n" for i, (a, b, t) in enumerate(items, 1))


def english_ass(subs, mode):
    """ซับอังกฤษ: both = ใต้ซับไทยของเอนจิน · en = แทนที่ซับไทย"""
    size = 46 if mode == "both" else 60
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: EN,Liberation Sans,{size},&H00FFFFFF,&H00FFFFFF,&H000C0A0A,&H00000000,1,0,0,0,100,100,0,0,1,{5 if mode == 'both' else 6},0,2,90,90,60,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev = []
    for x in subs:
        if not x.get("en"):
            continue
        y = SUB_Y.get(x["typ"], 1700)
        if mode == "both":   # ใต้ซับไทย: ประมาณจำนวนบรรทัดไทย (กว้าง 900px, ~34px/ตัว, สูงสุด 3 บรรทัด)
            lines = max(1, min(3, -(-len(x["th"]) * 34 // 900)))
            pos = f"{{\\an8\\pos(540,{min(1840, y + lines * 43 + 18)})}}"
        else:
            pos = f"{{\\an5\\pos(540,{y})}}"
        txt = x["en"].replace("\n", " ").replace("{", "(").replace("}", ")")
        ev.append(f"Dialogue: 0,{_t(x['t0'])},{_t(x['t1'])},EN,,0,0,0,,{pos}{txt}")
    return head + "\n".join(ev) + "\n"


# ---------------- ซ่อมไฟล์สกิลที่หาย (เทียบกับสกิลใน repo) ----------------
REPO_SKILLS = Path(__file__).resolve().parent.parent / "skills"


def heal_skill(skill):
    """คัดลอกไฟล์ที่มีในสกิลของ repo แต่ไม่มีในสกิลที่ใช้งาน (Drive) ไม่ทับไฟล์ที่มีอยู่"""
    src = REPO_SKILLS / skill["id"]
    dst = Path(skill["dir"])
    if not src.is_dir() or src.resolve() == dst.resolve():
        return []
    fixed = []
    for f in src.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            t = dst / f.relative_to(src)
            if not t.exists():
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, t)
                fixed.append(str(f.relative_to(src)))
    return fixed


# ---------------- ทำ 1 EP ----------------
def run_episode(ctx, proj, ep, s, skill):
    name = proj["name"]
    m = manifest(skill)
    skill_dir = Path(skill["dir"])
    fixed = heal_skill(skill)
    if fixed:
        ctx.log(f"เติมไฟล์สกิลที่ขาด {len(fixed)} ไฟล์จากโค้ดล่าสุด: " + ", ".join(fixed[:5]))
    edir = core.ep_dir(name, ep)
    raw = core.read_json(edir / "engine_ep.json")
    if not raw:
        raise ValueError(f"เทมเพลต '{skill['name']}' มีเอนจินของตัวเอง ต้องวางบท JSON ของ EP {ep} "
                         "(กดคัดลอกคำสั่งไปให้ Claude เขียน)")
    sdir = engine_dir(name)
    if not (sdir / "series.json").exists():
        raise ValueError("ไม่พบ series.json ของเรื่องนี้")
    state_f = edir / "state.json"
    state = core.read_json(state_f, {}) or {}

    def stage(t, **kw):
        state.update(stage=t, updated=time.time(), **kw)
        core.write_json(state_f, state)
        ctx.stage(f"EP {ep}: " + {"check": "ตรวจบท", "render": "สกิลเรนเดอร์", "post": "ลายน้ำ/export", "done": "เสร็จ"}.get(t, t))

    ep_json = sdir / f"ep{ep:02d}.json"
    core.write_json(ep_json, raw)
    py = sys.executable
    sec = int(s.get("target_seconds") or m.get("default_seconds") or 90)

    # 1) ตรวจบทด้วยตัวตรวจของสกิล
    stage("check")
    if m.get("check"):
        cmd = [py, str(skill_dir / m["check"][0])] + [str(x).format(episode=ep_json, seconds=sec) for x in m["check"][1:]]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(skill_dir), timeout=300)
        out = (r.stdout + r.stderr).strip()
        errs = [l for l in out.splitlines() if l.startswith("ERROR")]
        for l in out.splitlines()[-4:]:
            ctx.log("ตรวจบท: " + l)
        if r.returncode != 0 or errs:
            raise RuntimeError("บทไม่ผ่านตัวตรวจของสกิล ก๊อปข้อความนี้ไปให้ Claude แก้:\n" + "\n".join(errs or out.splitlines()[-8:]))
    ctx.check()

    # 2) เรนเดอร์ด้วยเอนจินของสกิล (เสียงคุมโดยระบบเรา)
    stage("render")
    work = core.WORK_DIR / core.safe_name(name) / f"ep{ep:02d}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    from . import voicecast, voicesheet
    try:
        series_now = core.read_json(sdir / "series.json") or {}
        spk = voicesheet.speakers(voicesheet.lines_engine(str(skill_dir), series_now, raw), series_now)
        s["voice_map"] = voicecast.resolve_for_episode(ctx, name, skill, s, spk, series_now, engine=True)
    except Exception as e:
        ctx.log(f"เลือกเสียงตัวละครอัตโนมัติไม่สำเร็จ: {e}")
    opts = {"voice": s.get("_voice_full") or "", "voice_map": s.get("voice_map") or {},
            "eleven_model": s.get("eleven_model") or "",
            "rate_add": int(str(s.get("edge_rate") or "+0%").replace("%", "") or 0),
            "mute": not s.get("voice_on", True),
            "sub_mode": sub_mode(s)}
    from .pipeline import voice_file_path
    own = voice_file_path(s)
    if own:
        opts.update(voice_file={k: str(v) for k, v in own.items()}, mute=False)
        ctx.log("ใช้เสียงพากย์ที่อัปโหลดแทนเสียง AI: " + ", ".join(f"{k}={v.name}" for k, v in own.items()))
    rawmp4 = work / "raw.mp4"
    total_shots = max(1, len(raw.get("shots") or []))

    def on_line(line):
        mm = re.match(r"shot (\d+)/(\d+)", line)
        if mm:
            ctx.progress(15 + 70 * int(mm.group(1)) / max(1, int(mm.group(2))))
        if line.startswith(("voice", "WARNING", "background", "DONE")):
            ctx.log(line[:200])

    ctx.log(f"สกิล {skill['name']} กำลังเรนเดอร์ {total_shots} ช็อต (ใช้เวลาหลายนาที)")
    ctx.run_stream([py, "-m", "app.engines.drama_runner", str(skill_dir), str(ep_json), "--out", str(rawmp4),
                    "--opts", json.dumps(opts, ensure_ascii=False)], "เรนเดอร์", cwd=str(CODE_DIR), on_line=on_line)

    # 3) ลายน้ำ + ความคมชัด
    stage("post")
    w, h = video.resolution("9:16", s.get("quality", "hd"))
    total = video.probe_duration(rawmp4)
    wm = (s.get("watermark_text") or "Thuean Studio") if s.get("watermark") else ""
    vf = [f"scale={w}:{h}:flags=lanczos"]
    if wm:
        ass, _, _ = video.build_subs([], w, h, s, watermark=wm, total=total, mode="none")
        (work / "wm.ass").write_text(ass, encoding="utf-8")
        vf.append("ass=wm.ass")
    subs = timeline_subs(ctx, raw, rawmp4, s)
    if subs and sub_mode(s) in ("en", "both"):
        (work / "en.ass").write_text(english_ass(subs, sub_mode(s)), encoding="utf-8")
        vf.append("ass=en.ass")
    ctx.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", "raw.mp4", "-vf", ",".join(vf),
             "-c:v", "libx264", "-preset", s["preset"], "-crf", str(s["crf"]), "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", "final.mp4"], "export", cwd=work)
    tmp = edir / "final.part.mp4"
    shutil.copyfile(work / "final.mp4", tmp)
    tmp.replace(edir / "final.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(3.0, total / 3):.1f}", "-i", str(edir / "final.mp4"),
                    "-frames:v", "1", "-vf", "scale=360:-1", str(edir / "thumb.jpg")])
    # ซับ .srt: จากไทม์ไลน์เสียงจริง (แม่นกว่า) · ไม่มีไทม์ไลน์ → ตัว export ของสกิล
    if subs:
        (edir / "subs.srt").write_text(_srt([(x["t0"], x["t1"], x["th"]) for x in subs]), encoding="utf-8")
        if any(x.get("en") for x in subs):
            (edir / "subs_en.srt").write_text(_srt([(x["t0"], x["t1"], x["en"]) for x in subs if x.get("en")]), encoding="utf-8")
    else:
        try:
            subprocess.run([py, str(skill_dir / "scripts" / "drama_tool.py"), "export", str(ep_json), "--cps", "12"],
                           capture_output=True, cwd=str(skill_dir), timeout=120)
            srt = sdir / f"ep{ep:02d}.srt"
            if srt.exists():
                shutil.copyfile(srt, edir / "subs.srt")
        except Exception:
            pass
    shutil.rmtree(work, ignore_errors=True)
    dur = video.probe_duration(edir / "final.mp4")
    stage("done", duration=round(dur, 1))
    ctx.progress(100)
    ctx.log(f"EP {ep} เสร็จ ({dur:.1f} วินาที)")
