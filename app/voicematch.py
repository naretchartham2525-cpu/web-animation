"""เสียงต้นฉบับของแต่ละสกิล → เสียงประจำเทมเพลต (ใช้ทุกเรื่องของเทมเพลตนั้น แค่เปลี่ยนบท)

ลำดับ:
  1) สกิลระบุชื่อเสียงไว้เอง (เช่น Kokoro `am_michael`, `am_liam:0.6,bm_george:0.4` + speed) → ใช้ตามนั้น
  2) ไม่ระบุ → ฟังเสียงพากย์ในหนังเดโมของสกิล แล้วเทียบลักษณะเสียง (speaker embedding) กับเสียงสำเร็จรูปทุกตัว
     หนังเดโมทำด้วย Kokoro เป็นหลัก → ได้เสียงเดียวกัน · 5 เรื่องทำด้วย Edge → เทียบกับเสียง Edge · Doubao (เสียเงิน) → ตัวที่ใกล้ที่สุด
  เป็นการ "เลือก" เสียงสำเร็จรูปที่ใช้ได้ฟรี ไม่ได้ลอกเสียงจากหนัง และไม่ได้เก็บเสียงของหนังไว้
ผลเก็บที่ AutoClip/cache/voicematch.json (ทำครั้งเดียวต่อสกิล)
"""
import re
import subprocess
import sys
import threading
from pathlib import Path

from . import core

FILMS = "https://lemomo-ai.github.io/lemo-opuscar-films"
EDGE_DEMOS = {"chalkboard", "circuit-board", "tabletop-app-flythrough", "isometric-people-scene", "scratchboard-long-take"}
EDGE_EN = ["en-US-AndrewMultilingualNeural", "en-US-AvaMultilingualNeural", "en-US-BrianMultilingualNeural",
           "en-US-EmmaMultilingualNeural", "en-US-AriaNeural", "en-US-ChristopherNeural", "en-US-EricNeural",
           "en-US-GuyNeural", "en-US-JennyNeural", "en-US-MichelleNeural", "en-US-RogerNeural", "en-US-SteffanNeural",
           "en-GB-RyanNeural", "en-GB-SoniaNeural", "en-GB-LibbyNeural", "en-GB-ThomasNeural", "en-AU-WilliamNeural",
           "en-AU-NatashaNeural"]
_lock = threading.Lock()
_enc = {}


def _cache():
    return core.ROOT / "cache" / "voicematch.json"


def _style_text(sid):
    d = core.SKILLS_DIR / sid
    return "\n".join((d / f).read_text(encoding="utf-8", errors="replace") for f in ("STYLE.md", "SKILL.md") if (d / f).exists())


def voice_note(text):
    """บรรทัด Voice/Announcer/Narrator ในสกิล → คำบรรยายเสียง (ใช้ออกแบบเสียง MOSS ตอนไม่มีเสียงต้นฉบับ)"""
    m = re.search(r"\*\*(?:Voice|Announcer|Narrator|Anchor voice)[^*]*\*\*\s*(?:\([^)]*\))?\s*[:：]?\s*(.+)", text or "")
    if not m:
        m = re.search(r"\|\s*(?:Voice|Anchor voice)\s*\|\s*([^|]+)\|", text or "")
    note = re.sub(r"`|\*\*", "", m.group(1)).strip() if m else ""
    return note.split(". ")[0][:220]


def declared(text):
    """เสียง Kokoro ที่สกิลระบุไว้เอง (+ ความเร็ว) → รหัสเสียง หรือ "" """
    from .kokoro_tts import VOICES, spec
    m = re.search(r"\b((?:[ab][fm]_[a-z]+)(?::[0-9.]+)?(?:\s*,\s*[ab][fm]_[a-z]+(?::[0-9.]+)?)*)\b", text or "")
    if not m:
        return ""
    parts = []
    for x in m.group(1).split(","):
        n, _, w = x.strip().partition(":")
        if n in VOICES:
            parts.append((n, float(w or 1)))
    if not parts:
        return ""
    sp = re.search(r"speed\s*[≈~]?\s*([01]\.\d+)(?:\s*[–-]\s*([01]\.\d+))?", text, re.I)
    speed = (float(sp.group(1)) + float(sp.group(2) or sp.group(1))) / 2 if sp else 1.0
    return spec(parts, round(speed, 2))


def profile(sid):
    """โทนเสียงประจำเทมเพลต: autoclip.json ของสกิล + เสียงต้นฉบับ (ถ้าจับคู่แล้ว) + คำบรรยายเสียงในสกิล"""
    prof = {k: dict(v) for k, v in (core.voice_profile(sid) or {}).items()}
    if not sid:
        return prof
    got = (core.read_json(_cache(), {}) or {}).get(sid) or {}
    nar = prof.setdefault("narrator", {})
    if got.get("voice") and not nar.get("voice"):
        nar["voice"] = got["voice"]
    if not nar.get("desc"):
        note = got.get("note") or voice_note(_style_text(sid))
        if note:
            nar["desc"] = note
    return {k: v for k, v in prof.items() if v}


# ---------------- ฟังเสียงเดโมแล้วเทียบ ----------------
def _ensure(log):
    try:
        import speechbrain  # noqa: F401
        return
    except Exception:  # noqa: BLE001
        pass
    log("จับคู่เสียง: ติดตั้งตัววัดลักษณะเสียงครั้งแรก (ฟรี)")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "speechbrain"], check=True, timeout=900)


def _encoder(log):
    if "m" not in _enc:
        _ensure(log)
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError:
            from speechbrain.pretrained import EncoderClassifier
        _enc["m"] = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                                   savedir=str(core.ROOT / "cache" / "models" / "ecapa"))
    return _enc["m"]


def _load16k(path, max_sec=120):
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", str(max_sec), "-ac", "1", "-ar", "16000",
                        "-af", "highpass=f=90,lowpass=f=4000", "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32)


def _embed(a, log):
    import torch
    e = _encoder(log).encode_batch(torch.from_numpy(a.copy()).unsqueeze(0)).squeeze()
    return (e / e.norm()).cpu().numpy()


def _windows(a, sec=2.5, hop=1.25):
    import numpy as np
    n, h = int(sec * 16000), int(hop * 16000)
    out = []
    for i in range(0, max(1, len(a) - n), h):
        w = a[i:i + n]
        if len(w) == n and float(np.sqrt((w ** 2).mean())) > 0.01:   # ข้ามช่วงเงียบ
            out.append(w)
    return out


def _cand_emb(kind, v, log):
    """ลักษณะเสียงของเสียงสำเร็จรูป (สร้างตัวอย่างครั้งเดียว เก็บไว้)"""
    import numpy as np
    d = core.ROOT / "cache" / "voicematch"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{kind}_{v}.npy"
    if f.exists():
        return np.load(f)
    wav = d / f"{kind}_{v}.wav"
    from .kokoro_tts import SAMPLE
    if kind == "kokoro":
        from .kokoro_tts import to_wav
        to_wav("kokoro:" + v, SAMPLE, wav, log)
    else:
        from .pipeline import edge_say
        edge_say(v, SAMPLE, wav.with_suffix(".mp3"), log=log)
        wav = wav.with_suffix(".mp3")
    e = _embed(_load16k(wav), log)
    np.save(f, e)
    return e


def match_one(sid, log=print):
    """ฟังหนังเดโมของสกิล → เสียงสำเร็จรูปที่ใกล้ที่สุด · คืน dict ผล (เก็บลงแคชด้วย)"""
    import numpy as np
    import requests
    from .kokoro_tts import VOICES
    text = _style_text(sid)
    res = {"note": voice_note(text)}
    dv = declared(text)
    if dv:
        res.update(voice=dv, how="สกิลระบุเสียงไว้")
    else:
        slug = sid.removeprefix("opuscar-")
        tmp = core.WORK_DIR / f"vm-{slug}.mp4"
        try:
            core.WORK_DIR.mkdir(parents=True, exist_ok=True)
            with requests.get(f"{FILMS}/{slug}.mp4", stream=True, timeout=60) as r:
                if r.status_code != 200:
                    res.update(how=f"ไม่มีหนังเดโม (HTTP {r.status_code})")
                    return _save(sid, res)
                with open(tmp, "wb") as fh:
                    for ch in r.iter_content(1 << 20):
                        fh.write(ch)
            wins = _windows(_load16k(tmp))
        finally:
            tmp.unlink(missing_ok=True)
        if len(wins) < 3:
            res.update(how="หนังเดโมไม่มีเสียงพากย์")
            return _save(sid, res)
        embs = np.stack([_embed(w, log) for w in wins[:48]])
        kind = "edge" if slug in EDGE_DEMOS else "kokoro"
        cands = EDGE_EN if kind == "edge" else list(VOICES)
        best = None
        for v in cands:
            s = embs @ _cand_emb(kind, v, log)
            score = float(np.sort(s)[-max(3, len(s) * 2 // 5):].mean())   # ช่วงที่มีเสียงพูด (เพลงล้วนได้คะแนนต่ำ ตัดทิ้ง)
            if not best or score > best[1]:
                best = (v, score)
        res.update(voice=("edge:" if kind == "edge" else "kokoro:") + best[0], score=round(best[1], 3),
                   how="เทียบกับเสียงในหนังเดโม" + (" (เดโมใช้ Doubao เสียเงิน → ใกล้ที่สุด)" if slug == "news-package" else ""))
    return _save(sid, res)


def _save(sid, res):
    with _lock:
        d = core.read_json(_cache(), {}) or {}
        d[sid] = res
        core.write_json(_cache(), d)
    return res


def ensure(sid, log=print):
    """ใช้ตอนเริ่มงาน: เทมเพลตชุด Opuscar ที่ยังไม่ได้จับคู่ → จับคู่ตอนนี้ (ไม่สำเร็จ = ใช้เสียงอัตโนมัติตามเดิม)"""
    sk = core.get_skill(sid) if sid else None
    if not sk or sk.get("pack") != "opuscar" or sid in (core.read_json(_cache(), {}) or {}):
        return
    try:
        r = match_one(sid, log)
        if r.get("voice"):
            log(f"เสียงต้นฉบับของเทมเพลต: {r['voice']} ({r.get('how', '')})")
    except Exception as e:  # noqa: BLE001
        log(f"จับคู่เสียงต้นฉบับไม่สำเร็จ (ใช้เสียงอัตโนมัติแทน): {str(e)[:150]}")


def match_all(busy=lambda: False):
    """เบื้องหลังตอนเปิดเครื่อง: จับคู่ทุกเทมเพลตชุด Opuscar ที่ยังไม่ได้ทำ (ทีละอัน · หลบตอนมีงาน)"""
    import time
    done = core.read_json(_cache(), {}) or {}
    for sk in [s for s in core.list_skills() if s.get("pack") == "opuscar" and s["id"] not in done]:
        while busy():
            time.sleep(30)
        try:
            r = match_one(sk["id"], lambda *_: None)
            print("🎙️ เสียงต้นฉบับ:", sk["id"], r.get("voice") or r.get("how"), flush=True)
        except Exception as e:  # noqa: BLE001  ลองใหม่รอบเปิดเครื่องถัดไป
            print("จับคู่เสียงไม่สำเร็จ:", sk["id"], str(e)[:120], flush=True)
