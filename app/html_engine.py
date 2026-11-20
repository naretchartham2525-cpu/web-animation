"""เรนเดอร์ภาพจาก "เอนจิน HTML" ของเทมเพลต → วิดีโอเงียบ (ระบบใส่เสียง ซับ ลายน้ำเอง)

สัญญาของเอนจิน (โฟลเดอร์ engine/ ของเทมเพลต):
  engine/index.html   หน้าเว็บที่วาดภาพเต็มจอ ขนาด TIMELINE.w × TIMELINE.h
  engine/SCRIPT.md    วิธีเขียนช่อง "ภาพ" ของแต่ละฉากให้เอนจินนี้เข้าใจ (ระบบแนบให้ AI ตอนเขียนบท)
  - ก่อนโหลดหน้า ระบบใส่ window.TIMELINE = {w, h, fps, duration, title, ep, lang,
        scenes: [{i, start, end, dur, text, speaker, en, visual}]}
  - หน้าต้องมี window.renderFrame(t) วาดภาพที่วินาที t (คืน Promise ได้) โดยไม่พึ่งเวลาจริง
    (ห้าม requestAnimationFrame/Date.now/setTimeout ในการเดินภาพ → เรนเดอร์ซ้ำได้ภาพเดิม)
  - ถ้าต้องโหลดของก่อน (ฟอนต์ ภาพ) ให้ตั้ง window.ENGINE_READY = Promise
  - ไม่ต้องวาดซับ ลายน้ำ หรือเล่นเสียง

ทดสอบเอนจิน (ใน Claude Code):
  pip install playwright && python -m playwright install chromium
  python html_engine.py <engine_dir> --sample timeline.json      # สร้าง timeline ตัวอย่าง
  python html_engine.py <engine_dir> timeline.json out.mp4        # เรนเดอร์
  python html_engine.py <engine_dir> timeline.json frame.png --at 3.2   # ภาพเดียว
"""
import json
import subprocess
import sys
from pathlib import Path


def sample_timeline(w=1080, h=1920, fps=24):
    lines = [("ทุกคนบนโลกห่างจากเรากี่คน", "", "How many people stand between you and anyone?", "two people far apart on a line"),
             ("ลองนับดูทีละมือ", "ผู้บรรยาย", "Count it hand by hand.", "a chain of people holding hands"),
             ("คำตอบคือหก", "", "The answer is six.", "big number 6, accent colour")]
    scenes, t = [], 0.0
    for i, (text, spk, en, vis) in enumerate(lines, 1):
        d = 3.0
        scenes.append({"i": i, "start": t, "end": t + d, "dur": d, "text": text, "speaker": spk, "en": en, "visual": vis})
        t += d
    return {"w": w, "h": h, "fps": fps, "duration": t, "title": "ตัวอย่าง", "ep": 1, "lang": "th", "scenes": scenes}


_READY = False


def _can_launch():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


def ensure_playwright(log=print):
    """Colab: ติดตั้ง playwright + chromium ครั้งแรกที่ต้องใช้ (~1–2 นาที) · เช็กครั้งเดียวต่อการเปิดเครื่อง"""
    global _READY
    if _READY:
        return
    try:
        import playwright  # noqa: F401
    except ImportError:
        log("ติดตั้งตัวเรนเดอร์เอนจิน (ครั้งแรก ~1–2 นาที)")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"], check=True)
    if not _can_launch():
        log("ดาวน์โหลด Chromium (ครั้งแรก)")
        r = subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
                           capture_output=True, text=True)
        if r.returncode != 0:   # ไม่มีสิทธิ์ติดตั้ง deps → ลองแค่ตัวเบราว์เซอร์
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    _READY = True


def render(engine_dir, timeline, out, at=None, log=print, check=None, progress=None):
    """เรนเดอร์ทั้งเรื่อง → out (.mp4 ไม่มีเสียง) หรือภาพเดียวที่วินาที at → out (.png/.jpg)"""
    from playwright.sync_api import sync_playwright
    engine_dir = Path(engine_dir).resolve()
    index = engine_dir / "index.html"
    if not index.exists():
        raise FileNotFoundError(f"เอนจินไม่มี index.html: {engine_dir}")
    w, h, fps = int(timeline["w"]), int(timeline["h"]), int(timeline.get("fps") or 24)
    total = float(timeline["duration"])
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-web-security", "--allow-file-access-from-files", "--disable-gpu"])
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.add_init_script(f"window.TIMELINE = {json.dumps(timeline, ensure_ascii=False)};")
        pg.goto(index.as_uri(), wait_until="load")
        pg.evaluate("() => Promise.resolve(window.ENGINE_READY).then(() => document.fonts && document.fonts.ready)")
        if not pg.evaluate("() => typeof window.renderFrame === 'function'"):
            raise RuntimeError("เอนจินไม่มี window.renderFrame(t)" + (f" · error: {errors[0]}" if errors else ""))
        step = "(t) => Promise.resolve(window.renderFrame(t))"
        if at is not None:
            pg.evaluate(step, float(at))
            pg.screenshot(path=str(out), type="png" if str(out).endswith(".png") else "jpeg")
            b.close()
            if errors:
                log("เอนจินมี error: " + errors[0])
            return
        n = max(1, round(total * fps))
        ff = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "image2pipe",
                               "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264",
                               "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                               "-vf", f"scale={w}:{h}", str(out)], stdin=subprocess.PIPE)
        try:
            for k in range(n):
                if check:
                    check()
                pg.evaluate(step, k / fps)
                ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
                if progress and k % fps == 0:
                    progress(k / n)
                if errors and k == 0:
                    raise RuntimeError("เอนจิน error: " + errors[0])
        finally:
            ff.stdin.close()
            ff.wait()
            b.close()
        if ff.returncode != 0:
            raise RuntimeError("ffmpeg ต่อภาพจากเอนจินไม่สำเร็จ")
        if errors:
            log(f"เอนจินมี error ระหว่างเรนเดอร์ {len(errors)} ครั้ง เช่น: {errors[0]}")


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    eng = argv[1]
    if len(argv) >= 4 and argv[2] == "--sample":
        Path(argv[3]).write_text(json.dumps(sample_timeline(), ensure_ascii=False, indent=1), encoding="utf-8")
        print("เขียน", argv[3])
        return
    if len(argv) < 4:
        sys.exit(__doc__)
    tl = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    at = float(argv[argv.index("--at") + 1]) if "--at" in argv else None
    render(eng, tl, argv[3], at=at)
    print("เสร็จ:", argv[3])


if __name__ == "__main__":
    main(sys.argv)
