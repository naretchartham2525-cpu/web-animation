"""นำเข้าสไตล์ Lemo-Opuscar เป็นเทมเพลตของระบบ

ใช้:  python tools/import_opuscar.py <โฟลเดอร์ lemo-opuscar ที่ clone มา>
รันซ้ำได้ (อัปเดตทับของเดิม) · ไม่แตะเทมเพลตอื่น

แต่ละสไตล์ → skills/opuscar-<slug>/
  SKILL.md   เทมเพลตของระบบ (ชื่อ, หมวด, image_style สำหรับภาพ AI, แนวทางเขียนบท)
  STYLE.md   คู่มือสไตล์ต้นฉบับ (CC BY-NC 4.0) ไว้แนบตอนคัดลอกคำสั่งให้ Claude
  cover.jpg  โปสเตอร์ย่อขนาด (เฉพาะที่เป็นของ Lemomo ล้วน CC BY 4.0)
เครดิต/สัญญาอนุญาต → skills/_opuscar/ (โฟลเดอร์ขึ้นต้น _ ระบบไม่นับเป็นเทมเพลต)
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
PREFIX = "opuscar-"
REPO = "https://github.com/lemomo-ai/lemo-opuscar"

CAT_TH = {
    "3D & Miniature": "3D และโมเดลจิ๋ว", "Cartoons": "การ์ตูน", "Data & Maps": "ข้อมูลและแผนที่",
    "Edit & Documentary": "สารคดีและตัดต่อ", "Film & Tape": "ฟิล์มและเทป", "Games": "เกม",
    "Graphic & Type": "กราฟิกและตัวอักษร", "Instruments & Evidence": "เครื่องมือและหลักฐาน",
    "Light & Lines": "แสงและเส้น", "Line Diagrams": "แผนภาพเส้น", "Painting & Illustration": "ภาพวาด",
    "Print & Printmaking": "งานพิมพ์", "Screens & Interfaces": "หน้าจอและอินเทอร์เฟซ",
    "Sketch & Board": "สเก็ตช์และกระดาน", "Traditional Crafts": "งานฝีมือดั้งเดิม",
}
CONTRIB = {"memphis-diorama": "EianLu", "crayon-world": "2nd1st"}


def special_posters(src):
    """สไตล์ที่โปสเตอร์มีของบุคคลที่สาม/Clawd/ผู้ร่วมสร้าง → ไม่เอาโปสเตอร์ (ใช้ภาพจากคลิปแรกแทน)"""
    t = (src / "REUSE.toml").read_text(encoding="utf-8")
    out = set()
    for b in t.split("[[annotations]]")[4:]:
        out |= {m.group(1) for m in re.finditer(r"styles/([a-z0-9-]+)/(?:poster\.jpg|\*\*)", b)}
    return out


def essence(style_md):
    """ประโยคสรุปลุคของสไตล์ (บรรทัด > แรกของ STYLE.md) → ใช้เป็น image_style"""
    for line in style_md.splitlines():
        if line.startswith("> ") and not line.startswith("> References"):
            s = re.sub(r"\s+", " ", line[2:]).strip()
            s = re.sub(r"[`*_]", "", s)
            if len(s) > 320:   # ตัดที่จบประโยค ไม่เกิน ~320 ตัว
                cut = max(s.rfind(". ", 0, 320), s.rfind(": ", 0, 320), s.rfind("; ", 0, 320))
                s = s[: cut + 1 if cut > 80 else 320].strip()
            return s.replace('"', "'")
    return ""


def one_line(v):
    return re.sub(r"\s+", " ", str(v or "")).replace('"', "'").strip()


def main(src):
    src = Path(src).resolve()
    styles = src / "styles"
    if not (styles.is_dir() and (src / "LICENSE").exists()):
        sys.exit(f"ไม่ใช่โฟลเดอร์ lemo-opuscar: {src}")
    try:
        from PIL import Image
    except ImportError:
        Image = None
    skip_poster = special_posters(src)
    done, slugs = [], []
    for d in sorted(styles.iterdir()):
        sj, sm = d / "style.json", d / "STYLE.md"
        if d.name.startswith("_") or not (sj.exists() and sm.exists()):
            continue
        meta = json.loads(sj.read_text(encoding="utf-8"))
        style_md = sm.read_text(encoding="utf-8")
        slug = d.name
        out = SKILLS / f"{PREFIX}{slug}"
        out.mkdir(parents=True, exist_ok=True)
        cat = meta.get("category_en", "")
        uses = ", ".join(meta.get("uses") or [])
        by = f" · สไตล์โดย {CONTRIB[slug]}" if slug in CONTRIB else ""
        look = essence(style_md)
        skill = f"""---
name: {one_line(meta.get('en') or slug)}
description: {CAT_TH.get(cat, cat)} · เหมาะกับ {one_line(uses)}{by}
tags: [opuscar, {one_line(cat)}]
pack: opuscar
image_style: "{look}"
---

# {meta.get('en') or slug}  ·  Lemo-Opuscar #{meta.get('num', '')}

**หมวด:** {CAT_TH.get(cat, cat)} ({cat})
**เหมาะกับ:** {uses}
**ลุคของสไตล์:** {look}

## วิธีเขียนบทสำหรับเทมเพลตนี้
- ทุกฉากต้องมีคำบรรยายภาพภาษาอังกฤษที่บรรยายตามลุคด้านบน (วัสดุ สี แสง มุมกล้อง) ให้เหมือนกันทั้งเรื่อง
- เรื่องเดียว เป้าหมายเดียว มีจุดพลิกหนึ่งครั้ง · 3 วินาทีแรกต้องดึงคนดู · ตอนจบย้อนกลับไปหาตอนเปิด
- ใช้คู่มือสไตล์ฉบับเต็มใน STYLE.md ของโฟลเดอร์นี้เป็นหลักเรื่องสี ตัวอักษร จังหวะ และสิ่งที่ห้ามทำ
- ห้ามลอกเรื่อง ตัวละคร หรือช็อตของเดโมต้นฉบับ ("{one_line(meta.get('film'))}")

---
ดัดแปลงจาก "{meta.get('en')}" ใน [Lemo-Opuscar]({REPO}) โดย Lemomo (LemoLab){(' และ ' + CONTRIB[slug]) if slug in CONTRIB else ''} ·
เอกสารสไตล์ใช้สัญญาอนุญาต [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) ·
เปลี่ยนแปลง: สรุปเป็นเทมเพลตของระบบนี้ (ไฟล์ STYLE.md คือต้นฉบับไม่ได้แก้)
"""
        (out / "SKILL.md").write_text(skill, encoding="utf-8")
        shutil.copyfile(sm, out / "STYLE.md")
        poster = d / "poster.jpg"
        cov = out / "cover.jpg"
        if slug in skip_poster or not poster.exists():
            cov.unlink(missing_ok=True)
        elif Image:
            im = Image.open(poster).convert("RGB")
            im.thumbnail((640, 640))
            im.save(cov, "JPEG", quality=82, optimize=True, progressive=True)
        else:
            shutil.copyfile(poster, cov)
        done.append((slug, bool(cov.exists())))
        slugs.append(slug)
    # เครดิตและสัญญาอนุญาต
    lic = SKILLS / "_opuscar"
    lic.mkdir(parents=True, exist_ok=True)
    for f in ("LICENSE",):
        shutil.copyfile(src / f, lic / f)
    (lic / "LICENSES").mkdir(exist_ok=True)
    for f in ("CC-BY-NC-4.0.txt", "CC-BY-4.0.txt", "MIT.txt"):
        shutil.copyfile(src / "LICENSES" / f, lic / "LICENSES" / f)
    (lic / "README.md").write_text(f"""# Lemo-Opuscar ในระบบนี้

เทมเพลต `skills/{PREFIX}*` ดัดแปลงจาก **Lemo-Opuscar by Lemomo (LemoLab)** — {REPO}

- เอกสารสไตล์ (`STYLE.md`, และเนื้อหาที่สรุปใน `SKILL.md`): [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) — ห้ามใช้เพื่อการค้า (เช่น ขายหรือนำไปทำบริการหาเงิน) โดยไม่มีใบอนุญาตเชิงพาณิชย์จากผู้สร้าง
- ภาพปก (`cover.jpg` ย่อจาก poster.jpg): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · ไม่รวมสไตล์ที่โปสเตอร์มีเนื้อหาของบุคคลที่สาม
- Memphis Diorama by EianLu และ Crayon World 3D by 2nd1st, in Lemo-Opuscar by Lemomo (LemoLab)
- เปลี่ยนแปลง: สรุปแต่ละสไตล์เป็นเทมเพลต (`SKILL.md`) · `STYLE.md` เป็นต้นฉบับไม่ได้แก้
- คลิปที่ทำด้วยสไตล์เหล่านี้เป็นของผู้ทำ ใช้เชิงพาณิชย์ได้ (ดู LICENSE หัวข้อ FILMS YOU MAKE)

อัปเดต: `python tools/import_opuscar.py <โฟลเดอร์ lemo-opuscar>` · นำเข้าแล้ว {len(slugs)} สไตล์
""", encoding="utf-8")
    print(f"นำเข้า {len(done)} สไตล์ · มีภาพปก {sum(c for _, c in done)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
