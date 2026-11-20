"""เอนจิน HTML ของเทมเพลต: คำสั่งทำคลิปแรกใน Claude Code + ติดตั้ง/ลบเอนจินที่อัปโหลด

ขั้นตอน: เทมเพลต (สกิล) → คัดลอกคำสั่งไป Claude Code → ได้ engine.zip + บท EP 1
→ อัปโหลด zip ที่หน้าเทมเพลต → วางบท EP 1 แล้วกด Create → ตอนต่อไปกดทำต่อได้อัตโนมัติ (ฟรี บน Colab)
"""
import shutil
import zipfile
from pathlib import Path

from . import core

REPO_RAW = "https://raw.githubusercontent.com/naretchartham2525-cpu/web-animation/main"
OPUSCAR = "https://github.com/lemomo-ai/lemo-opuscar"
MAX_ZIP = 80 * 1024 * 1024


def engine_dir(skill):
    return Path(skill["dir"]) / "engine" if skill and skill.get("dir") else None


def has_engine(skill):
    d = engine_dir(skill)
    return bool(d and (d / "index.html").exists())


def claude_code_prompt(skill, idea="", s=None):
    s = s or {}
    sid = skill["id"]
    slug = sid[len("opuscar-"):] if sid.startswith("opuscar-") else ""
    style_src = (f"- คู่มือสไตล์ฉบับเต็ม: {REPO_RAW}/skills/{sid}/STYLE.md (อ่านทั้งหมด ทำตามเคร่งครัด)\n"
                 f"- ต้นฉบับของสไตล์: `git clone --depth 1 {OPUSCAR}` แล้วดู styles/{slug}/ "
                 f"(STYLE.md, demo/ คือโค้ดหนังตัวอย่างของสไตล์นี้ ใช้เป็นแนวการวาด/การเคลื่อนไหวได้ แต่ห้ามลอกเรื่อง/ช็อต) "
                 f"และ DIRECTOR.md, TECHNIQUE.md (หลักการกำกับ)\n") if slug else \
        "- คู่มือสไตล์: เนื้อหาเทมเพลตด้านล่าง\n"
    lang = s.get("language", "ไทย")
    return f"""ช่วยสร้าง "เอนจินแอนิเมชัน" สำหรับเทมเพลต "{skill['name']}" ของระบบทำคลิปของผม แล้วเขียนบท EP 1

## เป้าหมาย
ทำหนังสั้นแนวตั้ง 9:16 (1080×1920) ในสไตล์นี้ โดยเขียนเป็นเอนจินที่ "อ่านบทจากไฟล์" ใช้ซ้ำได้ทุกตอน
ห้ามฝังเรื่อง ข้อความ หรือฉากของ EP 1 ไว้ในโค้ด ระบบผมจะส่งบทตอนใหม่เข้าไปแล้วเรนเดอร์เองบน Colab (ไม่มีคนแก้โค้ดอีก)

## สไตล์
{style_src}
=== สรุปเทมเพลต ===
{skill['content'].strip()}
=== จบ ===

## สัญญาของเอนจิน (ต้องตรงทุกข้อ)
- โฟลเดอร์ `engine/` มี `index.html` (+ ไฟล์ js/css/ภาพ/ฟอนต์ที่ใช้ อ้างแบบ relative path ทั้งหมด ห้ามโหลดจากเน็ต)
- ก่อนโหลดหน้า ระบบใส่ `window.TIMELINE` =
  `{{w, h, fps, duration, title, series, ep, lang, scenes: [{{i, start, end, dur, speech, text, speaker, en, visual}}]}}`
  - `text` บทพากย์ภาษา{lang} (ระบบพากย์และใส่ซับเอง) · `speaker` ชื่อผู้พูด (ว่าง = ผู้บรรยาย) · `en` ซับอังกฤษ
  - `visual` = คำสั่งภาพของฉาก (ภาษาอังกฤษ) ที่คุณออกแบบรูปแบบเอง แล้วอธิบายใน SCRIPT.md
  - `start/end/dur` วินาทีของฉากในเรื่อง (มาจากความยาวเสียงพากย์จริง) · `speech` ความยาวเสียงพูดในฉาก
- ต้องมี `window.renderFrame(t)` วาดภาพทั้งจอ ณ วินาที t (คืน Promise ได้) แบบ deterministic:
  ห้ามใช้ requestAnimationFrame / Date.now / setTimeout เดินภาพ · ระบบเรียก renderFrame ทีละเฟรมแล้วจับภาพ
- ของที่ต้องโหลดก่อน (ฟอนต์ ภาพ) → ตั้ง `window.ENGINE_READY = Promise`
- ห้ามวาดซับ ลายน้ำ หรือเล่นเสียง (ระบบทำเอง) · เว้นพื้นที่ล่าง ~22% ของจอไว้ให้ซับ
- ข้อความบนจอ (ชื่อตอน ตัวเลข ป้าย) ต้องรองรับภาษาไทย: ใส่ฟอนต์ไทยฟรี (OFL) ไว้ใน engine/fonts/
- ทนบทที่ไม่คาดคิด: visual ว่างหรือคำสั่งที่ไม่รู้จัก → ยังวาดฉากที่สวยตามสไตล์ได้ ห้าม error
- `engine/SCRIPT.md` (ภาษาไทย สั้นๆ): วิธีเขียนช่อง visual ให้เอนจินนี้เข้าใจ (คำสั่ง/รูปแบบ + ตัวอย่าง 3–5 บรรทัด)
  ระบบจะแนบไฟล์นี้ให้ AI ทุกครั้งที่เขียนบทตอนต่อไป ดังนั้นต้องชัดและครบ
- ความเร็ว: 1 เฟรมควรวาดเสร็จใน < 50 ms · ขนาด zip < 50 MB

## ทดสอบ (ต้องทำจนผ่าน)
```
curl -sLO {REPO_RAW}/app/html_engine.py
pip install playwright && python -m playwright install chromium
python html_engine.py engine --sample timeline.json      # timeline ตัวอย่าง (แก้ให้ตรงบท EP 1 ได้)
python html_engine.py engine timeline.json test.mp4     # เรนเดอร์แบบเดียวกับระบบจริง
python html_engine.py engine timeline.json f.png --at 3  # ดูทีละภาพ
```
ดูภาพหลายจุดทุกฉาก เทียบกับคู่มือสไตล์ แก้จนสวยและไม่มี error ใน console

## ส่งงาน
1. `engine.zip` (ข้างในคือโฟลเดอร์ engine/) → ผมจะอัปโหลดที่หน้าเทมเพลตในเว็บ
2. บท EP 1 ในรูปแบบนี้ (ผมจะวางในเว็บ):
```
# EP 1: <ชื่อตอน>
<บทพากย์ภาษา{lang}> | <visual ตาม SCRIPT.md> | <ซับอังกฤษ>
[ชื่อตัวละคร] <บทพูด> | <visual> | <ซับอังกฤษ>
```
1 บรรทัด = 1 ฉาก · ยาวรวมราว {s.get('target_seconds', 45)} วินาที · บทพากย์ห้ามมีวงเล็บหรือคำกำกับท่าทาง · 3 วินาทีแรกต้องดึงคนดู

## เรื่อง
{idea.strip() or '(ให้ถามผมก่อนว่าเรื่องอะไร)'}
"""


def install_zip(skill, fileobj):
    """แตก zip เอนจินลง skills/<id>/engine/ (แทนของเดิม) · รองรับ zip ที่มีโฟลเดอร์ engine/ ครอบหรือไม่ครอบ"""
    if not skill or not skill.get("dir"):
        raise ValueError("เทมเพลตนี้รับเอนจินไม่ได้ (ต้องเป็นเทมเพลตแบบโฟลเดอร์)")
    sdir = Path(skill["dir"])
    tmp = sdir / ".engine-upload.zip"
    fileobj.save(tmp)
    try:
        if tmp.stat().st_size > MAX_ZIP:
            raise ValueError("ไฟล์ใหญ่เกิน 80 MB")
        with zipfile.ZipFile(tmp) as z:
            names = [n for n in z.namelist() if not n.endswith("/") and "__MACOSX" not in n and not n.split("/")[-1].startswith("._")]
            idx = sorted((n for n in names if n.split("/")[-1] == "index.html"), key=lambda n: n.count("/"))
            if not idx:
                raise ValueError("ใน zip ไม่มี index.html ของเอนจิน")
            base = idx[0][: -len("index.html")]
            new = sdir / ".engine-new"
            shutil.rmtree(new, ignore_errors=True)
            new.mkdir()
            total = 0
            for n in names:
                if not n.startswith(base):
                    continue
                rel = Path(n[len(base):])
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError(f"ชื่อไฟล์ใน zip ไม่ปลอดภัย: {n}")
                info = z.getinfo(n)
                total += info.file_size
                if total > 300 * 1024 * 1024:
                    raise ValueError("ไฟล์ใน zip รวมกันใหญ่เกินไป")
                out = new / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        old = sdir / "engine"
        if old.exists():
            shutil.rmtree(sdir / "engine.old", ignore_errors=True)
            old.rename(sdir / "engine.old")   # เก็บเวอร์ชันก่อนไว้ 1 ชุด
        new.rename(old)
    finally:
        tmp.unlink(missing_ok=True)
        shutil.rmtree(sdir / ".engine-new", ignore_errors=True)
    core.reload_skills()
    return {"files": sum(1 for _ in (sdir / "engine").rglob("*") if _.is_file()),
            "script_md": (sdir / "engine" / "SCRIPT.md").exists()}


def remove(skill):
    d = engine_dir(skill)
    if d and d.exists():
        shutil.rmtree(d.parent / "engine.old", ignore_errors=True)
        d.rename(d.parent / "engine.old")
    core.reload_skills()


def import_skill(fileobj):
    """เพิ่มเทมเพลตจากไฟล์: .md/.txt = เนื้อหาสกิล · .zip = โฟลเดอร์สกิลทั้งชุด (ต้องมี SKILL.md)"""
    name = Path(fileobj.filename or "skill").name
    tmp = core.SKILLS_DIR / f".import-{int(__import__('time').time())}"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        src = tmp / name
        fileobj.save(src)
        if src.stat().st_size > MAX_ZIP:
            raise ValueError("ไฟล์ใหญ่เกิน 80 MB")
        if src.suffix.lower() in (".md", ".txt"):
            text = src.read_text(encoding="utf-8", errors="replace")
            meta, body = core._parse_frontmatter(text)
            title = meta.get("name") or Path(name).stem
            sk = core.save_skill({"name": title, "description": meta.get("description", ""), "content": body.strip() or text, "is_new": True})
            return {"id": sk["id"], "name": sk["name"]}
        if src.suffix.lower() not in (".zip", ".skill"):
            raise ValueError("รองรับไฟล์ .zip .skill .md .txt")
        with zipfile.ZipFile(src) as z:
            names = [n for n in z.namelist() if not n.endswith("/") and "__MACOSX" not in n and not n.split("/")[-1].startswith("._")]
            mk = sorted((n for n in names if n.split("/")[-1].upper() == "SKILL.MD"), key=lambda n: n.count("/"))
            if not mk:
                raise ValueError("ใน zip ไม่มี SKILL.md")
            base = mk[0][: -len("SKILL.md")]
            meta, _ = core._parse_frontmatter(z.read(mk[0]).decode("utf-8", "replace"))
            sid = core.skill_slug(meta.get("name") or base.strip("/").split("/")[-1] or Path(name).stem)
            dest = core.SKILLS_DIR / sid
            if dest.exists():
                sid = f"{sid}-{int(__import__('time').time()) % 100000}"
                dest = core.SKILLS_DIR / sid
            total = 0
            for n in names:
                if not n.startswith(base):
                    continue
                rel = Path(n[len(base):])
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError(f"ชื่อไฟล์ใน zip ไม่ปลอดภัย: {n}")
                info = z.getinfo(n)
                total += info.file_size
                if total > 300 * 1024 * 1024:
                    raise ValueError("ไฟล์ใน zip รวมกันใหญ่เกินไป")
                out = dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as a, open(out, "wb") as b:
                    shutil.copyfileobj(a, b)
        core.reload_skills()
        sk = core.get_skill(sid)
        return {"id": sid, "name": sk["name"] if sk else sid}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
