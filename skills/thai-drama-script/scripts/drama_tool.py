import argparse
import json
import sys
from pathlib import Path

TYPES = ("scene", "phone", "card")
UIS = ("chat", "review", "live", "post", "forum", "doc", "system")
DOC_KINDS = ("letter", "slip", "bill", "certificate", "form", "police", "court", "medical", "statement", "notice", "note")
FRAMES = ("wide", "medium", "close", "ots")
POS = ("left", "center", "right")
FX = ("none", "vein", "sweat", "tears", "gloom", "sparkle", "")
LIMITS = {"chat": ("msgs", 4), "review": ("reviews", 2), "live": ("comments", 2), "post": ("comments", 2), "forum": ("answers", 3)}
SHOT_SEC = 3.6
CPS = 12.0
FACE_TH = {"neutral": "เฉย", "happy": "ยิ้ม", "smug": "ยิ้มเยาะ", "angry": "โกรธ", "yell": "ตะโกน", "shock": "ตกใจ", "sad": "เศร้า", "cry": "ร้องไห้",
           "worried": "กังวล", "scared": "กลัว", "tired": "เหนื่อย", "disgust": "รังเกียจ", "confused": "งง", "sly": "เจ้าเล่ห์"}
UI_TH = {"chat": "แชต", "review": "รีวิว", "live": "ไลฟ์", "post": "โพสต์", "forum": "กระทู้ถาม", "doc": "เอกสาร", "system": "ระบบ"}


def load(path):
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        sys.exit(f"ERROR {p.name} is not valid JSON: {ex.msg} at line {ex.lineno}, column {ex.colno}")


def series_of(ep_path):
    p = Path(ep_path).parent / "series.json"
    return load(p) if p.is_file() else None


def spoken(shot):
    out = []
    t = shot.get("type")
    if t == "phone":
        ui, d = shot.get("ui"), shot.get("data") or {}
        if ui == "chat":
            out += [(m.get("from") or ("hero" if m.get("me") else "other"), m.get("text", "")) for m in d.get("msgs") or []]
        elif ui == "post":
            out.append((d.get("author") or "other", d.get("text", "")))
            out += [(c.get("name") or "other", c.get("text", "")) for c in d.get("comments") or []]
        elif ui == "forum":
            out.append(("hero" if d.get("me") else (d.get("author") or "other"), d.get("text", "")))
            out += [(a.get("name") or "other", a.get("text", "")) for a in d.get("answers") or []]
    return out


def speaker(shot):
    t = shot.get("type")
    if t == "scene":
        return shot.get("say") or "narration"
    if t == "phone" and shot.get("ui") == "live":
        return (shot.get("data") or {}).get("host") or "narration"
    if t == "phone" and shot.get("ui") == "system":
        return "system"
    return "narration"


def check(ep, series, sec, cps):
    errs, warns = [], []
    n = ep.get("ep")
    title = str(ep.get("title") or "")
    if not isinstance(n, int):
        errs.append('"ep" must be the episode number')
    if not title.startswith(f"EP{n} "):
        errs.append(f'title must start with "EP{n} " (got: {title[:30]})')
    if len(title) > 70:
        errs.append(f"title is {len(title)} chars, max 70")
    if len(str(ep.get("cover_text") or "")) > 22:
        warns.append("cover_text is longer than 22 chars")
    if not ep.get("hashtags"):
        warns.append("no hashtags")
    finale = ep.get("advice", {}).get("continue") is False or (series and n == series.get("episodes"))
    for k, mx in (("teaser", 60), ("ask", 70)):
        v = str(ep.get(k) or "")
        if len(v) > mx:
            errs.append(f"{k} is {len(v)} chars, max {mx}")
        if not v and not (finale and k == "teaser"):
            warns.append(f"{k} is empty")
    if not ep.get("summary"):
        errs.append("summary is empty (needed for the story so far)")
    cast = {c["id"]: c for c in (series or {}).get("cast") or [] if "id" in c}
    places = {p["id"] for p in (series or {}).get("places") or [] if "id" in p}
    shots = ep.get("shots") or []
    want = round(sec / SHOT_SEC)
    if len(shots) < 6:
        errs.append(f"only {len(shots)} shots")
    elif not want - 3 <= len(shots) <= want + 3:
        warns.append(f"{len(shots)} shots, aim for {want - 3}-{want + 3} for {sec}s")
    seen, total, dia, lines_n = {}, 0, 0, 0
    for i, s in enumerate(shots, 1):
        tag = f"shot {i}"
        t = s.get("type")
        if t not in TYPES:
            errs.append(f"{tag}: type must be scene, phone or card")
            continue
        line = str(s.get("line") or "")
        if '"' in line:
            errs.append(f'{tag}: straight double quote inside the line, use “ ”')
        if line:
            key = line.strip()
            if key in seen:
                errs.append(f"{tag}: same line as shot {seen[key]}")
            seen[key] = i
            total += len(line)
            lines_n += 1
            if len(line) > 90:
                errs.append(f"{tag}: line is {len(line)} chars, split it (max 70)")
            elif len(line) > 70 or len(line) < 12:
                warns.append(f"{tag}: line is {len(line)} chars (20-70 reads best)")
        for who, txt in spoken(s):
            total += len(txt)
            if len(txt) > 60:
                warns.append(f"{tag}: read-aloud text over 60 chars")
        if t == "scene":
            if not line:
                errs.append(f"{tag}: scene line is empty")
            if places and s.get("place") not in places:
                errs.append(f"{tag}: unknown place {s.get('place')!r}")
            if s.get("frame", "medium") not in FRAMES:
                errs.append(f"{tag}: frame must be one of {', '.join(FRAMES)}")
            chars = s.get("chars") or []
            ids = [c.get("id") for c in chars]
            if not chars:
                errs.append(f"{tag}: nobody in the scene")
            if len(chars) > 3:
                errs.append(f"{tag}: {len(chars)} people, max 3")
            pos = [c.get("pos") for c in chars]
            if len(set(pos)) != len(pos):
                errs.append(f"{tag}: two people in the same pos")
            for c in chars:
                if cast and c.get("id") not in cast:
                    errs.append(f"{tag}: unknown cast id {c.get('id')!r}")
                if c.get("pos") not in POS:
                    errs.append(f"{tag}: pos must be left, center or right")
                if c.get("fx", "none") not in FX:
                    warns.append(f"{tag}: unknown fx {c.get('fx')!r}")
            say = s.get("say") or "narration"
            if say != "narration":
                dia += 1
                if say not in ids:
                    errs.append(f"{tag}: speaker {say!r} is not in the scene")
            if s.get("frame") == "ots" and len(chars) != 2:
                warns.append(f"{tag}: ots needs exactly 2 people")
        elif t == "phone":
            ui, d = s.get("ui"), s.get("data") or {}
            if ui not in UIS:
                errs.append(f"{tag}: ui must be one of {', '.join(UIS)}")
                continue
            if ui in LIMITS:
                k, mx = LIMITS[ui]
                if len(d.get(k) or []) > mx:
                    errs.append(f"{tag}: {ui} has {len(d.get(k) or [])} {k}, max {mx}")
            if ui in ("review", "doc", "live", "system") and not line:
                errs.append(f"{tag}: {ui} needs a line")
            if ui == "doc" and d.get("kind") not in DOC_KINDS:
                errs.append(f"{tag}: doc kind must be one of {', '.join(DOC_KINDS)}")
            if ui == "live" or spoken(s):
                dia += 1
        elif t == "card" and not s.get("text"):
            errs.append(f"{tag}: card needs text")
    target = sec * cps
    if total < target * 0.7:
        errs.append(f"too short: {total} spoken chars, target about {int(target)} (at least {int(target * 0.7)})")
    elif total > target * 1.3:
        warns.append(f"long: {total} spoken chars, target about {int(target)}")
    ratio = dia / max(1, len(shots))
    if ratio < 0.25:
        errs.append(f"only {ratio:.0%} dialogue shots, aim for 40% or more")
    elif ratio < 0.4:
        warns.append(f"{ratio:.0%} dialogue shots, aim for 40% or more")
    phones = sum(1 for s in shots if s.get("type") == "phone")
    if shots and not 0.12 <= phones / len(shots) <= 0.4:
        warns.append(f"phone shots are {phones / len(shots):.0%} of the episode, 20-30% works best")
    return errs, warns, total


def who_name(series, sid):
    if sid in ("narration", "hero"):
        return "ผม (บรรยาย)" if sid == "narration" else "ผม"
    if sid == "system":
        return "ระบบ"
    for c in (series or {}).get("cast") or []:
        if c.get("id") == sid:
            return c.get("name") or sid
    return sid


def voice_of(series, sid):
    if sid in ("narration", "hero"):
        sid = "hero"
    for c in (series or {}).get("cast") or []:
        if c.get("id") == sid:
            return c.get("voice") or ""
    return ""


def ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def export(path, ep, series, cps):
    base = Path(path).with_suffix("")
    places = {p["id"]: p.get("name", p["id"]) for p in (series or {}).get("places") or []}
    md = [f"# {ep.get('title', '')}", "", f"**ปก:** {ep.get('cover_text', '')}", f"**แฮชแท็ก:** {' '.join(ep.get('hashtags') or [])}", ""]
    srt, voice, t, k = [], [], 0.0, 0

    def say_line(sid, text):
        nonlocal t, k
        if not text:
            return
        dur = max(1.2, len(text) / cps)
        k += 1
        srt.append(f"{k}\n{ts(t)} --> {ts(t + dur)}\n{text}\n")
        voice.append((sid, text))
        t += dur + 0.25

    for i, s in enumerate(ep.get("shots") or [], 1):
        typ = s.get("type")
        sid = speaker(s)
        if typ == "scene":
            people = ", ".join(f"{who_name(series, c.get('id'))} ({c.get('pos', '')}) {c.get('action', '')} หน้า{FACE_TH.get(c.get('face', ''), c.get('face', ''))}"
                               + (f" [{c['fx']}]" if c.get("fx") not in (None, "", "none") else "") for c in s.get("chars") or [])
            md.append(f"### {i}. ฉาก · {places.get(s.get('place'), s.get('place', ''))} · {s.get('frame', 'medium')}")
            md.append(f"- ในภาพ: {people}")
            if s.get("sfx"):
                md.append(f"- เสียง: {s['sfx']}")
            md.append(f"- **{who_name(series, sid)}:** {s.get('line', '')}")
            say_line(sid, s.get("line", ""))
        elif typ == "phone":
            ui, d = s.get("ui"), s.get("data") or {}
            md.append(f"### {i}. หน้าจอมือถือ · {UI_TH.get(ui, ui)}")
            if s.get("line"):
                md.append(f"- **{who_name(series, sid)}:** {s['line']}")
                say_line(sid, s["line"])
            if ui == "chat":
                md.append(f"- ห้องแชต: {d.get('name', '')}")
                for m in d.get("msgs") or []:
                    w = "hero" if m.get("me") else (m.get("from") or "other")
                    md.append(f"  - {who_name(series, w)}: {m.get('text', '')}")
                    say_line(w, m.get("text", ""))
            elif ui == "review":
                md.append(f"- ร้าน: {d.get('shop', '')} ⭐ {d.get('stars', '')}")
                md += [f"  - {r.get('name', '')} ({r.get('stars', '')}★): {r.get('text', '')}" for r in d.get("reviews") or []]
            elif ui == "live":
                md.append(f"- ไลฟ์: {d.get('name', '')} · ผู้ชม {d.get('viewers', '')}")
                md += [f"  - {c.get('name', '')}: {c.get('text', '')}" for c in d.get("comments") or []]
            elif ui == "post":
                md.append(f"- กลุ่ม: {d.get('group', '')} · โดย {d.get('author', '')} · ❤ {d.get('likes', '')}")
                md.append(f"  - {d.get('text', '')}")
                say_line(d.get("author") or "other", d.get("text", ""))
                for c in d.get("comments") or []:
                    md.append(f"  - {c.get('name', '')}: {c.get('text', '')}")
                    say_line(c.get("name") or "other", c.get("text", ""))
            elif ui == "forum":
                asker = "hero" if d.get("me") else (d.get("author") or "other")
                md.append(f"- บอร์ด: {d.get('board', '')} · {d.get('title', '')}")
                md.append(f"  - {who_name(series, asker)}: {d.get('text', '')}")
                say_line(asker, d.get("text", ""))
                for a in d.get("answers") or []:
                    md.append(f"  - {a.get('name', '')} (▲{a.get('votes', '')}): {a.get('text', '')}")
                    say_line(a.get("name") or "other", a.get("text", ""))
            elif ui == "doc":
                md.append(f"- เอกสาร ({d.get('kind', '')}): {d.get('title', '')} · {d.get('org', '')} {d.get('stamp', '')}")
                md += [f"  - {x}" for x in d.get("lines") or []]
                if d.get("amount"):
                    md.append(f"  - จำนวนเงิน: {d['amount']}")
            elif ui == "system":
                md.append(f"- [ระบบ] {d.get('title', '')}")
                md += [f"  - {x}" for x in d.get("lines") or []]
                if d.get("reward"):
                    md.append(f"  - รางวัล: {d['reward']}")
        elif typ == "card":
            md.append(f"### {i}. การ์ดข้อความ: {s.get('text', '')}")
            if s.get("line"):
                md.append(f"- **ผม (บรรยาย):** {s['line']}")
                say_line("narration", s["line"])
        md.append("")
    md += ["---", f"**ตอนต่อไป (ข้อความท้ายคลิป):** {ep.get('teaser', '')}", f"**คำถามท้ายคลิป (เสียงพูด):** {ep.get('ask', '')}"]
    if ep.get("ask"):
        say_line("narration", ep["ask"])
    md += [f"**ค้างไว้:** {ep.get('cliff', '')}", f"**สรุปตอนนี้:** {ep.get('summary', '')}", "",
           f"_ความยาวโดยประมาณ {t:.0f} วินาที ที่ความเร็ว {cps:g} ตัวอักษรต่อวินาที_"]
    Path(f"{base}.md").write_text("\n".join(md), encoding="utf-8")
    Path(f"{base}.srt").write_text("\n".join(srt), encoding="utf-8")
    vt = ["# ลำดับเสียงพากย์ (อัดตามลำดับนี้)", ""]
    vt += [f"{j:03d} [{who_name(series, w)}{' | ' + voice_of(series, w) if voice_of(series, w) else ''}] {x}" for j, (w, x) in enumerate(voice, 1)]
    groups = {}
    for j, (w, x) in enumerate(voice, 1):
        groups.setdefault(who_name(series, w), []).append(f"{j:03d} {x}")
    vt += ["", "# แยกตามคนพากย์", ""]
    for name, rows in groups.items():
        vt += [f"## {name}"] + rows + [""]
    Path(f"{base}_voice.txt").write_text("\n".join(vt), encoding="utf-8")
    return [f"{base}.md", f"{base}.srt", f"{base}_voice.txt"], t


def main():
    ap = argparse.ArgumentParser(description="Check and export Thai drama episode scripts")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("check", "export"):
        p = sub.add_parser(c)
        p.add_argument("episode")
        p.add_argument("--sec", type=int, default=0)
        p.add_argument("--cps", type=float, default=CPS)
    a = ap.parse_args()
    ep = load(a.episode)
    series = series_of(a.episode)
    sec = a.sec or int((series or {}).get("seconds") or 90)
    errs, warns, total = check(ep, series, sec, a.cps)
    if a.cmd == "check" or errs:
        for e in errs:
            print("ERROR", e)
        for w in warns:
            print("WARN ", w)
        print(f"spoken chars: {total} (target about {int(sec * a.cps)}) · shots: {len(ep.get('shots') or [])}")
        print("PASS" if not errs else f"FAIL ({len(errs)} errors)")
        if errs:
            sys.exit(1)
        if a.cmd == "check":
            return
    files, dur = export(a.episode, ep, series, a.cps)
    print(f"exported ({dur:.0f}s): " + ", ".join(files))


if __name__ == "__main__":
    main()
