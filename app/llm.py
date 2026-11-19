"""เรียก OpenRouter: แชท (เขียนบท) + TTS"""
import json
import os
import re
import threading
import time
from pathlib import Path

import requests

BASE = os.environ.get("OPENROUTER_BASE", "https://openrouter.ai/api/v1")


class LLMError(Exception):
    pass


# ---------------- บันทึกค่าใช้จ่าย (usage.jsonl ใน AUTOCLIP_ROOT) ----------------
_tl = threading.local()
_DEFAULT_TAG = os.environ.get("AUTOCLIP_TAG", "")  # subprocess ของเอนจินได้ tag ของงานจาก env


def set_tag(tag):
    """ผูกการเรียก AI ต่อจากนี้ (ในเธรดนี้ + subprocess ที่เปิดหลังจากนี้) กับงาน/EP"""
    _tl.tag = tag or ""
    os.environ["AUTOCLIP_TAG"] = tag or ""


def ledger(kind, model, cost=None, units=None, ok=True, note="", tag=None):
    root = os.environ.get("AUTOCLIP_ROOT")
    if not root:
        return
    rec = {"t": round(time.time(), 1), "tag": tag if tag is not None else getattr(_tl, "tag", _DEFAULT_TAG),
           "kind": kind, "model": model, "cost": None if cost is None else round(float(cost), 6),
           "units": units, "ok": ok}
    if note:
        rec["note"] = str(note)[:200]
    try:
        with open(Path(root) / "usage.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_ledger(limit=2000):
    root = os.environ.get("AUTOCLIP_ROOT")
    p = Path(root or ".") / "usage.jsonl"
    if not root or not p.exists():
        return []
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def account():
    """ข้อมูล key จาก OpenRouter: limit, limit_remaining, usage, usage_daily/weekly/monthly"""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    r = requests.get(f"{BASE}/key", headers={"Authorization": f"Bearer {key}"}, timeout=10)
    return (r.json() or {}).get("data") or {}


def _headers():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise LLMError("ยังไม่ได้ตั้ง OPENROUTER_API_KEY (ดูคู่มือขั้นที่ 3)")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/autoclip",
        "X-Title": "AutoClip",
    }


def chat(model, messages, json_mode=False, temperature=0.8, max_tokens=2500, retries=3):
    """คืน (text, cost_usd)"""
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "usage": {"include": True},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(f"{BASE}/chat/completions", headers=_headers(), json=body, timeout=300)
            if r.status_code == 400 and json_mode and "response_format" in body:
                body.pop("response_format")  # บาง model ไม่รองรับ → ลองใหม่แบบปกติ
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                time.sleep(8 * (attempt + 1))
                continue
            if r.status_code == 402:
                ledger("บท/ข้อความ", model, None, None, ok=False, note="402 เครดิตไม่พอ")
                raise LLMError("เครดิต OpenRouter ไม่พอ → เปลี่ยน 'เขียนบท' เป็น ฟรี หรือ เขียนเอง "
                               f"หรือเติมเครดิต (รายละเอียด: {r.text[:200]})")
            if r.status_code == 429 and attempt == retries - 1:
                raise LLMError("โมเดลฟรีถูกจำกัดการใช้ (ฟรีได้ ~50 ครั้ง/วัน, 20 ครั้ง/นาที) รอสักพักแล้วกดทำต่อ")
            if r.status_code != 200:
                raise LLMError(f"OpenRouter HTTP {r.status_code}: {r.text[:500]}")
            data = r.json()
            if "error" in data:
                raise LLMError(f"OpenRouter: {data['error']}")
            text = data["choices"][0]["message"].get("content") or ""
            u = data.get("usage") or {}
            cost = float(u.get("cost") or 0)
            ledger("บท/ข้อความ", data.get("model") or model, cost,
                   {"in": u.get("prompt_tokens"), "out": u.get("completion_tokens")})
            return text, cost
        except requests.RequestException as e:
            last = str(e)
            time.sleep(3 * (attempt + 1))
    raise LLMError(f"เรียก OpenRouter ไม่สำเร็จ: {last}")


def parse_json(text):
    """ดึง JSON ออกจากคำตอบ (รองรับ ```json ... ```)"""
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        s, e = t.find("{"), t.rfind("}")
        if s != -1 and e > s:
            return json.loads(t[s:e + 1])
        raise LLMError("AI ตอบกลับไม่ใช่ JSON: " + text[:300])


def free_image(prompt, out_path, width, height, seed=1, model="", retries=4):
    """ฟรีแบบไม่ใช้ key จำกัด ~1 ภาพ/15 วินาที → เว้นจังหวะให้เอง"""
    from urllib.parse import quote
    params = {"width": width, "height": height, "seed": seed, "nologo": "true"}
    if model:
        params["model"] = model
    url = f"{POLLINATIONS}/prompt/{quote(prompt[:900], safe='')}"
    last = None
    for attempt in range(retries):
        wait = float(os.environ.get("POLLINATIONS_GAP", "15.5")) - (time.time() - _last_img[0])
        if wait > 0:
            time.sleep(wait)
        _last_img[0] = time.time()
        try:
            r = requests.get(url, params=params, timeout=180)
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and ctype.startswith("image") and len(r.content) > 2000:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                ledger("ภาพฟรี", model or "pollinations", 0, {"img": 1})
                return
            last = f"HTTP {r.status_code} {ctype} {r.text[:200] if not ctype.startswith('image') else ''}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(10 * (attempt + 1))
    raise LLMError(f"สร้างภาพฟรีไม่สำเร็จ: {last}")
