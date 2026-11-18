"""ค่าพื้นฐาน, path, settings, skills, projects"""
import json
import os
import re
import threading
import time
from pathlib import Path

ROOT = Path(os.environ.get("AUTOCLIP_ROOT", Path(__file__).resolve().parent.parent)).resolve()
SKILLS_DIR = ROOT / "skills"
PROJECTS_DIR = ROOT / "projects"
FONTS_DIR = ROOT / "fonts"
WORK_DIR = Path(os.environ.get("AUTOCLIP_WORK", "/tmp/autoclip_work"))
SETTINGS_FILE = ROOT / "settings.json"
JOBS_FILE = ROOT / "jobs.json"

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}

DEFAULT_SETTINGS = {
    # --- AI เขียนบท (OpenRouter) ---
    "draft_model": "google/gemini-3.8-flash",
    "polish_enabled": False,
    "polish_model": "google/gemini-3.8-flash",
    "helper_model": "google/gemini-3.8-flash",   # ใช้คิดไอเดีย/อัปเดต bible (งานเล็ก)
    "language": "ไทย",
    "scenes_per_episode": 8,
    "target_seconds": 60,
    # --- เสียงพากย์ ---
    "tts_engine": "openrouter",                   # openrouter | edge
    "openrouter_tts_model": "google/gemini-3.8-flash-tts",
    "openrouter_voice": "Kore",
    "edge_voice": "th-TH-PremwadeeNeural",
    "edge_rate": "+0%",
    # --- วิดีโอ ---
    "aspect": "9:16",
    "fps": 30,
    "crf": 20,
    "preset": "veryfast",
    "scene_gap": 0.35,
    "ken_burns": True,
    "subtitles": True,
    "subtitle_font": "Loma",
    "subtitle_size": 0,           # 0 = อัตโนมัติตามขนาดจอ
    "subtitle_max_chars": 0,      # 0 = อัตโนมัติ
    "bgm_volume": 0.12,
    "review_script": False,       # หยุดให้ตรวจบทก่อนทำเสียง/วิดีโอ
}

_lock = threading.RLock()


def ensure_dirs():
    for d in (SKILLS_DIR, PROJECTS_DIR, WORK_DIR):
        d.mkdir(parents=True, exist_ok=True)


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------- settings ----------------
def load_settings():
    with _lock:
        s = dict(DEFAULT_SETTINGS)
        s.update(read_json(SETTINGS_FILE, {}) or {})
        return s


def save_settings(new):
    with _lock:
        s = load_settings()
        for k, v in new.items():
            if k in DEFAULT_SETTINGS:
                default = DEFAULT_SETTINGS[k]
                try:
                    if isinstance(default, bool):
                        v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "on", "yes")
                    elif isinstance(default, int):
                        v = int(float(v))
                    elif isinstance(default, float):
                        v = float(v)
                    else:
                        v = str(v)
                except (TypeError, ValueError):
                    continue
                s[k] = v
        write_json(SETTINGS_FILE, s)
        return s


def keys_status():
    return {
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
    }


# ---------------- names ----------------
def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", str(name or "")).strip().strip(".")
    name = re.sub(r"\s+", " ", name)
    return name[:80]


# ---------------- skills ----------------
_skills_cache = None


def _parse_frontmatter(text):
    meta, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip('"').strip("'")
            body = text[end + 4:].lstrip("\n")
    return meta, body


def _first_line(body):
    for line in body.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:160]
    return ""


def reload_skills():
    """สกิล = โฟลเดอร์ที่มี SKILL.md หรือไฟล์ .md เดี่ยวๆ ใน skills/"""
    global _skills_cache
    items = []
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for p in sorted(SKILLS_DIR.iterdir(), key=lambda x: x.name.lower()):
        if p.name.startswith((".", "_")):
            continue
        if p.is_dir():
            f = p / "SKILL.md"
            if not f.exists():
                mds = sorted(p.glob("*.md"))
                if not mds:
                    continue
                f = mds[0]
        elif p.suffix.lower() in (".md", ".txt"):
            f = p
        else:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_frontmatter(text)
        sid = p.name if p.is_dir() else p.stem
        items.append({
            "id": sid,
            "name": meta.get("name") or sid,
            "description": meta.get("description") or _first_line(body),
            "file": str(f.relative_to(ROOT)),
            "chars": len(body),
        })
    _skills_cache = items
    return items


def list_skills():
    return _skills_cache if _skills_cache is not None else reload_skills()


def get_skill(sid):
    for s in list_skills():
        if s["id"] == sid:
            text = (ROOT / s["file"]).read_text(encoding="utf-8", errors="replace")
            _, body = _parse_frontmatter(text)
            return {**s, "content": body}
    return None


# ---------------- projects ----------------
def project_dir(name):
    name = safe_name(name)
    if not name:
        raise ValueError("ชื่อโปรเจกต์ว่าง")
    d = (PROJECTS_DIR / name).resolve()
    if PROJECTS_DIR.resolve() not in d.parents:
        raise ValueError("ชื่อไม่ถูกต้อง")
    return d


def ep_dir(name, ep):
    return project_dir(name) / f"ep{int(ep):02d}"


def create_project(data):
    name = safe_name(data.get("name"))
    if not name:
        raise ValueError("กรุณาใส่ชื่อเรื่อง")
    d = project_dir(name)
    if (d / "project.json").exists():
        raise ValueError("มีเรื่องชื่อนี้แล้ว")
    (d / "input").mkdir(parents=True, exist_ok=True)
    (d / "music").mkdir(exist_ok=True)
    proj = {
        "name": name,
        "topic": str(data.get("topic") or "").strip(),
        "skill": data.get("skill") or "",
        "episodes_total": max(1, int(data.get("episodes_total") or 1)),
        "aspect": data.get("aspect") or "",          # ว่าง = ใช้ค่าในตั้งค่า
        "tts_engine": data.get("tts_engine") or "",  # ว่าง = ใช้ค่าในตั้งค่า
        "voice": data.get("voice") or "",
        "notes": str(data.get("notes") or ""),
        "created": time.time(),
        "cost_usd": 0.0,
    }
    write_json(d / "project.json", proj)
    if not (d / "bible.md").exists():
        (d / "bible.md").write_text("", encoding="utf-8")
    return proj


def get_project(name):
    d = project_dir(name)
    p = read_json(d / "project.json")
    if not p:
        return None
    p["episodes"] = list_episodes(name)
    p["inputs"] = list_inputs(name)
    p["bible"] = (d / "bible.md").read_text(encoding="utf-8") if (d / "bible.md").exists() else ""
    p["done_count"] = sum(1 for e in p["episodes"] if e.get("final"))
    return p


def update_project(name, changes):
    with _lock:
        d = project_dir(name)
        p = read_json(d / "project.json")
        if not p:
            raise ValueError("ไม่พบโปรเจกต์")
        for k in ("topic", "skill", "episodes_total", "aspect", "tts_engine", "voice", "notes"):
            if k in changes:
                p[k] = int(changes[k]) if k == "episodes_total" else changes[k]
        if "bible" in changes:
            (d / "bible.md").write_text(str(changes["bible"]), encoding="utf-8")
        write_json(d / "project.json", p)
        return p


def add_cost(name, usd):
    if not usd:
        return
    with _lock:
        d = project_dir(name)
        p = read_json(d / "project.json") or {}
        p["cost_usd"] = round(float(p.get("cost_usd") or 0) + float(usd), 6)
        write_json(d / "project.json", p)


def list_projects():
    out = []
    if not PROJECTS_DIR.exists():
        return out
    for d in sorted(PROJECTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        p = read_json(d / "project.json")
        if not p:
            continue
        eps = list_episodes(p["name"])
        p["done_count"] = sum(1 for e in eps if e.get("final"))
        p["input_count"] = len(list_inputs(p["name"]))
        out.append(p)
    return out


def list_episodes(name):
    d = project_dir(name)
    eps = []
    for e in sorted(d.glob("ep[0-9][0-9]*")):
        if not e.is_dir():
            continue
        st = read_json(e / "state.json", {}) or {}
        script = read_json(e / "script.json", {}) or {}
        eps.append({
            "ep": int(e.name[2:]),
            "stage": st.get("stage", "new"),
            "title": script.get("title", ""),
            "duration": st.get("duration"),
            "final": f"ep{int(e.name[2:]):02d}/final.mp4" if (e / "final.mp4").exists() else None,
            "srt": f"ep{int(e.name[2:]):02d}/subs.srt" if (e / "subs.srt").exists() else None,
        })
    return eps


def list_inputs(name):
    d = project_dir(name) / "input"
    if not d.exists():
        return []
    files = []
    for f in sorted(d.rglob("*")):
        if f.is_file() and f.suffix.lower() in VIDEO_EXT | IMAGE_EXT:
            files.append(str(f.relative_to(d)))
    return files


def next_episode(name):
    d = project_dir(name)
    n = 1
    while (d / f"ep{n:02d}" / "final.mp4").exists():
        n += 1
    return n


def list_outputs():
    out = []
    for p in list_projects():
        for e in list_episodes(p["name"]):
            if e.get("final"):
                f = project_dir(p["name"]) / e["final"]
                out.append({
                    "project": p["name"], "ep": e["ep"], "title": e["title"],
                    "path": e["final"], "srt": e.get("srt"), "duration": e.get("duration"),
                    "mtime": f.stat().st_mtime, "size": f.stat().st_size,
                })
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out
