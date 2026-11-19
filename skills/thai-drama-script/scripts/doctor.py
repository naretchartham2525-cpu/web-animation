import importlib.util
import json
import platform
import shutil
import subprocess
import sys

PIP_PKGS = (("edge_tts", "edge-tts", "free Thai voices"), ("imageio_ffmpeg", "imageio-ffmpeg", "ffmpeg for audio and video"),
            ("numpy", "numpy", "video math"), ("cv2", "opencv-python-headless", "backgrounds and frames"), ("PIL", "pillow", "drawing"),
            ("pythainlp", "pythainlp", "Thai line breaks"), ("uharfbuzz", "uharfbuzz", "Thai text shaping"), ("freetype", "freetype-py", "Thai text shaping"))


def osname():
    return {"Darwin": "mac", "Windows": "windows"}.get(platform.system(), "linux")


def ffmpeg_path():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


def pip_install(pkgs):
    base = [sys.executable, "-m", "pip", "install", "--upgrade"]
    for extra in ([], ["--user"], ["--user", "--break-system-packages"]):
        r = subprocess.run(base + extra + pkgs, capture_output=True, text=True)
        if r.returncode == 0:
            return True, " ".join(extra) or "default"
        last = (r.stderr or r.stdout).strip().splitlines()[-1:] or [""]
    return False, last[0]


def check():
    items = []
    py_ok = sys.version_info >= (3, 9)
    items.append({"name": "python", "ok": py_ok, "found": platform.python_version(), "why": "runs the skill scripts"})
    for mod, pkg, why in PIP_PKGS:
        ok = importlib.util.find_spec(mod) is not None
        if mod == "imageio_ffmpeg" and shutil.which("ffmpeg"):
            ok = True
        items.append({"name": pkg, "ok": ok, "found": "installed" if ok else "", "why": why})
    return items


def main():
    if "--ffmpeg" in sys.argv:
        print(ffmpeg_path())
        return
    if "--install" in sys.argv:
        need = [pkg for mod, pkg, _ in PIP_PKGS if not (importlib.util.find_spec(mod) or (mod == "imageio_ffmpeg" and shutil.which("ffmpeg")))]
        if need:
            ok, how = pip_install(need)
            print(("installed " if ok else "FAILED to install ") + ", ".join(need) + f" ({how})")
            importlib.invalidate_caches()
    items = check()
    if "--json" in sys.argv:
        print(json.dumps({"os": osname(), "python": sys.executable, "ffmpeg": ffmpeg_path(), "items": items}, ensure_ascii=False, indent=1))
        return
    print(f"system: {osname()} · python {platform.python_version()} · {sys.executable}")
    for i in items:
        print(f"{'OK     ' if i['ok'] else 'MISSING'} {i['name']:<16} {i['why']}")
    print(f"ffmpeg: {ffmpeg_path() or 'not found'}")
    missing = [i for i in items if not i["ok"]]
    if missing:
        print(f'NOT READY - run: "{sys.executable}" "{__file__}" --install')
    else:
        print("READY")


if __name__ == "__main__":
    main()
