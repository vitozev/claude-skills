# The reference build

This is the code of one finished reel. Mossling Tea Co. is a made-up loose-leaf tea brand with five boxes
(Chamomile, Earl Grey, Hibiscus, Chai, and Rooibos as the hero) on sage tiles and a walnut sideboard. It is 9 s
long, 1080x1920, at 30 fps, with music at 112.5 BPM.

The generated images, fonts and audio are not included. Make your own with the steps in `../references/build.md`,
then copy this folder and re-measure the constants listed at the top of `studio/lib/reel.js`.

| File | What |
|---|---|
| `look/prompt-plate.txt` | The prompt for the empty set (`gpt-image-2`, 1152x2048) |
| `look/prompt-hands.txt` | The edit prompt that adds both hands and the blank phone to the plate. This makes the master |
| `look/layers/polys.json` | Rough outlines of the hand and the phone, traced on the master in plate pixels |
| `look/layers.py` | Cuts the master into `base`, `phone`, `hand` and `screen`, and writes `layers.json` |
| `studio/assets/layers/layers.json` | What `layers.py` measured on this plate: screen corners and homography, fingertip, arm entry |
| `look/armext.py` | Builds the sleeve beyond the frame edge from a fitted outpaint |
| `studio/index.html` | The HyperFrames composition: one canvas, one `<audio>`, rendered on `hf-seek` |
| `studio/lib/reel.js` | The engine: the drops table, the solver, the hand, the compositor shader, motion blur |
| `studio/lib/mossling.js` | The product: flavours, label drawing, box mesh and materials, set lighting, camera |
| `sound/spec.json` | The music and foley prompts, for `../scripts/elevenlabs.py` |
| `sound/mix.py` | Places the hits on their frames, adds the dead stop and the tape-stop, and masters to -14 LUFS |

## Running it

```text
project/
  look/master.png                    ← the master: plate plus hands and phone
  look/layers/clean-hand.png         ← the master with the swiping hand removed (blend-edit.py)
  look/layers/clean-all.png          ← the master with both hands and the phone removed
  look/layers/polys.json             ← your traced outlines
  look/layers/arm-ext15.png          ← an outpaint of the sleeve past the frame edge, for armext.py
  studio/assets/layers/   ← layers.py and armext.py write here
  studio/assets/fonts/    ← your fonts (mossling.js names them)
  studio/assets/bot/      ← the label art, one PNG per product
  studio/lib/three/       ← three.module.js, RoundedBoxGeometry.js and RoomEnvironment.js from three@0.169.0
  sound/sfx/              ← elevenlabs.py writes here
```

Run these from the project folder. `$SKILL` is this skill's folder.

```bash
python3 look/layers.py && python3 look/armext.py
python3 $SKILL/scripts/elevenlabs.py sound/spec.json sound/sfx
python3 $SKILL/scripts/beats.py sound/sfx/bed_v1-*.mp3
python3 sound/mix.py
cd studio && npx hyperframes@0.9.19 snapshot --at 0.5,1.3,3.7 && npx hyperframes@0.9.19 render -q delivery -o ../review/reel.mp4
```

Open `studio/index.html?t=1.23` in the preview to see a single frame.
