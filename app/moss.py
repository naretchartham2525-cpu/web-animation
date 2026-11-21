"""เสียงพากย์ MOSS (ฟรี · ทดลอง · ต้องเปิด GPU ใน Colab)

ตัวละครแต่ละตัว:
  1) ครั้งแรก: MOSS-VoiceGenerator ออกแบบเสียงจากคำบรรยาย (เพศ/วัย/นิสัย) → เก็บเป็น "เสียงต้นแบบ" ของตัวละคร
  2) ทุกประโยค ทุก EP: MOSS-TTS v1.5 พูดภาษาไทยโดยอิงเสียงต้นแบบนั้น → โทนเสียงเหมือนเดิมทุกตอน
เสียงต้นแบบเก็บที่ AutoClip/voices/moss/<เรื่อง>/<ตัวละคร>.wav (ลบไฟล์ = ให้ระบบออกแบบใหม่)
สัญญาอนุญาตโมเดล: Apache-2.0 (ใช้เชิงพาณิชย์ได้) · เป็นเสียงที่สร้างใหม่ ไม่ได้ลอกเสียงใคร
"""
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from . import core

GEN_REPO = os.environ.get("MOSS_VOICEGEN_REPO", "OpenMOSS-Team/MOSS-VoiceGenerator")
# รุ่น v1.5 รองรับภาษาไทย (รุ่นก่อนหน้าไม่มีไทย) · เปลี่ยนได้ด้วย MOSS_TTS_REPO
TTS_REPOS = [r for r in (os.environ.get("MOSS_TTS_REPO"),
                         "OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5",
                         "OpenMOSS-Team/MOSS-TTS-v1.5") if r]
SAMPLE_TEXT = "Hello there. Let me tell you a short story today, so sit back and listen closely."

# ประเภทเสียง (จาก voicecast) → คำบรรยายเสียงให้ตัวออกแบบเสียง (ภาษาอังกฤษ: ตัวออกแบบรองรับจีน/อังกฤษ)
DESC = {
    "narrator": "A calm, clear adult narrator with a warm medium-low voice, steady storytelling pace.",
    "hero": "A young adult man with a bright, confident, friendly voice, natural and expressive.",
    "hero_f": "A young adult woman with a bright, confident, friendly voice, natural and expressive.",
    "system": "A neutral, crisp announcer voice, clean and slightly robotic, even pace.",
    "man": "A middle-aged man with a firm, natural voice, moderate pace.",
    "woman": "A middle-aged woman with a clear, natural voice, moderate pace.",
    "oldman": "An elderly man with a deep, slightly raspy, slow and wise voice.",
    "oldwoman": "An elderly woman with a soft, slightly shaky, kind voice, slow pace.",
    "boy": "A young boy around ten years old with a high, energetic, playful voice.",
    "girl": "A young girl around ten years old with a high, cheerful, lively voice.",
}

_lock = threading.Lock()
_state = {"tts": None, "proc": None, "repo": None, "dev": None, "dtype": None, "failed": None}


def ref_dir(project):
    return core.ROOT / "voices" / "moss" / core.safe_name(project or "_")


def ref_path(project, speaker):
    return ref_dir(project) / f"{core.safe_name(speaker or 'ผู้บรรยาย')[:60]}.wav"


def _ensure_deps(log):
    """ติดตั้งครั้งแรก (โมเดลต้องใช้ transformers รุ่นใหม่) · ไม่แตะ torch ของ Colab"""
    try:
        import transformers  # noqa: F401
        if int(transformers.__version__.split(".")[0]) >= 5:
            import torchaudio  # noqa: F401
            return
    except Exception:  # noqa: BLE001
        pass
    log("MOSS: ติดตั้งไลบรารีครั้งแรก (transformers 5) …")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers>=5.0.0", "accelerate", "soundfile", "librosa"],
                   check=True, timeout=900)
    import importlib
    for m in [m for m in sys.modules if m == "transformers" or m.startswith("transformers.")]:
        del sys.modules[m]
    importlib.invalidate_caches()


def _device():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("ไม่มี GPU (ใน Colab: Runtime → Change runtime type → T4 GPU แล้วรันใหม่)")
    torch.backends.cuda.enable_cudnn_sdp(False)   # ตามตัวอย่างของผู้ทำ: cuDNN SDPA มีปัญหา
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16   # T4 ไม่รองรับ bf16
    return "cuda", dtype


def _load(repo, log):
    import torch
    from transformers import AutoModel, AutoProcessor
    dev, dtype = _device()
    log(f"MOSS: โหลดโมเดล {repo} (ครั้งแรกดาวน์โหลดหลาย GB)")
    proc = AutoProcessor.from_pretrained(repo, trust_remote_code=True, normalize_inputs=True)
    proc.audio_tokenizer = proc.audio_tokenizer.to(dev)
    model = AutoModel.from_pretrained(repo, trust_remote_code=True, attn_implementation="sdpa", torch_dtype=dtype).to(dev).eval()
    return model, proc, dev, torch


def _gen(model, proc, dev, torch, msg, out_wav, max_new=1500):
    import torchaudio
    batch = proc([[msg]], mode="generation")
    with torch.no_grad():
        outputs = model.generate(input_ids=batch["input_ids"].to(dev), attention_mask=batch["attention_mask"].to(dev),
                                 max_new_tokens=max_new)
    audio = next(iter(proc.decode(outputs))).audio_codes_list[0]
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(out_wav), audio.unsqueeze(0).float().cpu(), proc.model_config.sampling_rate)


def design(project, speaker, arch, log, instruction=None):
    """ออกแบบเสียงต้นแบบของตัวละคร (ครั้งเดียว) → wav"""
    out = ref_path(project, speaker)
    inst = instruction or DESC.get(arch) or DESC["man"]
    if _state["tts"]:                       # GPU ฟรี (T4 15GB) ใส่สองโมเดลพร้อมกันไม่สบาย → ปล่อยตัวพากย์ก่อน
        import torch
        _state["tts"] = None
        torch.cuda.empty_cache()
    model, proc, dev, torch = _load(GEN_REPO, log)
    try:
        _gen(model, proc, dev, torch, proc.build_user_message(text=SAMPLE_TEXT, instruction=inst), out, 600)
    finally:
        del model
        torch.cuda.empty_cache()            # ปล่อย GPU ให้ตัวพากย์
    core.write_json(out.with_suffix(".json"), {"speaker": speaker, "arch": arch, "instruction": inst})
    log(f"MOSS: ออกแบบเสียง \"{speaker or 'ผู้บรรยาย'}\" แล้ว ({arch}) · ใช้เสียงนี้ทุก EP")
    return out


def _tts(log):
    if _state["tts"]:
        return _state["tts"]
    err = None
    for repo in TTS_REPOS:
        try:
            _state["tts"] = _load(repo, log)
            _state["repo"] = repo
            return _state["tts"]
        except Exception as e:  # noqa: BLE001  ชื่อรุ่นไม่ตรง → ลองตัวถัดไป
            err = e
            log(f"MOSS: โหลด {repo} ไม่ได้ ({str(e)[:100]})")
    raise RuntimeError(f"โหลดตัวพากย์ MOSS ไม่ได้: {err}")


def speak(project, speaker, arch, text, out_mp3, log):
    """พูดภาษาไทยด้วยเสียงต้นแบบของตัวละคร → mp3 · พังครั้งไหน = เลิกใช้ MOSS ทั้งงานนี้ (กลับไปใช้ Edge)"""
    if _state["failed"]:
        raise RuntimeError(_state["failed"])
    with _lock:
        try:
            _device()                          # ไม่มี GPU → รู้ทันที ไม่ต้องติดตั้งอะไร
            _ensure_deps(log)
            ref = ref_path(project, speaker)
            if not ref.exists():
                design(project, speaker, arch, log)
            model, proc, dev, torch = _tts(log)
            wav = Path(out_mp3).with_suffix(".moss.wav")
            try:
                msg = proc.build_user_message(text=text, reference=[str(ref)], language="Thai")
            except TypeError:
                msg = proc.build_user_message(text=text, reference=[str(ref)])
            n = max(200, min(4000, int(len(text) * 2.2) + 150))   # ~12.5 โทเคน/วินาที · ไทยราว 6-8 ตัวอักษร/วินาที
            _gen(model, proc, dev, torch, msg, wav, n)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", "silenceremove=start_periods=1:start_threshold=-50dB",
                            "-c:a", "libmp3lame", "-q:a", "3", str(out_mp3)], check=True)
            wav.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            _state["failed"] = f"MOSS ใช้ไม่ได้: {str(e)[:160]}"
            raise RuntimeError(_state["failed"]) from e


def reset_failure():
    _state["failed"] = None


def list_refs(project):
    d = ref_dir(project)
    out = []
    for w in sorted(d.glob("*.wav")) if d.exists() else []:
        meta = core.read_json(w.with_suffix(".json"), {}) or {}
        out.append({"file": w.name, "speaker": meta.get("speaker") or w.stem, "arch": meta.get("arch", ""),
                    "instruction": meta.get("instruction", "")})
    return out


def is_moss(v):
    return str(v or "").startswith("moss:")


def safe_file(name):
    return bool(re.fullmatch(r"[^/\\]+\.wav", name or ""))


__all__ = ["speak", "design", "list_refs", "ref_path", "ref_dir", "is_moss", "reset_failure"]
