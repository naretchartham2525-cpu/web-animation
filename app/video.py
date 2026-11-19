"""ffmpeg: ตัดต่อ, ซับ ASS/SRT"""
import json
import re
import subprocess

RATIO = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1), "4:5": (4, 5)}
QUALITY = {"sd": 540, "hd": 720, "fhd": 1080}   # ด้านสั้นของจอ
QUALITY_TH = {"sd": "มาตรฐาน", "hd": "HD", "fhd": "FHD"}


def resolution(aspect, quality="fhd"):
    a, b = RATIO.get(aspect, RATIO["9:16"])
    short = QUALITY.get(quality, 1080)
    if a <= b:
        w, h = short, short * b / a
    else:
        w, h = short * a / b, short
    return int(round(w / 2)) * 2, int(round(h / 2)) * 2


def probe_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def _vf_cover(w, h, fps):
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"setsar=1,fps={fps},format=yuv420p")


def segment_cmd(kind, src, audio, out, dur, w, h, s, offset=0.0, zoom_in=True):
    """สร้างคำสั่ง ffmpeg ของ 1 ฉาก: ภาพ + เสียง ยาว dur วินาที"""
    fps = int(s["fps"])
    enc = ["-c:v", "libx264", "-preset", s["preset"], "-crf", str(s["crf"]),
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
           "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out)]
    af = ["-af", "apad"]
    if kind == "video":
        return (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-stream_loop", "-1", "-ss", f"{offset:.2f}", "-i", str(src), "-i", str(audio),
                 "-map", "0:v:0", "-map", "1:a:0", "-vf", _vf_cover(w, h, fps)] + af + enc)
    if kind == "image":
        frames = max(1, int(dur * fps) + 1)
        if s.get("ken_burns", True):
            k = float(s.get("kb_speed") or 0.0007)
            z = f"min(zoom+{k},1.12)" if zoom_in else f"if(eq(on,0),1.12,max(zoom-{k},1.0))"
            vf = (f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
                  f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps},"
                  f"setsar=1,format=yuv420p")
            inp = ["-i", str(src)]
        else:
            vf = _vf_cover(w, h, fps)
            inp = ["-loop", "1", "-framerate", str(fps), "-i", str(src)]
        return (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + inp + ["-i", str(audio),
                "-map", "0:v:0", "-map", "1:a:0", "-vf", vf] + af + enc)
    # ไม่มีภาพ → พื้นสีเข้ม
    return (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", f"color=c=0x14141c:s={w}x{h}:r={fps}", "-i", str(audio),
             "-map", "0:v:0", "-map", "1:a:0", "-vf", "format=yuv420p"] + af + enc)


# ---------------- ซับไตเติล ----------------
def _tokenize(text):
    try:  # ตัดคำไทยให้สวยถ้ามี pythainlp
        from pythainlp.tokenize import word_tokenize
        return word_tokenize(text, engine="newmm", keep_whitespace=True)
    except Exception:
        return re.findall(r"\S+\s*", text)


_THAI_FOLLOW = set("ะัาำิีึืฺุู็่้๊๋์ํ๎ๅ")   # สระ/วรรณยุกต์ที่ห้ามขึ้นต้นบรรทัด
_THAI_LEAD = set("เแโใไ")                     # สระหน้าที่ห้ามอยู่ท้ายบรรทัด


def _cut_point(tok, n):
    """หาจุดตัดคำยาวที่ไม่ทำให้สระ/วรรณยุกต์ลอย"""
    i = min(n, len(tok) - 1)
    while i > 1 and (tok[i] in _THAI_FOLLOW or tok[i - 1] in _THAI_LEAD):
        i -= 1
    return max(1, i)


def split_chunks(text, max_chars):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    chunks, cur = [], ""
    for tok in _tokenize(text):
        while len(tok) > max_chars:  # คำยาวเกิน ตัดกลาง
            if cur.strip():
                chunks.append(cur.strip())
                cur = ""
            cut = _cut_point(tok, max_chars)
            chunks.append(tok[:cut])
            tok = tok[cut:]
        if len(cur) + len(tok) > max_chars and cur.strip():
            chunks.append(cur.strip())
            cur = tok
        else:
            cur += tok
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def _ts_ass(t):
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ts_srt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_subs(items, w, h, s, watermark="", total=0.0):
    """items: [(start, speech_dur, text)] → (ass_text, srt_text)  watermark = ข้อความลายน้ำมุมขวาบน"""
    portrait = h > w
    size = int(s.get("subtitle_size") or 0) or (int(w * 0.068) if portrait else int(h * 0.058))
    max_chars = int(s.get("subtitle_max_chars") or 0) or (20 if portrait else 38)
    margin_v = int(h * (0.16 if portrait else 0.07))
    font = s.get("subtitle_font") or "Loma"
    ass = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{max(3, size // 14)},2,2,60,60,{margin_v},1",
        f"Style: WM,{font},{max(14, int(min(w, h) * 0.035))},&H60FFFFFF,&H000000FF,&H80000000,&H00000000,"
        f"-1,0,0,0,100,100,0,0,1,{max(1, int(min(w, h) * 0.002))},0,9,30,30,30,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    srt, n = [], 0
    if watermark and total > 0:
        wm = watermark.replace("{", "(").replace("}", ")").replace("\\", "/")
        ass.append(f"Dialogue: 1,{_ts_ass(0)},{_ts_ass(total + 1)},WM,,0,0,0,,{wm}")
    for start, dur, text in items:
        chunks = split_chunks(text, max_chars)
        if not chunks or dur <= 0:
            continue
        total = sum(len(c) for c in chunks)
        t = start
        for c in chunks:
            d = dur * len(c) / total
            safe = c.replace("{", "(").replace("}", ")").replace("\\", "/")
            ass.append(f"Dialogue: 0,{_ts_ass(t)},{_ts_ass(t + d)},Default,,0,0,0,,{safe}")
            n += 1
            srt.append(f"{n}\n{_ts_srt(t)} --> {_ts_srt(t + d)}\n{c}\n")
            t += d
    return "\n".join(ass) + "\n", "\n".join(srt)


def silent_audio_cmd(out, dur):
    return ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{dur:.2f}", "-c:a", "libmp3lame", "-b:a", "64k", str(out)]


def estimate_speech_seconds(text):
    """ประมาณเวลาอ่านภาษาไทย (~13 ตัวอักษร/วินาที) ใช้ตอนปิดเสียงพากย์"""
    return max(2.0, len((text or "").replace(" ", "")) / 13.0)
