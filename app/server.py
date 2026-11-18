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

VERSION = "0.1.0"
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
    })


# ---------------- สกิล ----------------
@app.get("/api/skills")
def skills():
    return ok(core.list_skills())


@app.post("/api/skills/reload")
def skills_reload():
    return ok(core.reload_skills())


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
        for f in ("final.mp4", "subs.srt"):
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
    return send_file(f, conditional=True, download_name=f"{name}_{f.parent.name}_{f.name}"
                     if request.args.get("dl") else None, as_attachment=bool(request.args.get("dl")))


@app.get("/api/outputs")
def outputs():
    return ok(core.list_outputs())


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
    text, cost = llm.chat(s["helper_model"], msgs, json_mode=True, temperature=1.0, max_tokens=1500)
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
