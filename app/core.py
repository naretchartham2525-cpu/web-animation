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
    "ui_accent": "#4F46E5",                       # สีหลักของหน้าเว็บ (ตั้งในหน้า ตั้งค่า)
    "ui_mode": "light",                           # light | dark | auto
    # --- AI เขียนบท (OpenRouter) ---
    "script_engine": "free",                      # free | claude | paid  (โหมดเขียนเองเลือกที่แถบพิมพ์)
    "claude_model": "anthropic/claude-haiku-5.5", # Claude เขียนบท (ถูกมาก ~$0.001/EP)
    "free_model": "openrouter/free",              # router เลือกโมเดลฟรีที่ว่างให้เอง
    "draft_model": "google/gemini-3.8-flash",     # โมเดลเสียเงิน
    "polish_enabled": False,
    "polish_model": "google/gemini-3.8-flash",
    "max_tokens": 2500,                           # จำกัดความยาวคำตอบ กันเครดิตบาน
    "update_bible": True,                         # +1 ครั้งต่อตอน ช่วยให้เรื่องต่อเนื่อง
    "language": "ไทย",
    "scenes_per_episode": 0,                      # 0 = คำนวณจากความยาว (~6 วิ/ฉาก)
    "target_seconds": 30,
    # --- ภาพ ---
    "visual_source": "ai",                        # ai (Pollinations ฟรี) | drive | none
    "image_model": "",                            # ว่าง = ค่าเริ่มต้นของ Pollinations
    "image_style": "",
    # --- เสียงพากย์ ---
    "voice_on": True,
    "tts_engine": "edge",                         # เสียง AI ใช้ Edge ฟรีเท่านั้น (Gemini ตัดออกแล้ว)
    "edge_voice": "th-TH-PremwadeeNeural",
    "edge_rate": "+0%",
    # --- วิดีโอ ---
    "aspect": "9:16",
    "quality": "hd",                              # sd (มาตรฐาน 540p) | hd (720p) | fhd (1080p)
    "watermark": True,
    "watermark_text": "Thuean Studio",
    "fps": 30,
    "crf": 20,
    "preset": "veryfast",
    "scene_gap": 0.35,
    "ken_burns": True,
    "subtitles": True,
    "sub_lang": "th",             # th | en | both | none
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


SKILL_OPTION_KEYS = ("duration", "quality", "aspect", "voice_on", "tts_engine", "voice", "edge_rate",
                     "image_style", "scenes", "visual_source", "watermark", "sub_lang", "look")


def _parse_list(v):
    v = (v or "").strip().strip("[]")
    return [t.strip().strip("'\"").lstrip("#") for t in v.split(",") if t.strip()]


def _skill_from(p):
    if p.is_dir():
        f = p / "SKILL.md"
        if not f.exists():
            mds = sorted(p.glob("*.md"))
            if not mds:
                return None
            f = mds[0]
    elif p.suffix.lower() in (".md", ".txt"):
        f = p
    else:
        return None
    text = f.read_text(encoding="utf-8", errors="replace")
    meta, body = _parse_frontmatter(text)
    sid = p.name if p.is_dir() else p.stem
    cover = None
    if p.is_dir():
        for c in sorted(p.iterdir()):
            if c.stem.lower() == "cover" and c.suffix.lower() in IMAGE_EXT:
                cover = c.name
                break
    if not cover and sample_cover(sid):
        cover = "sample"   # ยังไม่มี cover.* → ใช้ภาพนิ่งจากคลิปล่าสุดที่ทำด้วยเทมเพลตนี้
    opts = {k: meta[k] for k in SKILL_OPTION_KEYS if meta.get(k)}
    engine = read_json(p / "autoclip.json") if p.is_dir() else None   # สกิลที่มีเอนจินของตัวเอง
    return {
        "id": sid,
        "name": (engine or {}).get("title") or meta.get("name") or sid,
        "description": (engine or {}).get("description_th") or meta.get("description") or _first_line(body),
        "engine": (engine or {}).get("engine") or "",
        "dir": str(p) if p.is_dir() else "",
        "tags": _parse_list(meta.get("tags")),
        "pack": meta.get("pack", ""),
        "category": meta.get("category", ""),   # หมวดของการ์ด (ว่าง = ของฉัน)
        "html_engine": p.is_dir() and (p / "engine" / "index.html").exists(),   # เอนจินจากคลิปแรก (Claude Code)   # ชุดเทมเพลตที่นำเข้า (เช่น opuscar) → แสดงหลังเทมเพลตของผู้ใช้
        "cover": cover,
        "options": opts,
        "file": str(f.relative_to(ROOT)),
        "chars": len(body),
        "mtime": f.stat().st_mtime,
    }


def reload_skills():
    """สกิล/เทมเพลต = โฟลเดอร์ที่มี SKILL.md หรือไฟล์ .md เดี่ยวๆ ใน skills/"""
    global _skills_cache
    items = []
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for p in sorted(SKILLS_DIR.iterdir(), key=lambda x: x.name.lower()):
        if p.name.startswith((".", "_")):
            continue
        sk = _skill_from(p)
        if sk:
            items.append(sk)
    items.sort(key=lambda x: (bool(x.get("pack")), 0 if x.get("pack") else -x["mtime"], x["name"].lower()))   # ของผู้ใช้ก่อน แล้วค่อยชุดที่นำเข้า
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


def skill_slug(name):
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return slug[:40] or f"template-{int(time.time())}"


def save_skill(data):
    """สร้าง/แก้เทมเพลตจากหน้าเว็บ → skills/<id>/SKILL.md"""
    name = str(data.get("name") or "").strip()
    content = str(data.get("content") or "").strip()
    if not name or not content:
        raise ValueError("ต้องมีชื่อและเนื้อหาเทมเพลต")
    sid = data.get("id") or skill_slug(data.get("slug") or name)
    if sid != skill_slug(sid) and not (SKILLS_DIR / sid).is_dir():
        sid = skill_slug(sid)
    d = SKILLS_DIR / sid
    if data.get("is_new") and d.exists():
        sid = f"{sid}-{int(time.time()) % 100000}"
        d = SKILLS_DIR / sid
    d.mkdir(parents=True, exist_ok=True)
    clean = lambda v: str(v).replace("\n", " ").replace("\r", " ").strip()
    fm = [f"name: {clean(name)}", f"description: {clean(data.get('description') or '')}"]
    old = {}
    if (d / "SKILL.md").exists():   # แก้จากเว็บ: เก็บ tags/pack เดิมไว้ (เช่น เทมเพลตชุดที่นำเข้า)
        old, _ = _parse_frontmatter((d / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
    for k in ("pack", "category"):
        if old.get(k):
            fm.append(f"{k}: {clean(old[k])}")
    tags = data.get("tags") or _parse_list(old.get("tags"))
    if isinstance(tags, str):
        tags = _parse_list(tags)
    if tags:
        fm.append("tags: " + ", ".join(clean(t).lstrip("#") for t in tags))
    for k in SKILL_OPTION_KEYS:
        v = (data.get("options") or {}).get(k)
        if k == "image_style" and v == "":
            v = "none"  # ปิดสไตล์ของระบบ (ไม่ใช้ค่าเริ่มต้น)
        if v not in (None, ""):
            fm.append(f"{k}: {clean(v)}")
    (d / "SKILL.md").write_text("---\n" + "\n".join(fm) + "\n---\n\n" + content + "\n", encoding="utf-8")
    reload_skills()
    return get_skill(sid)


# ---------------- คลังข้อความ ----------------
LIBRARY_FILE = ROOT / "library.json"


def list_library():
    return read_json(LIBRARY_FILE, []) or []


def save_library_item(item):
    with _lock:
        items = list_library()
        text = str(item.get("text") or "").strip()
        if not text:
            raise ValueError("ข้อความว่าง")
        iid = item.get("id") or f"t{int(time.time() * 1000)}"
        title = str(item.get("title") or "").strip() or text.splitlines()[0][:40]
        new = {"id": iid, "title": title, "text": text, "updated": time.time()}
        items = [i for i in items if i["id"] != iid]
        items.insert(0, new)
        write_json(LIBRARY_FILE, items[:500])
        return new


def delete_library_item(iid):
    with _lock:
        items = [i for i in list_library() if i["id"] != iid]
        write_json(LIBRARY_FILE, items)
        return True


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


def unique_project_name(name):
    base = safe_name(name) or "เรื่องใหม่"
    n, cand = 2, base
    while (project_dir(cand) / "project.json").exists():
        cand = f"{base} ({n})"
        n += 1
    return cand


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
        "script_mode": data.get("script_mode") or "ai",      # ai | manual
        "manual_text": str(data.get("manual_text") or ""),
        "options": data.get("options") or {},                # ค่าที่เลือกจากแถบพิมพ์
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
        for k in ("topic", "skill", "episodes_total", "aspect", "tts_engine", "voice", "notes",
                  "script_mode", "manual_text", "options"):
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


def sample_cover(sid):
    """ภาพตัวอย่างของเทมเพลต: thumb.jpg ของ EP ล่าสุดที่ทำด้วยเทมเพลตนี้"""
    best = None
    if not PROJECTS_DIR.exists():
        return None
    for d in PROJECTS_DIR.iterdir():
        if d.name.startswith("_") or not d.is_dir():
            continue
        pj = read_json(d / "project.json") or {}
        if pj.get("skill") != sid:
            continue
        for t in d.glob("ep*/thumb.jpg"):
            m = t.stat().st_mtime
            if not best or m > best[0]:
                best = (m, t)
    return best[1] if best else None


def list_projects():
    out = []
    if not PROJECTS_DIR.exists():
        return out
    for d in sorted(PROJECTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if d.name.startswith("_"):
            continue
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
            "srt_en": f"ep{int(e.name[2:]):02d}/subs_en.srt" if (e / "subs_en.srt").exists() else None,
            "thumb": f"ep{int(e.name[2:]):02d}/thumb.jpg" if (e / "thumb.jpg").exists() else None,
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
                    "path": e["final"], "srt": e.get("srt"), "srt_en": e.get("srt_en"), "thumb": e.get("thumb"), "duration": e.get("duration"),
                    "mtime": f.stat().st_mtime, "size": f.stat().st_size,
                })
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out
