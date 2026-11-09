---
name: phone-portal-reel
description: Use when making a short vertical product reel (Instagram Reels, TikTok, YouTube Shorts) in which a hand swipes a phone and each product falls out of the screen into the real scene, or any "phone portal", "swipe to drop" or "falls out of the screen" ad, especially when there is no camera footage and the set, hands and product have to be generated.
---

# Phone-portal reel

## Overview

A 9-second 9:16 product ad shot on one locked tripod frame, in three beats:

1. **Portal drops (about 4.3 s).** A hand holds a phone. A second hand swipes it, and each swipe drops one product
   out of the screen onto a shelf below, landing on the beat. The hero product drops last, after a dead stop in
   the music.
2. **Stop-motion shuffle (about 2.7 s).** A hard cut removes the hands and phone. The product turns through the
   whole line, one still per 16th note, held on fours.
3. **Logo hold (about 2 s).** The wordmark fades in over 6 to 8 frames and holds still. Music only, no voice.

There is no camera footage. One generated photo is cut into layers (set, phone and holding hand, swiping hand) and
animated in code. The product is a real 3D model, rendered by the same camera inside the phone and in the room, so
it crosses the glass as one object.

**The bar:** it passes as a real shoot. Every failure we hit was a continuity break that someone saw in a single
frame. Look at full size, at every contact moment, on the delivered file.

## You need

| Need | For |
|---|---|
| `OPENAI_API_KEY` | `gpt-image-2` for the plate and master; `gpt-image-1.5` with `input_fidelity: high` for edits that must keep the photo |
| `ELEVENLABS_API_KEY` | The music bed (`music_v2_5`) and foley |
| HyperFrames CLI (`npx hyperframes`), three.js r169 | The frame engine and the render |
| ffmpeg; Python 3 with `numpy opencv-python-headless pillow openai` | The scripts |

The scripts read keys from the environment, or from a `.env` in the working folder or any folder above it. They
never print them. Report what each run spends: OpenAI dollars (the scripts log an estimate) and ElevenLabs credits.

If someone can film a real hand swiping a phone on a tripod, use that footage for the hand. It is the hardest part
to fake.

## Gates: stop for an OK at each

1. **Brief and beat sheet.** The brand, 4 to 6 products (the hero last, in the colour that complements the set),
   the set, and a tempo where a beat is a whole number of frames. At 30 fps, 112.5 BPM gives 16 frames, 120 BPM
   gives 15 and 90 BPM gives 20. Put every landing on the music's grid, on a beat or a half-beat, never between.
   For the number of drops, see `references/build.md`, section 1.
2. **Look.** The plate, the master (hands and phone), a first render of the 3D product in the fitted camera, and
   the end card set in 3 font pairings, all on one sheet.
3. **Motion test.** One swipe and one drop, rendered at delivery quality and checked frame by frame. Most failures
   show up here.
4. **Build, then sound, then the final.**

## Build

Follow `references/build.md`. It has every step, with the numbers that worked. In order:

1. Generate a plate (the empty set), then a master: one edit of the plate that adds both hands and a blank phone.
   **The master is the frame.** Every clean plate is made from it.
2. Cut layers from the master and measure the screen corners, the screen's bottom edge, the fingertip and the
   wrist.
3. Fit the 3D camera to the shelf's edges.
4. Build the engine. Copy `example/studio/` (the reference build: a tea brand, five boxes) and re-measure its
   constants for your plate. It holds code only: bring your own images, fonts, label art and three.js files. If the
   product is not a carton (a jar, a bottle, a can, anything glass), read "Other products" in `build.md` first.
5. Make the music first and measure its beats. Then lock the landings to the grid, add foley and mix.
6. Render, then run the checks below.

## Rules that broke the illusion

| What showed | Fix |
|---|---|
| The product appears under the phone a few frames late | It is one 3D object on both sides of the glass. Solve each swipe backward from its landing frame: from the frame its lowest point reaches the edge, it falls under gravity at the scroll's speed |
| The product falls behind the hand | Below the screen's bottom edge, draw it in front of the bezel and the fingers |
| It hangs under the phone for a few frames | Gravity takes over at the edge. Don't let it keep following the page's glide |
| The swipe reads as a sliding photo | Flick from the wrist and keep the forearm rigid. Solve the wrist angle so the fingertip moves with the page. No two swipes alike |
| The frame looks like a still | The held phone drifts 1.5 to 2 px and gives under each press. The wall never moves |
| A dark line moves through the phone | No page dividers in the feed. Keep any ghosting low |
| A watch or jewellery slides on the wrist | Ask for a bare wrist in the master. If one gets in, mask all of it and remove it with `scripts/blend-edit.py` |
| A cut turns into a dissolve | Decide every cut, swap and still on the whole frame, never inside the shutter samples |
| The label prints as a comb of copies | Use 48 sub-frames while the product falls and 10 otherwise, with a 0.38-frame shutter |
| A generated edit moved things outside its mask | Masked edits are not respected. Register the edit, then take it only inside the mask |
| A thud lands before the box | Trim each take to 4 ms before its loudest attack, and align on that attack |

The full list, with causes, is in `references/lessons.md`.

## Check before sending

- Full-size crops of the delivered file at every contact moment: each swipe's first frame, the product crossing
  the edge, each landing, the cut, and the arm leaving the frame.
- `python3 scripts/sync-sheet.py final.mp4 --audio sound/stems/sfx.wav`: each hit sits on its outlined frame.
- `bash scripts/check-final.sh final.mp4 1080x1920`: -14 LUFS ±1 and a true peak at or below -1 dBTP.

## Scripts

| Script | Does |
|---|---|
| `scripts/openai-image.py OUT.png "prompt" [--edit IN.png --mask M.png --fidelity high]` | Generates or edits one image and logs tokens and an estimated cost |
| `scripts/blend-edit.py crop` / `blend` | Prepares a masked edit of one region, then registers the result and takes it only inside the mask |
| `scripts/elevenlabs.py spec.json OUTDIR` | Generates the music bed and effects from a spec, caches them and logs the credits spent |
| `scripts/beats.py bed.mp3` | Finds the bed's tempo, its beat grid and its first downbeat |
| `scripts/sync-sheet.py VIDEO --audio sfx.wav` or `--cues cues.json` | Shows the five frames around every sound hit, on one sheet |
| `bash scripts/check-final.sh VIDEO [WxH]` | Checks size, fps, duration, loudness and true peak |

Run each with `--help` for its options. `example/README.md` maps the reference build.
