"""ElevenLabs (เสียงพากย์เสียเงิน ใช้ key จาก Colab Secrets: ELEVENLABS_API_KEY)
- เสียงในระบบเขียนเป็น "eleven:<voice_id>"
- ทุกประโยคที่สร้างแล้วเก็บแคชใน Drive (AutoClip/cache/eleven) → เรนเดอร์ซ้ำ/แก้บทบางประโยค ไม่เสียเครดิตซ้ำ
- โมเดลที่อ่านภาษาไทยได้: eleven_v4, eleven_v4_turbo (ครึ่งราคา), eleven_v3 · Flash/Multilingual v2 ไม่รองรับไทย
"""
import hashlib
import os
import shutil
import time
from pathlib import Path

import requests

BASE = os.environ.get("ELEVENLABS_BASE", "https://api.elevenlabs.io/v1")
MODELS = [  # (model_id, ชื่อในเว็บ, เครดิตต่อตัวอักษรโดยประมาณ, รองรับ [tag] อารมณ์) · ค่าเริ่มต้น = ถูกสุดที่อ่านไทยได้
    ("eleven_v4_turbo", "Eleven v4 Turbo · ประหยัดสุด (ค่าเริ่มต้น)", 0.5, True),
    ("eleven_v4", "Eleven v4 · อารมณ์ดีสุด (2 เท่า)", 1.0, True),
    ("eleven_v3", "Eleven v3 (2 เท่า)", 1.0, True),
]
DEFAULT_MODEL = "eleven_v4_turbo"
NO_THAI = ("eleven_flash", "eleven_turbo_v2", "eleven_multilingual_v2", "eleven_monolingual")


class ElevenError(Exception):
    pass


def key():
    return os.environ.get("ELEVENLABS_API_KEY", "").strip()


def enabled():
    return bool(key())


def _h():
    k = key()
    if not k:
        raise ElevenError("ยังไม่ได้ตั้ง ELEVENLABS_API_KEY ใน Colab Secrets")
    return {"xi-api-key": k}


def _err(r):
    try:
        d = r.json().get("detail")
        msg = d.get("message") if isinstance(d, dict) else str(d)
    except Exception:
        msg = r.text[:200]
    if r.status_code == 401:
        return ElevenError("ElevenLabs: API key ไม่ถูกต้อง หรือ key ไม่มีสิทธิ์ (ตรวจใน ElevenLabs → Developers → API Keys)")
    if r.status_code in (402, 429) or "quota" in str(msg).lower() or "credit" in str(msg).lower():
        return ElevenError(f"ElevenLabs: เครดิตไม่พอหรือใช้ถี่เกินไป ({msg})")
    return ElevenError(f"ElevenLabs HTTP {r.status_code}: {msg}")


def voices():
    """เสียงใน My Voices ของบัญชี (เพิ่มเสียงจาก Voice Library เข้า My Voices ก่อน)"""
    r = requests.get(f"{BASE}/voices", headers=_h(), timeout=30)
    if r.status_code != 200:
        raise _err(r)
    out = []
    for v in r.json().get("voices") or []:
        lb = v.get("labels") or {}
        out.append({"id": v.get("voice_id"), "name": v.get("name") or v.get("voice_id"),
                    "gender": lb.get("gender") or "", "age": lb.get("age") or "", "accent": lb.get("accent") or "",
                    "category": v.get("category") or "", "preview": v.get("preview_url") or ""})
    return sorted(out, key=lambda x: x["name"].lower())


AGE_MAP = {"young": "young", "middle_aged": "middle_aged", "old": "old"}


def library(gender="", age="", language="th", page_size=30):
    """ค้นเสียงใน Voice Library (เสียงที่คนอื่นแชร์) · กรองภาษาไทย/เพศ/วัย · ตัดเสียงที่คิดเครดิตแพงกว่าปกติ"""
    params = {"page_size": page_size, "language": language, "sort": "usage_character_count_1y"}
    if gender:
        params["gender"] = gender
    if age:
        params["age"] = age
    r = requests.get(f"{BASE}/shared-voices", headers=_h(), params=params, timeout=30)
    if r.status_code != 200:
        raise _err(r)
    out = []
    for v in r.json().get("voices") or []:
        rate = v.get("rate")
        if rate not in (None, 0, 1, 1.0):
            continue          # ตัวคูณราคา > 1 = แพงกว่าปกติ
        out.append({"id": v.get("voice_id"), "owner": v.get("public_owner_id"), "name": v.get("name") or "",
                    "gender": v.get("gender") or "", "age": v.get("age") or "", "language": v.get("language") or "",
                    "accent": v.get("accent") or "", "use_case": v.get("use_case") or "", "preview": v.get("preview_url") or "",
                    "desc": v.get("descriptive") or ""})
    return out


def add_shared(v):
    """เพิ่มเสียงจาก Voice Library เข้า My Voices (ใช้ช่องเสียงของแผน) → คืน voice_id ในบัญชี"""
    r = requests.post(f"{BASE}/voices/add/{v['owner']}/{v['id']}", headers={**_h(), "Content-Type": "application/json"},
                      json={"new_name": f"สตูดิโอเถื่อน · {v.get('name') or v['id']}"[:60]}, timeout=30)
    if r.status_code != 200:
        raise _err(r)
    return r.json().get("voice_id") or v["id"]


def subscription():
    r = requests.get(f"{BASE}/user/subscription", headers=_h(), timeout=20)
    if r.status_code != 200:
        raise _err(r)
    d = r.json()
    used, limit = d.get("character_count"), d.get("character_limit")
    return {"used": used, "limit": limit, "left": (limit - used) if isinstance(used, int) and isinstance(limit, int) else None,
            "tier": d.get("tier") or "", "reset": d.get("next_character_count_reset_unix")}


def model_info(model):
    for m in MODELS:
        if m[0] == model:
            return m
    return (model, model, 1.0, model.startswith(("eleven_v3", "eleven_v4")))


def with_tag(text, emo, model):
    return f"[{emo}] {text}" if emo and model_info(model)[3] else text


def cache_dir():
    root = Path(os.environ.get("AUTOCLIP_ROOT", "."))
    d = root / "cache" / "eleven"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tts(text, voice_id, model, out_path, retries=3):
    """สร้างเสียง 1 ประโยค → mp3 (มีแคช: ข้อความ+เสียง+โมเดลเดิม = ไม่เสียเครดิตซ้ำ) · คืนจำนวนตัวอักษรที่ถูกคิด (0 = จากแคช)"""
    model = model or DEFAULT_MODEL
    if model.startswith(NO_THAI):
        raise ElevenError(f"โมเดล {model} ไม่รองรับภาษาไทย ใช้ eleven_v4 / eleven_v4_turbo / eleven_v3")
    text = str(text or "").strip()
    if not text:
        raise ElevenError("ข้อความว่าง")
    h = hashlib.sha1(f"{voice_id}|{model}|{text}".encode()).hexdigest()[:20]
    cached = cache_dir() / f"{h}.mp3"
    out_path = Path(out_path)
    if cached.exists() and cached.stat().st_size > 800:
        shutil.copyfile(cached, out_path)
        return 0
    last = None
    for i in range(retries):
        try:
            r = requests.post(f"{BASE}/text-to-speech/{voice_id}", params={"output_format": "mp3_44100_128"},
                              headers={**_h(), "Content-Type": "application/json"},
                              json={"text": text, "model_id": model}, timeout=120)
        except requests.RequestException as e:
            last = ElevenError(f"ElevenLabs เชื่อมต่อไม่ได้: {e}")
            time.sleep(2 * (i + 1))
            continue
        if r.status_code == 200 and len(r.content) > 800:
            tmp = cached.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.replace(cached)
            shutil.copyfile(cached, out_path)
            try:
                from . import llm
                llm.ledger("เสียง ElevenLabs", model, None, {"chars": len(text)}, note="หักเครดิต ElevenLabs (ไม่ใช่ OpenRouter)")
            except Exception:
                pass
            return len(text)
        last = _err(r)
        if r.status_code in (401, 402, 400, 422):
            break
        time.sleep(3 * (i + 1))
    raise last or ElevenError("ElevenLabs ไม่ตอบ")
