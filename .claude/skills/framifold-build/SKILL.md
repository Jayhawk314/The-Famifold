---
name: framifold-build
description: Build a video from a Framifold plan (the JSON exported by the Framifold app). Use when given a Framifold plan or brief, asked to "make the video from this plan", fill its requests, or render a draft. Covers any style: documentary, screen tour, CG/Blender, mood piece, explainer.
---

# Building a video from a Framifold plan

The plan is the contract. James fills in what he knows; everything else is yours to propose, find or make.
`framifold/render.py` turns any plan into a video, so your work is the same for every film:
**turn requests into real files, write them into the plan, render, look, repeat.**

## 0. Read the plan before anything

- `meta.strictness` decides how free you are:
  - **Strict**: filled fields are exact. Change nothing. Ask James before inventing anything for a blank.
  - **Balanced**: follow filled fields; propose blanks and mark them as proposals.
  - **Loosey-goosey**: everything is an idea. Improve freely, then list every change and why.
- `meta.rules` and `meta.look` override this skill wherever they disagree.
- Render the plan untouched first (`python framifold/render.py plan.json`). The draft, with orange stand-in cards
  where requests are, is the clearest picture of what is still missing. Read the `.report.md` next to it.

## 1. The plan's fields (what render.py does with them)

| Field | Meaning |
|---|---|
| `segments[]` | the film in order; `duration_s` sets the length, the rest (story, mood, narration, voice) is intent |
| `clips[].lane` | Visual, Overlay / text (pictures) · Voice, SFX, Music (sounds) |
| `start`, `end` | seconds on the film's clock |
| `layer` | overlapping clips in a lane stack; all play together; a higher picture layer covers a lower one |
| `asset_path` | the file. Empty = a REQUEST: `request` says what is wanted |
| `level` | sounds: volume 0-1. Pictures: 0-1 opacity (see-through), 1-1.5 brighter |
| `pan` | -1 left … +1 right |
| `fade_in`, `fade_out` | seconds |
| `trim_in` | start this many seconds into the file |
| `loop` | repeat the file to fill the clip |
| `placement` | Full screen, Picture-in-picture top right / bottom left, Centred small, Left half, Right half, Lower third |

To fill a request: put the file's absolute path in `asset_path` and its name in `asset_name`; leave the
request text in place as the record of what was asked for. Never move, lengthen or delete James's clips to make
something fit unless the strictness allows it; say what does not fit instead.

## 2. Turning requests into files: pick the right maker

- **Sounds and music:** Freesound CC0 first (`komposos-labs-videos/market_system_video/tools/freesound.py search
  "<words>"`, then `get <id> <out.mp3>`), which logs source and licence. ElevenLabs sound effects or music only
  with James's yes (credits).
- **Photos and historical images:** Wikimedia Commons, reuse-safe licences only (public domain, CC0, CC BY,
  CC BY-SA): `market_system_video/tools/commons.py` to search, `commons_get.py` to fetch and log.
- **CG and motion:** Blender, headless:
  `"C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" --background --factory-startup --python scene.py -- <out_dir>`.
  Render PNG frames (RGBA if it floats over other layers), then make a clip with ffmpeg. Load the installed
  Blender skills for the craft: `blender-director` (plan), `camera-cinematography`, `lighting`, `materials`,
  `animation`, `compositing`, `vfx-fx`, `stylized-style` or `lowpoly-style` (look). Worked examples:
  `market_system_video/blender/*.py` (dial wall, floating robot, hawk flight, spark).
- **Screens of real software:** record the real app with Playwright, logging the moment each action finishes so
  the cut lands on it (`market_system_video/captures.py`, `scripts/capture_live.py`).
- **Text cards and captions:** HTML rendered to PNG with Playwright (`market_system_video/cards.py`), placed on
  the Overlay lane, usually Lower third.
- **Voice:** ElevenLabs, one file per paragraph so cuts land on paragraphs. Key in `komposos-labs-videos/.env`
  (never print it). **Ask James before any recording**, with a character count and cost estimate. Use the
  plan's voice choice; never "River"; never imitate a real person's voice.
- **AI-generated images:** only in a clearly illustrative style, never anything that could pass for a real
  event, person or document.

Log every outside file's source and licence (an `assets/_licenses.json` row) as you fetch it.

## 3. Craft: what makes it feel like a film

The plan gives structure; feeling comes from these. Use them on purpose and say where you did.

- **Breath.** Leave air: half a second after a paragraph, longer before and after the line that matters most.
  Silence is a sound; plan it.
- **Rhythm.** Vary shot length. Quick cuts, then one long hold. A held image after a hard line lets it land.
- **Sound in layers** (think of Walter Murch's idea of sound as half the picture): a room or world tone under
  everything at low volume, a few specific sounds that match what is seen (a bell when the bell is shown), music
  that steps back under the voice (around 0.2-0.3) and rises in the gaps. Pan sounds toward where their source
  is on screen. Fade everything in and out; hard starts sound like mistakes unless they are meant.
- **One idea per image.** If the narration names something, show that thing then, not before or after.
- **Motion with a reason.** A slow push-in to draw the eye, a held frame for weight. No drifting effects for
  their own sake.
- **Picture-in-picture and lower thirds** are for evidence and names, not decoration.
- **End on an image, not a title.** Let the last sound ring out over it.

## 4. Look before you say it is done

- Render, then **look**: a frame at about 15% and 80% of every segment, beside that segment's story and
  narration (`market_system_video/tools/review.py` does this for its own format; for a plan, pull frames with
  ffmpeg at those times). Listen to the mix at the busiest moments.
- Check the report: planned length = rendered length; no MISSING FILE; nothing cut at the end by accident.
- Measure what you claim. "The bell is on the left" means you measured left vs right
  (`ffmpeg -i out.mp4 -af astats=measure_perchannel=RMS_level -f null -`).

## 5. Report honestly

Tell James: what you made or found (with sources and licences), what you proposed in blanks, what is still a
stand-in, what did not fit the plan, and anything that looks wrong. If something is wrong, say so plainly; never
crop, cut or reword around it. Ask before any credit spend, upload, publish or push.
