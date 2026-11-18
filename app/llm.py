"""เรียก OpenRouter: แชท (เขียนบท) + TTS"""
import json
import os
import re
import time

import requests

BASE = os.environ.get("OPENROUTER_BASE", "https://openrouter.ai/api/v1")


class LLMError(Exception):
    pass


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


def chat(model, messages, json_mode=False, temperature=0.8, max_tokens=8000, retries=3):
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
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code != 200:
                raise LLMError(f"OpenRouter HTTP {r.status_code}: {r.text[:500]}")
            data = r.json()
            if "error" in data:
                raise LLMError(f"OpenRouter: {data['error']}")
            text = data["choices"][0]["message"].get("content") or ""
            cost = float((data.get("usage") or {}).get("cost") or 0)
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


def tts(model, text, voice, out_path, retries=3):
    """OpenRouter /audio/speech → mp3 (Gemini 3.8 TTS อ่านตามตัวอักษร ห้ามใส่คำสั่งน้ำเสียงในข้อความ)"""
    body = {"model": model, "input": text, "voice": voice, "response_format": "mp3"}
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(f"{BASE}/audio/speech", headers=_headers(), json=body, timeout=300)
            if r.status_code == 200 and r.content:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                return
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        except requests.RequestException as e:
            last = str(e)
        time.sleep(3 * (attempt + 1))
    raise LLMError(f"TTS ไม่สำเร็จ: {last}")
