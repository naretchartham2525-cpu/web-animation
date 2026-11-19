"""เรียกเอนจินของสกิลแบบ drama-json (เช่น thai-drama-script)
สกิลวาดแอนิเมชัน · ระบบสตูดิโอเถื่อนคุมเสียง (เลือกเสียงผู้บรรยาย/ตัวละคร, ความเร็ว, Gemini หรือ Edge)

python -m app.engines.drama_runner <skill_dir> <episode.json> --out raw.mp4 --opts '{"voice": "edge:th-TH-NiwatNeural"}'
"""
import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path


def _rate(rate, add):
    try:
        v = int(str(rate or "+0%").replace("%", "")) + int(add)
    except ValueError:
        v = int(add)
    return f"{'+' if v >= 0 else ''}{v}%"


def load_engine(skill_dir):
    script = Path(skill_dir) / "scripts" / "render_ep.py"
    spec = importlib.util.spec_from_file_location("skill_render_ep", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def patch_voices(R, opts):
    main_voice = str(opts.get("voice") or "")          # เสียงพระเอก/ผู้บรรยาย
    voice_map = opts.get("voice_map") or {}             # {cast_id หรือ man/woman/...: "edge:..."|"gemini:..."}
    rate_add = int(opts.get("rate_add") or 0)
    orig_voice = R.Cast.voice

    def voice(self, cid):
        v, pitch, rate = orig_voice(self, cid)
        c = (self.by.get(cid) or {}) if hasattr(self, "by") else {}
        chosen = voice_map.get(cid) or voice_map.get(c.get("voice") or "")
        if not chosen and cid in ("hero", "narration") and main_voice:
            chosen = main_voice
        if chosen:
            if chosen.startswith("gemini:"):
                v, pitch = chosen, "+0Hz"
            elif chosen.startswith("edge:"):
                v = chosen[5:]
        return v, pitch, _rate(rate, rate_add)

    R.Cast.voice = voice

    orig_synth = R._synth_all
    tts_model = opts.get("tts_model") or "google/gemini-3.8-flash-tts"

    async def synth(items, outdir):
        gem = [it for it in items if str(it["voice"]).startswith("gemini:")]
        rest = [it for it in items if not str(it["voice"]).startswith("gemini:")]
        if rest:
            await orig_synth(rest, outdir)
        if gem:
            from app import llm
            for it in gem:
                p = Path(outdir) / f"{it['key']}.mp3"
                if not (p.exists() and p.stat().st_size > 800):
                    llm.tts(tts_model, it["tts"], it["voice"][7:], p)

    R._synth_all = synth


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir")
    ap.add_argument("episode")
    ap.add_argument("--out", required=True)
    ap.add_argument("--opts", default="{}")
    ap.add_argument("--mute", action="store_true")
    a = ap.parse_args()
    opts = json.loads(a.opts or "{}")
    R = load_engine(a.skill_dir)
    patch_voices(R, opts)
    sys.argv = ["render_ep.py", a.episode, "--out", a.out] + (["--mute"] if a.mute or opts.get("mute") else [])
    R.main()


if __name__ == "__main__":
    main()
