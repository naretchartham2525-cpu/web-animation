"""บทพากย์แยกตัวละคร (ระบบสร้างจากบทเอง ไม่ต้องให้ Claude เขียนแยก)
ใช้ทำ 2 อย่าง: 1) ไฟล์ .txt ให้ผู้ใช้ไปอัดเสียง  2) จับคู่ไฟล์เสียงแต่ละตัวละครกับประโยคตอนตัดเสียง
speaker key: เทมเพลตปกติ = ชื่อใน [ชื่อ] หน้าบท (ไม่มี = ผู้บรรยาย) · เทมเพลตเอนจิน = id ตัวละคร (บรรยาย = hero)
"""
import re
from pathlib import Path

NARRATOR = "ผู้บรรยาย"


def is_free_line(ln):
    """ประโยคที่ตัวละครไม่ได้พูดเอง → ใช้เสียงฟรี (ข้อความบนจอ, เสียงระบบ, ผู้บรรยายของเทมเพลตทั่วไป)"""
    return ln.get("note") == "ข้อความบนจอ" or ln.get("key") in ("system", NARRATOR)
# สีหน้า/ท่าในบท → audio tag ของ ElevenLabs v3 (ภาษาอังกฤษในวงเล็บ)
EMO = {"angry": "angry", "yell": "shouting", "rage": "furious", "sad": "sad", "cry": "crying", "happy": "happy",
       "smug": "smug", "sly": "mischievously", "shock": "surprised", "scared": "scared", "worried": "nervous",
       "tired": "tired", "disgust": "disgusted", "confused": "confused", "whisper": "whispers"}


def norm(s):
    return re.sub(r"[\s_\-.()\[\]]+", "", str(s or "")).lower()


# ---------------- เทมเพลตปกติ ----------------
def lines_manual(scenes):
    out = []
    for sc in scenes:
        sp = (sc.get("speaker") or "").strip() or NARRATOR
        out.append({"key": sp, "name": sp, "text": sc.get("narration", "")})
    return out


# ---------------- เทมเพลตมีเอนจิน (drama-json) ----------------
def _engine_mod(skill_dir):
    from .engines.drama_runner import load_engine
    return load_engine(skill_dir)


def engine_key(who, by=None):
    """ผู้พูดในเอนจิน → speaker key (บรรยาย = hero · ชื่อตัวละครแทน id → id)"""
    if who in ("narration", "hero"):
        return "hero"
    who = str(who)
    if by and who not in by and who != "system":
        for cid, c in by.items():
            if norm(c.get("name")) and norm(c.get("name")) == norm(who):
                return cid
    return who


def lines_engine(skill_dir, series, ep):
    R = _engine_mod(skill_dir)
    cast = R.Cast(series)
    by = {c.get("id"): c for c in series.get("cast") or []}
    hero = (by.get("hero") or {}).get("name") or "พระเอก"
    out = []
    for k, shot in enumerate(ep.get("shots") or []):
        for sg in R.segments(shot, cast, k):
            if not R.clean_tts(sg["text"]):
                continue
            key = engine_key(sg["who"], by)
            emo = ""
            if shot.get("type") == "scene" and sg["who"] not in ("narration",):
                me = next((c for c in shot.get("chars") or [] if engine_key(c.get("id"), by) == key), {})
                emo = EMO.get(me.get("pose")) or EMO.get(me.get("face")) or ""
            name = hero if key == "hero" else ("เสียงระบบ" if key == "system" else (by.get(key) or {}).get("name") or cast.name(key))
            out.append({"key": key, "name": name, "text": R.clean_tts(sg["text"]), "emo": emo,
                        "note": "บรรยาย" if sg["who"] == "narration" else ("ข้อความบนจอ" if not sg.get("sub") else "")})
    if ep.get("ask"):
        out.append({"key": "hero", "name": hero, "text": R.clean_tts(ep["ask"]), "note": "ถามคนดูตอนจบ"})
    return out


def speakers(lines, series=None):
    by = {c.get("id"): c for c in (series or {}).get("cast") or []}
    seen = {}
    for ln in lines:
        s = seen.setdefault(ln["key"], {"key": ln["key"], "name": ln["name"], "count": 0, "chars": 0, "paid_chars": 0, "aliases": set()})
        s["count"] += 1
        s["chars"] += len(ln["text"])
        if not is_free_line(ln):
            s["paid_chars"] += len(ln["text"])          # เฉพาะบทพูดของตัวละครที่จะใช้เสียงเสียเงินได้
        s["aliases"].update({ln["key"], ln["name"]})
        c = by.get(ln["key"])
        if c:
            s["aliases"].add(c.get("name") or "")
            s["voice"] = c.get("voice") or ""
    for s in seen.values():
        s["aliases"] = sorted(a for a in s["aliases"] if a)
    return list(seen.values())


def match_file(filename, spk):
    """ชื่อไฟล์ → speaker key (เช่น mam.mp3, เจ๊แหม่ม.m4a, 02_ฝ้าย.wav)"""
    stem = norm(re.sub(r"^\d+[_\-\s]*", "", Path(filename).stem))
    best = None
    for s in spk:
        for a in s["aliases"]:
            na = norm(a)
            if not na:
                continue
            score = 3 if stem == na else 2 if na in stem else 1 if len(stem) >= 2 and stem in na else 0
            if score and (not best or (score, len(na)) > best[0]):
                best = ((score, len(na)), s["key"])
    return best[1] if best else None


def sheet_text(title, lines, spk):
    w = []
    w.append(f"บทพากย์ · {title}")
    w.append("วิธีอัด: แยก 1 ไฟล์ต่อ 1 ตัวละคร ตั้งชื่อไฟล์เป็นชื่อตัวละคร (เช่น " +
             ", ".join(f"{s['name']}.mp3" for s in spk[:3]) + ")")
    w.append("อ่านเฉพาะประโยคของตัวละครนั้นตามลำดับเลข เว้นจังหวะ ~0.5 วินาทีระหว่างประโยค ไม่ต้องอ่านเลขและชื่อ")
    w.append("(หรืออัดไฟล์เดียวทั้งตอนตามลำดับด้านล่างก็ได้ แต่ตัดเสียงแม่นน้อยกว่า)")
    w.append("")
    w.append("== ตัวละคร ==")
    for s in spk:
        v = f" · เสียง {s['voice']}" if s.get("voice") else ""
        w.append(f"- {s['name']} ({s['key']}){v}: {s['count']} ประโยค")
    w.append("")
    for s in spk:
        w.append(f"== ไฟล์: {s['name']}.mp3 ==")
        for i, ln in enumerate(lines, 1):
            if ln["key"] == s["key"]:
                n = f" [{ln['note']}]" if ln.get("note") else ""
                w.append(f"{i:03d}{n} {ln['text']}")
        w.append("")
    w.append("== ลำดับทั้งตอน ==")
    for i, ln in enumerate(lines, 1):
        w.append(f"{i:03d} {ln['name']}: {ln['text']}")
    w.append("")
    w.append("=" * 40)
    w.append("พร้อมวางใน ElevenLabs (ก๊อปทั้งก้อนของแต่ละตัวละคร → Generate 1 ครั้ง → ดาวน์โหลดตั้งชื่อตามตัวละคร)")
    w.append("- บรรทัดว่างระหว่างประโยค = เว้นจังหวะ ช่วยให้ระบบตัดเสียงแม่น อย่าลบ")
    w.append("- [tag] ในวงเล็บ = อารมณ์ ใช้ได้กับโมเดล Eleven v3 · ถ้าใช้ Flash/Multilingual ให้ใช้ก้อน 'ไม่มี tag'")
    for s in spk:
        mine = [ln for ln in lines if ln["key"] == s["key"]]
        plain = "\n\n".join(ln["text"] for ln in mine)
        tagged = "\n\n".join((f"[{ln['emo']}] " if ln.get("emo") else "") + ln["text"] for ln in mine)
        w.append("")
        w.append(f"----- {s['name']} → ไฟล์ {s['name']}.mp3 · {len(mine)} ประโยค · v3 ≈ {len(tagged):,} เครดิต · Flash ≈ {len(plain) // 2:,} เครดิต -----")
        if tagged != plain:
            w.append("[Eleven v3 มี tag อารมณ์]")
            w.append(tagged)
            w.append("")
            w.append("[ไม่มี tag]")
        w.append(plain)
    total = sum(len(ln["text"]) for ln in lines)
    w.append("")
    w.append(f"รวมทั้งตอน ≈ {total:,} ตัวอักษร · v3/Multilingual ≈ {total:,} เครดิต · Flash v2.5 ≈ {total // 2:,} เครดิต (ไม่รวมการสร้างซ้ำ)")
    return "\n".join(w) + "\n"
