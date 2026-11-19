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


def is_engine(skill):
    return bool(skill and skill.get("engine"))


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


def count_episodes(text):
    try:
        return len(parse_paste(text)["episodes"])
    except ValueError:
        return 0


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
    if idea:
        parts.append(f"ไอเดีย/พล็อต: {idea}")
    if s.get("_tweak_th"):
        parts.append(f"ปรับแต่งเพิ่มเติม: {s['_tweak_th']}")
    sec = int((series or {}).get("seconds") or s.get("target_seconds") or m.get("default_seconds") or 90)
    parts.append(f"""รูปแบบคำตอบ (ระบบอ่านอัตโนมัติ):
- ตอบเป็น code block ```json``` แยกก้อนละไฟล์: {'series.json แล้วตามด้วย ' if not series else ''}epNN.json ทีละ EP
- ความยาวตอนละประมาณ {sec} วินาที · ทุกคนในฉากต้องมี pose (และ prop ถ้าถือของ) · ตัวละครต้องมี rig
- ถ้ารันโค้ดได้ ให้รันตัวตรวจ drama_tool.py check จนผ่านก่อนส่ง
- ฉากหลังเฉพาะ (ไม่บังคับ): ส่งเป็น code block ```python``` บรรทัดแรก "# bg: <place_id>"
- ไม่ต้องมีคำอธิบายอื่น""")
    for f in m.get("prompt_files") or ["SKILL.md"]:
        p = sdir / f
        if p.exists():
            parts.append(f"===== {f} =====\n" + p.read_text(encoding="utf-8", errors="replace").strip())
    return "\n\n".join(parts)


# ---------------- ทำ 1 EP ----------------
def run_episode(ctx, proj, ep, s, skill):
    name = proj["name"]
    m = manifest(skill)
    skill_dir = Path(skill["dir"])
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
    opts = {"voice": s.get("_voice_full") or "", "voice_map": s.get("voice_map") or {},
            "rate_add": int(str(s.get("edge_rate") or "+0%").replace("%", "") or 0),
            "tts_model": s.get("openrouter_tts_model"), "mute": not s.get("voice_on", True)}
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
    wm = (s.get("watermark_text") or "สตูดิโอเถื่อน") if s.get("watermark") else ""
    vf = [f"scale={w}:{h}:flags=lanczos"]
    if wm:
        ass, _, _ = video.build_subs([], w, h, s, watermark=wm, total=total, mode="none")
        (work / "wm.ass").write_text(ass, encoding="utf-8")
        vf.append("ass=wm.ass")
    ctx.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", "raw.mp4", "-vf", ",".join(vf),
             "-c:v", "libx264", "-preset", s["preset"], "-crf", str(s["crf"]), "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", "final.mp4"], "export", cwd=work)
    tmp = edir / "final.part.mp4"
    shutil.copyfile(work / "final.mp4", tmp)
    tmp.replace(edir / "final.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(3.0, total / 3):.1f}", "-i", str(edir / "final.mp4"),
                    "-frames:v", "1", "-vf", "scale=360:-1", str(edir / "thumb.jpg")])
    # ซับ .srt จากตัว export ของสกิล (ถ้ามี)
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
