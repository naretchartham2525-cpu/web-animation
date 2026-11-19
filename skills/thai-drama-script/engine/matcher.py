import re

import drama_items as IT
import drama_poses as PZ

SYN = {
    "cash": "money_wad", "money": "money", "bills": "banknotes", "banknote": "bank100", "baht": "banknotes", "bribe": "envelope_brown", "salary": "envelope_brown",
    "card": "credit_card", "atm": "atm_card", "id": "id_card", "gold": "goldbar", "jewelry": "ring_box", "ring": "ring_box", "necklace": "amulet",
    "booze": "whisky", "liquor": "whisky", "alcohol": "whisky", "lao_khao": "whisky", "beer": "beer_bottle", "wine": "wine_bottle", "drink": "water_glass", "water": "water_bottle",
    "coffee": "coffee_cup", "tea": "tea_cup", "milk_tea": "bubble_tea", "soda": "soda_can", "coke": "soda_can", "juice": "juice_box",
    "rice": "rice_plate", "food": "fried_rice", "meal": "basil_rice", "noodle": "noodle_bowl", "soup": "tom_yum", "salad": "papaya_salad", "pork": "moo_ping", "chicken": "grilled_chicken",
    "fruit": "apple", "snack": "cookie", "sweets": "candy", "dessert": "cake", "phone": "smartphone", "mobile": "smartphone", "iphone": "smartphone", "computer": "laptop", "notebook_pc": "laptop",
    "doc": "letter", "document": "letter", "paper": "paper", "report": "folder", "file": "folder", "bill": "bill", "debt": "debt_notice", "summons": "contract", "deed": "land_deed",
    "photo": "photo", "picture": "photo", "evidence": "evidence_bag", "usb_drive": "usb", "recorder": "microphone", "cctv": "video_camera", "gun": "stick", "knife": "knife", "weapon": "stick",
    "club": "baseball_bat", "bat": "baseball_bat", "broom": "broom", "bag": "bag", "purse": "handbag", "luggage": "suitcase", "gift": "gift_box", "present": "gift_box", "flower": "flowers",
    "medicine": "pill_bottle", "pills": "pill_strip", "drug": "pill_bottle", "injection": "syringe", "makeup": "lipstick", "key": "key", "lock": "padlock", "tool": "toolbox",
    "slipper": "slipper", "shoe": "slipper", "banner": "sign_board", "contract_paper": "contract", "lottery_ticket": "lottery", "ticket": "ticket",
    "repair": "fix_engine", "fix": "fix_engine", "fix_car": "fix_engine", "repair_car": "fix_engine", "mechanic": "fix_engine", "engine": "fix_engine", "wrench": "tighten_bolt",
    "under": "under_car", "tire": "change_tire", "tyre": "change_tire", "wash": "wash_car", "grill": "grill_fan", "bbq": "grill_fan", "fry": "fry", "stir": "cook_stir",
    "pound": "pound_mortar", "somtam": "pound_mortar", "wipe": "wipe_table", "change": "give_change", "laundry": "hang_laundry", "plant": "plant_rice", "harvest": "pick_fruit",
    "paint": "paint_wall", "deliver": "deliver_parcel", "arrest": "handcuff", "cuff": "handcuff", "ticket_write": "write_ticket", "search": "search_bag", "inject": "give_injection",
    "haircut": "cut_hair", "massage": "massage", "sew": "sew", "carry": "carry_box", "lift": "lift_heavy", "push": "push", "chop": "chop", "atm": "withdraw_atm", "pay": "scan_qr",
    "work": "type_standing", "teach": "write_board", "present": "present", "serve": "serve_food", "sell": "sell_shout", "pack": "bag_goods",
    "hit": "slap", "smack": "slap", "punch": "punch", "fight": "fight_stance", "beg": "kneel_beg", "plead": "plead", "kneel": "kneel", "fall": "fall_back", "trip": "trip",
    "faint": "faint", "pass_out": "faint", "collapse": "collapse", "lie": "lie_back", "sleep": "lie_side", "sit": "sit_chair", "squat": "squat", "cry": "cry_face", "sob": "sob",
    "laugh": "laugh_belly", "giggle": "giggle", "angry": "rage", "rage": "rage", "dance": "dance_disco", "run": "run", "flee": "run_scared", "escape": "run_scared", "jump": "jump",
    "hug": "hug_open", "kiss": "blow_kiss", "eat": "eat_spoon", "drink_pose": "drink", "cook": "cook_stir", "clean": "sweep", "type": "text_phone", "call": "phone_call", "pray": "pray_incense",
    "dancing": "dance_disco", "drunk": "wobble", "lottery": "lottery", "scared": "cower", "afraid": "cower", "shocked": "gasp", "surprised": "gasp", "happy": "jump_joy",
    "win": "victory", "proud": "proud_chest", "sad": "sad", "tired": "sit_wall", "sick": "cough", "hurt": "beaten", "injured": "beaten", "drive": "steer", "write": "write",
    "read": "read_paper", "sign": "sign_paper", "wave": "wave", "point": "point_forward", "shout": "yell", "scream": "panic", "whisper": "whisper", "listen": "listen",
    "bow": "bow_deep", "thank": "wai", "sorry": "wai_low", "apologize": "wai_low", "salute": "salute_sharp", "shrug": "shrug", "nod": "nod", "think": "think", "count": "count_money",
}


def stem(w):
    for suf in ("ing", "es", "s", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def near(v, allowed, dv):
    v = re.sub(r"[\s\-]+", "_", str(v or "").strip().lower()).strip("_")
    if not v or v == "none":
        return dv
    if v in allowed:
        return v
    if SYN.get(v) in allowed:
        return SYN[v]
    words = [w for w in v.split("_") if len(w) >= 3]
    stems = [stem(w) for w in words]

    def part(w, x):
        if w == x or stem(w) == stem(x):
            return 1.0
        short = min(len(w), len(x))
        return 0.6 if short >= 5 and (w.startswith(x) or x.startswith(w)) else 0.0

    best, score = None, 0.0
    for a in allowed:
        aw = a.split("_")
        sc = sum(max((part(w, x) for x in aw), default=0.0) for w in words)
        sc += sum(0.5 for w, st in zip(words, stems) if SYN.get(w) == a or SYN.get(st) == a) - 0.01 * len(aw)
        if sc > score:
            best, score = a, sc
    if best and score >= 0.5:
        return best
    for w, st in zip(words, stems):
        for q in (w, st):
            if SYN.get(q) in allowed:
                return SYN[q]
    for k, name in list(PZ.TH.items()) + list(IT.TH.items()):
        if k in allowed and name and (name in str(v) or str(v) in name):
            return k
    return dv
