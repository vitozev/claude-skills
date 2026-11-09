# Building a phone-portal reel

These are the steps and numbers from the reference build in `example/`: a made-up loose-leaf tea brand with five
boxes, on sage tiles and a walnut sideboard. It renders at 1080x1920, 30 fps, 270 frames.

## 1. Brief and beat sheet

- **Goal:** the viewer wants the product, and nobody can tell the reel was generated.
- **Products:** 4 to 6, each in its own colour that reads against the set. The hero drops last and stars in the end
  card. Give it the colour that complements the set, such as terracotta on sage.
- **Tempo:** choose a BPM where a beat is a whole number of frames (`frames = 1800 / BPM` at 30 fps). At 112.5 BPM a
  beat is 16 frames, a 16th note is 4 and a bar is 64.
- **Beat sheet** (the reference):

| Drop | Lands | On the grid | Notes |
|---|---|---|---|
| 1 | f16 | beat 2 | The reel opens with the finger already moving: motion in the first 2 frames |
| 2 | f40 | beat 3½ | |
| 3 | f64 | beat 5 | |
| 4 | f88 | beat 6½ | |
| — | f96–f112 | | The music stops dead for one beat. The hand pauses on the hero |
| 5 (hero) | f112 | beat 8 | The music comes back in. A heavier landing with a bigger bounce: the one oversized moment |
| Cut | f128 | bar 3 | A hard cut on the bar line to the stop-motion: 20 stills on fours, f128–f207 |
| Logo | f205–f213 | | The last still (the hero, facing front) arrives at f204 and holds to the end. The wordmark fades in over it, then holds about 2 s |

The ordinary drops land every 24 frames, a dotted quarter (1.5 beats), so they fall alternately on the beat and
on the half-beat between. That syncopation against a steady kick is what makes the drops feel played, not
metronomic. Land only on beats or half-beats, never between them.

**Other numbers of products.** Keep these fixed: the first landing at f16 (the hook), one beat of dead stop
before the hero (f96–f112), the hero at f112 and the cut at f128. Space the ordinary drops evenly from f16, all
on the half-beat grid (multiples of 8 frames at 112.5 BPM):

| Products | Ordinary drops land | Gap |
|---|---|---|
| 4 | f16, f48, f80 | 32 frames (2 beats), all on beats |
| 5 | f16, f40, f64, f88 | 24 frames (1.5 beats), alternately on the beat and the half-beat: the reference |
| 6 | f16, f32, f48, f64, f80 | 16 frames (1 beat), the tightest a swipe allows |

One swipe cycle (lift, flick, follow-through, return) takes about 16 frames at the least, so 6 products is the
most that fits. With 7 or more, lengthen the reel by a bar.

- **Hook:** something moves in the first 2 frames.
- **Sound at the end:** a soft rising tone peaks at f208 as the wordmark settles. The music tape-stops from f208
  over 1.25 s, and room tone carries the rest.

## 2. Plate and master

**Plate** (`gpt-image-2`, `--size 1152x2048 --quality medium`). It must be divisible by 16, then scale it ×0.9375
to 1080x1920. Describe the empty set as a real photograph:

- a vertical frame from a full-frame camera locked on a tripod, 50 mm at f/5.6, straight-on, just above the shelf;
- the front edge of the shelf exactly two thirds of the way down, with a thin band of shelf top above it;
- a plain wall, in focus, with no decorations;
- soft window light from one side, a faint warm bounce and very fine grain;
- no people, no objects, no text.

**Master** (an edit of the plate with `gpt-image-2`). Keep the exact photograph and add only two hands and a phone:

- a black phone held sideways, centred, its centre about a quarter of the way down, about 70% of the frame wide, its
  screen on and plain light grey with no interface;
- the holding hand behind and below, with only its fingertips showing under the bottom edge;
- the swiping hand coming in from a top corner, with its index finger resting on the upper third of the screen;
- a **bare wrist** under a soft knit cuff, with no watch, bracelet or rings (see `lessons.md`);
- five fingers, short clean nails, the same light, and no text.

Ask for 2 options and pick the one with the cleanest hands. The edit relights the wall a little, so from here on
the master is the frame. Never go back to the plate.

**Clean plates** are edits of the master: one with the swiping hand removed (`clean-hand`), and one with both hands
and the phone removed (`clean-all`). The model redraws the whole image and moves things, so take each edit only
inside its mask, registered and tone-matched (`scripts/blend-edit.py`). For rigid things like the phone, register
on the screen's four corners. They give an exact homography where SIFT finds only a handful of matches.

## 3. Layers

`example/look/layers.py` cuts the master into these layers, all at 1152x2048:

| Layer | What |
|---|---|
| `base.png` | The empty set: the master, with the hands and phone filled in from `clean-all` |
| `phone.png` | RGBA: the phone and whatever shows of the holding hand (the thumb along the top edge, the fingertips under it). Where the swiping hand covered them, `clean-hand` fills in |
| `hand.png` | RGBA: the swiping hand, forearm and cuff |
| `screen.png` | The blank screen's own light (high-passed): reflections to lay over the feed |
| `arm-ext.png` | The sleeve beyond the frame edge, for when the arm moves inward (`example/look/armext.py`) |
| `layers.json` | The screen's corners and homography, the fingertip, and where the arm enters the frame |

Matting:

- Trace each outline on a fine grid by hand. Then let GrabCut decide only a band of ±10 to 12 px around it.
  **Everything outside that band is sure background (`GC_BGD`).** If it's only "probable", the matte floods the wall.
- Where skin meets skin (the two hands), draw the boundary by hand.
- Soften the matte with a guided filter. Join overlapping mattes as a union, `1-(1-a)(1-b)`, never a max: a max
  leaves a dark seam.
- Strip wall-coloured pixels that ride along in a matte.
- Under the moving hand, fill the whole overlap from the registered clean plate, screen included, and inpaint the
  screen's light map there.

## 4. Camera

Measure the shelf's back and front edges on the plate, then fit a three.js camera to them. The reference has a 40°
vertical field of view and the camera 10.8 cm above the shelf, with the wall at 117 cm and the shelf's front edge
at 72 cm. A box at z = -95 cm is about 41% of the frame wide.

## 5. Product

- Build it as a real 3D model. For a carton, use `RoundedBoxGeometry` with a 1.4 mm edge radius and an uncoated card
  material (roughness about 0.62, a light sheen, a little seeded paper fibre per face).
- Draw labels in code on a canvas, so the small print stays sharp. A linocut botanical from `gpt-image-2`, keyed to
  alpha and tinted with the ink colour, gives the label art.
- Light it to match the plate: a near point light where the window is, with soft shadows, a sky hemisphere, a warm
  bounce from the shelf, `RoomEnvironment` reflections at about 0.55 and a contact shadow pad.
- Grade the 3D layer to sit in the photo: a neutral tonemap, a 0.75 px soften, saturation 0.86, a warm tint, a 2.5%
  lift, then grain (full on the 3D, about 35% on the plate).
- Size the product to about 40% of the frame's width at its resting depth, inside the safe area.

### Other products

The reference is a carton. These notes cover what changes for other shapes. They are not yet proven in a finished
reel, so render a still of each one at the look gate.

- **Round things (jars, bottles, cans):** use a `LatheGeometry` profile or a cylinder, with the label as a wrap
  texture. The solver needs the product's lowest and highest points on the frame. Project the corners of its
  bounding box (`Box3` of the mesh), which is exact for a box and slightly conservative for a cylinder.
- **Landing:** a box hits on one low corner and slaps flat. A round base lands on one edge of its rim, rocks once or
  twice and settles. A lid or cap follows through 2 to 4 frames later with a tiny tilt or rattle.
- **Glass:** the 3D layer is rendered with nothing behind it (the plate is composited later), so real transmission
  or refraction samples black. Either fake it as dense tinted glass (`MeshPhysicalMaterial`, low transmission, a
  clearcoat, and strong environment reflections), or put the plate in the 3D scene as a backdrop plane so the glass
  has something to refract. The second costs a render pass and needs the backdrop to line up with the plate exactly.
- **Identical containers** (all amber jars, all silver cans): give each product its own colour on the label, the lid
  or the liquid, and give the hero's the colour that complements the set.
- **Stop-motion on a symmetric product:** turning it shows only the wrap label. Make each still a new pose: the
  label turned, the lid off, set at an angle, moved a little, or a different product. A front-on still is never
  quite square.

## 6. The engine (`example/studio/lib/reel.js`)

Every frame is a pure function of time. The compositor draws, back to front: the base, the 3D layer, the phone and
holding hand (with the screen content and the in-phone 3D seen through the glass), the 3D again below the screen
edge (the portal), the swiping hand, then the logo, the grade and the grain.

**The swipe is a flick, not a drag.** Each swipe has its own parameters: travel 84 to 112 px, drag 3 to 5 frames,
a lift of 6 to 12 px before it, follow-through, and a return of 8 to 10 frames. The page follows the finger, then
glides into the next page on a Hermite curve, so its position and speed stay continuous. The fingertip arcs because
the hand turns at the wrist.

**The arm is rigid.** The forearm and cuff move as one piece that lowers by `armK × travel` (0.45 to 0.62 per swipe),
down and a little sideways, so nothing has to come in from past the frame edge. The wrist bends for the rest. Its
angle is solved by Newton's method each frame so that the fingertip moves exactly with the page. Between swipes,
the hand rests at a slightly different spot each time.

**The product in the phone is the real 3D box.** It sits inside the phone, turned about -24°, tipped slightly and
turning slowly, like a product viewer. It is rendered by the room camera and composited through the glass in the
phone's own coordinates, so it moves with the phone. The solver projects the box's corners through the camera to
find three heights: where it rests (its bottom 16 px above the edge), where its lowest point reaches the edge, and
where it is fully out.

**Timing is solved backward from the landing.** For each drop:

1. find the scroll time `tau1` at which the box's lowest point reaches the screen edge, and the scroll's speed
   there, `vOut`;
2. find the fall time from the edge to the shelf under gravity, starting at `vOut`:
   `T = (-vOut + sqrt(vOut² + 2·g·h)) / g`;
3. the box starts to come out at `E = land - T·fps`, so the flick starts at `E - tau1`, with its anticipation
   before that.

While it falls, the box levels out and turns into its resting angle (3 to 7°), drifting to where it will rest.
When it lands, one low corner hits first and it slaps flat. Then it bounces 3 mm (9 mm for the hero) and makes a
last small skid on the wood. The previous box disappears (a cut) on the frame before the next one starts to come
out, while the eye is on the swipe.

**Handheld life.** The phone drifts 1.5 to 1.9 px with a 0.2° turn, on slow, never-repeating sums of sines, and gives
2.4 px under each press. The swiping hand rides with the phone and sways 1 to 2 px of its own. The wall is locked.

**Motion blur.** Average sub-frames over a 0.38-frame shutter (about 1/80 s, a phone in daylight): 48 sub-frames
while a product falls, 10 while anything else moves, and 1 on a still frame. Decide cuts, swaps and stop-motion
stills on the rounded frame number, so the shutter samples never straddle them.

**Stop-motion.** Use 20 stills on fours. Turn the box unevenly, 12 to 35° per still, and add a few millimetres of
jitter and a 2.5% exposure flicker. The last 4 stills face the front (never quite square) and run through the line,
ending on the hero.

**Screen content.** Plain light pages, about `#e9e8e4`, each with a soft shadow under its box. Put no dividers
between pages. At about 0.94 brightness plus the screen's own reflections, the glass reads as filmed.

**HyperFrames wiring.** `example/studio/index.html` holds one canvas and one `<audio>`. A GSAP timeline only carries
the length. The engine renders on `hf-seek` and registers `window.__hf.buildReady`. Add `?t=1.23` to the page URL
to view one frame.

## 7. Sound

- **Music** (ElevenLabs `POST /v1/music`, `music_v2_5`, `force_instrumental`): ask for "exactly 112 BPM, 4/4, starts
  at once on the downbeat, no intro, no fade-in", with dry, crisp transients. Measure it with `scripts/beats.py`.
  Stretch it to the exact grid with `atempo` (112 → 112.5 is `atempo=1.004464`). Then measure the transients
  against the frame grid again: ours sat 25 ms late until we nudged them.
- **Dead stop:** cut the music with a 6 ms fade after the last ordinary landing's beat. Let it re-enter on the hero's
  landing. It is the strongest beat in the piece.
- **Tape-stop under the logo:** read the bed with a slowing head (`speed = (1-u)^1.6` over 1.25 s), and use a
  one-pole low-pass that slides from 16 kHz to 400 Hz. Filtering in FFT blocks clicks at every block edge.
- **Foley** (`/v1/sound-generation`): write the prompt for the real materials and the real drop. For example,
  "a small cardboard tea box dropped from 20 cm lands flat on an oiled walnut sideboard: one short dull papery thud,
  close-miked, dry, no echo", or, for a jar, "a small glass candle jar with a wooden lid set down hard on an oak
  shelf: a short knock with a faint glass ring, the lid ticking once". Use a different take for each landing,
  never the same sound twice in a row. Trim each take to 4 ms before its loudest attack, so any rustle before it is
  gone, and align it on that attack. If a take has several separate impacts but the product lands once, keep the
  first impact and fade the rest out over about 18 ms. Keep a ring or a rattle that belongs to that one landing.
  Set the landings 6.5 dB under the music and the hero 3.5 dB under. Bright sounds like a glass clink read louder,
  so check them by ear. Add a soft rising tone as the logo lands, and room tone about 30 dB under the music, coming up once the
  music has stopped.
- **Master:** iterate the gain through a limiter (`alimiter=limit=0.79`) to -13.6 LUFS. The AAC encode in the render
  loses about 0.5 LU, so the delivered file lands near -14.
- Write a stem of the effects alone, so `scripts/sync-sheet.py --audio` can find every hit.

## 8. Render and check

- Use `npx hyperframes render -q delivery -o review/reel.mp4`. A preview render at `-q looks` takes about 3 minutes
  per 51 frames with the 3D layer. `npx hyperframes snapshot` is much faster for stills, at about 1 s each on the GPU.
- Check every contact moment at full size on the delivered file, then run the sync sheet and the loudness check.
- **Costs in the reference build:** about $1.20 of OpenAI images over all rounds, and 264 ElevenLabs credits.
