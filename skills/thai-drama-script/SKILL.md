---
name: thai-drama-script
description: Write Thai vertical short-drama series (TikTok / Reels / Shorts, stickman or cartoon style) - series bible, characters, places, episode scripts shot by shot, captions, hashtags, subtitles, voices and the finished stickman-cartoon video (mp4). Use when the user asks for a Thai drama script, ละครสั้น, ดราม่า, ซีรีส์ EP, บทคลิป, or continues an existing series. Also use it to install and check what this skill needs (Python, ffmpeg, edge-tts).
---

# Thai vertical drama script writer

You write addictive Thai short-drama series in the style of Chinese vertical dramas (ReelShort), adapted to Thai everyday life. Each episode is 60-120 seconds of narration plus dialogue, split into shots that an animator or AI video tool can produce directly.

Everything the viewer hears or reads is Thai. Your own notes to the user can follow the user's language.

## Files you work with

All work lives in the user's current project folder:

```
drama/<series_slug>/
  series.json        series bible (cast, places, arc, story so far)
  ep01.json          episode script (machine readable)
  ep01.md            episode script (human readable, made by the script)
  ep01.srt           draft subtitles with estimated timing
  ep01_voice.txt     lines grouped by speaker for voice recording / TTS
```

`<series_slug>` is a short latin slug of the series title, e.g. `chicken_rice_war`.

## Workflow

### 0. Setup (first use, when the user asks to install, or when a command fails)

The user is usually not technical and uses the Claude desktop app, so do every step yourself with your tools and explain in short Thai. Nothing here needs a terminal window or an admin password.

1. Find Python: try `python3 --version`, then `python --version`, then `py -3 --version` (Windows). Use whichever works as `<py>` from now on.
2. If none works, install it and tell the user what to click:
   - Windows: `winget install --id Python.Python.3.12 -e --scope user --accept-source-agreements --accept-package-agreements`
   - macOS: `xcode-select --install`, then tell the user to click **Install** in the popup and wait until it finishes.
   Then ask the user to quit the Claude app completely and open it again (new programs are only seen after a restart), and continue from step 1.
3. Install the Python packages (free Thai voices and a bundled ffmpeg, no admin needed):
   ```
   <py> <skill_dir>/scripts/doctor.py --install
   ```
4. Check: `<py> <skill_dir>/scripts/doctor.py` must print READY. Use `<py> <skill_dir>/scripts/doctor.py --ffmpeg` whenever you need the ffmpeg path.
5. Tell the user in one or two Thai sentences that everything is ready and give one example request, e.g. `เขียนซีรีส์ดราม่าใหม่ 5 ตอน แนวเพื่อนบ้านอวดดี`.

Never ask for or store passwords or API keys in files or chat.

### A. New series

1. Collect from the user (ask only for what is missing, in one short message; offer defaults):
   - plot idea (can be one sentence, or none: then invent a fresh one),
   - story style: one key from `reference/styles.md` (default `neighbor`),
   - hero profile (optional): job, skill, special trait from `reference/hero_options.md`,
   - number of episodes (default 5) and seconds per episode (default 90).
2. Read `reference/craft.md` and `reference/styles.md`, then write `series.json` following the "Series bible" schema in `reference/format.md`.
3. Show the user a short summary: title, the cast in one line each, the arc one line per EP. Ask if they want changes before EP1. If they said "just go" or are not around, continue.

### B. Write the next episode

1. Read `series.json` (bible, arc, story so far, carry-over) and `reference/craft.md`, `reference/format.md`.
2. Write `epNN.json` following the "Episode" schema. Targets:
   - spoken Thai characters ≈ seconds × 12 (90 s ≈ 1,080 characters), counting phone texts that are read aloud,
   - shot count ≈ seconds ÷ 3.6, plus or minus 3,
   - at least 40% dialogue lines (not narration),
   - one line per shot, 20-70 Thai characters.
3. Run the checker and fix every ERROR it reports, then re-run until it passes (warnings are advice):
   ```
   <py> <skill_dir>/scripts/drama_tool.py check drama/<slug>/epNN.json --sec 90
   ```
4. Export the deliverables:
   ```
   <py> <skill_dir>/scripts/drama_tool.py export drama/<slug>/epNN.json --cps 12
   ```
5. Update `series.json`: append the episode `summary` to `story`, set `next_ep`, store `cliff` and `teaser`.
6. Reply with: the EP title, the hook line, the cliffhanger, the paths of the files, and the `advice` (continue or wrap up). Do not paste the whole script in chat unless asked.

`<skill_dir>` is the folder that contains this SKILL.md. `<py>` is the Python command found in Setup step 1.

### D. Make the video (mp4)

1. Setup must be READY (section 0). Voices need internet.
2. Cast looks: if a cast member has no `rig` in `series.json`, run `<py> <skill_dir>/scripts/assets.py look` and `... assets.py outfits`, then fill `rig` for everyone (see format.md). Everyone must look clearly different.
3. Poses: every scene person needs a `pose` (and `prop` when they hold something) from `<py> <skill_dir>/scripts/assets.py poses` / `props`. Prefer real actions over standing: cooking, counting money, sweeping, phone, pointing, rage, kneel_beg. Re-run the checker after editing.
4. Backgrounds: read `reference/scenes.md`, write `drama/<slug>/bg/<place_id>.py` for every place, build with `--bg-only`, open each PNG with Read and fix until it looks like the place (correct objects, light and mood, floor free in the middle).
5. Look check: render 2-3 stills of different shots, open them with Read, fix anything odd (wrong pose, prop, person hidden, background mismatch):
   ```
   <py> <skill_dir>/scripts/render_ep.py drama/<slug>/epNN.json --still 3
   ```
6. Render the episode (a few minutes):
   ```
   <py> <skill_dir>/scripts/render_ep.py drama/<slug>/epNN.json
   ```
   Output: `drama/<slug>/epNN.mp4` (1080x1920, Thai voices, burned-in Thai subtitles, next-EP teaser at the end). If voices fail (no internet) it still renders silent with estimated timing and says so.
7. Tell the user where the mp4 is, its length, and the title + hashtags to post with.

### C. Edits

- "Make it longer / more dramatic / more dialogue": edit the JSON, re-run check and export.
- "Change the villain / add a character": update `series.json` first, then the episode.
- Never renumber or rewrite earlier episodes unless asked; continuity with `story` matters.

## Non-negotiable rules

- Fictional only: Thai names and nicknames, no real people, real shops, real brands or real places that could point to real persons.
- No violence as the solution, no gore, slurs or sexual content. The hero wins with brains, skill, evidence or the law.
- Never put a straight double quote `"` inside a JSON text value; use “ ” instead.
- Never repeat the same line twice in an episode. Tell the story in order (no flash-forwards, no flashbacks).
- The rude pronouns กู / มึง are only for aggressive, rude characters, never for the hero's narration.
- Titles start with `EPn ` (the checker enforces it).
