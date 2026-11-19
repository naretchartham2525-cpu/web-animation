# File formats

Write strict JSON (UTF-8, no comments, no trailing commas). Never put a straight double quote inside a text value; use “ ”.

## Series bible: `drama/<slug>/series.json`

```json
{
  "series_title": "Thai title, max 22 chars",
  "slug": "latin_slug",
  "style": "neighbor",
  "plot": "the expanded plot in Thai, 3-6 sentences",
  "hero_profile": {"job": "", "skill": "", "power": ""},
  "villain": "Thai, 1-2 sentences: the main antagonist's personality and favourite excuses",
  "cast": [
    {"id": "hero", "name": "ผม", "role": "Thai role", "sex": "m", "age": "late 20s",
     "voice": "man", "personality": "Thai, 1 sentence",
     "look": "English, 1-2 sentences for the artist: hair, face marks, glasses, clothes and colours, signature item",
     "rig": {"hair": "short", "hair_c": "#1b1b1e", "hat": "none", "glasses": "none", "shirt": "collar", "shirt_c": "#3f6fb0", "pattern": "none",
             "mouth": "normal", "brows": "thick", "eyes": "sharp", "nose": "line", "extras": ["watch"], "outfit": ""}},
    {"id": "pa_noi", "name": "ป้าน้อย", "role": "เจ้าของร้านข้าวมันไก่ข้างๆ", "sex": "f", "age": "50s",
     "voice": "oldwoman", "personality": "...", "look": "..."}
  ],
  "places": [
    {"id": "shop", "name": "ร้านข้าวมันไก่ของผม", "indoor": false, "time": "day|golden|night|overcast", "weather": "clear|rain",
     "image_prompt": "English prompt for an AI image generator: the EMPTY location (no people), vertical 9:16, key objects, time of day, mood, art style"}
  ],
  "arc": [{"ep": 1, "beat": "Thai, what happens and the cliffhanger"}],
  "episodes": 5,
  "seconds": 90,
  "next_ep": 1,
  "story": [],
  "cliff": "",
  "teaser": ""
}
```

Rules:
- Cast: the hero plus 3-6 others, the main antagonist first after the hero. Every look must be clearly different (hair, colours, face marks) so viewers recognise people instantly.
- `voice` is one of man, woman, oldman, oldwoman, boy, girl (for TTS casting).
- `rig` is how the stickman is drawn in the video. Every value must come from `python scripts/assets.py look`; `outfit` (optional) is a key from `assets.py outfits` and overrides the clothes. Translate `look` into `rig` and make every cast member clearly different (hair, hat, glasses, shirt colour, face marks).
- Places: 4-7, mixing public places (shop, market, street) with quiet ones (side street, home, office) for private talks.
- `image_prompt` describes the empty background only, so the same background can be reused in many shots.

## Episode: `drama/<slug>/epNN.json`

```json
{
  "ep": 1,
  "title": "EP1 ... (max 70 chars)",
  "hashtags": ["#ละครสั้น", "#..."],
  "cover_text": "max 22 chars",
  "shots": [ ...shots... ],
  "summary": "Thai, 2-3 sentences of what happened",
  "cliff": "Thai, the open question for the next EP (empty for the finale)",
  "teaser": "Thai, max 60 chars (empty for the finale)",
  "ask": "Thai, max 70 chars, spoken question to viewers",
  "advice": {"continue": true, "why": "Thai, 1 sentence", "next": "Thai, 1 sentence idea for the next EP"}
}
```

### Shot types

**scene** - people in a place:
```json
{"type": "scene", "place": "shop", "frame": "wide|medium|close|ots", "say": "narration|<cast id>",
 "chars": [{"id": "hero", "pos": "left|center|right", "action": "counting change behind the counter", "pose": "count_money", "prop": "coin", "face": "smug", "fx": "none", "then": "", "enter": ""}],
 "sfx": "optional, e.g. door bell, crowd murmur",
 "line": "Thai line"}
```
- `say`: `narration` = the hero talking to the viewer; or the cast id of who speaks. The speaker must be in `chars`.
- `pose`: the action key the stickman performs, from `python scripts/assets.py poses` (e.g. chop, count_money, sweep, phone, cross, rage, kneel_beg). `prop`: what they hold, from `assets.py props`, or omit. `action` stays as the human description.
- `then` (optional): a second pose the person switches to halfway through the line, e.g. `"pose": "stand", "then": "fall_back"` for someone who gets pushed while the pusher uses `"pose": "push"`. The fall plays out: stagger back, drop, bounce, then stays down (next shot in the same place keeps them on the floor if their pose is still a fall).
- `enter` (optional): `left` or `right` = the person walks in from that side of the frame.
- Movement poses really move: `walk` makes the person walk into place, `run` / `run_scared` (or `then: run_scared`) makes them run out of the frame, `then: walk` makes them walk away. Do not use them for someone who should stay put.
- Falls: fall_back, fall_forward, trip, slip, fall_sit (lands on the butt), knocked_out.
- `face`: neutral, happy, smug, angry, yell, shock, sad, cry, worried, scared, tired, disgust, confused, sly.
- `fx` (emotion mark, peaks only): none, vein (anger), sweat (nervous), tears, gloom (despair), sparkle (smug win).
- `frame`: close = one person chest up for a punchline; ots = over the shoulder for tense back-and-forth (2 people).
- Max 3 people, never two in the same `pos`.

**phone** - a phone screen shown full screen:
```json
{"type": "phone", "ui": "chat", "data": {"name": "กลุ่มไลน์ตลาด", "msgs": [{"me": false, "from": "pa_noi", "text": "..."}]}, "line": "optional lead-in by the hero"}
{"type": "phone", "ui": "review", "data": {"shop": "...", "stars": 1.5, "reviews": [{"name": "...", "stars": 1, "text": "..."}]}, "line": "the hero's narration about it"}
{"type": "phone", "ui": "live", "data": {"host": "pa_noi", "name": "live title", "viewers": "1.2K", "comments": [{"name": "...", "text": "..."}]}, "line": "what the host says on the live"}
{"type": "phone", "ui": "post", "data": {"group": "...", "author": "...", "text": "...", "likes": "356", "comments": [{"name": "...", "text": "..."}]}, "line": "..."}
{"type": "phone", "ui": "forum", "data": {"board": "...", "title": "...", "text": "...", "me": true, "answers": [{"name": "...", "text": "...", "votes": "320"}]}, "line": "..."}
{"type": "phone", "ui": "doc", "data": {"kind": "letter|slip|bill|certificate|form|police|court|medical|statement|notice|note", "title": "หมายศาล", "org": "issuing office", "lines": ["label: value"], "amount": "500,000 บาท", "stamp": "ด่วนที่สุด"}, "line": "the hero's narration about it"}
{"type": "phone", "ui": "system", "data": {"title": "ภารกิจใหม่", "lines": ["...", "..."], "reward": "..."}, "line": "the system notice read aloud, starting with ระบบ"}
```
- Limits: chats max 4 messages, reviews max 2, live/post comments max 2, forum answers max 3.
- Chat messages, post text, post comments, the forum question and answers are READ ALOUD by the writer's voice: natural spoken Thai, max 60 characters each. Reviews, live comments and documents are only shown.
- `system` only for heroes with a system power, max 4 per EP, title max 20 chars, lines max 30 chars.

**card** - a full-screen text card (time skip, chapter):
```json
{"type": "card", "text": "สามวันต่อมา", "line": "narration"}
```

### Counting length

Spoken characters = every `line` + read-aloud phone texts. Target ≈ seconds × 12 Thai characters. The checker counts it for you.
