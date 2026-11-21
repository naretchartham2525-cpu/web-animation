"""ภาษาพากย์ (ไทย/อังกฤษ) · ทุกอย่างในคลิปต้องเป็นภาษาเดียวกัน: เสียง + ซับ + ข้อความบนจอ
เทมเพลตที่มีเอนจินของตัวเอง: ใช้แค่สไตล์ภาพของเขา → แปลบท JSON ทั้งหมด + ป้ายสำเร็จรูปในเอนจิน เป็นอังกฤษก่อนเรนเดอร์
คำแปลจำไว้ต่อเรื่อง (ชื่อตัวละคร/คำเดิม = คำแปลเดิมทุก EP) · แปลด้วย AI ฟรี
"""
import ast
import hashlib
import json
import re
from pathlib import Path

from . import core

THAI = re.compile("[\u0E01-\u0E3A\u0E40-\u0E5B]")   # ตัวอักษรไทย (ไม่นับ ฿ ซึ่งใช้ได้ทุกภาษา)
EN_NARRATOR = "en-US-AndrewMultilingualNeural"
# เสียง Edge อังกฤษ (ฟรี) ต่อประเภทเสียง · รุ่น Multilingual เป็นธรรมชาติที่สุดของ Edge
EDGE_EN = {
    "narrator": ["edge:en-US-AndrewMultilingualNeural"],
    "hero": ["edge:en-US-BrianMultilingualNeural"],
    "hero_f": ["edge:en-US-AvaMultilingualNeural"],
    "system": ["edge:en-US-EricNeural|+4Hz"],
    "man": ["edge:en-US-GuyNeural", "edge:en-US-ChristopherNeural", "edge:en-GB-RyanNeural"],
    "woman": ["edge:en-US-EmmaMultilingualNeural", "edge:en-US-JennyNeural", "edge:en-US-AriaNeural", "edge:en-GB-SoniaNeural"],
    "oldman": ["edge:en-US-RogerNeural", "edge:en-GB-ThomasNeural|-6Hz"],
    "oldwoman": ["edge:en-US-MichelleNeural|-10Hz", "edge:en-GB-LibbyNeural|-10Hz"],
    "boy": ["edge:en-US-AnaNeural|-10Hz"],
    "girl": ["edge:en-US-AnaNeural"],
}
SKIP_KEYS = {"personality", "look", "notes", "note_th", "prompt"}   # ไม่ขึ้นจอ ไม่ต้องแปล


def has_thai(t):
    return bool(THAI.search(str(t or "")))


def dub_lang(s):
    return "en" if str((s or {}).get("dub_lang") or "th") == "en" else "th"


def edge_en(arch, i=0):
    pool = EDGE_EN.get(arch) or EDGE_EN["man"]
    return pool[i % len(pool)]


def to_english_voice(v, arch="narrator"):
    """เสียง Edge ไทย → เสียง Edge อังกฤษประเภทเดียวกัน (ภาษาอังกฤษห้ามใช้เสียงไทยอ่าน)"""
    v = str(v or "")
    if "th-TH" in v or not v:
        return edge_en(arch)
    return v


# ---------------- แปล ----------------
def _translate(strings, glossary, log):
    from . import llm
    model = core.load_settings().get("free_model") or "openrouter/free"
    out = {}
    for i in range(0, len(strings), 50):
        part = strings[i:i + 50]
        msgs = [{"role": "system", "content":
                 "Translate each Thai string into natural, short English for a vertical drama short "
                 "(spoken dialogue, narration, on-screen text, chat and UI labels). Use the GLOSSARY for names so they stay "
                 "the same everywhere. Keep numbers, emoji, symbols, currency and leading/trailing punctuation or spaces. "
                 "Keep it as short as the original (it is drawn on screen). "
                 'Reply JSON only: {"t": ["..."]} with the same count and order.'},
                {"role": "user", "content": json.dumps({"GLOSSARY": glossary, "strings": part}, ensure_ascii=False)}]
        for _ in range(2):
            try:
                text, _cost = llm.chat(model, msgs, json_mode=True, temperature=0.2, max_tokens=4000)
                got = (llm.parse_json(text) or {}).get("t") or []
                if len(got) == len(part):
                    out.update({a: str(b) for a, b in zip(part, got) if str(b).strip()})
                    break
            except Exception as e:  # noqa: BLE001
                log(f"แปลอังกฤษ: {str(e)[:120]}")
    return out


def _walk(o, fn, key=""):
    if isinstance(o, dict):
        return {k: (v if k in SKIP_KEYS else _walk(v, fn, k)) for k, v in o.items()}
    if isinstance(o, list):
        return [_walk(x, fn, key) for x in o]
    if isinstance(o, str) and has_thai(o):
        return fn(o)
    return o


def _dict_path(project):
    return core.ROOT / "cache" / "i18n" / f"en_{core.safe_name(project)}.json"


def translate_engine(project, series, ep, log):
    """series.json + epNN.json → ฉบับอังกฤษ · คืน (series_en, ep_en, คำแปลทั้งหมดของเรื่อง)"""
    f = _dict_path(project)
    d = core.read_json(f, {}) or {}
    todo = []
    _walk([series, ep], lambda t: todo.append(t) or t)
    names = [c.get("name") for c in series.get("cast") or [] if has_thai(c.get("name"))]
    miss = [t for t in dict.fromkeys(names + todo) if t not in d]
    if miss:
        log(f"แปลบทเป็นอังกฤษ {len(miss)} ข้อความ (AI ฟรี · จำคำแปลไว้ใช้ทุก EP)")
        first = [n for n in miss if n in names]
        if first:
            d.update(_translate(first, {}, log))
        rest = [t for t in miss if t not in d]
        if rest:
            gl = {n: d[n] for n in names if n in d}
            d.update(_translate(rest, gl, log))
        f.parent.mkdir(parents=True, exist_ok=True)
        core.write_json(f, d)
    left = [t for t in dict.fromkeys(todo) if t not in d]
    if left:
        raise RuntimeError(f"แปลบทเป็นอังกฤษไม่ครบ ({len(left)} ข้อความ) ลองใหม่อีกครั้ง")
    tr = lambda t: d.get(t, t)
    return _walk(series, tr), _walk(ep, tr), d


UI_FILES = ("phone_ui.py", "render_ep.py", "drama_sets.py", "drama_cars.py")   # ไฟล์ที่วาดหน้าจอ/ป้าย
DRAW_CALLS = {"text", "draw_text", "block", "subtitle", "card", "_phone", "wrap", "avatar", "bubble", "label"}


def engine_literals(skill_dir):
    """ข้อความไทยที่เอนจินวาดขึ้นจอ (หน้าจอแชต/ป้ายของ/ตอนต่อไป ฯลฯ)
    ไฟล์หน้าจอ = ทุกข้อความ · ไฟล์คลังท่า/ชุด/ของ = เฉพาะที่ส่งเข้าฟังก์ชันวาดตัวหนังสือ (ชื่อในคลังไม่ได้ขึ้นจอ ไม่ต้องแปล)"""
    files = sorted(Path(skill_dir).glob("engine/*.py")) + [Path(skill_dir) / "scripts" / "render_ep.py"]
    out = []
    for p in files:
        if not p.exists():
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        roots = [tree] if p.name in UI_FILES else [
            n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and (n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")) in DRAW_CALLS]
        for r in roots:
            for n in ast.walk(r):
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs \
                        and has_thai(n.value) and len(n.value) <= 60:
                    out.append(n.value)
    return list(dict.fromkeys(out))


def engine_builtin(skill_dir, log):
    """คำแปลป้ายสำเร็จรูปในเอนจิน (แปลครั้งเดียวต่อรุ่นโค้ด เก็บใน cache/i18n)"""
    lits = engine_literals(skill_dir)
    h = hashlib.md5("\n".join(lits).encode()).hexdigest()[:10]
    f = core.ROOT / "cache" / "i18n" / f"builtin_{core.safe_name(Path(skill_dir).name)}.json"
    d = core.read_json(f, {}) or {}
    miss = [t for t in lits if t not in d]
    if miss:
        log(f"แปลป้ายในเอนจินเป็นอังกฤษ {len(miss)} คำ (ครั้งแรกครั้งเดียว)")
        d.update(_translate(miss, {}, log))
        f.parent.mkdir(parents=True, exist_ok=True)
        core.write_json(f, d)
    d["_v"] = h
    return d


def add_builtin(skill_dir, strings, log):
    """ข้อความที่หลุด (ไม่ได้แปลตอนเรนเดอร์) → แปลเก็บไว้ EP ถัดไปถูกต้อง"""
    strings = [t for t in dict.fromkeys(strings) if has_thai(t)][:200]
    if not strings:
        return 0
    f = core.ROOT / "cache" / "i18n" / f"builtin_{core.safe_name(Path(skill_dir).name)}.json"
    d = core.read_json(f, {}) or {}
    got = _translate([t for t in strings if t not in d], {}, log)
    d.update(got)
    f.parent.mkdir(parents=True, exist_ok=True)
    core.write_json(f, d)
    return len(got)


class Translator:
    """ใช้ตอนวาด: ข้อความไทย → อังกฤษ (ตรงทั้งข้อความ → ทีละส่วนที่มาจากโค้ด เช่น "ถูกใจ 12 คน")"""

    def __init__(self, d):
        self.d = {k: v for k, v in (d or {}).items() if not k.startswith("_") and isinstance(v, str)}
        self.frags = sorted((k for k in self.d if k.strip()), key=len, reverse=True)
        self.miss = set()

    def __call__(self, t):
        if not isinstance(t, str) or not has_thai(t):
            return t
        if t in self.d:
            return self.d[t]
        s = t.strip()
        if s in self.d:
            return t.replace(s, self.d[s])
        out = t
        for k in self.frags:
            if k in out and has_thai(k):
                out = out.replace(k, self.d[k])
                if not has_thai(out):
                    break
        if has_thai(out):
            self.miss.add(t)
        return out
