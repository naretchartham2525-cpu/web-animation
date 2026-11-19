from scene_kit import *


def draw():
    room = Room((675, 1150), (230, 560, 1120, 1560), seed=12)
    room.surface("back", tex_tiles(900, 1000, "#e8e4da", "#d8d2c4", 12, 90, "#b8b2a4"))
    room.surface("floor", tex_concrete(900, 1500, "#6a6862", 13, 0.4, 6))
    room.surface("left", tex_plaster(1200, 900, "#c9b48a", "#8f7a55", 14, 0.55))
    room.surface("right", tex_plaster(1200, 900, "#c9b48a", "#8f7a55", 15, 0.55))
    room.surface("ceil", tex_ribs(900, 900, "#5a5650", 16, 44, vertical=True))
    sign(room.img, 330, 600, 1020, 760, "#c0392b", "#f5e6c8")
    for k in range(4):
        ellipse(room.img, (420 + k * 170, 680), (52, 52), "#f5e6c8")
    rect(room.img, 300, 1180, 1050, 1420, "#b8bcc2")
    rect(room.img, 300, 1180, 1050, 1205, "#e6e9ee")
    rect(room.img, 330, 900, 760, 1180, "#a8d4e6", 0.35)
    cv2.rectangle(room.img, (330, 900), (760, 1180), col("#8a8f96").tolist(), 10)
    for k in range(4):
        x = 380 + k * 100
        cv2.line(room.img, (x, 910), (x, 960), (60, 60, 60), 4, cv2.LINE_AA)
        ellipse(room.img, (x, 1010), (38, 52), "#f2d7a0")
        ellipse(room.img, (x - 10, 995), (12, 16), "#fff4d8", 0.6)
    cyl(room.img, 830, 1000, 1030, 1180, "#9aa0a8", rim="#7a8088", top="#c8ccd2")
    for k in range(3):
        ellipse(room.img, (870 + k * 40, 990 - k * 30), (30, 40), "#ffffff", 0.18, blur=12)
    for x in (360, 1000):
        cyl(room.img, x - 40, x + 40, 1500, 1560, "#d33a2c", rim="#a52a20", top="#e8503e")
    lamp_hanging(room, 520, 620, 560, "#ffe0a8", 1.0, 260)
    lamp_hanging(room, 860, 620, 560, "#ffe0a8", 1.0, 260)
    room.ao(0.45)
    return room.finish(ambient=0.9, tint="#c9bfae", haze=0.04, wet=0.15, grade=(1.04, 1.0, 0.95))
