"""เช็ก index.html ก่อน commit: ชื่อ const/let/function ระดับบนสุดห้ามซ้ำ (ซ้ำ = หน้าเว็บค้างทั้งหน้า)
python tools/check_js.py"""
import re
import sys
from collections import Counter
from pathlib import Path

src = (Path(__file__).resolve().parent.parent / "app/static/index.html").read_text(encoding="utf-8")
js = "\n".join(re.findall(r"<script>(.*?)</script>", src, re.S))
names = re.findall(r"^(?:const|let|var|function|async function)\s+([A-Za-z_$][\w$]*)", js, re.M)
dup = [n for n, c in Counter(names).items() if c > 1]
if dup:
    print("ชื่อซ้ำ:", ", ".join(dup))
    sys.exit(1)
print(f"OK · {len(names)} ชื่อไม่ซ้ำ")
