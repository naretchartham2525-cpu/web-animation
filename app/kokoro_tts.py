"""เสียง Kokoro (ฟรี · Apache-2.0 · รันบน CPU ได้) — เสียงที่สกิลชุด Lemo-Opuscar ใช้ทำหนังต้นฉบับ
รหัสเสียง: "kokoro:<เสียง>|<ความเร็ว>" เช่น kokoro:am_michael|1.0 · ผสมเสียง: kokoro:am_liam:0.6,bm_george:0.4|1.17
พูดได้แค่อังกฤษ (และจีน) · พากย์ไทย = ให้ MOSS พูดไทยด้วยโทนของเสียงนี้ (ดู pipeline.make_tts)
"""
import re
import subprocess
import sys
import threading
from pathlib import Path

from . import core

VOICES = {   # เสียงอังกฤษทั้งหมดของ Kokoro v1.0 → (เพศ, สำเนียง)
    **{v: ("female", "US") for v in ("af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore", "af_nicole",
                                      "af_nova", "af_river", "af_sarah", "af_sky")},
    **{v: ("male", "US") for v in ("am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa")},
    **{v: ("female", "UK") for v in ("bf_alice", "bf_emma", "bf_isabella", "bf_lily")},
    **{v: ("male", "UK") for v in ("bm_daniel", "bm_fable", "bm_george", "bm_lewis")},
}
SAMPLE = ("Some stories begin quietly. A small shop opens on a busy street, and nobody expects much. "
          "But by the end of the week, everyone in town is talking about it.")
_lock = threading.Lock()
_pipes = {}


def is_kokoro(v):
    return str(v or "").startswith("kokoro:")


def parse(v):
    """kokoro:am_liam:0.6,bm_george:0.4|1.17 → ([(am_liam, .6), (bm_george, .4)], 1.17)"""
    body, _, sp = str(v).removeprefix("kokoro:").partition("|")
    parts = []
    for x in body.split(","):
        name, _, w = x.strip().partition(":")
        if name in VOICES:
            parts.append((name, float(w or 1)))
    try:
        speed = min(1.4, max(0.7, float(sp))) if sp else 1.0
    except ValueError:
        speed = 1.0
    return parts or [("am_michael", 1.0)], speed


def spec(parts, speed=1.0):
    body = ",".join(f"{n}:{w:g}" if len(parts) > 1 else n for n, w in parts)
    return f"kokoro:{body}" + (f"|{speed:g}" if abs(speed - 1) > 1e-3 else "")


def gender(v):
    parts, _ = parse(v)
    return VOICES.get(max(parts, key=lambda p: p[1])[0], ("male",))[0]


def _ensure(log):
    try:
        import kokoro  # noqa: F401
        return
    except Exception:  # noqa: BLE001
        pass
    log("Kokoro: ติดตั้งครั้งแรก (ฟรี · ราว 1-2 นาที)")
    subprocess.run(["apt-get", "install", "-y", "-qq", "espeak-ng"], capture_output=True, timeout=300)   # อ่านคำแปลกๆ ได้ดีขึ้น (ไม่มีก็ใช้ได้)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "kokoro>=0.9.4", "soundfile"], check=True, timeout=900)


def _pipe(lang, log):
    if lang not in _pipes:
        _ensure(log)
        from kokoro import KPipeline
        _pipes[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    return _pipes[lang]


def to_wav(v, text, out_wav, log=print):
    """พูดอังกฤษด้วยเสียง Kokoro → wav 24kHz"""
    import numpy as np
    import soundfile as sf
    parts, speed = parse(v)
    lang = "b" if parts[0][0].startswith("b") else "a"
    with _lock:
        p = _pipe(lang, log)
        if len(parts) == 1:
            voice = parts[0][0]
        else:   # ผสมเสียงตามน้ำหนัก (เหมือนที่สกิลต้นฉบับใช้)
            tot = sum(w for _, w in parts)
            voice = sum(p.load_voice(n) * (w / tot) for n, w in parts)
        chunks = [a.cpu().numpy() if hasattr(a, "cpu") else np.asarray(a)
                  for _, _, a in p(text, voice=voice, speed=speed, split_pattern=r"\n+") if a is not None]
    if not chunks:
        raise RuntimeError("Kokoro ไม่ได้เสียงกลับมา")
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), np.concatenate(chunks), 24000)
    return out_wav


def say(v, text, out_mp3, log=print):
    wav = Path(out_mp3).with_suffix(".k.wav")
    to_wav(v, text, wav, log)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libmp3lame", "-q:a", "3", str(out_mp3)], check=True)
    wav.unlink(missing_ok=True)


def _sample_path(v):
    name = re.sub(r"[^a-z0-9_.,:-]", "_", str(v).removeprefix("kokoro:").replace("|", "_s"))
    return core.ROOT / "voices" / "kokoro" / f"{name}.wav"


def ready(v):
    """มีเสียงตัวอย่างแล้ว หรือโหลดโมเดลไว้แล้ว (สร้างได้เร็ว)"""
    return _sample_path(v).exists() or bool(_pipes)


def sample(v, log=print):
    """เสียงตัวอย่างของเสียงนี้ (สร้างครั้งเดียว) — ใช้ฟังตัวอย่าง และเป็นเสียงต้นแบบให้ MOSS พูดไทยด้วยโทนเดียวกัน"""
    out = _sample_path(v)
    if not out.exists():
        to_wav(v, SAMPLE, out, log)
    return out
