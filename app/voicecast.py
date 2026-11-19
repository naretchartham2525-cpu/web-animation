"""เลือกเสียงตัวละครให้อัตโนมัติ + จดจำ
ลำดับ: เรื่องนี้เคยกำหนด (project voice_map) → ชื่อเดิมในเทมเพลตนี้ (ข้ามเรื่อง)
       → ช่องเสียงตามประเภทของเทมเพลต (ผู้หญิงคนที่ 1 = เสียง A ทุกเรื่อง) → เลือกใหม่จากเพศ/วัย แล้วจำ
ความจำของเทมเพลตเก็บที่ AutoClip/skills/<เทมเพลต>/voices.json (Drive)
ผู้ให้บริการ: ElevenLabs ถ้ามี key (และเทมเพลตไม่ได้ตั้ง voice_provider=edge) · ไม่มี key → Edge ฟรี
"""
import json
import os
import re

from . import core

# ประเภทเสียง → (เพศ, วัยที่ชอบ)
ARCH = {"man": ("male", ("middle_aged", "young")), "woman": ("female", ("middle_aged", "young")),
        "oldman": ("male", ("old", "middle_aged")), "oldwoman": ("female", ("old", "middle_aged")),
        "boy": ("male", ("young",)), "girl": ("female", ("young",))}
# Edge ไทยมีเสียงน้อย (ชาย 1 หญิง 2) → แยกตัวละครด้วยระดับเสียง (pitch) "edge:<voice>|<pitch>"
EDGE_ARCH = {
    "hero": ["edge:th-TH-NiwatNeural"], "narrator": ["edge:th-TH-NiwatNeural"], "system": ["edge:th-TH-NiwatNeural|+6Hz"],
    "hero_f": ["edge:th-TH-PremwadeeNeural"],
    "man": ["edge:th-TH-NiwatNeural|-8Hz", "edge:th-TH-NiwatNeural|+8Hz", "edge:th-TH-NiwatNeural|-16Hz"],
    "oldman": ["edge:th-TH-NiwatNeural|-20Hz", "edge:th-TH-NiwatNeural|-26Hz"],
    "boy": ["edge:th-TH-NiwatNeural|+22Hz", "edge:th-TH-NiwatNeural|+16Hz"],
    "woman": ["edge:th-TH-AcharaNeural", "edge:th-TH-PremwadeeNeural|-8Hz", "edge:th-TH-AcharaNeural|+8Hz"],
    "oldwoman": ["edge:th-TH-AcharaNeural|-14Hz", "edge:th-TH-PremwadeeNeural|-18Hz"],
    "girl": ["edge:th-TH-PremwadeeNeural|+14Hz", "edge:th-TH-AcharaNeural|+18Hz"],
}
FEMALE_CUE = ("เจ๊", "ป้า", "แม่", "ยาย", "นาง", "พี่สาว", "น้องสาว", "คุณนาย", "หญิง", "สาว", "เมีย", "ภรรยา", "ย่า")
MALE_CUE = ("ลุง", "ตา", "พ่อ", "นาย", "เฮีย", "พี่ชาย", "น้องชาย", "ปู่", "ชาย", "ผัว", "สามี", "หนุ่ม", "ผม")
OLD_CUE = ("ป้า", "ยาย", "ลุง", "ตา", "ปู่", "ย่า", "แก่")
KID_CUE = ("น้อง", "หนู", "เด็ก")


def _mem_path(skill_id):
    d = core.SKILLS_DIR / skill_id
    return d / "voices.json" if d.is_dir() else core.ROOT / "cache" / f"voices_{core.safe_name(skill_id)}.json"


def load_mem(skill_id):
    return core.read_json(_mem_path(skill_id), {}) or {} if skill_id else {}


def save_mem(skill_id, mem):
    if skill_id:
        p = _mem_path(skill_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        core.write_json(p, mem)


def classify(skill, speakers, context=""):
    """ให้ AI ฟรีอ่านเทมเพลต + บท แล้วบอกเพศ/วัยของตัวละครที่ยังไม่รู้จัก (จำไว้ในเทมเพลต ไม่ถามซ้ำ)"""
    sid = (skill or {}).get("id") or ""
    mem = load_mem(sid)
    known = mem.setdefault("arch", {})
    todo = [x["name"] for x in speakers if x["key"] not in ("ผู้บรรยาย", "hero", "system", "narrator") and x["name"] not in known]
    if not todo or not os.environ.get("OPENROUTER_API_KEY"):
        return known
    from . import llm
    tpl = ((skill or {}).get("content") or "")[:2500]
    msgs = [{"role": "system", "content": "You cast voices for a Thai animated short. For each character name decide the voice type "
             "from: man, woman, oldman, oldwoman, boy, girl. Use the template description, the script lines and Thai naming cues "
             "(e.g. เจ๊/ป้า/ยาย = female, ลุง/ตา/เฮีย = male, น้อง+name may be either: decide from context). "
             'Reply JSON only: {"voices": {"<name>": "<type>"}}'},
            {"role": "user", "content": f"TEMPLATE:\n{tpl}\n\nSCRIPT:\n{context[:3500]}\n\nCHARACTERS: {json.dumps(todo, ensure_ascii=False)}"}]
    try:
        text, _ = llm.chat(core.load_settings().get("free_model") or "openrouter/free", msgs, json_mode=True,
                           temperature=0.1, max_tokens=500)
        got = (llm.parse_json(text) or {}).get("voices") or {}
        for n in todo:
            v = str(got.get(n) or "").strip().lower()
            if v in ARCH:
                known[n] = v
        save_mem(sid, mem)
    except Exception:
        pass
    return known


def archetype_of(spk, series=None, known=None):
    """speaker → ประเภทเสียง (hero/narrator/man/woman/oldman/oldwoman/boy/girl)"""
    key, name = spk.get("key", ""), spk.get("name", "")
    if key in ("hero",):
        c = next((c for c in (series or {}).get("cast") or [] if c.get("id") == "hero"), {})
        return "hero_f" if str(c.get("sex", "")).startswith("f") else "hero"
    if key in ("ผู้บรรยาย", "narrator"):
        return "narrator"
    if key == "system":
        return "system"
    c = next((c for c in (series or {}).get("cast") or [] if c.get("id") == key), None)
    if c and c.get("voice") in ARCH:
        return c["voice"]
    if c and c.get("sex"):
        f = str(c["sex"]).startswith("f")
        age = str(c.get("age") or "")
        old = re.search(r"([5-9]\d)", age)
        return ("old" if old else "") + ("woman" if f else "man")
    if known and known.get(name) in ARCH:
        return known[name]
    n = str(name)
    f = any(x in n for x in FEMALE_CUE)
    m = any(x in n for x in MALE_CUE)
    old = any(x in n for x in OLD_CUE)
    kid = any(n.startswith(x) for x in KID_CUE)
    if kid:
        return "girl" if f else "boy"
    if f and not m:
        return "oldwoman" if old else "woman"
    return "oldman" if old else "man"


def _gender_age(arch):
    if arch in ("hero", "narrator", "system"):
        return "male", ("young", "middle_aged")
    if arch == "hero_f":
        return "female", ("young", "middle_aged")
    return ARCH.get(arch, ("male", ("middle_aged",)))


def _pool(provider, el_voices, arch):
    g, ages = _gender_age(arch)
    if provider != "eleven":
        return list(EDGE_ARCH.get(arch) or EDGE_ARCH["man"])
    def score(v):
        s = 0
        if (v.get("gender") or "").lower() == g:
            s += 10
        if (v.get("age") or "").lower().replace(" ", "_") in ages:
            s += 4 - ages.index((v.get("age") or "").lower().replace(" ", "_"))
        return s
    vs = sorted(el_voices, key=lambda v: (-score(v), v.get("name", "")))
    return ["eleven:" + v["id"] for v in vs if score(v) >= 10] or ["eleven:" + v["id"] for v in vs]


def provider_for(skill):
    from . import eleven
    pref = ((skill or {}).get("options") or {}).get("voice_provider") or "auto"
    return "eleven" if pref != "edge" and eleven.enabled() else "edge"


def _fits(v, arch, el_voices):
    """เสียงใน My Voices ตรงเพศไหม (Edge ถือว่าตรงเสมอ)"""
    if not v.startswith("eleven:"):
        return True
    g, ages = _gender_age(arch)
    m = next((x for x in el_voices or [] if "eleven:" + x["id"] == v), None)
    age = (m or {}).get("age", "").lower().replace(" ", "_")
    return bool(m) and (m.get("gender") or "").lower() == g and (not age or age in ages)


def _from_library(arch, used, mem):
    from . import eleven
    g, ages = _gender_age(arch)
    added = mem.setdefault("library_added", {})
    for age in ages + ("",):
        try:
            cands = eleven.library(gender=g, age=age)
        except Exception:
            return None
        for c in cands:
            vid = added.get(c["id"])
            if vid and "eleven:" + vid in used:
                continue
            if not vid:
                try:
                    vid = eleven.add_shared(c)
                except Exception:
                    return None           # ช่องเสียงเต็ม/ไม่มีสิทธิ์ → ใช้เสียงที่มี
                added[c["id"]] = vid
            return "eleven:" + vid
    return None


def auto_map(speakers, skill, project_map=None, series=None, el_voices=None, known=None, preview=False):
    """คืน (voice_map ครบทุกผู้พูด, มีการเปลี่ยนความจำเทมเพลตไหม) · ไม่ทับที่ผู้ใช้/เรื่องกำหนดไว้แล้ว"""
    sid = (skill or {}).get("id") or ""
    provider = provider_for(skill)
    if provider == "eleven" and el_voices is None:
        from . import eleven
        try:
            el_voices = eleven.voices()
        except Exception:
            el_voices, provider = [], "edge"
    mem = load_mem(sid)
    pm = mem.setdefault(provider, {"names": {}, "slots": {}})
    out = {k: v for k, v in (project_map or {}).items() if v}
    valid = (lambda v: v.startswith("eleven:")) if provider == "eleven" else (lambda v: v.startswith("edge:"))
    used = set(out.values())
    slot_n = {}
    changed = False
    for spk in speakers:
        key = spk["key"]
        arch = archetype_of(spk, series, known)
        if key in out:
            if arch not in ("hero", "hero_f", "narrator", "system"):
                slot_n[arch] = slot_n.get(arch, 0) + 1
            continue
        name = spk.get("name") or key
        v = pm["names"].get(name)
        if not v or not valid(v):
            slots = pm["slots"].setdefault(arch, [])
            i = slot_n.get(arch, 0)
            slot_n[arch] = i + 1
            v = slots[i] if i < len(slots) and valid(slots[i]) else None
            if not v:
                pool = _pool(provider, el_voices or [], arch)
                v = next((x for x in pool if x not in used and _fits(x, arch, el_voices)), None)
                if not v and provider == "eleven" and not preview:
                    v = _from_library(arch, used, mem)       # My Voices ไม่มีที่เข้ากัน → หาเสียงไทยจาก Voice Library
                if not v:
                    v = next((x for x in pool if x not in used), pool[i % len(pool)] if pool else "")
                if v:
                    if i < len(slots):
                        slots[i] = v
                    else:
                        slots.append(v)
                    changed = True
            if v and pm["names"].get(name) != v:
                pm["names"][name] = v
                changed = True
        if v:
            out[key] = v
            used.add(v)
    if changed:
        save_mem(sid, mem)
    return out, provider


def remember(skill, voice_map, speakers):
    """ผู้ใช้เลือกเสียงเอง → จำชื่อตัวละครนั้นกับเทมเพลตด้วย (ใช้ข้ามเรื่อง)"""
    sid = (skill or {}).get("id") or ""
    if not sid:
        return
    mem = load_mem(sid)
    names = {s["key"]: s.get("name") or s["key"] for s in speakers}
    for k, v in (voice_map or {}).items():
        if not v:
            continue
        prov = "eleven" if v.startswith("eleven:") else "edge"
        mem.setdefault(prov, {"names": {}, "slots": {}})["names"][names.get(k, k)] = v
    save_mem(sid, mem)


def resolve_for_episode(ctx, name, skill, s, speakers, series=None, engine=False, context=""):
    """ใช้ตอนเริ่มทำ EP: เติมเสียงตัวละครที่ยังไม่มี → บันทึกกับเรื่อง + เทมเพลต → คืน voice_map"""
    proj = core.get_project(name) or {}
    pmap = dict((proj.get("options") or {}).get("voice_map") or {})
    pmap.update({k: v for k, v in (s.get("voice_map") or {}).items() if v})   # ค่าที่เลือกตอนสร้าง/EP นี้
    main = str(s.get("_voice_full") or "")
    hero_key = "hero" if engine else "ผู้บรรยาย"
    if main and hero_key not in pmap:
        pmap[hero_key] = main        # เสียงหลักที่เลือกในแถบพิมพ์ = พระเอก/ผู้บรรยาย
    provider = provider_for(skill)
    known = None
    if not engine and context:
        known = classify(skill, speakers, context)
    if engine and provider == "edge":
        vm = pmap                    # เอนจินมีการแคสต์เสียง Edge ของตัวเองอยู่แล้ว (ต่างระดับเสียงต่อตัวละคร)
    else:
        vm, provider = auto_map(speakers, skill, pmap, series, known=known)
    new = {k: v for k, v in vm.items() if (proj.get("options") or {}).get("voice_map", {}).get(k) != v}
    if new:
        opts = dict(proj.get("options") or {})
        opts["voice_map"] = {**(opts.get("voice_map") or {}), **vm}
        core.update_project(name, {"options": opts})
        names = {x["key"]: x.get("name") or x["key"] for x in speakers}
        ctx.log("เสียงตัวละคร (" + ("ElevenLabs" if provider == "eleven" else "Edge ฟรี") + "): " +
                ", ".join(f"{names.get(k, k)}={_label(v)}" for k, v in vm.items() if k in names))
    remember(skill, {k: v for k, v in vm.items() if k in {x["key"] for x in speakers}}, speakers)
    return vm


def _label(v):
    return v.split(":", 1)[-1][:24]
