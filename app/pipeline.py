"""ขั้นตอนทำ 1 ตอน: บท → (ตรวจ) → เสียง → ประกอบวิดีโอ → ซับ → อัปเดต bible"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import core, llm, video


class Stopped(Exception):
    pass


STAGE_TH = {"script": "เขียนบท", "review": "รอตรวจบท", "tts": "พากย์เสียง", "render": "ตัดต่อ", "done": "เสร็จ"}


SCRIPT_SCHEMA = """{
  "title": "ชื่อตอน",
  "summary": "สรุปเหตุการณ์ของตอนนี้ 2-3 ประโยค",
  "scenes": [
    {
      "narration": "บทพากย์ของฉากนี้ (อ่านออกเสียงได้ทันที ห้ามมีคำกำกับท่าทาง/วงเล็บ)",
      "subtitle": "ข้อความซับ (เว้นว่างได้ = ใช้บทพากย์)",
      "visual": "คำอธิบายภาพของฉาก",
      "clip": "ชื่อไฟล์ภาพ/คลิปจากรายการที่ให้ ที่เข้ากับฉากที่สุด (เว้นว่างได้)"
    }
  ]
}"""


# ---------------- บท ----------------
def _script_messages(proj, skill_text, ep, s, prev_summary, inputs):
    total = int(proj.get("episodes_total") or 1)
    system = (
        "คุณคือนักเขียนบทหนังสั้นแอนิเมชันมืออาชีพ ทำตามสกิล/สไตล์ด้านล่างอย่างเคร่งครัด\n\n"
        f"=== สกิล ===\n{skill_text or '(ไม่มีสกิล ใช้วิจารณญาณของคุณ)'}\n=== จบสกิล ===\n\n"
        f"กฎ: เขียนเป็นภาษา{s['language']} ตอบเป็น JSON เท่านั้น ไม่มีข้อความอื่น ตามรูปแบบ:\n{SCRIPT_SCHEMA}"
    )
    parts = [f"เรื่อง: {proj['name']}"]
    if proj.get("topic"):
        parts.append(f"แนวคิด/หัวข้อ: {proj['topic']}")
    if proj.get("notes"):
        parts.append(f"หมายเหตุจากผู้ใช้: {proj['notes']}")
    if ep <= total:
        pos = f"ตอนที่ {ep} จากทั้งหมด {total} ตอน"
        if ep == total:
            pos += " (ตอนจบ ให้ปิดเรื่องอย่างสมบูรณ์)"
        elif ep == 1:
            pos += " (ตอนแรก ปูตัวละครและโลก จบด้วยปมให้อยากดูต่อ)"
    else:
        pos = f"ตอนที่ {ep} (ภาคต่อ เกินแผนเดิม {total} ตอน ให้เปิดเรื่องใหม่ต่อจากเดิมอย่างเป็นธรรมชาติ)"
    parts.append(pos)
    parts.append(f"จำนวนฉากประมาณ {s['scenes_per_episode']} ฉาก ความยาวรวมประมาณ {s['target_seconds']} วินาที "
                 f"(พูดไทยประมาณ 5-6 พยางค์ต่อวินาที)")
    bible = proj.get("bible") or ""
    if bible.strip():
        parts.append(f"ข้อมูลตัวละครและโลกของเรื่อง (ต้องสอดคล้อง):\n{bible}")
    if prev_summary:
        parts.append(f"สรุปตอนก่อนหน้า:\n{prev_summary}")
    if inputs:
        parts.append("ไฟล์ภาพ/คลิปที่มี (ชื่อไฟล์บอกเนื้อหา เลือกใส่ช่อง clip):\n" + "\n".join(inputs[:200]))
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]


def _validate_script(data):
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list) or not data["scenes"]:
        raise llm.LLMError("บทที่ได้ไม่มีฉาก")
    scenes = []
    for sc in data["scenes"]:
        if isinstance(sc, str):
            sc = {"narration": sc}
        nar = str(sc.get("narration") or "").strip()
        if not nar:
            continue
        scenes.append({
            "narration": nar,
            "subtitle": str(sc.get("subtitle") or "").strip(),
            "visual": str(sc.get("visual") or "").strip(),
            "clip": str(sc.get("clip") or "").strip(),
        })
    if not scenes:
        raise llm.LLMError("บทที่ได้ไม่มีบทพากย์")
    data["scenes"] = scenes
    data["title"] = str(data.get("title") or "").strip()
    data["summary"] = str(data.get("summary") or "").strip()
    return data


def write_script(ctx, proj, ep, s):
    skill = core.get_skill(proj.get("skill")) if proj.get("skill") else None
    if proj.get("skill") and not skill:
        ctx.log(f"⚠️ ไม่พบสกิล '{proj['skill']}' → เขียนบทแบบไม่มีสกิล")
    prev = core.read_json(core.ep_dir(proj["name"], ep - 1) / "script.json", {}) if ep > 1 else {}
    msgs = _script_messages(proj, skill["content"] if skill else "", ep, s,
                            (prev or {}).get("summary", ""), proj.get("inputs") or [])
    ctx.log(f"✍️ เขียนบทด้วย {s['draft_model']}")
    text, cost = llm.chat(s["draft_model"], msgs, json_mode=True)
    ctx.cost(cost)
    data = _validate_script(llm.parse_json(text))
    if s.get("polish_enabled") and s.get("polish_model"):
        ctx.check()
        ctx.log(f"✨ ขัดเกลาบทด้วย {s['polish_model']}")
        msgs2 = [msgs[0], {"role": "user", "content":
                 "ปรับปรุงบทร่างนี้ให้สนุก กระชับ เป็นธรรมชาติ และตรงสกิลมากขึ้น คงรูปแบบ JSON เดิม:\n"
                 + json.dumps(data, ensure_ascii=False)}]
        try:
            text2, cost2 = llm.chat(s["polish_model"], msgs2, json_mode=True)
            ctx.cost(cost2)
            data = _validate_script(llm.parse_json(text2))
        except llm.LLMError as e:
            ctx.log(f"⚠️ ขัดเกลาไม่สำเร็จ ใช้บทร่างแทน: {e}")
    return data


def update_bible(ctx, proj, script, s):
    d = core.project_dir(proj["name"])
    old = (d / "bible.md").read_text(encoding="utf-8") if (d / "bible.md").exists() else ""
    msgs = [
        {"role": "system", "content": "คุณดูแล series bible ของซีรีส์แอนิเมชัน ตอบเป็น markdown เท่านั้น"},
        {"role": "user", "content":
            f"bible เดิม:\n{old or '(ว่าง)'}\n\nตอนล่าสุด:\n{json.dumps(script, ensure_ascii=False)}\n\n"
            "อัปเดต bible ให้มี: ตัวละคร (ชื่อ ลักษณะ นิสัย), สถานที่, เหตุการณ์สำคัญที่ผ่านมา, ปมที่ยังค้าง "
            "กระชับไม่เกิน 400 คำ"},
    ]
    text, cost = llm.chat(s["helper_model"], msgs, temperature=0.3, max_tokens=2000)
    ctx.cost(cost)
    if text.strip():
        (d / "bible.md").write_text(text.strip(), encoding="utf-8")


# ---------------- เสียง ----------------
def make_tts(ctx, text, out, engine, voice, s):
    if engine == "edge":
        cmd = [sys.executable, "-m", "edge_tts", "--voice", voice or s["edge_voice"],
               f"--rate={s.get('edge_rate', '+0%')}", "--text", text, "--write-media", str(out)]
        ctx.run(cmd, "edge-tts")
    else:
        llm.tts(s["openrouter_tts_model"], text, voice or s["openrouter_voice"], out)


# ---------------- หลัก ----------------
def _pick_media(proj_name, scenes, ep):
    inp = core.project_dir(proj_name) / "input"
    files = core.list_inputs(proj_name)
    picks = []
    if not files:
        return [("none", None)] * len(scenes)
    n = len(scenes)
    for i, sc in enumerate(scenes):
        name = sc.get("clip") or ""
        if name not in files:
            name = files[((ep - 1) * n + i) % len(files)]
        p = inp / name
        kind = "video" if p.suffix.lower() in core.VIDEO_EXT else "image"
        picks.append((kind, p))
    return picks


def run_episode(ctx, proj_name, ep):
    s = core.load_settings()
    proj = core.get_project(proj_name)
    if not proj:
        raise ValueError(f"ไม่พบโปรเจกต์ {proj_name}")
    edir = core.ep_dir(proj_name, ep)
    edir.mkdir(parents=True, exist_ok=True)
    state_f = edir / "state.json"
    state = core.read_json(state_f, {}) or {}

    def set_stage(stage, **kw):
        state.update(stage=stage, updated=time.time(), **kw)
        core.write_json(state_f, state)
        ctx.stage(f"ตอน {ep}: {STAGE_TH.get(stage, stage)}")

    ctx.episode = ep
    aspect = proj.get("aspect") or s["aspect"]
    engine = proj.get("tts_engine") or s["tts_engine"]
    voice = proj.get("voice") or ""
    w, h = video.resolution(aspect)

    # 1) บท
    script_f = edir / "script.json"
    script = core.read_json(script_f)
    if not script:
        set_stage("script")
        script = write_script(ctx, proj, ep, s)
        core.write_json(script_f, script)
        state["approved"] = False
        ctx.log(f"📝 บทเสร็จ: {script.get('title')} ({len(script['scenes'])} ฉาก)")
    ctx.check()

    # 2) ตรวจบท
    if s.get("review_script") and not state.get("approved"):
        set_stage("review")
        ctx.wait_approval(proj_name, ep)
        script = core.read_json(script_f)  # อาจถูกแก้ในเว็บ
        script = _validate_script(script)
        core.write_json(script_f, script)
    state["approved"] = True

    # 3) เสียงพากย์
    set_stage("tts")
    adir = edir / "audio"
    adir.mkdir(exist_ok=True)
    sig = f"{engine}|{voice}"
    if state.get("tts_sig") and state["tts_sig"] != sig:
        shutil.rmtree(adir, ignore_errors=True)
        adir.mkdir()
    state["tts_sig"] = sig
    durations = []
    for i, sc in enumerate(script["scenes"], 1):
        ctx.check()
        a = adir / f"s{i:02d}.mp3"
        if not a.exists() or a.stat().st_size < 500:
            ctx.log(f"🎙️ พากย์ฉาก {i}/{len(script['scenes'])}")
            tmp = a.with_suffix(".part.mp3")
            make_tts(ctx, sc["narration"], tmp, engine, voice, s)
            tmp.replace(a)
        durations.append(video.probe_duration(a))
        ctx.progress(10 + 40 * i / len(script["scenes"]))

    # 4) ประกอบวิดีโอ (ทำใน /tmp แล้วค่อยคัดลอกไป Drive)
    set_stage("render")
    work = core.WORK_DIR / core.safe_name(proj_name) / f"ep{ep:02d}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    picks = _pick_media(proj_name, script["scenes"], ep)
    if picks[0][0] == "none":
        ctx.log("⚠️ ไม่มีภาพ/คลิปใน input/ → ใช้พื้นสีเรียบ")
    gap = float(s["scene_gap"])
    usage, segs, subs, t = {}, [], [], 0.0
    for i, (sc, dur, (kind, src)) in enumerate(zip(script["scenes"], durations, picks), 1):
        ctx.check()
        seg_dur = dur + gap
        offset = 0.0
        if kind == "video":
            clip_len = video.probe_duration(src)
            used = usage.get(src, 0)
            if clip_len > seg_dur:
                offset = (used * seg_dur) % max(0.01, clip_len - seg_dur)
            usage[src] = used + 1
        out = work / f"seg{i:02d}.mp4"
        ctx.log(f"🎬 ประกอบฉาก {i}/{len(picks)} ({src.name if src else 'พื้นสี'})")
        ctx.run(video.segment_cmd(kind, src, adir / f"s{i:02d}.mp3", out, seg_dur, w, h, s,
                                  offset=offset, zoom_in=(i % 2 == 1)), f"ฉาก {i}")
        segs.append(out)
        subs.append((t, dur, sc.get("subtitle") or sc["narration"]))
        t += seg_dur
        ctx.progress(50 + 35 * i / len(picks))

    (work / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in segs), encoding="utf-8")
    ctx.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", "list.txt", "-c", "copy", "joined.mp4"], "รวมฉาก", cwd=work)

    ass, srt = video.build_subs(subs, w, h, s)
    (work / "subs.ass").write_text(ass, encoding="utf-8")
    (edir / "subs.srt").write_text(srt, encoding="utf-8")

    # 5) ซับ + เพลงประกอบ (encode ครั้งสุดท้าย)
    ctx.check()
    music_dir = core.project_dir(proj_name) / "music"
    music = sorted(p for p in music_dir.glob("*") if p.suffix.lower() in core.AUDIO_EXT) if music_dir.exists() else []
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", "joined.mp4"]
    vf = "null"
    if s.get("subtitles", True):
        if core.FONTS_DIR.exists():
            shutil.copytree(core.FONTS_DIR, work / "fonts", dirs_exist_ok=True)
            vf = "ass=subs.ass:fontsdir=fonts"
        else:
            vf = "ass=subs.ass"
    if music:
        bgm = music[(ep - 1) % len(music)]
        cmd += ["-stream_loop", "-1", "-i", str(bgm)]
        fc = (f"[0:v]{vf}[v];[1:a]volume={float(s['bgm_volume'])}[b];"
              f"[0:a][b]amix=inputs=2:duration=first:dropout_transition=0,volume=2[a]")
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]"]
        ctx.log(f"🎵 ใส่เพลง {bgm.name}")
    else:
        cmd += ["-vf", vf, "-map", "0:v", "-map", "0:a", ]
    cmd += ["-c:v", "libx264", "-preset", s["preset"], "-crf", str(s["crf"]),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "final.mp4"]
    ctx.log("🔤 ใส่ซับ + export")
    ctx.run(cmd, "export", cwd=work)

    tmp_final = edir / "final.part.mp4"
    shutil.copyfile(work / "final.mp4", tmp_final)
    tmp_final.replace(edir / "final.mp4")
    total = video.probe_duration(edir / "final.mp4")
    ctx.progress(95)

    # 6) อัปเดต bible สำหรับตอนต่อไป
    try:
        ctx.log("📚 อัปเดตข้อมูลตัวละคร (bible)")
        update_bible(ctx, proj, script, s)
    except Exception as e:  # ไม่ให้ทั้งตอนพังเพราะส่วนนี้
        ctx.log(f"⚠️ อัปเดต bible ไม่สำเร็จ: {e}")
    shutil.rmtree(work, ignore_errors=True)
    set_stage("done", duration=round(total, 1))
    ctx.log(f"✅ ตอน {ep} เสร็จ ({total:.1f} วินาที)")
