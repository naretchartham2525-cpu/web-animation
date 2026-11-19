"""เว็บเซิร์ฟเวอร์ AutoClip  —  รัน: python -m app.server --port 8000"""
import argparse
import hashlib
import hmac
import os
import shutil
import time
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from . import core, llm
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


@app.get("/api/ping")
def ping():
    return ok({"auth_required": bool(PASSWORD)})


@app.post("/api/login")
def login():
    pw = (request.get_json(silent=True) or {}).get("password", "")
    if PASSWORD and not hmac.compare_digest(pw, PASSWORD):
        return jsonify({"ok": False, "error": "รหัสผ่านไม่ถูกต้อง"}), 401
    resp = ok()
    resp.set_cookie("ac_tok", TOKEN, max_age=30 * 86400, httponly=True, samesite="Lax", secure=True)
    return resp


# ---------------- สถานะ ----------------
@app.get("/api/status")
def status():
    projects = core.list_projects()
    return ok({
        "version": VERSION,
        "root": str(core.ROOT),
        "keys": core.keys_status(),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "busy": jobs.busy(),
        "queue": jobs.queue_len(),
        "projects": len(projects),
        "episodes_done": sum(p["done_count"] for p in projects),
        "cost_usd": round(sum(float(p.get("cost_usd") or 0) for p in projects), 4),
        "skills": len(core.list_skills()),
        "script_engine": core.load_settings().get("script_engine"),
    })


# ---------------- สกิล ----------------
@app.get("/api/skills")
def skills():
    return ok(core.list_skills())


@app.post("/api/skills/reload")
def skills_reload():
    return ok(core.reload_skills())


@app.post("/api/skills")
def skill_save():
    return ok(core.save_skill(request.get_json(force=True)))


@app.get("/skill-cover/<sid>")
def skill_cover(sid):
    sk = core.get_skill(sid)
    if not sk or not sk.get("cover"):
        abort(404)
    return send_file(core.SKILLS_DIR / sid / sk["cover"], max_age=3600)


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
        core.update_project(name, {"episodes_total": start + n - 1})
        return ok({**jobs.submit(name, n), "episodes": n})
    if b.get("mode") == "manual":
        from .pipeline import parse_manual_episodes
        eps = parse_manual_episodes(b.get("text"), _scenes_for(p.get("options") or {}, p.get("skill"))["scenes_per_episode"])
        _write_manual_eps(name, eps, start, ep_opts)
        core.update_project(name, {"episodes_total": start + len(eps) - 1})
        return ok({**jobs.submit(name, len(eps)), "episodes": len(eps)})
    if ep_opts:
        _prep_ep(name, start, ep_opts)
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


@app.post("/api/parse")
def parse_preview():
    from .pipeline import parse_manual_episodes
    eps = parse_manual_episodes(request.get_json(force=True).get("text"))
    return ok([{"title": e["title"], "scenes": len(e["scenes"])} for e in eps])


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
    import requests as rq
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return ok(None)
    try:
        r = rq.get(llm.BASE + "/key", headers={"Authorization": f"Bearer {key}"}, timeout=10)
        d = (r.json() or {}).get("data") or {}
        return ok({k: d.get(k) for k in ("limit", "limit_remaining", "usage", "is_free_tier",
                                          "free_model_daily_requests")})
    except Exception as e:
        return ok({"error": str(e)})


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
    """ลบคลิป 1 EP → ย้ายไปถังขยะในโปรเจกต์ (กู้คืนได้จาก Drive)"""
    if jobs.has_pending(name):
        raise ValueError("เรื่องนี้มีงานค้างอยู่ หยุดหรือลบงานก่อน")
    d = core.ep_dir(name, ep)
    if not d.exists():
        abort(404)
    trash = core.project_dir(name) / "_trash"
    trash.mkdir(exist_ok=True)
    shutil.move(str(d), str(trash / f"ep{ep:02d}_{int(time.time())}"))
    return ok()


@app.delete("/api/projects/<name>")
def project_delete(name):
    """ลบทั้งเรื่อง → ย้ายไป projects/_trash (กู้คืนได้จาก Drive)"""
    if jobs.has_pending(name):
        raise ValueError("เรื่องนี้มีงานค้างอยู่ หยุดหรือลบงานก่อน")
    d = core.project_dir(name)
    if not (d / "project.json").exists():
        abort(404)
    trash = core.PROJECTS_DIR / "_trash"
    trash.mkdir(exist_ok=True)
    shutil.move(str(d), str(trash / f"{d.name}_{int(time.time())}"))
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


def main():
    global jobs
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    core.ensure_dirs()
    core.reload_skills()
    jobs = JobManager()
    print(f"AutoClip {VERSION} | root={core.ROOT} | http://{a.host}:{a.port}", flush=True)
    app.run(host=a.host, port=a.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
