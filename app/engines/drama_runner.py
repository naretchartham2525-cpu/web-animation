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
MOSS = {}   # cast_id → {"name", "arch", "edge": (เสียง Edge สำรอง, pitch)}
KOKORO_FB = {}   # เสียง Kokoro → (เสียง Edge สำรอง, pitch)


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


def load_emotions(skill_dir, episode, narrator_paid=False):
    try:
        from app import voicesheet
        ep = json.loads(Path(episode).read_text(encoding="utf-8"))
        series = json.loads((Path(episode).parent / "series.json").read_text(encoding="utf-8"))
        for ln in voicesheet.lines_engine(skill_dir, series, ep):
            if ln.get("emo"):
                EMO[ln["text"]] = ln["emo"]
            if voicesheet.is_free_line(ln, narrator_paid):
                FREE.add(ln["text"])
    except Exception as ex:
        print(f"WARNING emotions: {ex}", flush=True)


def patch_voices(R, opts):
    main_voice = str(opts.get("voice") or "")          # เสียงพระเอก/ผู้บรรยาย
    voice_map = {k: v for k, v in (opts.get("voice_map") or {}).items() if str(v).startswith(("edge:", "eleven:", "moss:", "kokoro:"))}  # {cast_id: "edge:..."|"eleven:<id>"|"moss:auto"}
    if main_voice.startswith("gemini:"):
        main_voice = ""   # เสียงเสียเงินตัดออกแล้ว
    rate_add = int(opts.get("rate_add") or 0)
    profile = opts.get("voice_profile") or {}   # โทนเสียงประจำเทมเพลต (ใช้เมื่อผู้ใช้ไม่ได้เลือกเสียงเอง)
    all_moss = main_voice.startswith("moss:")
    en = opts.get("dub_lang") == "en"
    if en and "th-TH" in main_voice:
        main_voice = ""          # เสียงไทยอ่านอังกฤษไม่ได้ → ใช้เสียงอังกฤษตามประเภท
    voice_map = {k: v for k, v in voice_map.items() if not (en and "th-TH" in v)}   # เลือก MOSS เป็นเสียงหลัก = ทุกตัวละครใช้ MOSS
    orig_voice = R.Cast.voice

    def voice(self, cid):
        v, pitch, rate = orig_voice(self, cid)
        c = (self.by.get(cid) or {}) if hasattr(self, "by") else {}
        arch = {"narration": "narrator", "hero": "hero", "system": "system"}.get(cid) or str(c.get("voice") or "")
        mine = "" if en else str((profile.get(arch) or {}).get("edge") or "")
        if en and "th-TH" in str(v):     # พากย์อังกฤษ: เสียงไทยของเอนจิน → เสียงอังกฤษประเภทเดียวกัน (ตัวละครคนละเสียง)
            from app import lang
            pool = lang.EDGE_EN.get(arch) or lang.EDGE_EN["man"]
            import hashlib
            n = int(hashlib.md5(str(cid).encode()).hexdigest(), 16) if arch not in ("narrator", "hero", "system") else 0
            v, _, p = pool[n % len(pool)][5:].partition("|")
            pitch = p or "+0Hz"
        if mine.startswith("edge:"):
            v, _, p = mine[5:].partition("|")
            pitch = p or pitch
        from app.voicesheet import engine_key
        chosen = voice_map.get(engine_key(cid, getattr(self, "by", None))) or voice_map.get(cid) or voice_map.get(c.get("voice") or "")
        if not chosen and cid in ("hero", "narration") and main_voice:
            chosen = main_voice
        if str(chosen).startswith("kokoro:") and cid != "system":     # Kokoro ฟรี (ไทย = MOSS พูดด้วยโทนนี้ · ไม่ได้ = Edge เดิม)
            KOKORO_FB[chosen] = (v, pitch)
            return chosen, pitch, _rate(rate, rate_add)
        if (all_moss or str(chosen).startswith("moss:")) and cid != "system":   # เสียงระบบ = Edge เสมอ
            MOSS[cid] = {"name": "ผู้บรรยาย" if cid == "narration" else self.name(cid) if cid != "hero" else "hero",
                         "arch": arch or "man", "edge": (v, pitch)}
            return "moss:" + cid, pitch, _rate(rate, rate_add)
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
        mo = [it for it in items if str(it["voice"]).startswith("moss:")]
        if mo:
            from app import moss
            done = 0
            for it in mo:
                m = MOSS.get(it["voice"][5:]) or {"name": "", "arch": "man", "edge": ("th-TH-NiwatNeural", "+0Hz")}
                try:
                    moss.speak(opts.get("project") or "", m["name"], m["arch"], it["tts"], Path(outdir) / f"{it['key']}.mp3",
                               lambda t: print(t, flush=True), template=opts.get("template") or "",
                               lang="English" if opts.get("dub_lang") == "en" else "Thai")
                    done += 1
                except Exception as ex:   # ไม่มี GPU/โหลดไม่ได้ → ประโยคที่เหลือใช้ Edge ฟรี งานไม่พัง
                    if not MOSS.get("_warned"):
                        print(f"WARNING {str(ex)[:150]} → ใช้เสียง Edge ฟรีแทน", flush=True)
                        MOSS["_warned"] = True
                    it["voice"], it["pitch"] = m["edge"]
            if done:
                print(f"voice: MOSS {done} lines", flush=True)
        ko = [it for it in items if str(it["voice"]).startswith("kokoro:")]
        if ko:
            from app import kokoro_tts, moss
            en = opts.get("dub_lang") == "en"
            log = lambda t: print(t, flush=True)
            n = 0
            for it in ko:
                out = Path(outdir) / f"{it['key']}.mp3"
                try:
                    if en:
                        kokoro_tts.say(it["voice"], it["tts"], out, log)
                    else:
                        moss.check()
                        moss.speak_ref(kokoro_tts.sample(it["voice"], log), it["tts"], out, log)
                    n += 1
                except Exception as ex:  # noqa: BLE001
                    if not KOKORO_FB.get("_warned"):
                        print(f"WARNING {str(ex)[:150]} → ใช้เสียง Edge แทน", flush=True)
                        KOKORO_FB["_warned"] = True
                    it["voice"], it["pitch"] = KOKORO_FB.get(it["voice"]) or ("th-TH-NiwatNeural", "+0Hz")
            if n:
                print(f"voice: Kokoro {n} lines", flush=True)
        el = [it for it in items if str(it["voice"]).startswith("eleven:")]
        rest = [it for it in items if not str(it["voice"]).startswith(("eleven:", "moss:", "kokoro:"))]
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
            # ทีละประโยค: Edge พังประโยคเดียวไม่ทำให้ทั้งชุดเงียบ · ประโยคที่ยังไม่มีเสียงถูกรายงานชื่อ
            failed = []
            for it in rest:
                out = Path(outdir) / f"{it['key']}.mp3"
                if out.exists() and out.stat().st_size > 800:
                    continue
                try:
                    await orig_synth([it], outdir)
                except Exception as ex:  # noqa: BLE001
                    failed.append(it["tts"][:30])
                    print(f"WARNING voice line failed: {str(ex)[:120]}", flush=True)
            if failed:
                print(f"WARNING {len(failed)} lines still silent (retry พากย์ใหม่): " + " | ".join(failed[:5]), flush=True)
    R._synth_all = synth


def patch_lang(R, opts):
    """พากย์อังกฤษ: ข้อความไทยทุกตัวที่เอนจินวาด (ป้ายของ/หน้าจอแชต/ตอนต่อไป) → อังกฤษ
    (บท JSON แปลมาก่อนแล้ว · ตรงนี้กันป้ายสำเร็จรูปในโค้ดเอนจิน) · ข้อความที่หลุด → จดไว้ให้ระบบแปลเก็บ"""
    if opts.get("dub_lang") != "en":
        return None
    from PIL import ImageDraw, ImageFont
    from app.lang import Translator
    tr = Translator(json.loads(Path(opts["i18n"]).read_text(encoding="utf-8")) if opts.get("i18n") else {})

    def wrap1(cls, name, pos):
        f = getattr(cls, name, None)
        if not f or getattr(f, "_tr", False):
            return

        def g(*a, **k):
            if len(a) > pos:
                a = a[:pos] + (tr(a[pos]),) + a[pos + 1:]
            return f(*a, **k)
        g._tr = True
        setattr(cls, name, g)
    for cls, name, pos in ((ImageDraw.ImageDraw, "text", 2), (ImageDraw.ImageDraw, "textbbox", 2),
                           (ImageDraw.ImageDraw, "textlength", 1), (ImageFont.FreeTypeFont, "getlength", 1),
                           (ImageFont.FreeTypeFont, "getbbox", 1), (R.T.Draw, "text", 2)):
        wrap1(cls, name, pos)
    for name in ("wrap", "width", "measure", "subtitle", "block"):
        wrap1(R.T, name, {"wrap": 0, "width": 0, "measure": 0, "subtitle": 1, "block": 4}[name])
    orig_name = R.Cast.name
    R.Cast.name = lambda self, cid: tr(orig_name(self, cid))
    return tr


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
    ap.add_argument("--still", default="")      # ตรวจหน้าตา: บันทึกภาพนิ่งของช็อต N (ใช้ตอนทดสอบ)
    a = ap.parse_args()
    opts = json.loads(a.opts or "{}")
    R = load_engine(a.skill_dir)
    load_emotions(a.skill_dir, a.episode, bool(opts.get("narrator_paid")))
    patch_voices(R, opts)
    tr = patch_lang(R, opts)
    patch_free_lines(R)
    patch_own_voice(R, opts)
    captured = patch_subs(R, opts)
    sys.argv = ["render_ep.py", a.episode, "--out", a.out] + (["--mute"] if a.mute or opts.get("mute") else []) \
        + (["--still", a.still] if a.still else [])
    try:
        R.main()
    except PaidVoiceError as ex:
        print(f"ERROR ElevenLabs: {ex}", flush=True)
        sys.exit(3)
    finally:
        if tr is not None and tr.miss:     # ข้อความไทยที่ยังหลุด → ระบบแปลเก็บไว้ (EP ถัดไปถูก)
            Path(a.out).with_suffix(".i18n_miss.json").write_text(json.dumps(sorted(tr.miss), ensure_ascii=False), encoding="utf-8")
            print(f"WARNING English: {len(tr.miss)} on-screen texts still Thai", flush=True)
    dump_timeline(captured, a.out)


if __name__ == "__main__":
    main()
