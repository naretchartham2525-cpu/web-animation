"""เช็กชื่อที่ใช้แต่ไม่มีนิยาม (เช่น ลบค่าคงที่ไปแล้วแต่ยังมีโค้ดใช้) ใน app/**/*.py
python tools/check_py.py"""
import builtins
import symtable
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
bad = []
for f in sorted((root / "app").rglob("*.py")):
    src = f.read_text(encoding="utf-8")
    top = symtable.symtable(src, str(f), "exec")
    defined = {s.get_name() for s in top.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
    defined |= set(dir(builtins)) | {"__file__", "__name__"}

    def walk(t):
        for s in t.get_symbols():
            if s.is_referenced() and s.is_global() and not s.is_declared_global() and s.get_name() not in defined:
                bad.append(f"{f.relative_to(root)}: {t.get_name()}() ใช้ '{s.get_name()}' แต่ไม่มีนิยาม")
        for c in t.get_children():
            walk(c)
    walk(top)
if bad:
    print("\n".join(bad))
    sys.exit(1)
print("OK · ไม่พบชื่อที่ไม่มีนิยาม")
