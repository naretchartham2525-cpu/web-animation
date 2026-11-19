"""ขั้นตอนทำ 1 ตอน: บท → (ตรวจ) → ภาพ → เสียง → ประกอบวิดีโอ → ซับ/ลายน้ำ → อัปเดต bible"""
import json
import re
import shutil
import sys
import time
import zlib

from . import core, llm, video


class Stopped(Exception):
    pass


STAGE_TH = {"script": "เขียนบท", "review": "รอตรวจบท", "images": "สร้างภาพ", "tts": "พากย์เสียง",
            "render": "ตัดต่อ", "done": "เสร็จ"}

SCRIPT_SCHEMA = """{
  "title": "ชื่อตอน",
  "summary": "สรุปเหตุการณ์ของตอนนี้ 2-3 ประโยค",
  "scenes": [
    {
      "narration": "บทพากย์ของฉากนี้ (อ่านออกเสียงได้ทันที ห้ามมีคำกำกับท่าทาง/วงเล็บ)",
      "image_prompt": "English prompt describing this scene's picture: characters (same look every scene), action, place, camera angle",
      "subtitle_en": "ซับภาษาอังกฤษ แปลบทพากย์แบบเป็นธรรมชาติ (ใส่เมื่อขอซับอังกฤษ)",
      "clip": "ชื่อไฟล์ภาพ/คลิปจากรายการที่ให้ (ถ้ามีรายการ)"
    }
  ]
}"""


# ---------------- รวมค่าตั้ง: ตั้งค่าหลัก ← เทมเพลต ← ที่เลือกในแถบพิมพ์ ----------------
def _truthy(v):
    return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "on", "yes")


# ---------------- ปรับแต่งเพิ่มเติม (สั่งเฉพาะครั้ง ไม่เปลี่ยนเทมเพลต) ----------------
TWEAKS = {
    "slow":    {"th": "จังหวะช้าลง นุ่มนวล ไม่รีบ", "img": "", "set": {"scene_gap": 0.8, "kb_speed": 0.00035, "rate_add": -10}},
    "light":   {"th": "เน้นแสงเงา บรรยากาศมีมิติ", "img": "cinematic lighting, soft shadows, volumetric light, depth"},
    "real":    {"th": "รายละเอียดสมจริงขึ้น", "img": "highly detailed, realistic textures, natural colors"},
    "still":   {"th": "", "img": "", "set": {"ken_burns": False}},
    "vivid":   {"th": "สีสันสดใส มีชีวิตชีวา", "img": "vibrant colors, high contrast, lively"},
}


def _rate_add(rate, add):
    try:
        v = int(str(rate or "+0%").replace("%", "")) + add
    except ValueError:
        v = add
    return f"{'+' if v >= 0 else ''}{v}%"


def apply_tweaks(s):
    keys = s.get("_tweaks") or []
    if isinstance(keys, str):
        keys = [k.strip() for k in keys.split(",") if k.strip()]
    th, img = [], []
    for k in keys:
        t = TWEAKS.get(k)
        if not t:
            continue
        if t.get("th"):
            th.append(t["th"])
        if t.get("img"):
            img.append(t["img"])
        for sk, sv in (t.get("set") or {}).items():
            if sk == "rate_add":
                s["edge_rate"] = _rate_add(s.get("edge_rate"), sv)
            else:
                s[sk] = sv
    text = str(s.get("_tweak_text") or "").strip()
    if text:
        th.append(text)
        if text.isascii():          # เขียนเป็นอังกฤษ = ใช้กับภาพด้วย
            img.append(text)
    s["_tweak_th"] = " · ".join(th)
    s["_img_extra"] = ", ".join(img)
    return s


def _apply_voice(s, v):
    """เสียง: 'edge:th-TH-NiwatNeural' | 'gemini:Kore' | ชื่อเสียงเฉยๆ"""
    v = str(v).strip()
    s["_voice_full"] = v
    if v.startswith("edge:"):
        s["tts_engine"], s["_voice"] = "edge", v[5:]
    elif v.startswith("gemini:"):
        s["tts_engine"], s["_voice"] = "openrouter", v[7:]
    elif v:
        s["_voice"] = v
        if v.startswith(("th-", "en-")):
            s["tts_engine"] = "edge"


def effective_settings(proj, skill, ep_opts=None):
    """ลำดับ: ตั้งค่าหลัก ← เทมเพลต (เสียง/สไตล์) ← ตัวเลือกตอนสร้าง ← ตัวเลือกเฉพาะ EP"""
    s = core.load_settings()
    layers = [(skill or {}).get("options") or {}, proj.get("options") or {}, ep_opts or {}]
    for layer in layers:
        for k, v in layer.items():
            if v in (None, "") and k not in ("tweaks", "tweak_text"):
                continue
            if k == "duration":
                s["target_seconds"] = int(float(v))
            elif k == "scenes":
                s["scenes_per_episode"] = int(float(v))
            elif k == "voice":
                _apply_voice(s, v)
            elif k == "tweaks":
                s["_tweaks"] = v          # ชั้นหลังแทนที่ชั้นก่อน (EP ต่อสั่งใหม่ได้)
            elif k == "tweak_text":
                s["_tweak_text"] = v
            elif k in ("voice_on", "watermark"):
                s[k] = _truthy(v)
            else:
                s[k] = v
    # ค่าจาก project แบบเก่า
    if proj.get("aspect"):
        s["aspect"] = proj["aspect"]
    if proj.get("tts_engine"):
        s["tts_engine"] = proj["tts_engine"]
    if proj.get("voice"):
        s["_voice"] = proj["voice"]
    s["aspect"] = "9:16"   # ทำสำหรับ TikTok / Reels เท่านั้น
    apply_tweaks(s)
    if not int(s.get("scenes_per_episode") or 0):
        # 1 EP ไม่ต้องหลายฉาก แค่ครอบคลุมเรื่อง (~8 วิ/ฉาก)
        s["scenes_per_episode"] = max(2, min(12, round(int(s["target_seconds"]) / 8)))
    return s


def script_model(s):
    eng = s.get("script_engine", "claude")
    if eng == "free":
        return s["free_model"]
    if eng == "claude":
        return s.get("claude_model") or "anthropic/claude-haiku-5.5"
    return s["draft_model"]


# ---------------- บท ----------------
def _script_messages(proj, skill_text, ep, s, prev_summary, inputs):
    system = (
        "คุณคือนักเขียนบทหนังสั้นแอนิเมชันมืออาชีพ ทำตามเทมเพลต/สไตล์ด้านล่างอย่างเคร่งครัด\n\n"
        f"=== เทมเพลต ===\n{skill_text or '(ไม่มีเทมเพลต ใช้วิจารณญาณของคุณ)'}\n=== จบเทมเพลต ===\n\n"
        + (f"=== ปรับแต่งเพิ่มเติมครั้งนี้ (เสริมจากเทมเพลต ไม่เปลี่ยนสไตล์หลัก) ===\n{s['_tweak_th']}\n\n" if s.get("_tweak_th") else "")
        + f"กฎ: บทพากย์เป็นภาษา{s['language']} image_prompt เป็นภาษาอังกฤษ "
        + ("ต้องใส่ subtitle_en ทุกฉาก " if s.get("sub_lang") in ("en", "both") else "ไม่ต้องใส่ subtitle_en ")
        + f"ตอบเป็น JSON เท่านั้น ไม่มีข้อความอื่น ตามรูปแบบ:\n{SCRIPT_SCHEMA}"
    )
    parts = []
    if proj.get("topic"):
        parts.append(f"ไอเดีย/คำสั่งจากผู้ใช้: {proj['topic']}")
    else:
        parts.append(f"เรื่อง: {proj['name']}")
    if proj.get("notes"):
        parts.append(f"หมายเหตุจากผู้ใช้: {proj['notes']}")
    if ep == 1:
        parts.append("EP 1 (อาจมีภาคต่อ ตั้งชื่อและหน้าตาตัวละครให้ชัด จบให้คนอยากดู EP ถัดไป)")
    else:
        parts.append(f"EP {ep}: เขียนตอนใหม่ต่อจาก EP ก่อน ใช้ตัวละคร หน้าตา โลก โทน และสไตล์เดิมทั้งหมด "
                     "เดินเรื่องต่อ ห้ามเล่าซ้ำตอนเก่า จบให้คนอยากดู EP ถัดไป")
    parts.append(f"ประมาณ {s['scenes_per_episode']} ฉาก (ไม่ต้องเยอะ แค่ครอบคลุมเรื่อง) ความยาวรวมประมาณ {s['target_seconds']} วินาที "
                 f"(พูดไทยประมาณ 13 ตัวอักษรต่อวินาที)")
    bible = proj.get("bible") or ""
    if bible.strip():
        parts.append(f"ข้อมูลตัวละครและโลกของเรื่อง (ต้องสอดคล้อง):\n{bible}")
    if prev_summary:
        parts.append(f"สรุปตอนก่อนหน้า:\n{prev_summary}")
    if inputs:
        parts.append("ไฟล์ภาพ/คลิปที่มี (ชื่อไฟล์บอกเนื้อหา เลือกใส่ช่อง clip):\n" + "\n".join(inputs[:150]))
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
            "image_prompt": str(sc.get("image_prompt") or sc.get("visual") or "").strip(),
            "subtitle_en": str(sc.get("subtitle_en") or "").strip(),
            "clip": str(sc.get("clip") or "").strip(),
        })
    if not scenes:
        raise llm.LLMError("บทที่ได้ไม่มีบทพากย์")
    data["scenes"] = scenes
    data["title"] = str(data.get("title") or "").strip()
    data["summary"] = str(data.get("summary") or "").strip()
    return data


_EP_HEAD = re.compile(r"^\s*#{1,3}\s*(.+?)\s*$")
_EP_SEP = re.compile(r"^\s*(-{3,}|={3,})\s*$")
_NUM = re.compile(r"^\s*(?:ฉาก(?:ที่)?\s*\d+\s*[:.)\-]?|\d+\s*[.)]|[-*•])\s*")


def _scene_from_line(line):
    """'บทพากย์ | english image prompt' → scene  (ส่วนหลัง | ไม่บังคับ)"""
    line = _NUM.sub("", line).strip().strip('"').strip()
    parts = [p.strip() for p in line.split("|")]
    nar = re.sub(r"\s+", " ", parts[0]).strip()
    img = parts[1] if len(parts) > 1 else ""
    en = parts[2] if len(parts) > 2 else ""
    return {"narration": nar, "subtitle": "", "image_prompt": img, "subtitle_en": en, "clip": ""} if nar else None


def _split_paragraph(text, n_scenes):
    parts = [p for p in re.split(r"(?<=[.!?。…])\s+|\s{2,}|\s(?=\S{25,})", text) if p.strip()]
    if len(parts) < 2:
        if len(text) < 120:
            return [text]
        parts = text.split(" ")
    n = max(1, min(n_scenes, len(parts)))
    size = len(parts) / n
    return [" ".join(parts[round(i * size):round((i + 1) * size)]).strip() for i in range(n)]


def parse_manual_episodes(text, n_scenes=6):
    """บทเขียนเอง (ฟรี 100%) วางได้หลาย EP ทีเดียว:
    - '# ชื่อตอน' (หรือ # EP 2: ...) = เริ่ม EP ใหม่, '---' = คั่น EP
    - ใต้หัวข้อ 1 บรรทัด = 1 ฉาก, ท้ายบรรทัดใส่ '| english image prompt' ได้"""
    text = (text or "").replace("\r", "").strip()
    if not text:
        raise ValueError("ยังไม่ได้ใส่บท")
    eps, cur = [], None
    for raw in text.split("\n"):
        if _EP_SEP.match(raw):
            if cur and cur["lines"]:
                eps.append(cur)
            cur = None
            continue
        m = _EP_HEAD.match(raw)
        if m:
            if cur and cur["lines"]:
                eps.append(cur)
            cur = {"title": m.group(1).strip(), "lines": []}
            continue
        if raw.strip():
            if cur is None:
                cur = {"title": "", "lines": []}
            cur["lines"].append(raw.strip())
    if cur and cur["lines"]:
        eps.append(cur)
    out = []
    for e in eps:
        lines = e["lines"]
        if len(lines) == 1 and "|" not in lines[0]:
            lines = _split_paragraph(lines[0], n_scenes)
        scenes = [sc for sc in (_scene_from_line(l) for l in lines) if sc]
        if not scenes:
            continue
        title = re.sub(r"^EP\s*\d+\s*[:：.\-]?\s*", "", e["title"], flags=re.I).strip()
        out.append({"title": title or scenes[0]["narration"][:40],
                    "summary": " ".join(sc["narration"] for sc in scenes)[:300], "scenes": scenes})
    if not out:
        raise ValueError("ไม่พบบทพากย์ (1 บรรทัด = 1 ฉาก)")
    return out


def manual_script(text, n_scenes):
    return parse_manual_episodes(text, n_scenes)[0]


def story_context(proj_name, upto_ep, max_chars=2500):
    """สรุปเรื่องที่ผ่านมาแบบไม่ใช้ AI (ฟรี): ชื่อทุกตอน + บทเต็มของตอนล่าสุด"""
    titles, last = [], None
    for k in range(1, upto_ep + 1):
        sc = core.read_json(core.ep_dir(proj_name, k) / "script.json")
        if sc:
            titles.append(f"EP {k}: {sc.get('title') or '-'} — {sc.get('summary', '')[:160]}")
            last = (k, sc)
    parts = []
    if titles:
        parts.append("ตอนที่ผ่านมา:\n" + "\n".join(titles[-12:]))
    if last:
        parts.append(f"บทเต็มของ EP {last[0]} (ตอนล่าสุด):\n" + "\n".join(s["narration"] for s in last[1]["scenes"]))
    return "\n\n".join(parts)[-max_chars:]


def chat_prompt(skill, idea, start_ep, count, s, context="", bible=""):
    """คำสั่งสำเร็จรูปให้ผู้ใช้ก๊อปไปถาม Claude ในแชท (ฟรี) แล้ววางบทกลับมา"""
    end = start_ep + count - 1
    line_fmt = (f"บทพากย์ภาษา{s['language']} | คำบรรยายภาพเป็นภาษาอังกฤษ (ใส่ชื่อ/หน้าตาตัวละครแบบเดิมทุกฉาก)"
                + " | ซับภาษาอังกฤษ (แปลบทพากย์แบบเป็นธรรมชาติ สั้น อ่านทันในจอ)")
    eps = f"EP {start_ep}" if count == 1 else f"EP {start_ep} ถึง EP {end} ({count} ตอน)"
    lines = [f"ช่วยเขียนบทพากย์หนังสั้นแอนิเมชัน {eps}" + (" ต่อจากเรื่องเดิม" if start_ep > 1 else "")]
    if skill:
        lines.append(f"\n=== เทมเพลต / สไตล์ (ทำตามนี้เคร่งครัด) ===\n{skill['content'].strip()}\n=== จบเทมเพลต ===")
    if s.get("_tweak_th"):
        lines.append(f"\nปรับแต่งเพิ่มเติม (เสริมจากเทมเพลต ไม่เปลี่ยนสไตล์หลัก): {s['_tweak_th']}")
    if bible.strip():
        lines.append(f"\nตัวละครและโลกของเรื่อง:\n{bible.strip()}")
    if context:
        lines.append(f"\n{context}")
    lines.append(f"\nหัวข้อ/เรื่อง: {idea}" if idea else "\nหัวข้อ/เรื่อง: (ผมจะกำหนดเอง ให้รอรับหัวข้อก่อนเขียน)")
    lines.append(f"""
รูปแบบคำตอบ (สำคัญมาก ระบบจะอ่านอัตโนมัติ):
- แต่ละตอนขึ้นบรรทัดแรกด้วย "# EP <เลขตอน>: <ชื่อตอน>"
- ใต้หัวข้อ 1 บรรทัด = 1 ฉาก ตอนละประมาณ {s['scenes_per_episode']} ฉาก ไม่ต้องเยอะ แค่ครอบคลุมเรื่อง (ยาวรวมราว {s['target_seconds']} วินาที)
- แต่ละบรรทัด: {line_fmt}
- บทพากย์อ่านออกเสียงลื่น ห้ามมีวงเล็บ คำกำกับท่าทาง หรือชื่อคนพูดนำหน้า
- {"แต่ละตอนต้องต่อเนื่องกัน ใช้ตัวละครและสไตล์เดิม จบตอนให้อยากดูต่อ" if count > 1 or start_ep > 1 else "จบตอนให้อยากดูต่อ"}
- ตอบเฉพาะบท ไม่ต้องมีคำอธิบายอื่น""")
    return "\n".join(lines).strip()


def write_script(ctx, proj, ep, s, skill):
    prev = core.read_json(core.ep_dir(proj["name"], ep - 1) / "script.json", {}) if ep > 1 else {}
    inputs = proj.get("inputs") if s.get("visual_source") == "drive" else []
    msgs = _script_messages(proj, skill["content"] if skill else "", ep, s,
                            (prev or {}).get("summary", ""), inputs or [])
    model = script_model(s)
    ctx.log(f"เขียนบทด้วย {model}" + (" (ฟรี)" if s.get("script_engine") == "free" else ""))
    text, cost = llm.chat(model, msgs, json_mode=True, max_tokens=int(s["max_tokens"]))
    ctx.cost(cost)
    data = _validate_script(llm.parse_json(text))
    if s.get("polish_enabled") and s.get("script_engine") == "paid":
        ctx.check()
        ctx.log(f"ขัดเกลาบทด้วย {s['polish_model']}")
        msgs2 = [msgs[0], {"role": "user", "content":
                 "ปรับปรุงบทร่างนี้ให้สนุก กระชับ เป็นธรรมชาติ และตรงเทมเพลตมากขึ้น คงรูปแบบ JSON เดิม:\n"
                 + json.dumps(data, ensure_ascii=False)}]
        try:
            text2, cost2 = llm.chat(s["polish_model"], msgs2, json_mode=True, max_tokens=int(s["max_tokens"]))
            ctx.cost(cost2)
            data = _validate_script(llm.parse_json(text2))
        except llm.LLMError as e:
            ctx.log(f"ขัดเกลาไม่สำเร็จ ใช้บทร่างแทน: {e}")
    return data


def update_bible(ctx, proj, script, s):
    d = core.project_dir(proj["name"])
    old = (d / "bible.md").read_text(encoding="utf-8") if (d / "bible.md").exists() else ""
    brief = {"title": script.get("title"), "summary": script.get("summary"),
             "scenes": [sc["narration"] for sc in script["scenes"]]}
    msgs = [
        {"role": "system", "content": "คุณดูแล series bible ของซีรีส์แอนิเมชัน ตอบเป็น markdown เท่านั้น"},
        {"role": "user", "content":
            f"bible เดิม:\n{old or '(ว่าง)'}\n\nตอนล่าสุด:\n{json.dumps(brief, ensure_ascii=False)}\n\n"
            "อัปเดต bible: ตัวละคร (ชื่อ หน้าตาเป็นภาษาอังกฤษสั้นๆ นิสัย), สถานที่, เหตุการณ์สำคัญ, ปมที่ยังค้าง "
            "กระชับไม่เกิน 300 คำ"},
    ]
    text, cost = llm.chat(script_model(s), msgs, temperature=0.3, max_tokens=1200)
    ctx.cost(cost)
    if text.strip():
        (d / "bible.md").write_text(text.strip(), encoding="utf-8")


def sync_bible(ctx, proj, ep, s):
    """ก่อนทำ EP ใหม่: สรุปตัวละคร/เรื่องจาก EP ที่ยังไม่ได้สรุป (คลิปเดี่ยวไม่เสียเพิ่ม)"""
    d = core.project_dir(proj["name"])
    pj = core.read_json(d / "project.json", {}) or {}
    done_upto = int(pj.get("bible_ep") or 0)
    for k in range(done_upto + 1, ep):
        sc = core.read_json(core.ep_dir(proj["name"], k) / "script.json")
        if not sc:
            continue
        try:
            ctx.log(f"สรุปตัวละคร/เรื่องจาก EP {k} เพื่อให้ EP {ep} ต่อเนื่อง")
            update_bible(ctx, {**proj, "name": proj["name"]}, sc, s)
            pj = core.read_json(d / "project.json", {}) or {}
            pj["bible_ep"] = k
            core.write_json(d / "project.json", pj)
        except Exception as e:
            ctx.log(f"สรุป bible ไม่สำเร็จ (ใช้สรุปตอนก่อนแทน): {e}")
            break


def ensure_english(ctx, script, s):
    """ขอซับอังกฤษแต่บทยังไม่มี → แปลด้วย AI ฟรี 1 ครั้ง/EP (ไม่เสียเครดิต)"""
    missing = [i for i, sc in enumerate(script["scenes"]) if not sc.get("subtitle_en")]
    if not missing:
        return False
    lines = [script["scenes"][i]["narration"] for i in missing]
    msgs = [{"role": "system", "content": "Translate Thai narration lines to natural, short English subtitles. "
                                          'Reply JSON only: {"lines": ["..."]} same count and order.'},
            {"role": "user", "content": json.dumps({"lines": lines}, ensure_ascii=False)}]
    ctx.log(f"แปลซับอังกฤษ {len(lines)} บรรทัด (AI ฟรี)")
    text, cost = llm.chat(s["free_model"], msgs, json_mode=True, temperature=0.2, max_tokens=1500)
    ctx.cost(cost)
    out = llm.parse_json(text).get("lines") or []
    for i, en in zip(missing, out):
        script["scenes"][i]["subtitle_en"] = str(en).strip()
    return True


# ---------------- เสียง ----------------
def make_tts(ctx, text, out, s):
    voice = s.get("_voice") or ""
    if s.get("tts_engine") == "openrouter":
        llm.tts(s["openrouter_tts_model"], text, voice or s["openrouter_voice"], out)
    else:
        if voice and not voice.startswith(("th-", "en-")):
            voice = ""  # ชื่อเสียง Gemini ใช้กับ Edge ไม่ได้
        cmd = [sys.executable, "-m", "edge_tts", "--voice", voice or s["edge_voice"],
               f"--rate={s.get('edge_rate', '+0%')}", "--text", text, "--write-media", str(out)]
        ctx.run(cmd, "edge-tts")


# ---------------- ภาพ ----------------
def _drive_media(proj_name, scenes, ep):
    inp = core.project_dir(proj_name) / "input"
    files = core.list_inputs(proj_name)
    if not files:
        return None
    n, picks = len(scenes), []
    for i, sc in enumerate(scenes):
        name = sc.get("clip") or ""
        if name not in files:
            name = files[((ep - 1) * n + i) % len(files)]
        p = inp / name
        picks.append(("video" if p.suffix.lower() in core.VIDEO_EXT else "image", p))
    return picks


def _ai_images(ctx, proj_name, script, edir, s, w, h, skill):
    idir = edir / "images"
    idir.mkdir(exist_ok=True)
    # สไตล์มาจากสกิล/บท · ระบบเติมเฉพาะ "องค์ประกอบภาพ" ที่เปิดไว้ในเทมเพลต (ไม่มีค่าเริ่มต้นบังคับ)
    st = str((skill or {}).get("options", {}).get("image_style") or "").strip()
    if st.lower() == "none":
        st = ""
    style = ", ".join(x for x in (st, s.get("_img_extra") or "") if x)
    # ขนาดที่ขอจากบริการฟรี (ไม่ต้องใหญ่ เดี๋ยว ffmpeg ขยายให้) → เร็วขึ้น
    scale = min(1.0, 1024 / max(w, h))
    iw, ih = int(w * scale) // 8 * 8, int(h * scale) // 8 * 8
    seed = zlib.crc32(proj_name.encode()) % 100000
    picks, n = [], len(script["scenes"])
    for i, sc in enumerate(script["scenes"], 1):
        ctx.check()
        f = idir / f"s{i:02d}.jpg"
        if not f.exists() or f.stat().st_size < 2000:
            prompt = ", ".join(x for x in (sc.get("image_prompt") or sc["narration"], style) if x)
            ctx.log(f"สร้างภาพฉาก {i}/{n} (ฟรี, ~15 วิ/ภาพ)")
            try:
                tmp = f.with_suffix(".part.jpg")
                llm.free_image(prompt, tmp, iw, ih, seed=seed + i, model=s.get("image_model") or "")
                tmp.replace(f)
            except llm.LLMError as e:
                ctx.log(f"{e} → ใช้พื้นสีแทน")
                picks.append(("none", None))
                continue
        picks.append(("image", f))
        ctx.progress(10 + 25 * i / n)
    return picks


# ---------------- หลัก ----------------
def run_episode(ctx, proj_name, ep):
    proj = core.get_project(proj_name)
    if not proj:
        raise ValueError(f"ไม่พบโปรเจกต์ {proj_name}")
    skill = core.get_skill(proj.get("skill")) if proj.get("skill") else None
    if proj.get("skill") and not skill:
        ctx.log(f"ไม่พบเทมเพลต '{proj['skill']}' → ทำแบบไม่มีเทมเพลต")
    edir = core.ep_dir(proj_name, ep)
    edir.mkdir(parents=True, exist_ok=True)
    state_f = edir / "state.json"
    state = core.read_json(state_f, {}) or {}
    s = effective_settings(proj, skill, state.get("opts"))
    if skill and skill.get("engine"):
        from . import engine_skill        # สกิลมีเอนจินของตัวเอง → ให้สกิลเรนเดอร์ ระบบคุมเสียง/ลายน้ำ
        ctx.episode = ep
        return engine_skill.run_episode(ctx, proj, ep, s, skill)

    def set_stage(stage, **kw):
        state.update(stage=stage, updated=time.time(), **kw)
        core.write_json(state_f, state)
        ctx.stage(f"EP {ep}: {STAGE_TH.get(stage, stage)}")

    ctx.episode = ep
    w, h = video.resolution(s["aspect"], s.get("quality", "hd"))

    # 1) บท
    script_f = edir / "script.json"
    script = core.read_json(script_f)
    if not script and ep > 1 and s.get("update_bible", True):
        sync_bible(ctx, proj, ep, s)
        proj = core.get_project(proj_name)
    if not script:
        set_stage("script")
        if proj.get("script_mode") == "manual" and ep == 1:
            script = manual_script(proj.get("manual_text"), s["scenes_per_episode"])
            ctx.log("ใช้บทที่เขียนเอง (ฟรี)")
        else:
            script = write_script(ctx, proj, ep, s, skill)
        core.write_json(script_f, script)
        state["approved"] = False
        ctx.log(f"บท: {script.get('title')} ({len(script['scenes'])} ฉาก)")
    ctx.check()

    # 2) ตรวจบท
    if s.get("review_script") and not state.get("approved"):
        set_stage("review")
        ctx.wait_approval(proj_name, ep)
        script = _validate_script(core.read_json(script_f))
        core.write_json(script_f, script)
    state["approved"] = True
    if s.get("sub_lang") in ("en", "both") and s.get("subtitles", True):
        try:
            if ensure_english(ctx, script, s):
                core.write_json(script_f, script)
        except Exception as e:
            ctx.log(f"แปลซับอังกฤษไม่สำเร็จ ใช้ซับไทยแทน: {e}")
            s["sub_lang"] = "th"
    scenes = script["scenes"]

    # 3) ภาพ
    picks = None
    if s.get("visual_source") == "drive":
        picks = _drive_media(proj_name, scenes, ep)
        if not picks:
            ctx.log("ไม่มีไฟล์ในโฟลเดอร์ input/ ของเรื่องนี้ใน Drive → ใช้พื้นสีเรียบ")
    elif s.get("visual_source", "ai") == "ai":
        set_stage("images")
        picks = _ai_images(ctx, proj_name, script, edir, s, w, h, skill)
    if not picks:
        picks = [("none", None)] * len(scenes)

    # 4) เสียงพากย์ (หรือเสียงเงียบตามความยาวที่ควรอ่าน)
    set_stage("tts")
    adir = edir / "audio"
    adir.mkdir(exist_ok=True)
    sig = f"{s.get('voice_on')}|{s['tts_engine']}|{s.get('_voice', '')}"
    if state.get("tts_sig") and state["tts_sig"] != sig:
        shutil.rmtree(adir, ignore_errors=True)
        adir.mkdir()
    state["tts_sig"] = sig
    durations = []
    for i, sc in enumerate(scenes, 1):
        ctx.check()
        a = adir / f"s{i:02d}.mp3"
        if not a.exists() or a.stat().st_size < 300:
            tmp = a.with_suffix(".part.mp3")
            if s.get("voice_on", True):
                ctx.log(f"พากย์ฉาก {i}/{len(scenes)}")
                make_tts(ctx, sc["narration"], tmp, s)
            else:
                ctx.run(video.silent_audio_cmd(tmp, video.estimate_speech_seconds(sc["narration"])), "เสียงเงียบ")
            tmp.replace(a)
        durations.append(video.probe_duration(a))
        ctx.progress(35 + 15 * i / len(scenes))

    # 5) ประกอบวิดีโอ (ทำใน /tmp แล้วค่อยคัดลอกไป Drive)
    set_stage("render")
    work = core.WORK_DIR / core.safe_name(proj_name) / f"ep{ep:02d}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    gap = float(s["scene_gap"])
    usage, segs, subs, t = {}, [], [], 0.0
    for i, (sc, dur, (kind, src)) in enumerate(zip(scenes, durations, picks), 1):
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
        ctx.log(f"ประกอบฉาก {i}/{len(picks)} ({src.name if src else 'พื้นสี'})")
        ctx.run(video.segment_cmd(kind, src, adir / f"s{i:02d}.mp3", out, seg_dur, w, h, s,
                                  offset=offset, zoom_in=(i % 2 == 1)), f"ฉาก {i}")
        segs.append(out)
        subs.append((t, dur, sc.get("subtitle") or sc["narration"], sc.get("subtitle_en") or ""))
        t += seg_dur
        ctx.progress(50 + 35 * i / len(picks))

    (work / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in segs), encoding="utf-8")
    ctx.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", "list.txt", "-c", "copy", "joined.mp4"], "รวมฉาก", cwd=work)

    wm = (s.get("watermark_text") or "AutoClip") if s.get("watermark") else ""
    mode = s.get("sub_lang", "th") if s.get("subtitles", True) else "none"
    ass, srt_th, srt_en = video.build_subs(subs, w, h, s, watermark=wm, total=t, mode=mode)
    (work / "subs.ass").write_text(ass, encoding="utf-8")
    (edir / "subs.srt").write_text(srt_th, encoding="utf-8")
    if srt_en.strip():
        (edir / "subs_en.srt").write_text(srt_en, encoding="utf-8")

    # 6) ซับ + ลายน้ำ + เพลงประกอบ (encode ครั้งสุดท้าย)
    ctx.check()
    music_dir = core.project_dir(proj_name) / "music"
    music = sorted(p for p in music_dir.glob("*") if p.suffix.lower() in core.AUDIO_EXT) if music_dir.exists() else []
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", "joined.mp4"]
    vf = "null"
    if (mode != "none" and subs) or wm:
        if core.FONTS_DIR.exists() and any(core.FONTS_DIR.iterdir()):
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
        ctx.log(f"ใส่เพลง {bgm.name}")
    else:
        cmd += ["-vf", vf, "-map", "0:v", "-map", "0:a"]
    cmd += ["-c:v", "libx264", "-preset", s["preset"], "-crf", str(s["crf"]),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "final.mp4"]
    ctx.log(f"export {video.QUALITY_TH.get(s.get('quality'), '')} {w}x{h}" + (" + ลายน้ำ" if wm else ""))
    ctx.run(cmd, "export", cwd=work)

    tmp_final = edir / "final.part.mp4"
    shutil.copyfile(work / "final.mp4", tmp_final)
    tmp_final.replace(edir / "final.mp4")
    first_img = next((p for k, p in picks if k == "image" and p), None)
    if first_img:
        shutil.copyfile(first_img, edir / "thumb.jpg")
    total = video.probe_duration(edir / "final.mp4")
    ctx.progress(95)

    shutil.rmtree(work, ignore_errors=True)
    set_stage("done", duration=round(total, 1))
    ctx.log(f"EP {ep} เสร็จ ({total:.1f} วินาที)")
