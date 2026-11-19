# Drawing backgrounds (you draw them with code)

Every place in `series.json` needs a background. You draw it yourself as a small Python file; no image generator is needed.

## Where

- `drama/<slug>/bg/<place_id>.py` — your drawing code (you write this)
- `drama/<slug>/bg/<place_id>.png` — made from it automatically (or a picture the user drops in; a PNG newer than the .py wins)

Build and check them:
```
<py> <skill_dir>/scripts/render_ep.py drama/<slug>/ep01.json --bg-only
```
Then open each PNG with your Read tool and look at it. Fix and rebuild until it looks right. Places without a .py or .png fall back to a preset (market, garage, rented_room), which rarely fits: always draw your own.

## The file

```python
from scene_kit import *


def draw():
    room = Room((675, 1150), (230, 560, 1120, 1560), seed=12)
    room.surface("back", tex_tiles(900, 1000, "#e8e4da", "#d8d2c4", 12, 90, "#b8b2a4"))
    room.surface("floor", tex_concrete(900, 1500, "#6a6862", 13, 0.4, 6))
    room.surface("left", tex_plaster(1200, 900, "#c9b48a", "#8f7a55", 14, 0.55))
    room.surface("right", tex_plaster(1200, 900, "#c9b48a", "#8f7a55", 15, 0.55))
    room.surface("ceil", tex_ribs(900, 900, "#5a5650", 16, 44, vertical=True))
    sign(room.img, 330, 600, 1020, 760, "#c0392b", "#f5e6c8")
    rect(room.img, 300, 1180, 1050, 1420, "#b8bcc2")
    lamp_hanging(room, 520, 620, 560, "#ffe0a8", 1.0, 260)
    room.ao(0.45)
    return room.finish(ambient=0.9, tint="#c9bfae", haze=0.04, wet=0.15, grade=(1.04, 1.0, 0.95))
```

A full example is in `examples/chicken_rice_war/bg/my_shop.py`.

## Canvas and layout rules

- Canvas is 1350 × 2400 (portrait). x grows right, y grows down.
- `Room(vanishing_point, back_wall_rect, seed)` builds a one-point-perspective box: back wall rect `(x0, y0, x1, y1)`, the floor runs from the back wall bottom `y1` down to the screen bottom. Typical: `Room((675, 1150), (250, 560, 1100, 1560), seed)`.
- Characters stand on the floor around y = 1950–2050 and cover the middle. Keep the lower middle (x 200–1150, y 1600–2400) free of big objects; put furniture, counters, shelves and signs against the back wall (y < 1560) or at the far left/right edges.
- Outdoor places: use the room with sky-coloured back wall (`window` or a gradient), building fronts as rects on the back wall, `tex_concrete` floor as the road, and no ceiling (`room.surface("ceil", ...)` with a dark sky texture or skip it).
- Never write text or letters in the picture (signs are plain colour blocks).

## Tools (all colours are "#rrggbb")

Surfaces (pass to `room.surface(name, tex)` where name is back, floor, left, right, ceil):
- `tex_concrete(w, h, base, seed, stains=0.35, cracks=6)`
- `tex_plaster(w, h, top, bottom, seed, split=0.55)` two-tone wall
- `tex_tiles(w, h, base, base2, seed, size=90, grout="#3a3a3a")`
- `tex_wood(w, h, base, seed, plank=70)`
- `tex_ribs(w, h, base, seed, step=26, vertical=False, dirt=0.4)` metal sheet, shutters

Shapes (draw on `room.img`):
- `rect(img, x0, y0, x1, y1, c, alpha=1.0, blur=0)`
- `poly(img, [(x, y), ...], c, alpha=1.0, blur=0)`
- `ellipse(img, (cx, cy), (rx, ry), c, alpha=1.0, blur=0)`
- `cyl(img, x0, x1, y0, y1, base, rim=None, top=None)` pots, drums, stools
- `sign(img, x0, y0, x1, y1, c, border)` shop sign block
- `window(img, x0, y0, x1, y1, sky_top, sky_bottom, frame, night=False)`
- `tire(img, cx, cy, r)`, `tire_stack(img, cx, base_y, r, n)`
- `cv2.line(img, (x0, y0), (x1, y1), (r, g, b), width, cv2.LINE_AA)` for thin lines

Lights (on `room`, applied in `finish`):
- `lamp_hanging(room, x, y, cord_top, color, strength, r)`
- `tube_light(room, x, y, w, strength)`
- `glow(room.light, (x, y), r, strength, color)`
- `cone(room.light, (x, top_y), w_top, w_bottom, bottom_y, strength, color)` sunbeam

Finish (returns the picture):
- `room.ao(strength)` soft corner shadows, then
- `room.finish(ambient, tint, haze, wet, grade, paint=True, vignette=0.45)`: ambient 0.6 (night) to 0.95 (bright day); tint = overall light colour; wet 0–0.5 makes a shiny wet floor; grade = (r, g, b) multipliers.

Ready presets you can return directly or start from: `garage(seed)`, `market(seed)`, `rented_room(seed)` (each returns `(img, depth)`).
