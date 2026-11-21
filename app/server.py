"""เว็บเซิร์ฟเวอร์ AutoClip  —  รัน: python -m app.server --port 8000"""
import argparse
import hashlib
import hmac
import os
import sys
import subprocess
import re
import shutil
import threading
import time
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from . import core, llm, pipeline
from .jobs import JobManager

VERSION = "0.2.0"
STATIC = Path(__file__).resolve().parent / "static"
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # อัปโหลดได้ถึง 2GB
jobs = None
PASSWORD = os.environ.get("AUTOCLIP_PASSWORD", "")
TOKEN = hashlib.sha256(("autoclip:" + PASSWORD).encode()).hexdigest()


def ok(data=None, **kw):
    return jsonify({"ok": True, "data": data, **kw})


@app.errorhandler(ValueError)
@app.errorhandler(llm.LLMError)
def _bad(e):
    return jsonify({"ok": False, "error": str(e)}), 400


@app.before_request
def _auth():
    if not PASSWORD:
        return
    p = request.path
    if p in ("/", "/api/login", "/api/ping") or p.startswith("/static"):
        return
    tok = request.cookies.get("ac_tok") or request.headers.get("X-AutoClip-Token", "")
    if not hmac.compare_digest(tok, TOKEN):
        return jsonify({"ok": False, "error": "ต้องเข้าสู่ระบบ", "auth": True}), 401


# ---------------- หน้าเว็บ ----------------
@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/static/<path:f>")
def static_file(f):
    r = send_from_directory(STATIC, f)
    r.headers["Cache-Control"] = "public, max-age=86400"
    return r


@app.get("/api/ping")
def ping():
    return ok({"auth_required": bool(PASSWORD)})


_LOGIN_TRIES = {}   # ip → เวลาที่ลอง (กันเดารหัสรัวๆ เพราะหน้าเว็บตรวจรหัสทุกครั้งที่พิมพ์)


@app.post("/api/login")
def login():
    ip = request.headers.get("CF-Connecting-IP") or request.remote_addr or "?"
    now = time.time()
    tries = [t for t in _LOGIN_TRIES.get(ip, []) if now - t < 60]
    if len(tries) >= 60:
        return jsonify({"ok": False, "error": "ลองบ่อยเกินไป รอ 1 นาที"}), 429
    _LOGIN_TRIES[ip] = tries + [now]
    pw = (request.get_json(silent=True) or {}).get("password", "")
    if PASSWORD and not hmac.compare_digest(pw, PASSWORD):
        return jsonify({"ok": False, "error": "รหัสผ่านไม่ถูกต้อง"}), 401
    resp = ok()
    resp.set_cookie("ac_tok", TOKEN, max_age=30 * 86400, httponly=True, samesite="Lax", secure=True)
    return resp


# ---------------- สถานะ ----------------
# ---------------- สกิล ----------------
@app.get("/api/skills")
def skills():
    return ok(core.list_skills())


@app.post("/api/skills")
def skill_save():
    return ok(core.save_skill(request.get_json(force=True)))


@app.get("/skill-cover/<sid>")
def skill_cover(sid):
    sk = core.get_skill(sid)
    if not sk or not sk.get("cover"):
        abort(404)
    if sk["cover"] == "sample":
        src, age = core.sample_cover(sid), 60
    else:
        src, age = core.SKILLS_DIR / sid / sk["cover"], 3600
    if not src:
        abort(404)
    w = request.args.get("w", type=int)
    if w:                                   # ภาพย่อสำหรับการ์ด: เล็ก โหลดเร็ว เก็บแคชบนเครื่อง (ไม่อ่าน Drive ซ้ำ)
        src = _thumb(Path(src), max(120, min(w, 800)))
    return send_file(src, max_age=age)


def _thumb(src, w):
    try:
        st = src.stat()
        out = core.WORK_DIR / "thumbs" / f"{hashlib.md5(str(src).encode()).hexdigest()[:12]}-{int(st.st_mtime)}-{w}.jpg"
        if not out.exists():
            from PIL import Image
            out.parent.mkdir(parents=True, exist_ok=True)
            im = Image.open(src).convert("RGB")
            im.thumbnail((w, w * 2))
            im.save(out, "JPEG", quality=82, optimize=True, progressive=True)
        return out
    except Exception:  # noqa: BLE001  ย่อไม่ได้ → ส่งภาพเต็ม
        return src


@app.delete("/api/skills/<sid>")
def skill_delete(sid):
    return ok(core.delete_skill(sid))


@app.post("/api/skills/<sid>/media")
def skill_media(sid):
    f = request.files.get("file")
    if not f:
        abort(400)
    return ok(core.save_skill_media(sid, f))


@app.get("/skill-sample/<sid>")
def skill_sample(sid):
    d = core.SKILLS_DIR / sid
    f = d / "card.mp4" if request.args.get("card") and (d / "card.mp4").exists() else d / "sample.mp4"
    if not core.get_skill(sid) or not f.exists():
        abort(404)
    return send_file(f, max_age=300, conditional=True)


@app.post("/api/skills/<sid>/engine")
def skill_engine_upload(sid):
    """อัปโหลด engine.zip ที่ได้จาก Claude Code → เทมเพลตนี้วาดภาพด้วยเอนจินนั้นทุกตอน"""
    from . import engine_html
    sk = core.get_skill(sid)
    f = request.files.get("file")
    if not sk or not f:
        abort(400)
    return ok(engine_html.install_zip(sk, f))


@app.post("/api/skills/<sid>/engine-prompt")
def skill_engine_prompt(sid):
    """คำสั่งให้ Claude Code สร้างเอนจิน + บท EP 1 (ใช้โควตา Claude ของผู้ใช้ ไม่เสียเครดิตเว็บ)"""
    from . import engine_html
    from .pipeline import effective_settings
    sk = core.get_skill(sid)
    if not sk:
        abort(404)
    b = request.get_json(force=True, silent=True) or {}
    s = effective_settings({"options": b.get("options") or {}}, sk)
    return ok({"prompt": engine_html.claude_code_prompt(sk, b.get("idea") or "", s)})


@app.get("/api/skills/<sid>")
def skill_get(sid):
    s = core.get_skill(sid)
    if not s:
        abort(404)
    return ok(s)


# ---------------- โปรเจกต์ ----------------
@app.get("/api/projects")
def projects():
    return ok(core.list_projects())


@app.post("/api/projects")
def project_create():
    return ok(core.create_project(request.get_json(force=True)))


@app.get("/api/projects/<name>")
def project_get(name):
    p = core.get_project(name)
    if not p:
        abort(404)
    return ok(p)


@app.patch("/api/projects/<name>")
def project_update(name):
    return ok(core.update_project(name, request.get_json(force=True)))


@app.post("/api/projects/<name>/upload")
def project_upload(name):
    d = core.project_dir(name)
    if not (d / "project.json").exists():
        abort(404)
    target = request.form.get("target", "input")
    if target not in ("input", "music"):
        raise ValueError("target ต้องเป็น input หรือ music")
    allowed = (core.VIDEO_EXT | core.IMAGE_EXT) if target == "input" else core.AUDIO_EXT
    saved = []
    for f in request.files.getlist("files"):
        fn = core.safe_name(Path(f.filename or "").name)
        if not fn or Path(fn).suffix.lower() not in allowed:
            continue
        (d / target).mkdir(exist_ok=True)
        f.save(d / target / fn)
        saved.append(fn)
    return ok(saved)


@app.get("/api/projects/<name>/episodes/<int:ep>/script")
def script_get(name, ep):
    s = core.read_json(core.ep_dir(name, ep) / "script.json")
    if s is None:
        abort(404)
    return ok(s)


@app.put("/api/projects/<name>/episodes/<int:ep>/script")
def script_put(name, ep):
    data = request.get_json(force=True)
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
        raise ValueError("รูปแบบบทไม่ถูกต้อง ต้องมี scenes")
    core.write_json(core.ep_dir(name, ep) / "script.json", data)
    return ok()


@app.post("/api/projects/<name>/episodes/<int:ep>/reset")
def episode_reset(name, ep):
    """mode=render: ลบแค่วิดีโอ (ใช้บท/เสียงเดิม)  mode=voice: ลบเสียง+วิดีโอ  mode=all: เริ่มตอนนี้ใหม่หมด"""
    if jobs.busy():
        raise ValueError("มีงานกำลังรันอยู่ หยุดงานก่อน")
    mode = (request.get_json(silent=True) or {}).get("mode", "render")
    d = core.ep_dir(name, ep)
    if not d.exists():
        abort(404)
    if mode == "all":
        d.rename(d.parent / f"_old_ep{ep:02d}_{int(time.time())}")
    else:
        for f in ("final.mp4", "subs.srt", "subs_en.srt", "final_nosound.mp4"):
            (d / f).unlink(missing_ok=True)
        if mode == "voice":
            shutil.rmtree(d / "audio", ignore_errors=True)
        st = core.read_json(d / "state.json", {}) or {}
        st["stage"] = "reset"
        core.write_json(d / "state.json", st)
    return ok()


@app.post("/api/projects/<name>/episodes/<int:ep>/revoice")
def episode_revoice(name, ep):
    """พากย์ EP ที่เสร็จแล้วใหม่: เปลี่ยนเสียง และ/หรือ ใช้ไฟล์เสียงที่อัปเอง · ใช้บทและภาพเดิม
    คลิปเดิมเก็บไว้เป็นอีกคลิปในคลัง (ไม่ลบทิ้ง) · ไม่มีงานรันอยู่ในเรื่องเดียวกันก่อน"""
    b = request.get_json(force=True) or {}
    d = core.ep_dir(name, ep)
    if not (d / "final.mp4").exists():
        abort(404)
    if any(j["project"] == name and j["status"] in ("queued", "running", "review") for j in jobs.list()):
        raise ValueError("เรื่องนี้มีงานกำลังทำอยู่ รอให้เสร็จก่อน")
    vf = _take_voice({"voice_file": b.get("voice_file")}) if b.get("voice_file") else None
    vmap = {k: v for k, v in (b.get("voice_map") or {}).items() if k and v}
    if not vf and not b.get("voice") and not vmap:
        raise ValueError("เปลี่ยนเสียงตัวละคร หรือใส่ไฟล์เสียงก่อน")
    if vmap:                                       # เสียงตัวละครที่เปลี่ยน → จำไว้กับเรื่อง (EP ต่อไปใช้เสียงใหม่ด้วย)
        p = core.get_project(name) or {}
        opts = dict(p.get("options") or {})
        opts["voice_map"] = {**(opts.get("voice_map") or {}), **vmap}
        core.update_project(name, {"options": opts})
    keep = core.project_dir(name) / f"_old_ep{ep:02d}_{int(time.time())}"   # คลิปเดิม → อีกคลิปในคลัง
    keep.mkdir(parents=True)
    for f in ("final.mp4", "thumb.jpg", "subs.srt", "subs_en.srt", "script.json", "caption.txt"):
        if (d / f).exists():
            shutil.copy2(d / f, keep / f)
    for f in ("final.mp4", "subs.srt", "subs_en.srt", "final_nosound.mp4", "caption.txt"):
        (d / f).unlink(missing_ok=True)
    shutil.rmtree(d / "audio", ignore_errors=True)
    st = core.read_json(d / "state.json", {}) or {}
    st["stage"] = "reset"
    o = st.setdefault("opts", {})
    o.pop("voice_file", None)
    if b.get("voice"):
        o["voice"] = b["voice"]
    if vmap:
        o["voice_map"] = {**(o.get("voice_map") or {}), **vmap}
    if vf:
        o["voice_file"] = vf
    core.write_json(d / "state.json", st)
    return ok(jobs.submit(name, 1))


@app.get("/api/projects/<name>/moss-voices")
def moss_voices(name):
    from . import moss
    return ok(moss.list_refs(name))


@app.route("/api/projects/<name>/moss-voices/<fname>", methods=["GET", "DELETE"])
def moss_voice_file(name, fname):
    """ฟังเสียงต้นแบบของตัวละคร · ลบ = ให้ระบบออกแบบเสียงใหม่ตอนพากย์ครั้งถัดไป"""
    from . import moss
    f = moss.ref_file(name, fname)
    if not moss.safe_file(fname) or not f.exists():
        abort(404)
    if request.method == "DELETE":
        f.unlink()
        f.with_suffix(".json").unlink(missing_ok=True)
        return ok()
    return send_file(f, mimetype="audio/wav", max_age=0)


@app.get("/media/<name>/<path:rel>")
def media(name, rel):
    d = core.project_dir(name)
    f = (d / rel).resolve()
    if d not in f.parents or not f.is_file():
        abort(404)
    if request.args.get("mute") and f.suffix == ".mp4":
        m = f.with_name(f.stem + "_nosound.mp4")
        if not m.exists() or m.stat().st_mtime < f.stat().st_mtime:
            import subprocess
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(f), "-an", "-c:v", "copy",
                            "-movflags", "+faststart", str(m)], check=True)
        f = m
    return send_file(f, conditional=True, download_name=f"{name}_{f.parent.name}_{f.name}"
                     if request.args.get("dl") else None, as_attachment=bool(request.args.get("dl")))


@app.get("/api/outputs")
def outputs():
    return ok(core.list_outputs())


# ---------------- สร้างคลิปจากแถบพิมพ์ (หน้าเดียวจบ) ----------------
def _clean_opts(o):
    # tweaks ว่าง = ตั้งใจไม่ปรับแต่ง (ต้องเก็บไว้เพื่อแทนที่ค่าของ EP ก่อน)
    return {k: v for k, v in (o or {}).items() if v not in (None, "") or k in ("tweaks", "tweak_text")}


VOICE_DIR = core.ROOT / "uploads" / "voice"
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".webm"}


@app.post("/api/voice-upload")
def voice_upload():
    """อัปไฟล์เสียงพากย์ทั้ง EP (ใช้แทนเสียง AI)"""
    from . import voiceover
    f = request.files.get("file")
    if not f or not f.filename:
        raise ValueError("ไม่พบไฟล์เสียง")
    ext = Path(f.filename).suffix.lower()
    if ext not in AUDIO_EXT:
        raise ValueError("รองรับไฟล์เสียง " + " ".join(sorted(AUDIO_EXT)))
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time())}_{core.safe_name(Path(f.filename).stem)[:40]}{ext}"
    dst = VOICE_DIR / name
    f.save(dst)
    if dst.stat().st_size > 80e6:
        dst.unlink()
        raise ValueError("ไฟล์เสียงใหญ่เกิน 80 MB")
    dur = voiceover.duration(dst)
    if dur < 1:
        dst.unlink()
        raise ValueError("อ่านไฟล์เสียงไม่ได้ หรือสั้นเกินไป")
    return ok({"id": name, "name": f.filename, "duration": round(dur, 1)})


def _take_voice(opts):
    """voice_file ใช้กับ EP เดียว (EP แรกของงานนี้) → แยกออกจากค่าของเรื่อง"""
    vf = (opts or {}).pop("voice_file", None)
    if not vf:
        return None
    m = vf if isinstance(vf, dict) else {"*": vf}
    out = {}
    for k, v in m.items():
        if not v:
            continue
        if not (VOICE_DIR / Path(str(v)).name).exists():
            raise ValueError(f"ไม่พบไฟล์เสียงที่อัปไว้ ({v}) ลองอัปใหม่")
        out[str(k)] = Path(str(v)).name
    return out or None


def _attach_voice(name, ep, vf):
    if not vf:
        return
    f = core.ep_dir(name, ep) / "state.json"
    st = core.read_json(f, {}) or {}
    st.setdefault("opts", {})["voice_file"] = vf
    core.write_json(f, st)


def _voice_sheets(text=None, tpl=None, project=None, ep=None):
    """บทพากย์แยกตัวละคร จากบทที่วาง (ก่อนสร้าง) หรือจาก EP ที่ทำแล้ว"""
    from . import voicesheet as VS
    p = core.get_project(project) if project else None
    sid = tpl or (p or {}).get("skill") or ""
    skill = core.get_skill(sid) if sid else None
    out = []
    if skill and skill.get("engine"):
        from . import engine_skill
        if text:
            parsed = engine_skill.parse_paste(text)
            series = parsed["series"] or (core.read_json(engine_skill.engine_dir(project) / "series.json") if project else None)
            eps = parsed["episodes"]
        else:
            series = core.read_json(engine_skill.engine_dir(project) / "series.json")
            eps = [core.read_json(core.ep_dir(project, ep) / "engine_ep.json")]
        if not series:
            raise ValueError("ต้องมี series.json (รายชื่อตัวละคร) ในบทที่วาง")
        for e in eps:
            if not e:
                continue
            lines = VS.lines_engine(skill["dir"], series, e)
            spk = VS.speakers(lines, series)
            out.append({"title": e.get("title") or f"EP{e.get('ep', '')}", "speakers": spk, "lines": lines,
                        "sheet": VS.sheet_text(e.get("title") or "", lines, spk)})
    else:
        from .pipeline import parse_manual_episodes
        if text:
            eps = parse_manual_episodes(text, 99)
        else:
            eps = [core.read_json(core.ep_dir(project, ep) / "script.json")]
        for e in eps:
            if not e:
                continue
            lines = VS.lines_manual(e.get("scenes") or [])
            spk = VS.speakers(lines)
            out.append({"title": e.get("title") or "", "speakers": spk, "lines": lines, "sheet": VS.sheet_text(e.get("title") or "", lines, spk)})
    if not out:
        raise ValueError("ไม่พบบทพากย์")
    return out


PREVIEW_TEXT = "สวัสดีครับ นี่คือเสียงตัวอย่างสำหรับเล่าเรื่องในคลิปของคุณ"


@app.get("/api/voices/preview")
def voice_preview():
    """ฟังเสียงตัวอย่าง: Edge ฟรี (สร้างครั้งเดียวแล้วเก็บไว้) · ElevenLabs ใช้ตัวอย่างของเขาเอง (ไม่เสียเครดิต)"""
    v = request.args.get("v", "")
    if v.startswith("eleven:"):
        from . import eleven
        url = next((x.get("preview") for x in eleven.voices() if x.get("id") == v[7:]), "")
        return ok({"url": url}) if url else (jsonify({"ok": False, "error": "เสียงนี้ไม่มีตัวอย่างให้ฟัง"}), 404)
    name = v.removeprefix("edge:").split("|")[0]
    if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}-\w+Neural", name):
        abort(400)
    name = pipeline.EDGE_FIX.get(name, name)
    out = core.WORK_DIR / "voice-preview" / f"{name}.mp3"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            pipeline.edge_say(name, PREVIEW_TEXT, out)
        except Exception as e:  # noqa: BLE001
            out.unlink(missing_ok=True)
            return jsonify({"ok": False, "error": str(e)}), 502
    return ok({"url": f"/api/voices/preview.mp3?v={name}"})


@app.get("/api/voices/preview.mp3")
def voice_preview_file():
    name = request.args.get("v", "")
    f = core.WORK_DIR / "voice-preview" / f"{name}.mp3"
    if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}-\w+Neural", name) or not f.exists():
        abort(404)
    return send_file(f, mimetype="audio/mpeg", max_age=86400)


@app.get("/api/eleven")
def eleven_status():
    """สถานะ ElevenLabs: มี key ไหม + รายชื่อเสียงในบัญชี + โมเดลที่อ่านไทยได้ + เครดิตคงเหลือ"""
    from . import eleven
    out = {"enabled": eleven.enabled(), "models": [{"id": m[0], "name": m[1], "rate": m[2], "tags": m[3]} for m in eleven.MODELS],
           "default_model": eleven.DEFAULT_MODEL, "voices": [], "sub": None, "error": ""}
    if out["enabled"]:
        try:
            out["voices"] = eleven.voices()
        except Exception as e:
            out["error"] = str(e)
        try:
            out["sub"] = eleven.subscription()
        except Exception:
            pass
    return ok(out)


@app.post("/api/voice-auto")
def voice_auto():
    """ดูเสียงที่ระบบจะเลือกให้ (ไม่บันทึก) + เครดิตโดยประมาณ"""
    from . import voicecast, eleven
    b = request.get_json(force=True)
    sheets = _voice_sheets(text=b.get("text"), tpl=b.get("template"), project=b.get("project"),
                           ep=b.get("ep"))
    p = core.get_project(b.get("project")) if b.get("project") else None
    sid = b.get("template") or (p or {}).get("skill") or ""
    skill = core.get_skill(sid) if sid else None
    series = None
    if skill and skill.get("engine"):
        from . import engine_skill
        parsed = engine_skill.parse_paste(b.get("text")) if b.get("text") else {"series": None}
        series = parsed.get("series") or (core.read_json(engine_skill.engine_dir(p["name"]) / "series.json") if p else None)
    pmap = dict(((p or {}).get("options") or {}).get("voice_map") or {})
    pmap.update({k: v for k, v in (b.get("voice_map") or {}).items() if v})
    spk = sheets[0]["speakers"]
    from .pipeline import _apply_voice
    sv = {}
    if b.get("voice"):
        _apply_voice(sv, b["voice"])
    np_ = b.get("narrator_paid")
    if np_ is None:
        np_ = ((p or {}).get("options") or {}).get("narrator_paid")
    if np_:
        sv["narrator_paid"] = True
        from . import voicesheet as VS
        spk = VS.speakers(sheets[0]["lines"], series, True)   # บรรยายคิดเครดิตด้วย
    provider = voicecast.provider_for(skill, sv)
    if skill and skill.get("engine") and provider == "edge":
        vm = pmap
    else:
        known = None
        if not (skill and skill.get("engine")):
            ctxt = "\n".join(f"[{x['name']}] {x['text']}" for x in sheets[0]["lines"])
            known = voicecast.classify(skill, spk, ctxt)       # ความรู้เรื่องเพศ/วัย เก็บไว้ได้
        mem_before = voicecast.load_mem(sid)
        vm, provider = voicecast.auto_map(spk, skill, pmap, series, known=known, preview=True, s=sv)
        voicecast.save_mem(sid, mem_before)          # แค่ดูตัวอย่าง: ยังไม่จำการเลือกเสียง
    model = b.get("eleven_model") or ((p or {}).get("options") or {}).get("eleven_model") or eleven.DEFAULT_MODEL
    rate = eleven.model_info(model)[2]
    credits = sum(int(x.get("paid_chars", x["chars"]) * rate) for x in spk if str(vm.get(x["key"], "")).startswith("eleven:"))
    return ok({"provider": provider, "voice_map": vm, "speakers": spk, "credits": credits, "model": model, "narrator_paid": bool(np_)})


@app.post("/api/projects/<name>/voices")
def project_voices(name):
    """บันทึกเสียงตัวละครของเรื่อง (ใช้ทุก EP ต่อจากนี้)"""
    p = core.get_project(name)
    if not p:
        abort(404)
    b = request.get_json(force=True)
    opts = dict(p.get("options") or {})
    if "voice_map" in b:
        opts["voice_map"] = {k: v for k, v in (b.get("voice_map") or {}).items() if v}
    if b.get("eleven_model"):
        opts["eleven_model"] = b["eleven_model"]
    if "narrator_paid" in b:
        opts["narrator_paid"] = bool(b["narrator_paid"])
    core.update_project(name, {"options": opts})
    return ok({"options": opts})


@app.post("/api/voice-sheet")
def voice_sheet():
    b = request.get_json(force=True)
    return ok(_voice_sheets(text=b.get("text"), tpl=b.get("template"), project=b.get("project")))


@app.get("/api/projects/<name>/episodes/<int:ep>/voice-sheet")
def voice_sheet_ep(name, ep):
    return ok(_voice_sheets(project=name, ep=ep))


@app.post("/api/voice-match")
def voice_match():
    """จับคู่ชื่อไฟล์เสียงกับตัวละคร"""
    from . import voicesheet as VS
    b = request.get_json(force=True)
    spk = b.get("speakers") or []
    return ok({f: VS.match_file(f, spk) for f in b.get("files") or []})


def _prep_ep(name, ep, opts=None, script=None):
    d = core.ep_dir(name, ep)
    if d.exists():
        d.rename(d.parent / f"_old_ep{ep:02d}_{int(time.time())}")
    st = {"stage": "script" if script else "new", "approved": bool(script), "updated": time.time()}
    if opts:
        st["opts"] = opts
    core.write_json(d / "state.json", st)
    if script:
        core.write_json(d / "script.json", script)


def _write_manual_eps(name, eps, start, opts=None):
    for i, sc in enumerate(eps):
        _prep_ep(name, start + i, opts, sc)


def _scenes_for(opts, skill_id):
    from .pipeline import effective_settings
    return effective_settings({"options": opts}, core.get_skill(skill_id) if skill_id else None)


@app.post("/api/create")
def quick_create():
    b = request.get_json(force=True)
    mode = b.get("mode") or "ai"
    idea = str(b.get("idea") or "").strip()
    if not idea:
        raise ValueError("พิมพ์ไอเดียหรือบทก่อน")
    opts = _clean_opts(b.get("options"))
    vf = _take_voice(opts)
    tpl = b.get("template") or ""
    skill = core.get_skill(tpl) if tpl else None
    if skill and skill.get("engine"):
        from . import engine_skill
        parsed = engine_skill.parse_paste(idea)
        if not parsed["episodes"]:
            raise ValueError("ยังไม่มีบท EP (epNN.json) ในข้อความที่วาง")
        if not parsed["series"]:
            raise ValueError("เรื่องใหม่ต้องมี series.json (ไบเบิลซีรีส์) มาด้วย")
        name = core.unique_project_name(b.get("name") or engine_skill.series_title(parsed, "ซีรีส์ใหม่")[:40])
        proj = core.create_project({"name": name, "skill": tpl, "episodes_total": len(parsed["episodes"]),
                                    "topic": "", "script_mode": "engine", "options": opts})
        n = engine_skill.save_paste(proj["name"], parsed, 1)
        _attach_voice(proj["name"], 1, vf)
        return ok({"project": proj, "job": jobs.submit(proj["name"], n), "episodes": n})
    eps = []
    if mode == "manual":
        from .pipeline import parse_manual_episodes
        eps = parse_manual_episodes(idea, _scenes_for(opts, tpl)["scenes_per_episode"])
        first = eps[0]["title"]
    else:
        first = idea.lstrip("#").strip().splitlines()[0]
    name = core.unique_project_name(b.get("name") or first[:40])
    proj = core.create_project({
        "name": name, "skill": tpl, "episodes_total": max(1, len(eps)),
        "topic": idea if mode == "ai" else "", "script_mode": mode, "options": opts,
    })
    if eps:
        _write_manual_eps(proj["name"], eps, 1)
    elif vf:
        _prep_ep(proj["name"], 1)
    _attach_voice(proj["name"], 1, vf)
    job = jobs.submit(proj["name"], max(1, len(eps)))
    return ok({"project": proj, "job": job, "episodes": max(1, len(eps))})


@app.post("/api/projects/<name>/next")
def project_next(name):
    """ทำ EP ต่อ: mode=manual วางบท (หลาย EP ได้, ฟรี) | mode=ai ให้ AI เขียน 1 EP"""
    p = core.get_project(name)
    if not p:
        abort(404)
    if jobs.has_pending(name):
        raise ValueError("เรื่องนี้มีงานค้างอยู่แล้ว รอให้เสร็จก่อน")
    b = request.get_json(silent=True) or {}
    start = p["done_count"] + 1
    ep_opts = _clean_opts(b.get("options"))   # เช่น เลือกเสียงเฉพาะ EP นี้
    vf = _take_voice(ep_opts)
    skill = core.get_skill(p.get("skill")) if p.get("skill") else None
    if skill and skill.get("engine"):
        from . import engine_skill
        if b.get("mode") != "manual":
            raise ValueError("เทมเพลตนี้มีเอนจินของตัวเอง ต้องวางบท JSON จาก Claude (กดคัดลอกคำสั่ง)")
        parsed = engine_skill.parse_paste(b.get("text"))
        if not parsed["episodes"]:
            raise ValueError("ไม่พบบท EP (epNN.json) ในข้อความที่วาง")
        n = engine_skill.save_paste(name, parsed, start)
        if ep_opts:
            for k in range(start, start + n):
                st = core.read_json(core.ep_dir(name, k) / "state.json", {}) or {}
                st["opts"] = ep_opts
                core.write_json(core.ep_dir(name, k) / "state.json", st)
        _attach_voice(name, start, vf)
        core.update_project(name, {"episodes_total": start + n - 1})
        return ok({**jobs.submit(name, n), "episodes": n})
    if b.get("mode") == "manual":
        from .pipeline import parse_manual_episodes
        eps = parse_manual_episodes(b.get("text"), _scenes_for(p.get("options") or {}, p.get("skill"))["scenes_per_episode"])
        _write_manual_eps(name, eps, start, ep_opts)
        _attach_voice(name, start, vf)
        core.update_project(name, {"episodes_total": start + len(eps) - 1})
        return ok({**jobs.submit(name, len(eps)), "episodes": len(eps)})
    if ep_opts or vf:
        _prep_ep(name, start, ep_opts)
    _attach_voice(name, start, vf)
    core.update_project(name, {"episodes_total": start})
    return ok(jobs.submit(name, 1))


@app.post("/api/prompt")
def make_prompt():
    """คำสั่งสำเร็จรูปสำหรับก๊อปไปถาม Claude ในแชท (ฟรี)"""
    from .pipeline import chat_prompt, effective_settings, story_context
    b = request.get_json(force=True)
    count = max(1, min(20, int(b.get("count") or 1)))
    if b.get("project"):
        p = core.get_project(b["project"])
        if not p:
            abort(404)
        skill = core.get_skill(p.get("skill")) if p.get("skill") else None
        s = effective_settings(p, skill, _clean_opts(b.get("options")))
        start = p["done_count"] + 1
        if skill and skill.get("engine"):
            from . import engine_skill
            return ok({"prompt": engine_skill.chat_prompt(skill, p["name"], start, count, s, b.get("idea") or "")})
        text = chat_prompt(skill, b.get("idea") or "", start, count, s,
                           story_context(p["name"], start - 1), p.get("bible") or "")
    else:
        skill = core.get_skill(b.get("template")) if b.get("template") else None
        s = effective_settings({"options": b.get("options") or {}}, skill)
        if skill and skill.get("engine"):
            from . import engine_skill
            return ok({"prompt": engine_skill.chat_prompt(skill, "", 1, count, s, b.get("idea") or "")})
        text = chat_prompt(skill, b.get("idea") or "", 1, count, s)
    return ok({"prompt": text})


# ---------------- คลังข้อความ ----------------
@app.get("/api/library")
def library_list():
    return ok(core.list_library())


@app.post("/api/library")
def library_save():
    return ok(core.save_library_item(request.get_json(force=True)))


@app.delete("/api/library/<iid>")
def library_delete(iid):
    return ok(core.delete_library_item(iid))


# ---------------- เครดิต OpenRouter ----------------
@app.get("/api/credits")
def credits():
    if not os.environ.get("OPENROUTER_API_KEY"):
        return ok(None)
    try:
        d = llm.account() or {}
        return ok({k: d.get(k) for k in ("limit", "limit_remaining", "usage", "usage_daily", "usage_weekly",
                                          "usage_monthly", "is_free_tier", "free_model_daily_requests")})
    except Exception as e:
        return ok({"error": str(e)})


@app.get("/api/usage")
def usage():
    """รายละเอียดค่าใช้จ่าย: รายการล่าสุด + สรุปตามประเภท/โมเดล (วันนี้ และทั้งหมดที่บันทึก)"""
    import datetime as dt
    rows = llm.read_ledger(3000)
    today = dt.datetime.now().date()

    def summarize(items):
        agg = {}
        for r in items:
            if r.get("kind", "").startswith("รวมทั้งงาน"):
                continue
            k = (r.get("kind"), r.get("model"))
            a = agg.setdefault(k, {"kind": k[0], "model": k[1], "calls": 0, "cost": 0.0, "unknown": 0, "fail": 0})
            a["calls"] += 1
            if not r.get("ok", True):
                a["fail"] += 1
            if r.get("cost") is None:
                a["unknown"] += 1
            else:
                a["cost"] += r["cost"]
        return sorted(agg.values(), key=lambda a: -a["cost"])

    todays = [r for r in rows if dt.datetime.fromtimestamp(r.get("t", 0)).date() == today]
    jobs_cost = [r for r in rows if r.get("kind", "").startswith("รวมทั้งงาน")]
    return ok({"recent": rows[-150:][::-1], "today": summarize(todays), "all": summarize(rows),
               "jobs": jobs_cost[-30:][::-1], "since": rows[0]["t"] if rows else None})


# ---------------- AI ช่วยคิดเรื่อง ----------------
@app.post("/api/ai/idea")
def ai_idea():
    body = request.get_json(force=True)
    s = core.load_settings()
    skill = core.get_skill(body.get("skill")) if body.get("skill") else None
    msgs = [
        {"role": "system", "content":
            "คุณคือนักคิดพล็อตหนังสั้นแอนิเมชัน ตอบ JSON เท่านั้น: "
            '{"name": "ชื่อเรื่องสั้นๆ", "topic": "พล็อตย่อ 3-5 ประโยค", "episodes_total": จำนวนตอนที่เหมาะ}'
            + (f"\n\nสไตล์ที่ต้องใช้:\n{skill['content'][:4000]}" if skill else "")},
        {"role": "user", "content": f"คิดเรื่องใหม่ที่สนุกและไม่ซ้ำ ภาษา{s['language']} "
                                    f"{('แนวทาง: ' + body['hint']) if body.get('hint') else ''}"},
    ]
    from .pipeline import script_model
    text, cost = llm.chat(script_model(s), msgs, json_mode=True, temperature=1.0, max_tokens=800)
    data = llm.parse_json(text)
    data["cost_usd"] = cost
    return ok(data)


# ---------------- งาน ----------------
@app.get("/api/jobs")
def jobs_list():
    return ok(jobs.list())


@app.post("/api/jobs")
def jobs_submit():
    b = request.get_json(force=True)
    return ok(jobs.submit(b.get("project"), b.get("count", 1)))


@app.get("/api/jobs/<jid>")
def job_get(jid):
    j = jobs.get(jid)
    if not j:
        abort(404)
    return ok(j)


@app.post("/api/jobs/<jid>/stop")
def job_stop(jid):
    return ok(jobs.stop(jid))


@app.post("/api/jobs/<jid>/approve")
def job_approve(jid):
    return ok(jobs.approve(jid))


@app.post("/api/jobs/<jid>/resume")
def job_resume(jid):
    return ok(jobs.resume(jid))


@app.delete("/api/jobs/<jid>")
def job_delete(jid):
    return ok(jobs.delete(jid))


@app.post("/api/jobs/clear")
def jobs_clear():
    return ok(jobs.clear_finished())


@app.delete("/api/projects/<name>/episodes/<int:ep>")
def episode_delete(name, ep):
    """ลบคลิป 1 EP ถาวร (บทต้นฉบับ/เทมเพลตยังอยู่ ทำใหม่ได้)"""
    if jobs.has_pending(name):
        raise ValueError("เรื่องนี้มีงานค้างอยู่ หยุดหรือลบงานก่อน")
    d = core.ep_dir(name, ep)
    if not d.exists():
        abort(404)
    others = [e for e in [*core.project_dir(name).glob("ep[0-9]*"), *core.project_dir(name).glob("_old_ep*")]
              if e.is_dir() and e != d and any(f.is_file() for f in e.rglob("*"))]
    if not others:                                  # ผู้ใช้ลบตอนสุดท้ายของเรื่อง → ย้ายทั้งเรื่องไปถังขยะพร้อมกัน (ไม่เหลือโฟลเดอร์ค้าง)
        core.trash_move(core.project_dir(name), "story", name)
        jobs.forget_project(name)
        return ok({"story": True})
    core.trash_move(d, "ep", f"{name} · EP {ep}")   # ไปถังขยะ (กู้คืนได้)
    return ok()


@app.get("/api/trash")
def trash_list():
    return ok(core.trash_list())


@app.post("/api/trash/restore")
def trash_restore():
    m = core.trash_restore((request.get_json(force=True) or {}).get("id"))
    return ok(m)


@app.post("/api/trash/purge")
def trash_purge():
    """ลบถาวรจากถังขยะ (ids ว่าง/ไม่ส่ง = ล้างทั้งหมด) → หายจาก Drive ทันที"""
    b = request.get_json(force=True) or {}
    return ok(core.trash_purge(b.get("ids") if b.get("ids") else None))


@app.get("/api/storage")
def storage():
    """ไฟล์ค้าง/ไม่ได้ใช้ ให้เลือกลบเอง"""
    return ok(core.storage_report(jobs.has_pending))


@app.post("/api/storage/delete")
def storage_delete():
    r = core.storage_delete((request.get_json(force=True) or {}).get("ids") or [], jobs.has_pending)
    for n in r["stories"]:
        jobs.forget_project(n)
    return ok(r)


@app.post("/api/projects/<name>/rename")
def project_rename(name):
    """เปลี่ยนชื่อเรื่อง (ชื่อโฟลเดอร์ใน Drive + project.json)"""
    new = core.safe_name((request.get_json(force=True) or {}).get("name"))
    if not new:
        raise ValueError("ชื่อเรื่องว่าง")
    if jobs.has_pending(name):
        raise ValueError("เรื่องนี้มีงานค้างอยู่ รอให้เสร็จก่อนค่อยเปลี่ยนชื่อ")
    d = core.project_dir(name)
    if not (d / "project.json").exists():
        abort(404)
    nd = core.project_dir(new)
    if nd != d:
        if nd.exists():
            raise ValueError(f"มีเรื่องชื่อ “{new}” อยู่แล้ว")
        d.rename(nd)
    p = core.read_json(nd / "project.json", {})
    p["name"] = new
    core.write_json(nd / "project.json", p)
    return ok({"name": new})


@app.route("/api/projects/<name>/episodes/<int:ep>/caption", methods=["GET", "POST"])
def ep_caption(name, ep):
    """แคปชั่นโพสต์ TikTok/Reels ของตอนนี้ (AI ฟรี) · เก็บไว้ใน caption.txt · POST = คิดใหม่"""
    d = core.ep_dir(name, ep)
    f = d / "caption.txt"
    if request.method == "GET" and f.exists():
        return ok({"caption": f.read_text(encoding="utf-8")})
    sc = core.read_json(d / "script.json", {}) or {}
    lines = " ".join((x.get("narration") or "") for x in sc.get("scenes") or [])[:3000]
    if not lines.strip():
        raise ValueError("ตอนนี้ไม่มีบท คิดแคปชั่นไม่ได้")
    s = core.load_settings()
    msgs = [{"role": "system", "content":
             "คุณคือแอดมินช่อง TikTok/Reels หนังสั้นแอนิเมชันไทย เขียนแคปชั่นโพสต์ที่คนอยากกดดูและกดติดตาม "
             "รูปแบบ: บรรทัดแรกเป็นประโยคเปิดที่ชวนสงสัย (ไม่สปอยล์ตอนจบ) · บรรทัดที่สองสั้นๆ ชวนติดตามตอนต่อไป · "
             "บรรทัดสุดท้ายแฮชแท็ก 5-8 อัน (ไทยผสมอังกฤษ เกี่ยวกับเรื่อง + #หนังสั้น #การ์ตูน #fyp) · "
             "ภาษาเป็นกันเอง ไม่ยาวเกิน 300 ตัวอักษร ไม่ใช้อีโมจิเกิน 2 ตัว ตอบเฉพาะแคปชั่น"},
            {"role": "user", "content": f"เรื่อง: {name} · EP {ep}: {sc.get('title') or ''}\nบท: {lines}"}]
    from .pipeline import script_model
    llm.set_tag("แคปชั่น")
    text, _ = llm.chat(script_model(s), msgs, temperature=0.9, max_tokens=500)
    text = text.strip().strip('"').strip()
    f.write_text(text, encoding="utf-8")
    return ok({"caption": text})


@app.post("/api/skills/import")
def skill_import():
    """เพิ่มเทมเพลตจากไฟล์สกิล (.zip ที่มี SKILL.md · หรือ .md/.txt)"""
    f = request.files.get("file")
    if not f:
        abort(400)
    from . import engine_html
    return ok(engine_html.import_skill(f))


@app.delete("/api/projects/<name>")
def project_delete(name):
    """ลบทั้งเรื่อง → ถังขยะของเว็บ (กู้คืนได้) + เอางานของเรื่องนี้ออกจากรายการ"""
    if jobs.has_pending(name):
        raise ValueError("เรื่องนี้มีงานค้างอยู่ หยุดหรือลบงานก่อน")
    d = core.project_dir(name)
    if not (d / "project.json").exists():
        abort(404)
    core.trash_move(d, "story", name)
    jobs.forget_project(name)
    return ok()


@app.post("/api/jobs/stop_all")
def jobs_stop_all():
    return ok(jobs.stop_all())


# ---------------- ตั้งค่า ----------------
@app.get("/api/settings")
def settings_get():
    return ok(core.load_settings(), defaults=core.DEFAULT_SETTINGS)


@app.post("/api/settings")
def settings_post():
    return ok(core.save_settings(request.get_json(force=True)))


READY = {"covers_total": 0, "covers_done": 0, "covers_failed": 0, "current": "", "done": False}


@app.get("/api/ready")
def ready():
    """หน้ารอโหลดถามว่าเว็บพร้อมหรือยัง (ภาพปกเทมเพลตที่ยังไม่มี กำลังสร้างอยู่)"""
    return ok(READY)


OPUSCAR_FILMS = os.environ.get("OPUSCAR_FILMS_URL", "https://lemomo-ai.github.io/lemo-opuscar-films")


def _opuscar_demos():
    """คลิปตัวอย่างของเทมเพลตชุด Lemo-Opuscar (หนังเดโมของแต่ละสไตล์ CC BY 4.0 · เครดิตใน skills/_opuscar)
    ดาวน์โหลดทีละอัน → ตัด 30 วิแรก ไม่เอาเสียง (เสียงพากย์บางเรื่องห้ามนำไปใช้) ย่อ 720 → เป็นคลิปบนการ์ด + รูปการ์ด
    ทำครั้งเดียวต่อเทมเพลต · ข้ามอันที่ผู้ใช้ใส่คลิปเองแล้ว"""
    import requests
    while not READY.get("done"):            # ให้ภาพปกทำก่อน (หน้ารอโหลดรอสิ่งนั้นอยู่)
        time.sleep(10)
    mark = core.SKILLS_DIR / "_opuscar" / "demos.json"
    done = core.read_json(mark, {}) or {}
    todo = [sk for sk in core.list_skills() if sk.get("pack") == "opuscar" and sk["id"] not in done and not sk.get("sample")]
    for sk in todo:
        while jobs and jobs.busy():
            time.sleep(30)
        slug = sk["id"].removeprefix("opuscar-")
        tmp = core.WORK_DIR / f"demo-{slug}.mp4"
        try:
            core.WORK_DIR.mkdir(parents=True, exist_ok=True)
            with requests.get(f"{OPUSCAR_FILMS}/{slug}.mp4", stream=True, timeout=60) as r:
                if r.status_code != 200:
                    done[sk["id"]] = f"HTTP {r.status_code}"
                    continue
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            core.set_skill_clip(sk["id"], tmp, max_sec=30, audio=False)
            done[sk["id"]] = "ok"
            print("🎬 คลิปตัวอย่างเทมเพลต:", sk["id"], flush=True)
        except Exception as e:  # noqa: BLE001  ไม่สำเร็จ → ลองใหม่รอบเปิดเครื่องถัดไป
            print("คลิปตัวอย่างไม่สำเร็จ:", sk["id"], str(e)[:120], flush=True)
        finally:
            tmp.unlink(missing_ok=True)
            core.write_json(mark, {k: v for k, v in done.items() if v == "ok" or v.startswith("HTTP 404")})


def _auto_covers():
    """เทมเพลตที่ยังไม่มีภาพปก → สร้างภาพตัวอย่างด้วย AI ฟรี ตามลุคของเทมเพลต (ทีละภาพ ระหว่างหน้ารอโหลด)
    ภาพไหนไม่สำเร็จ (เว็บฟรีติดคิว/ล่ม) → วนกลับมาทำใหม่อีก 2 รอบในการเปิดเครื่องครั้งเดียวกัน"""
    todo = [s for s in core.list_skills() if not s.get("cover")]
    READY.update(covers_total=len(todo), covers_done=0, covers_failed=0, done=not todo)
    for rnd in range(3):
        failed = []
        for sk in todo:
            READY["current"] = sk["name"]
            while jobs and jobs.busy():
                time.sleep(30)
            o = sk.get("options") or {}
            look = str(o.get("look") or (o.get("image_style") if o.get("image_style") not in (None, "", "none") else "") or "").strip()
            prompt = (f"{look}. " if look else f"{sk['name']}, {sk.get('description', '')}. ") + \
                "Key art poster for a short vertical film, one striking subject, strong composition, no text, no letters, no watermark"
            try:
                llm.set_tag("ภาพปกเทมเพลต")
                llm.free_image(prompt, str(Path(sk["dir"]) / "cover.jpg"), 768, 1024, seed=hash(sk["id"]) % 10000 + rnd, retries=2)
                core.reload_skills()
                print("🖼 ภาพปกเทมเพลต:", sk["id"], flush=True)
                if rnd:
                    READY["covers_failed"] -= 1
            except Exception as e:  # noqa: BLE001
                failed.append(sk)
                if not rnd:
                    READY["covers_failed"] += 1
                print(f"ภาพปกไม่สำเร็จ (รอบ {rnd + 1}):", sk["id"], str(e)[:120], flush=True)
            if not rnd:
                READY["covers_done"] += 1
        if rnd == 0:
            READY.update(current="", done=True)       # รอบแรกจบ = หน้ารอโหลดเข้าเว็บได้ ที่เหลือทำต่อเบื้องหลัง
        if not failed:
            break
        todo = failed
        time.sleep(60)
    READY["current"] = ""


def main():
    global jobs
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    core.ensure_dirs()
    core.purge_legacy_trash()
    core.reload_skills()
    jobs = JobManager()
    threading.Thread(target=_auto_covers, daemon=True).start()
    threading.Thread(target=_opuscar_demos, daemon=True).start()
    threading.Thread(target=core.make_card_clips, daemon=True).start()
    print(f"AutoClip {VERSION} | root={core.ROOT} | http://{a.host}:{a.port}", flush=True)
    app.run(host=a.host, port=a.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
