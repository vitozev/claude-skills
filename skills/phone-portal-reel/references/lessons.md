# Lessons

Each of these broke the illusion in the reference build. Most were spotted by a viewer in a single frame. Each one
gives what showed, why it happened, and the fix.

## The portal

- **The product appeared under the phone a few frames after it left the screen.** The flat picture on the screen
  and the falling box were separate things, and their timings didn't meet. A gap of 4 to 6 frames reads as a cut.
  *Fix:* put the real 3D box inside the phone and solve each swipe backward from its landing frame
  (`build.md`, section 6).
- **The box fell behind the holding hand.** It was drawn under the phone layer. *Fix:* below the screen's bottom
  edge, composite the box over the bezel and the fingers. The edge moves with the phone, feathered over about 4 px.
- **The box hung under the phone for about 5 frames.** It kept following the page's glide, which slows down.
  *Fix:* from the frame its lowest point reaches the edge, it falls under gravity, starting at the scroll's speed.
- **The box sat 12 to 14 px off its picture on the screen.** The picture and the box were drawn separately.
  *Fix:* one object, one camera. Then it lines up by construction. Measure the hand-off on the frame, never in theory.
- **The box looked like two objects.** The screen was dim and washed out next to a fully lit box. *Fix:* screen
  gain about 0.94, smaller reflections.
- **The label crossing the edge showed twice.** The picture was a different size from the real box, and its speed
  was converted at the wrong depth. *Fix:* the 3D box in the phone (see above).

## The hand

- **The swipe read as a sliding photo.** *Fix:* make it a flick from the wrist, about 9 to 12°. The forearm and cuff
  move as one rigid piece that lowers, and the wrist angle is solved so the fingertip moves with the page.
  Vary every swipe: travel, sideways drift, the arc, the follow-through and the return. Lift the hand about 1.7%
  toward the lens as it comes back.
- **The watch slid on the wrist.** A spatial warp pinned at the frame edge shears whatever sits near the pin.
  A rigid arm fixed the slide, but a watch frozen while the hand moves under it still reads as pasted on. *Fix:*
  **no accessories on the moving hand.** Ask for a bare wrist in the master.
- **The watch was still there after it was removed.** The strap's lower end, where it wraps under the wrist, sat
  outside the mask. A second edit then drew a piece of strap back in, inside its own mask. *Fix:* mask the whole
  accessory (face, strap, buckle, the part under the wrist). Run a small second pass on whatever survives. Check
  the **delivered file** at full size, in every frame where the wrist shows. A snapshot is not enough.
- **A lighter band showed at the frame edge.** An 18 px cross-fade blended generated sleeve into the original
  photo. *Fix:* inside the frame, never blend generated pixels into the photo. Blend only beyond the edge.
- **A reflected sleeve showed a seam, and later a copy of the watch.** *Fix:* a fitted outpaint for the sleeve beyond
  the frame (rigid fit by silhouette overlap; affine ECC collapsed), with the reflection capped at 22 px deep.
  Keep swipes small enough that little picture is needed from beyond the frame.
- **A frozen hand gave it away as a photo.** *Fix:* the held phone drifts and gives under the press, and the
  swiping hand rides along with its own sway. The wall stays locked, because the camera is on a tripod.

## The screen

- **A dark line moved through the phone during every swipe.** A 14 px divider between pages, doubled by the
  screen's ghosting. *Fix:* pages butt together, and the ghost is at 30% or less.
- **Ghosting during scroll should be subtle.** A real screen on camera shows 2 or 3 faint copies when it scrolls
  fast. Too much reads as a glitch.

## Images

- **Masked edits are not respected.** `gpt-image-2` redraws the whole frame. The wall stays within 1 to 2 px, but
  objects move: the phone shifted about 22 px, and a sleeve outside the mask vanished. *Fix:* take an edit only
  inside its mask. Register it first, by rigid features or ECC on the untouched area, then tone-match it on a ring
  around the region (`scripts/blend-edit.py`).
- **Ask for the hard part first.** The edit that adds hands also relights the wall, so the master becomes the frame.
  Make the clean plates from the master, not the original plate.
- **For small fixes, edit a crop.** Crop about 256 px around the problem, scale it to 1024, edit it with
  `gpt-image-1.5` at `input_fidelity: high`, and blend it back. ECC registration of 0.96 is typical.
- **API limits (Nov 2026):** `gpt-image-2` takes any size divisible by 16, but refuses `background: transparent` and
  `input_fidelity`. To get a cutout, generate on white and key it.
- **Matting:** everything outside the GrabCut band must be sure background. Union-join overlapping mattes.

## Motion and rendering

- **A cut turned into a dissolve.** The shutter samples straddled it. *Fix:* decide anything discrete on the whole
  frame.
- **A falling label printed as a comb of copies.** At about 200 px per frame it needs about 48 sub-frames.
- **A 180° shutter smeared the fall.** A 0.38-frame shutter keeps the box readable.
- **Stop-motion by hand is uneven.** Turn it 12 to 35° per still, with jitter, and keep the front-on stills never
  quite square.
- **A shader variable named `up` rendered black frames.** It redefined a built-in name, and only the browser console
  showed it. Open the page in a browser and read the console when frames come out black.

## Sound

- **The hiss landed before the box.** The effect takes had rustle ahead of the impact. *Fix:* trim to 4 ms before the
  attack.
- **One thud was early.** That take opened with a small tick. *Fix:* align on the loudest transient, not the first.
- **One thud was a tumble.** It had three knocks in 130 ms, but the box lands once. *Fix:* keep the first knock and
  fade the rest out over about 18 ms.
- **Loudness failed at -15.1 LUFS.** A limiter eats level. *Fix:* iterate the gain until the limited mix measures
  the target, and aim 0.4 LU hot for the AAC encode.
- **The beat grid was 25 ms late after the stretch.** *Fix:* measure the transients against the frame grid again
  after `atempo`.
