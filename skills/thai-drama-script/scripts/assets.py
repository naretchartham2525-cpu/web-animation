import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import drama_items as IT
import drama_poses as PZ
import drama_rig as G

HELP = """usage: assets.py poses [group] | props [group] | outfits | look | all
  poses    actions a character can do (use the key in "pose")
  props    things a character can hold (use the key in "prop")
  outfits  ready uniforms and costumes (use the key in cast "rig.outfit")
  look     values for cast "rig" (hair, hat, glasses, shirt, ...)"""


def poses(group=None):
    groups = {}
    for k in G.POSES:
        groups.setdefault(PZ.CAT.get(k, "basic"), []).append(k)
    for g, ks in groups.items():
        if group and g != group:
            continue
        print(f"[{g}] " + " ".join(sorted(ks)))


def props(group=None):
    groups = {}
    for k in G.PROPS:
        groups.setdefault(IT.ITEMS[k][0] if k in IT.ITEMS else "basic", []).append(k)
    for g, ks in groups.items():
        if group and g != group:
            continue
        print(f"[{g}] " + " ".join(sorted(ks)))


def outfits():
    for k, (th, _) in G.OUTFITS.items():
        print(f"{k} = {th}")


def look():
    print("hair: " + " | ".join(G.HAIRS))
    print("hat: " + " | ".join(G.HATS))
    print("glasses: " + " | ".join(G.GLASSES))
    print("shirt: " + " | ".join(G.SHIRTS))
    print("pattern: " + " | ".join(G.PATTERNS))
    print("mouth: " + " | ".join(G.MOUTHS))
    print("brows: " + " | ".join(G.BROWS))
    print("eyes: " + " | ".join(G.EYES))
    print("nose: " + " | ".join(G.NOSES))
    print("extras (list): " + " | ".join(G.EXTRAS))
    print("colors: hair_c and shirt_c as #rrggbb")
    print("faces for scenes: " + " | ".join(G.FACES) + " (also happy, scared, tired, disgust, confused, sly)")
    print("fx for scenes: none | " + " | ".join(G.FX))


def main():
    a = sys.argv[1:] or ["help"]
    cmd, arg = a[0], (a[1] if len(a) > 1 else None)
    if cmd == "poses":
        poses(arg)
    elif cmd == "props":
        props(arg)
    elif cmd == "outfits":
        outfits()
    elif cmd == "look":
        look()
    elif cmd == "all":
        look()
        print("\n# outfits")
        outfits()
        print("\n# poses")
        poses()
        print("\n# props")
        props()
    else:
        print(HELP)


if __name__ == "__main__":
    main()
