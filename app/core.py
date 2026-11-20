"""ค่าพื้นฐาน, path, settings, skills, projects"""
import json
import os
import re
import threading
import shutil
import subprocess
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
        "category": meta.get("category") or (engine or {}).get("category", ""),   # หมวดของการ์ด
        "html_engine": p.is_dir() and (p / "engine" / "index.html").exists(),   # เอนจินจากคลิปแรก (Claude Code)   # ชุดเทมเพลตที่นำเข้า (เช่น opuscar) → แสดงหลังเทมเพลตของผู้ใช้
        "cover": cover,
        "cover_v": int((p / cover).stat().st_mtime) if cover and cover != "sample" else 0,   # เปลี่ยนรูปการ์ด → URL ใหม่ (ไม่ติดแคชเก่า)
        "sample": p.is_dir() and (p / "sample.mp4").exists(),   # คลิปตัวอย่างที่ผู้ใช้ใส่เอง (หน้าเพิ่ม/แก้เทมเพลต)
        "card_v": next((int(f.stat().st_mtime) for f in (p / "card.mp4", p / "sample.mp4") if p.is_dir() and f.exists()), 0),   # คลิปเล่นวนบนการ์ด (ยังไม่มีคลิปย่อ → ใช้คลิปตัวอย่าง)
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
    if old.get("pack"):
        fm.append(f"pack: {clean(old['pack'])}")
    cat = data.get("category") if data.get("category") is not None else old.get("category")
    if cat:
        fm.append(f"category: {clean(cat)}")
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


def _ff(args, timeout=120):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode == 0, (r.stderr or "").strip().splitlines()[-1:] or [""]


def save_skill_media(sid, fileobj):
    """รูปการ์ดหรือคลิปตัวอย่างของเทมเพลต: รูป → cover.* · คลิป → ภาพนิ่งเป็นรูปการ์ดทันที + แปลงคลิปเป็น mp4 เบื้องหลัง (ไม่ให้หน้าเว็บรอนาน)"""
    d = SKILLS_DIR / sid
    if not d.is_dir():
        raise ValueError("ไม่พบเทมเพลต")
    ext = Path(fileobj.filename or "").suffix.lower()
    if ext in IMAGE_EXT:                      # เปลี่ยนเป็นรูป → การ์ดเป็นภาพนิ่ง (เลิกเล่นคลิปบนการ์ด · คลิปตัวอย่างเดิมไม่ใช้แล้ว)
        for c in [*d.glob("cover.*"), d / "card.mp4", d / "sample.mp4"]:
            c.unlink(missing_ok=True)
        fileobj.save(d / f"cover{ext}")
    elif ext in VIDEO_EXT:
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        tmp = WORK_DIR / f"sample-{sid}-{int(time.time())}{ext}"
        fileobj.save(tmp)
        frame = WORK_DIR / f"cover-{sid}.jpg"
        ok_, err = _ff(["-ss", "1", "-i", str(tmp), "-frames:v", "1", "-q:v", "3", str(frame)], 60)
        if not ok_ or not frame.exists():
            ok_, err = _ff(["-i", str(tmp), "-frames:v", "1", "-q:v", "3", str(frame)], 60)
        if not ok_ or not frame.exists():
            tmp.unlink(missing_ok=True)
            raise ValueError("อ่านไฟล์คลิปไม่ได้: " + err[0][:160])
        for c in d.glob("cover.*"):
            c.unlink()
        shutil.move(str(frame), str(d / "cover.jpg"))

        def convert():   # คลิปตัวอย่างสำหรับเปิดดูในเว็บ: mp4 (h264) ขนาดไม่เกิน 720 · เสร็จแล้วค่อยแทนของเดิม
            out = WORK_DIR / f"sample-{sid}-out.mp4"
            ok2, _ = _ff(["-i", str(tmp), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                          "-vf", "scale=w='min(720,iw)':h=-2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                          "-movflags", "+faststart", str(out)], 900)
            card = WORK_DIR / f"card-{sid}-out.mp4"   # คลิปสั้นเล็กๆ ไว้เล่นวนบนการ์ด (ไม่มีเสียง · 6 วิ · กว้าง 360)
            ok3, _ = _ff(["-i", str(tmp), "-t", "6", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                          "-vf", "scale=w='min(360,iw)':h=-2,fps=24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(card)], 600)
            if ok2 and out.exists():
                shutil.move(str(out), str(d / "sample.mp4"))
            if ok3 and card.exists():
                shutil.move(str(card), str(d / "card.mp4"))
            reload_skills()
            tmp.unlink(missing_ok=True)
        threading.Thread(target=convert, daemon=True).start()
    else:
        raise ValueError("ใส่ได้เฉพาะรูป (.jpg .png .webp) หรือคลิป (.mp4 .mov .webm .mkv)")
    reload_skills()
    return get_skill(sid)


def make_card_clips():
    """เทมเพลตที่มีคลิปตัวอย่างแต่ยังไม่มีคลิปย่อสำหรับการ์ด (อัปไว้ก่อนมีฟีเจอร์นี้) → ทำให้ครบ"""
    done = 0
    for d in SKILLS_DIR.iterdir():
        if d.is_dir() and (d / "sample.mp4").exists() and not (d / "card.mp4").exists():
            out = WORK_DIR / f"card-{d.name}-out.mp4"
            WORK_DIR.mkdir(parents=True, exist_ok=True)
            ok_, _ = _ff(["-i", str(d / "sample.mp4"), "-t", "6", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                          "-vf", "scale=w='min(360,iw)':h=-2,fps=24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], 600)
            if ok_ and out.exists():
                shutil.move(str(out), str(d / "card.mp4"))
                done += 1
    if done:
        reload_skills()
    return done


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


def _size(p):
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


# ---------------- ถังขยะของเว็บ ----------------
# ลบในเว็บ = ย้ายมาถังขยะ (กู้คืนได้) · ลบในถังขยะ = หายถาวรจาก Drive ทันที (ไม่ค้าง 30 วัน)
TRASH_DIR = ROOT / "trash"


def trash_move(path, kind, label, orig=None):
    path = Path(path)
    if not path.exists():
        return None
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    tid = f"{int(time.time() * 1000)}"
    box = TRASH_DIR / tid
    box.mkdir()
    write_json(box / "meta.json", {"kind": kind, "label": label, "orig": str((orig or path).relative_to(ROOT)),
                                   "deleted": time.time(), "size": _size(path)})
    shutil.move(str(path), str(box / "data"))
    return tid


def trash_list():
    out = []
    if TRASH_DIR.exists():
        for b in sorted(TRASH_DIR.iterdir(), reverse=True):
            m = read_json(b / "meta.json")
            if m:
                out.append({"id": b.name, **m})
    return out


def _trash_box(tid):
    b = (TRASH_DIR / str(tid)).resolve()
    if b.parent != TRASH_DIR.resolve() or not (b / "meta.json").exists():
        raise ValueError("ไม่พบรายการในถังขยะ")
    return b


def trash_restore(tid):
    b = _trash_box(tid)
    m = read_json(b / "meta.json")
    dst = (ROOT / m["orig"]).resolve()
    if ROOT.resolve() not in dst.parents:
        raise ValueError("ตำแหน่งเดิมไม่ถูกต้อง")
    if dst.exists():
        raise ValueError(f"มี “{m['label']}” อยู่แล้วที่เดิม (ชื่อซ้ำ) เปลี่ยนชื่อหรือลบอันที่มีอยู่ก่อน")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(b / "data"), str(dst))
    shutil.rmtree(b, ignore_errors=True)
    return m


def trash_purge(ids=None):
    """ลบถาวร (ids=None = ล้างถังขยะทั้งหมด) · คืนจำนวน + พื้นที่ + ลบจาก Drive ทันทีได้ไหม"""
    from . import gdrive
    boxes = [_trash_box(i) for i in ids] if ids is not None else ([b for b in TRASH_DIR.iterdir()] if TRASH_DIR.exists() else [])
    n, freed, instant = 0, 0, True
    for b in boxes:
        m = read_json(b / "meta.json") or {}
        freed += m.get("size", 0)
        instant = gdrive.delete_forever(b) and instant
        n += 1
    return {"count": n, "freed": freed, "instant": instant if n else True}


def purge_legacy_trash():
    """ถังขยะแบบเก่า (projects/_trash) → ย้ายเข้าถังขยะใหม่ให้เห็นและเลือกได้ · engine.old ไม่ใช้แล้ว"""
    for t in [PROJECTS_DIR / "_trash", *PROJECTS_DIR.glob("*/_trash")]:
        if t.is_dir():
            for x in list(t.iterdir()):
                trash_move(x, "legacy", x.name, orig=PROJECTS_DIR / x.name)
            shutil.rmtree(t, ignore_errors=True)
    for s in SKILLS_DIR.glob("*/engine.old"):
        shutil.rmtree(s, ignore_errors=True)


def storage_report(busy=lambda n: False):
    """ไฟล์ค้าง/ของที่ไม่ได้ใช้ ให้ผู้ใช้เลือกลบเอง (ระบบไม่ลบเอง)"""
    items = []
    add = lambda kind, path, label, note="": items.append(
        {"id": str(path.relative_to(ROOT)), "kind": kind, "label": label, "note": note,
         "size": _size(path), "mtime": path.stat().st_mtime})
    if PROJECTS_DIR.exists():
        for d in sorted(PROJECTS_DIR.iterdir()):
            if not d.is_dir():
                continue
            p = read_json(d / "project.json")
            if not p:
                continue
            if busy(p["name"]):
                continue
            eps = list_episodes(p["name"])
            if not any(e.get("final") for e in eps) and not any(d.glob("_old_ep*")):
                add("story", d, p["name"], "เรื่องที่ยังไม่มีคลิปเสร็จ (ทำแล้วพังหรือยังไม่ได้ทำ)")
                continue
            for e in eps:
                if not e.get("final"):
                    add("ep", ep_dir(p["name"], e["ep"]), f"{p['name']} · EP {e['ep']}", "ตอนที่ทำไม่สำเร็จ")
            for o in sorted(d.glob("_old_ep*")):
                add("old", o, f"{p['name']} · EP {int(o.name[7:9] or 0)}", "คลิป")
    return items


def storage_delete(ids, busy=lambda n: False):
    """ย้ายไปถังขยะตามที่ผู้ใช้เลือก (เฉพาะรายการที่อยู่ใน storage_report เท่านั้น)"""
    allowed = {i["id"]: i for i in storage_report(busy)}
    done, freed, stories = [], 0, []
    for i in ids:
        it = allowed.get(i)
        if not it:
            continue
        p = (ROOT / i).resolve()
        if ROOT.resolve() not in p.parents:
            continue
        freed += it["size"]
        trash_move(p, it["kind"], it["label"])
        done.append(i)
        if it["kind"] == "story":
            stories.append(it["label"])
    return {"deleted": done, "freed": freed, "stories": stories}


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
        p["failed_eps"] = [e["ep"] for e in eps if not e.get("final")]
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
        d = project_dir(p["name"])
        for o in d.glob("_old_ep*"):   # คลิปที่ทำซ้ำของตอนเดิม → โชว์เป็นคลิปปกติ (ผู้ใช้รู้เองว่าอันไหนก่อนหลัง)
            f = o / "final.mp4"
            if not f.exists():
                continue
            sc = read_json(o / "script.json", {}) or {}
            out.append({"project": p["name"], "ep": int(o.name[7:9] or 0), "title": sc.get("title") or "",
                        "path": f"{o.name}/final.mp4", "srt": f"{o.name}/subs.srt" if (o / "subs.srt").exists() else None,
                        "srt_en": f"{o.name}/subs_en.srt" if (o / "subs_en.srt").exists() else None,
                        "thumb": f"{o.name}/thumb.jpg" if (o / "thumb.jpg").exists() else None,
                        "duration": (read_json(o / "state.json", {}) or {}).get("duration"),
                        "mtime": f.stat().st_mtime, "size": f.stat().st_size, "copy": str(o.relative_to(ROOT))})
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out
