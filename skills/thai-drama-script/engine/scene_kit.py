import cv2
import numpy as np

from drama_sets import (H, SETS, W, Room, col, cone, cyl, ellipse, garage, glow, lamp_hanging, market, noise, poly, rented_room, rng, tex_concrete,
                        tex_plaster, tex_ribs, tex_tiles, tex_wood, tire, tire_stack, tube_light, warp)

PRESETS = {k: v[1] for k, v in SETS.items()}

__all__ = ["W", "H", "Room", "col", "cone", "cyl", "ellipse", "glow", "lamp_hanging", "noise", "poly", "rng", "tex_concrete", "tex_plaster", "tex_ribs",
           "tex_tiles", "tex_wood", "tire", "tire_stack", "tube_light", "warp", "cv2", "np", "rect", "sign", "window", "PRESETS", "garage", "market", "rented_room"]


def rect(img, x0, y0, x1, y1, c, alpha=1.0, blur=0):
    poly(img, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], c, alpha, blur)


def window(img, x0, y0, x1, y1, sky_top="#9cc4e8", sky_bottom="#e8eef2", frame="#3a2a1c", night=False):
    h, w = int(y1 - y0), int(x1 - x0)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    a, b = (col("#0d1830"), col("#24304a")) if night else (col(sky_top), col(sky_bottom))
    img[int(y0):int(y0) + h, int(x0):int(x0) + w] = a * (1 - yy) + b * yy
    cv2.rectangle(img, (int(x0), int(y0)), (int(x1), int(y1)), col(frame).tolist(), 14)
    cv2.line(img, (int((x0 + x1) / 2), int(y0)), (int((x0 + x1) / 2), int(y1)), col(frame).tolist(), 8)


def sign(img, x0, y0, x1, y1, c="#c0392b", border="#f5f0e0"):
    rect(img, x0, y0, x1, y1, c)
    cv2.rectangle(img, (int(x0), int(y0)), (int(x1), int(y1)), col(border).tolist(), 8)
