"""เรียกเอนจินของสกิลแบบ drama-json (เช่น thai-drama-script)
สกิลวาดแอนิเมชัน · ระบบสตูดิโอเถื่อนคุมเสียง (เลือกเสียงผู้บรรยาย/ตัวละคร, ความเร็ว, Edge ฟรี หรือไฟล์เสียงที่อัปเอง)

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


class PaidVoiceError(BaseException):
    """BaseException: ทะลุ try/except ของเอนจิน → งานหยุดพร้อมข้อความ แทนที่จะเรนเดอร์เงียบ"""


EMO = {}   # ข้อความที่อ่าน → tag อารมณ์ (ElevenLabs v3/v4)
FREE = set()   # ข้อความที่ตัวละครไม่ได้พูดเอง (ข้อความบนจอ/เสียงระบบ) → เสียงฟรีเสมอ
FREE_VOICE = {}   # ข้อความ → (เสียง Edge เดิมของสกิล, pitch)


def patch_free_lines(R):
    """ก่อนสร้างเสียง: จำเสียงฟรีเดิมของสกิลสำหรับข้อความบนจอ/เสียงระบบ (แต่ละตัวละครยังได้เสียงต่างกัน)"""
    inner = R.voice_track

    def voice_track(segs, cast, *a, **k):
        orig = FREE_VOICE.get("_orig")
        for sg in segs:
            t = R.clean_tts(sg["text"])
            if t in FREE and orig:
                v, pitch, _ = orig(cast, sg["who"])
                FREE_VOICE[t] = (v, pitch)
        return inner(segs, cast, *a, **k)
    R.voice_track = voice_track


def load_emotions(skill_dir, episode):
    try:
        from app import voicesheet
        ep = json.loads(Path(episode).read_text(encoding="utf-8"))
        series = json.loads((Path(episode).parent / "series.json").read_text(encoding="utf-8"))
        for ln in voicesheet.lines_engine(skill_dir, series, ep):
            if ln.get("emo"):
                EMO[ln["text"]] = ln["emo"]
            if voicesheet.is_free_line(ln):
                FREE.add(ln["text"])
    except Exception as ex:
        print(f"WARNING emotions: {ex}", flush=True)


def patch_voices(R, opts):
    main_voice = str(opts.get("voice") or "")          # เสียงพระเอก/ผู้บรรยาย
    voice_map = {k: v for k, v in (opts.get("voice_map") or {}).items() if str(v).startswith(("edge:", "eleven:"))}  # {cast_id: "edge:..."|"eleven:<id>"}
    if main_voice.startswith("gemini:"):
        main_voice = ""   # เสียงเสียเงินตัดออกแล้ว
    rate_add = int(opts.get("rate_add") or 0)
    orig_voice = R.Cast.voice

    def voice(self, cid):
        v, pitch, rate = orig_voice(self, cid)
        c = (self.by.get(cid) or {}) if hasattr(self, "by") else {}
        from app.voicesheet import engine_key
        chosen = voice_map.get(engine_key(cid, getattr(self, "by", None))) or voice_map.get(cid) or voice_map.get(c.get("voice") or "")
        if not chosen and cid in ("hero", "narration") and main_voice:
            chosen = main_voice
        if chosen and chosen.startswith("edge:"):
            v = chosen[5:]
            if "|" in v:
                v, pitch = v.split("|", 1)
        elif chosen and chosen.startswith("eleven:"):
            v, pitch = chosen, "+0Hz"
        return v, pitch, _rate(rate, rate_add)

    R.Cast.voice = voice
    FREE_VOICE["_orig"] = orig_voice

    orig_synth = R._synth_all
    async def synth(items, outdir):
        # ไฟล์ที่มีแล้ว (เสียงที่ผู้ใช้อัป/แคช) ไม่ต้องสร้าง · Edge พัง = เฉพาะประโยคนั้นเงียบ · ElevenLabs พัง = หยุดงาน (กันคลิปเงียบทั้งที่จ่ายเงิน)
        items = [it for it in items if not ((Path(outdir) / f"{it['key']}.mp3").exists()
                                            and (Path(outdir) / f"{it['key']}.mp3").stat().st_size > 800)]
        free_moved = 0
        for it in items:
            if str(it["voice"]).startswith("eleven:") and it["tts"] in FREE:
                it["voice"], it["pitch"] = FREE_VOICE.get(it["tts"]) or ("th-TH-PremwadeeNeural", "+0Hz")
                free_moved += 1
        if free_moved:
            print(f"voice: {free_moved} on-screen/system lines use free voice", flush=True)
        el = [it for it in items if str(it["voice"]).startswith("eleven:")]
        rest = [it for it in items if not str(it["voice"]).startswith("eleven:")]
        if el:
            from app import eleven
            model = opts.get("eleven_model") or eleven.DEFAULT_MODEL
            spent = 0
            for it in el:
                try:
                    spent += eleven.tts(eleven.with_tag(it["tts"], EMO.get(it["tts"], ""), model), it["voice"][7:], model,
                                        Path(outdir) / f"{it['key']}.mp3")
                except Exception as ex:
                    raise PaidVoiceError(str(ex))
            print(f"voice: ElevenLabs {len(el)} lines · {spent} chars billed ({model})", flush=True)
        if rest:
            try:
                await orig_synth(rest, outdir)
            except Exception as ex:
                print(f"WARNING AI voice failed for {len(rest)} lines (they stay silent): {str(ex)[:150]}", flush=True)
    R._synth_all = synth


def patch_subs(R, opts):
    """ซับเป็นงานของระบบ: th = ซับไทยของเอนจินตามเดิม · en/none = ปิดซับไทยของเอนจิน
    และเก็บไทม์ไลน์เสียงจริง (t0, dur ของทุกประโยค) ไว้ให้ระบบใส่ซับอังกฤษ/ทำ .srt"""
    if (opts.get("sub_mode") or "th") in ("en", "none") and hasattr(R, "T"):
        R.T.subtitle = lambda *a, **k: None
    captured = []
    orig = R.voice_track

    def voice_track(segs, *a, **k):
        captured.append(segs)
        return orig(segs, *a, **k)
    R.voice_track = voice_track
    return captured


def patch_own_voice(R, opts):
    """เสียงพากย์ของผู้ใช้: {"*": ไฟล์ทั้งตอน} หรือ {speaker_key: ไฟล์ของตัวละคร}
    ตัดเป็นท่อนตามประโยคของเจ้าของไฟล์ แล้วให้เอนจินใช้แทน TTS (ตัวละครที่ไม่มีไฟล์ = เสียง AI ตามเดิม)"""
    vf = opts.get("voice_file")
    if not vf:
        return
    if not isinstance(vf, dict):
        vf = {"*": vf}
    import hashlib
    from app import voiceover
    from app.voicesheet import engine_key
    inner = R.voice_track

    def voice_track(segs, cast, work, ff, mute, log):
        own = Path(work).parent / (".own_voice_" + hashlib.md5(json.dumps(vf, sort_keys=True).encode()).hexdigest()[:10])
        keyed = []
        for s in segs:
            v, pitch, rate = cast.voice(s["who"])
            tts = R.clean_tts(s["text"])
            keyed.append((s, hashlib.md5(f"{v}|{pitch}|{rate}|{tts}".encode()).hexdigest()[:16]))
        groups = {"*": keyed} if "*" in vf else {}
        if not groups:
            for s, k in keyed:
                groups.setdefault(engine_key(s["who"], getattr(cast, "by", None)), []).append((s, k))
        for spk, items in groups.items():
            f = vf.get(spk)
            if not f:
                log(f"voice: no own file for {spk} -> AI voice ({len(items)} lines)")
                continue
            log(f"voice: own recording {spk}, splitting into {len(items)} lines")
            cuts = voiceover.split(f, [s["text"] for s, _ in items], [own / f"{k}.mp3" for _, k in items])
            log(f"own voice cuts {spk}: " + ", ".join(f"{a:.1f}" for a, _ in cuts))
        return inner(segs, cast, own, ff, False, log)
    R.voice_track = voice_track


def dump_timeline(captured, out):
    if not captured:
        return
    rows = [{"t0": round(float(x.get("t0", 0)), 3), "dur": round(float(x.get("dur", 0)), 3), "text": x.get("text", ""),
             "sub": bool(x.get("sub")), "shot": x.get("shot")} for x in captured[-1] if "t0" in x]
    Path(out).with_suffix(".timeline.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


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
    load_emotions(a.skill_dir, a.episode)
    patch_voices(R, opts)
    patch_free_lines(R)
    patch_own_voice(R, opts)
    captured = patch_subs(R, opts)
    sys.argv = ["render_ep.py", a.episode, "--out", a.out] + (["--mute"] if a.mute or opts.get("mute") else [])
    try:
        R.main()
    except PaidVoiceError as ex:
        print(f"ERROR ElevenLabs: {ex}", flush=True)
        sys.exit(3)
    dump_timeline(captured, a.out)


if __name__ == "__main__":
    main()
