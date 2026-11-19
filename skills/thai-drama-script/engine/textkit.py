import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

FONT_DIR = Path(__file__).resolve().parent / "fonts"
_CACHE = {}
MARKS = set(chr(c) for c in list(range(0x0E31, 0x0E32)) + list(range(0x0E34, 0x0E3B)) + list(range(0x0E47, 0x0E4F)))
LEAD = set("เแโใไ")


RAQM = features.check("raqm") and not os.environ.get("TDS_FORCE_HB")


def font(size, weight="Bold"):
    k = (size, weight)
    if k not in _CACHE:
        p = FONT_DIR / f"IBMPlexSansThai-{weight}.ttf"
        f = ImageFont.truetype(str(p), size, layout_engine=ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC)
        f.tds_path = str(p)
        _CACHE[k] = f
    return _CACHE[k]


_HB = {}


def _hb(path, size):
    k = (path, size)
    if k not in _HB:
        import freetype
        import uharfbuzz as hb
        blob = hb.Blob.from_file_path(path)
        face = hb.Face(blob)
        hf = hb.Font(face)
        hf.scale = (size * 64, size * 64)
        ft = freetype.Face(path)
        ft.set_char_size(size * 64)
        ext = hf.get_font_extents("ltr")
        _HB[k] = (hf, ft, ext.ascender / 64, -ext.descender / 64)
    return _HB[k]


def _hb_mask(text, f):
    import freetype
    import uharfbuzz as hb
    hf, ft, asc, desc = _hb(f.tds_path, f.size)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hf, buf, {})
    pen = 0.0
    glyphs = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs.append((info.codepoint, pen + pos.x_offset / 64, pos.y_offset / 64))
        pen += pos.x_advance / 64
    pad = int(f.size * 0.25)
    w, h = int(pen) + 2 * pad + 2, int(asc + desc) + 2 * pad + 2
    m = Image.new("L", (max(1, w), max(1, h)), 0)
    for gid, x, yo in glyphs:
        ft.load_glyph(gid, freetype.FT_LOAD_DEFAULT)
        ft.glyph.render(freetype.FT_RENDER_MODE_NORMAL)
        bm = ft.glyph.bitmap
        if bm.width and bm.rows:
            g = Image.frombytes("L", (bm.width, bm.rows), bytes(bm.buffer))
            gx = int(round(pad + x + ft.glyph.bitmap_left))
            gy = int(round(pad + asc - yo - ft.glyph.bitmap_top))
            m.paste(Image.eval(g, lambda v: v), (gx, gy), g)
    return m, pad, asc, desc, pen


class Draw(ImageDraw.ImageDraw):
    def text(self, xy, text, fill=None, font=None, anchor=None, spacing=4, align="left", direction=None, features=None, language=None,
             stroke_width=0, stroke_fill=None, embedded_color=False, *args, **kwargs):
        if RAQM or font is None or not getattr(font, "tds_path", None) or not str(text or "").strip():
            return super().text(xy, text, fill=fill, font=font, anchor=anchor, stroke_width=stroke_width, stroke_fill=stroke_fill)
        m, pad, asc, desc, w = _hb_mask(str(text), font)
        a = anchor or "la"
        x, y = xy
        x -= {"l": 0, "m": w / 2, "r": w}.get(a[0], 0)
        y -= {"a": 0, "t": 0, "m": (asc + desc) / 2, "s": asc, "b": asc + desc, "d": asc + desc}.get(a[1] if len(a) > 1 else "a", 0)
        ox, oy = int(round(x - pad)), int(round(y - pad))
        img = self._image
        if stroke_width:
            import numpy as np
            import cv2
            k = 2 * int(stroke_width) + 1
            sm = Image.fromarray(cv2.dilate(np.asarray(m), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))))
            img.paste(Image.new(img.mode, m.size, stroke_fill if stroke_fill is not None else fill), (ox, oy), sm)
        img.paste(Image.new(img.mode, m.size, fill), (ox, oy), m)


def width(text, f):
    return f.getlength(text)


def _breaks(text):
    try:
        from pythainlp.tokenize import word_tokenize
        out, i = [], 0
        for w in word_tokenize(text, engine="newmm", keep_whitespace=True)[:-1]:
            i += len(w)
            out.append(i)
        return out
    except Exception:
        pass
    out = []
    for i in range(1, len(text)):
        a, b = text[i - 1], text[i]
        if b in MARKS or a in LEAD or b in "ะาำๆ":
            continue
        out.append(i)
    return out


def wrap(text, f, maxw, max_lines=99):
    text = " ".join(str(text or "").split())
    lines = []
    while text:
        if width(text, f) <= maxw:
            lines.append(text)
            break
        cut = 0
        spaces = [i for i, ch in enumerate(text) if ch == " " and width(text[:i], f) <= maxw]
        if spaces and width(text[:spaces[-1]], f) > maxw * 0.55:
            cut = spaces[-1]
        else:
            for i in _breaks(text):
                if width(text[:i], f) <= maxw:
                    cut = i
                else:
                    break
        if cut <= 0:
            cut = max(1, len(text) // 2)
        lines.append(text[:cut].strip())
        text = text[cut:].strip()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip() + "…"
    return lines


def draw_text(d, xy, text, f, fill, anchor="la", stroke=0, stroke_fill=None):
    d.text(xy, text, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)


def block(d, x, y, text, f, fill, maxw, lh=1.32, anchor="l", max_lines=99, stroke=0, stroke_fill=None):
    lines = wrap(text, f, maxw, max_lines)
    step = int(f.size * lh)
    for k, ln in enumerate(lines):
        yy = y + k * step
        if anchor == "c":
            d.text((x, yy), ln, font=f, fill=fill, anchor="ma", stroke_width=stroke, stroke_fill=stroke_fill)
        elif anchor == "r":
            d.text((x, yy), ln, font=f, fill=fill, anchor="ra", stroke_width=stroke, stroke_fill=stroke_fill)
        else:
            d.text((x, yy), ln, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return y + len(lines) * step


def measure(text, f, maxw, lh=1.32, max_lines=99):
    return len(wrap(text, f, maxw, max_lines)) * int(f.size * lh)


def subtitle(img, text, y=1430, size=66, maxw=900):
    d = Draw(img)
    f = font(size, "Bold")
    lines = wrap(text, f, maxw, 3)
    step = int(size * 1.3)
    y0 = y - (len(lines) - 1) * step // 2
    for k, ln in enumerate(lines):
        d.text((img.width // 2, y0 + k * step), ln, font=f, fill=(255, 255, 255), anchor="mm", stroke_width=9, stroke_fill=(10, 10, 12))


def rounded(d, box, r, fill, outline=None, width=0):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def avatar(d, cx, cy, r, name, col):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    ch = (str(name or "?").strip() or "?")[:1]
    d.text((cx, cy), ch, font=font(int(r * 1.05), "Bold"), fill=(255, 255, 255), anchor="mm")


def canvas(w, h, col):
    return Image.new("RGB", (w, h), col)
