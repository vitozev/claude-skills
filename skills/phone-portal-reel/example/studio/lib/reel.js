// The reference phone-portal reel (a made-up tea brand, Mossling): every frame is a pure function of time.
// Layers, back to front: the empty set (base), the 3D boxes, the phone and holding hand (with the screen's pages and
// the in-phone boxes seen through the glass), the boxes again below the screen's edge (the portal), the swiping hand
// (rigid forearm, bent at the wrist), the end-card wordmark. One grade and grain over everything.
// Moving frames average sub-frames over a 0.38-frame shutter (48 while a box falls, else 10), so motion blur comes
// from the motion itself.
//
// Measured on this build's plate, so re-measure them for yours: PW/PH, PHONE_C, PAGE, PX_PER_CM, EDGE_Y,
// SCREEN_TOP, SCREEN_H, SX, SCREEN_YAW, CAM, ARM (P, W, a, F), HOME, the arm-ext origin in COMP_FS, and the DROPS
// table (landing frames on your beat grid). layers.json carries the screen's corners and homography.
import * as THREE from 'three';
import * as M from './mossling.js';

export const FPS = 30;
export const DURATION = 9.0;           // 270 frames
const PW = 1152, PH = 2048;            // layer pixel space (the plate); the output is the same frame at 1080x1920

// ---- the script, in frames ---------------------------------------------------------------------------------
// a: anticipation starts, d: drag starts, dd: drag frames, snap: frames for the feed to settle after release,
// land: the frame the box hits the shelf (its fall takes 6 frames before that, from behind the phone).
// Flicks, not drags: the finger travels amp px in dd fast frames (the content under it moves with it), then lets go
// and the feed glides on into the next page. No two are the same. lift = the small up-move before, over = the
// follow-through after letting go, back = frames to return. The path is an arc because it comes from the wrist.
export const DROPS = [
  { f: 'chamomile', armK: 0.55, ant: 2, dd: 4, snap: 9, land: 16, x: -0.6, yaw: -4, roll: 3.0, spin: 5,
    amp: 92, lift: -8, over: 8, back: 9 },
  { f: 'earlgrey', armK: 0.45, ant: 2, dd: 5, snap: 10, land: 40, x: 0.8, yaw: 3, roll: -2.5, spin: -4,
    amp: 84, lift: -6, over: 6, back: 10 },
  { f: 'hibiscus', armK: 0.62, ant: 3, dd: 4, snap: 9, land: 64, x: -1.2, yaw: -2, roll: 2.0, spin: 6,
    amp: 100, lift: -10, over: 10, back: 8 },
  { f: 'chai', armK: 0.5, ant: 2, dd: 4, snap: 10, land: 88, x: 0.4, yaw: 5, roll: -3.0, spin: -3,
    amp: 88, lift: -7, over: 7, back: 10 },
  { f: 'rooibos', armK: 0.6, ant: 4, dd: 3, snap: 8, land: 112, x: 0.0, yaw: -1, roll: 3.5, spin: 7, heavy: true,
    amp: 112, lift: -12, over: 12, back: 9 },
];
const HOME = [[0, 0], [6, -4], [-4, 3], [7, 2], [-3, -5], [2, 0]];   // plate px, before swipe i
export const CUT = 128;                // hard cut to the stop-motion
export const STILL_FRAMES = 4;         // stop-motion on fours: one still per 16th note at 112.5 BPM
export const LOGO_IN = 205, LOGO_FRAMES = 8;
const SHUTTER = 0.38;                  // of a frame: about 1/80 s, a phone in daylight, a little crisper than 180°
const PHONE_C = [557, 712];            // the phone turns about its own centre (plate px)

// stop-motion: 16 stills turning a full circle, then 4 facing front ending on Rooibos
const SPIN = ['rooibos', 'chamomile', 'earlgrey', 'hibiscus', 'chai', 'rooibos', 'earlgrey', 'chamomile', 'chai', 'hibiscus',
  'rooibos', 'chamomile', 'hibiscus', 'earlgrey', 'chai', 'chamomile'];
const FRONT = ['chai', 'hibiscus', 'chamomile', 'rooibos'];

// ---- small helpers -------------------------------------------------------------------------------------------
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const p2in = (t) => t * t, p3out = (t) => 1 - (1 - t) ** 3, s2 = (t) => t * t * (3 - 2 * t);
const p2inout = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
function hash(i, salt = 0) { let x = Math.imul(i ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul(salt + 1, 0xc2b2ae35); x ^= x >>> 13; x = Math.imul(x, 0x27d4eb2f); x ^= x >>> 16; return (x >>> 0) / 4294967296; }
// slow, smooth, never-repeating drift (about -1..1): a held phone and a resting hand are never perfectly still
function drift(t, seed) {
  const F = [0.21, 0.37, 0.61, 1.07, 1.73];
  let v = 0, n = 0;
  F.forEach((f, i) => { const a = 1 / (1 + i * 0.9); v += a * Math.sin(2 * Math.PI * f * t + hash(i, seed) * 6.2832); n += a; });
  return v / n;
}
// ---- the box inside the phone -------------------------------------------------------------------------------------
// The box on the screen is not a picture: it is the real 3D box, seen through the glass by the same camera as the room,
// sitting in the phone turned -24° and tipped 11.5° so its end and a sliver of its top show (and turning slowly, like a
// product viewer). Scrolling moves it down; below the screen's bottom edge it is drawn in front of the bezel and the
// fingers. Being one object on both sides of the edge, it lines up by construction. Measured by projecting its corners
// through the room camera: where it rests (bottom 16 px above the edge), where it starts to come out and where it is
// fully out. From there it falls, levelling and turning to its resting pose, and lands on its frame.
const PAGE = 327, PX_PER_CM = 2813 / 91.5, G = 981;            // screen px per page; plate px per cm at the box's face
const EDGE_Y = 870.2, SCREEN_TOP = 544.4, SCREEN_H = 325.8;    // plate px: the screen's bottom edge at the box's x
const SX = -0.78, SCREEN_YAW = -24, SCREEN_PITCH = 0.2;         // the box's place and angle inside the phone
const CAM = new THREE.PerspectiveCamera(40, 1080 / 1920, 1, 400);
CAM.position.set(0, 10.8, 0); CAM.lookAt(0, 10.8, -100); CAM.updateMatrixWorld(); CAM.updateProjectionMatrix();
function boxYs(lift, yawDeg = SCREEN_YAW, pitch = SCREEN_PITCH) {   // [top, bottom] of the box on the frame, plate px
  const m = new THREE.Matrix4().compose(new THREE.Vector3(SX, lift + M.BOX.h / 2, -95),
    new THREE.Quaternion().setFromEuler(new THREE.Euler(pitch, yawDeg * Math.PI / 180, 0, 'YXZ')), new THREE.Vector3(1, 1, 1));
  let lo = Infinity, hi = -Infinity;
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) {
    const v = new THREE.Vector3(sx * M.BOX.w / 2, sy * M.BOX.h / 2, sz * M.BOX.d / 2).applyMatrix4(m).project(CAM);
    const y = (1 - v.y) / 2 * 2048; lo = Math.min(lo, y); hi = Math.max(hi, y);
  }
  return [lo, hi];
}
function liftWhere(which, y) { let lo = -20, hi = 80; for (let k = 0; k < 60; k++) { const m = (lo + hi) / 2; if (boxYs(m)[which] > y) lo = m; else hi = m; } return (lo + hi) / 2; }
const L0 = liftWhere(1, EDGE_Y - 16);          // at rest: its lowest point 16 px above the edge
const LIFT_IN = liftWhere(1, EDGE_Y);          // its lowest point reaches the edge: it starts to come out
const LIFT_OUT = liftWhere(0, EDGE_Y);         // its highest point passes the edge: fully out
const PAGE_CM = PAGE / PX_PER_CM;              // one page of scroll moves it this far
const SHADOW_Y = (boxYs(L0)[1] - SCREEN_TOP) / SCREEN_H;   // page fraction of its lowest point at rest
export function screenYaw(k, t) { return SCREEN_YAW + 5 * Math.sin(2 * Math.PI * 0.17 * t + k * 1.7); }
// the feed's travel (screen px) for one swipe, tau frames after the drag starts: follows the finger, then after
// release carries on at the finger's speed and eases into the next page (Hermite: position and speed continuous)
function feedPx(s, tau) {
  if (tau <= 0) return 0;
  if (tau < s.dd) { const u = tau / s.dd; return Math.max(0, lerp(s.lift, s.amp, u * u)) * 1.06; }
  const p0 = s.amp * 1.06, S = s.snap, x = Math.min(1, (tau - s.dd) / S);
  const v0 = Math.min(2 * (s.amp - s.lift) * 1.06 / s.dd, 2.8 * (PAGE - p0) / S);   // no overshoot past the page
  if (x >= 1) return PAGE;
  return (2 * x ** 3 - 3 * x ** 2 + 1) * p0 + (x ** 3 - 2 * x ** 2 + x) * S * v0 + (-2 * x ** 3 + 3 * x ** 2) * PAGE;
}
function tauAt(s, px) { let lo = 0, hi = s.dd + s.snap; for (let k = 0; k < 50; k++) { const m = (lo + hi) / 2; if (feedPx(s, m) < px) lo = m; else hi = m; } return (lo + hi) / 2; }
DROPS.forEach((s, k) => {
  s.k = k;
  // the scroll carries the box down until its lowest point reaches the glass's bottom edge; from that frame it is
  // falling: it keeps the scroll's speed and gravity takes over (it never slows with the page's glide)
  const px1 = (L0 - LIFT_IN) * PX_PER_CM;
  s.tau1 = tauAt(s, px1);
  const v1 = (feedPx(s, s.tau1 + 0.01) - feedPx(s, s.tau1 - 0.01)) / 0.02;     // screen px per frame at the edge
  s.vOut = v1 / PX_PER_CM * FPS;                                                // cm/s as it starts to come out
  const T = (-s.vOut + Math.sqrt(s.vOut * s.vOut + 2 * G * LIFT_IN)) / G;       // from the edge to the shelf
  s.E = s.land - T * FPS;                                                       // frame it starts to come out
  s.d = s.E - s.tau1;                                                           // the flick that makes it so
  s.a = s.d - s.ant;
});

// uneven stop-motion steps: a person turning a box by hand does not turn it 22.5° every time
const SPIN_YAW = (() => {
  const raw = SPIN.map((_, i) => 0.55 + hash(i, 7) * 0.9), sum = raw.reduce((x, y) => x + y, 0);
  let acc = 22; return raw.map((r) => { const y = acc; acc += (r / sum) * 360; return y; });
})();

// ---- state at time t (seconds) ---------------------------------------------------------------------------------
// hand: displacement (px, plate space), rotation and scale (lift toward the lens); phone: drift + press;
// feed: pages scrolled; boxes on the shelf or falling.
export function stateAt(t) {
  const fr = t * FPS;
  const fi = Math.round(fr);  // cuts and stills are decided per whole frame
  const st = { fr, scene: fi < CUT ? 'portal' : 'stop', hand: { dy: 0, scale: 1, reach: null, tx: 0, ty: 0, hx: 0, hy: 0, armK: 0.5 },
    phone: { dx: 0, dy: 0, rot: 0 }, feed: 0, feedVel: 0, boxes: [], logo: 0, logoY: 0, exposure: 1 };
  if (st.scene === 'portal') {
    let pages = 0, press = 0;
    for (let i = 0; i < DROPS.length; i++) {
      const s = DROPS[i];
      const dEnd = s.d + s.dd, back = dEnd + s.back;
      if (fr >= s.a && fr < back) {
        let dy, scale = 1;
        if (fr < s.d) {                                   // anticipation: a small lift
          dy = s.lift * s2((fr - s.a) / (s.d - s.a));
        } else if (fr < dEnd) {                           // the flick: accelerates, the content moves with it
          const u = (fr - s.d) / s.dd; dy = lerp(s.lift, s.amp, u * u); press = Math.sin(Math.PI * u);
        } else {                                          // let go: follow through, lift toward the lens, come back
          const k = (fr - dEnd) / (back - dEnd);
          const o = k < 0.2 ? p3out(k / 0.2) : 1, r = k < 0.2 ? 0 : p2inout((k - 0.2) / 0.8);
          dy = lerp(s.amp + s.over * o, 0, r) - 8 * Math.sin(Math.PI * r);
          scale = 1 + 0.015 * Math.sin(Math.PI * Math.min(1, k * 1.15));
        }
        let hx = HOME[i][0], hy = HOME[i][1];
        if (fr >= dEnd) { const k = p2inout(clamp((fr - dEnd) / (back - dEnd))); hx = lerp(HOME[i][0], HOME[i + 1][0], k); hy = lerp(HOME[i][1], HOME[i + 1][1], k); }
        st.hand = { dy, scale, reach: null, tx: 0, ty: 0, hx, hy, armK: s.armK };
      }
      // feed: follows the finger during the drag, then carries on into the next page
      if (fr >= s.d) pages = i + feedPx(s, fr - s.d) / PAGE;
    }
    for (let i = DROPS.length - 1; i >= 0; i--) {
      const s = DROPS[i];
      if (fr >= s.d + s.dd + s.back) { if (st.hand.dy === 0 && st.hand.hx === 0 && st.hand.hy === 0) { st.hand.hx = HOME[i + 1][0]; st.hand.hy = HOME[i + 1][1]; } break; }
    }
    const last = DROPS[DROPS.length - 1], leave0 = last.d + last.dd + last.back;
    if (fr >= leave0) { const k = p2inout(clamp((fr - leave0) / 16)); st.hand = { dy: 0, scale: 1 + 0.012 * k, reach: -60 * k, tx: 0, ty: 0, hx: HOME[5][0], hy: HOME[5][1], armK: 0 }; }   // draws the arm back
    st.feed = pages;
    st.press = press;
    // the holding hand drifts the phone a couple of pixels and gives under the finger's press
    st.phone = { dx: 1.5 * drift(t, 11), dy: 1.9 * drift(t, 12) + 2.4 * press, rot: 0.0032 * drift(t, 13) + 0.0022 * press };
    // the swiping hand rides along with the phone it touches, plus its own small sway
    st.hand.tx = st.phone.dx + 1.8 * drift(t, 21); st.hand.ty = st.phone.dy + 1.3 * drift(t, 22);
    // inside the phone: every box not yet fully out, at its place on the scrolling page (the screen clips the rest)
    DROPS.forEach((s, k) => {
      if (fr >= s.E) return;
      const lift = L0 + (k - pages) * PAGE_CM;
      if (lift > L0 + PAGE_CM * 1.05) return;
      st.boxes.push({ f: s.f, x: SX, z: -95, lift, yaw: screenYaw(k, t) * Math.PI / 180, roll: 0, tiltX: SCREEN_PITCH,
        cast: false, inScreen: true });
    });
    // falling out and on the shelf: the newest box that has started to come out. The one before it goes (a cut) on
    // the frame before the next starts to come out, while the eye is on the swipe
    for (let i = DROPS.length - 1; i >= 0; i--) {
      const s = DROPS[i];
      if (fr >= s.E) { st.boxes.push(dropPose(s, fr, t)); break; }
      if (Math.round(fr) >= Math.round(s.E) - 1) break;                         // shelf already cleared for it
    }
  } else {
    const k = Math.floor((fi - CUT) / STILL_FRAMES);
    const n = SPIN.length + FRONT.length;
    const i = Math.min(k, n - 1);
    const id = i < SPIN.length ? SPIN[i] : FRONT[i - SPIN.length];
    const yaw = i < SPIN.length ? SPIN_YAW[i] % 360 : (hash(i, 9) - 0.5) * 3;   // front-on stills are never quite square
    const jit = i === n - 1 ? 0 : 1;
    st.boxes.push({ f: id, x: (hash(i, 1) - 0.5) * 1.8 * jit, z: -95 + (hash(i, 2) - 0.5) * 1.6 * jit, lift: 0,
      yaw: (yaw + (hash(i, 3) - 0.5) * 3 * jit) * Math.PI / 180, roll: 0, tiltX: 0 });
    st.exposure = 1 + (hash(i, 4) - 0.5) * 0.025 * jit;   // stills flicker a hair, like a real stop-motion
    const e = p3out(clamp((fr - LOGO_IN) / LOGO_FRAMES));
    st.logo = e; st.logoY = 12 * (1 - e);               // the wordmark eases up into place, no bounce
  }
  return st;
}

function dropPose(s, fr, t) {
  let lift, roll = 0, tiltX = 0, yaw, x;
  const yawOut = screenYaw(s.k, s.E / FPS);
  if (fr < s.land) {
    // falling: out through the glass, levelling, turning and drifting to where it will rest
    const t2 = (fr - s.E) / FPS, kf = s2(clamp((fr - s.E) / (s.land - s.E)));
    lift = Math.max(0, LIFT_IN - s.vOut * t2 - 0.5 * G * t2 * t2);
    x = lerp(SX, s.x, kf); yaw = lerp(yawOut, s.yaw, kf);
    roll = (s.roll * Math.PI / 180) * kf; tiltX = lerp(SCREEN_PITCH, 0.015 * Math.sign(s.roll), kf);
  } else {
    // one low corner hits, the box slaps flat and rebounds a few millimetres, then settles
    const a = (fr - s.land) / FPS;
    const bounce = s.heavy ? 0.9 : 0.32, dur = s.heavy ? 0.14 : 0.1;
    lift = a < dur ? bounce * Math.sin(Math.PI * a / dur) : 0;
    const rr = s.heavy ? 4.5 : 1.2, decay = s.heavy ? 14 : 34, freq = s.heavy ? 48 : 70;
    roll = (rr * Math.PI / 180) * Math.sign(s.roll) * Math.exp(-a * decay) * Math.cos(a * freq);
    x = s.x; yaw = s.yaw - 0.6 * Math.sign(s.spin) * Math.exp(-a * 30) * Math.sin(a * 60);   // a last skid on the wood
  }
  return { f: s.f, x, z: -95, lift, yaw: yaw * Math.PI / 180, roll, tiltX, cast: true, inScreen: false };
}

// Is anything moving at this frame? (static frames render one sample)
function moving(t) {
  const a = stateAt(t - 0.25 / FPS), b = stateAt(t + 0.25 / FPS);
  if (a.scene !== b.scene) return true;
  if (a.scene === 'portal') return true;   // the held phone and hand always drift a little
  if (Math.abs(a.logo - b.logo) > 1e-4) return true;
  if (a.boxes.length !== b.boxes.length) return true;
  for (let i = 0; i < a.boxes.length; i++) if (Math.abs(a.boxes[i].lift - b.boxes[i].lift) > 1e-3 || Math.abs(a.boxes[i].roll - b.boxes[i].roll) > 1e-4) return true;
  return false;
}

// ---- the screen: plain light pages that scroll, each with a soft shadow under where its box rests ----------------
const FEED_W = 1424, FEED_H = 654;     // 2x the screen's plate size
function drawFeed(g, pages, pageCol) {
  g.fillStyle = pageCol; g.fillRect(0, 0, FEED_W, FEED_H);
  for (let k = 0; k < DROPS.length; k++) {
    const y = (pages - k) * FEED_H + SHADOW_Y * FEED_H + 6;
    if (y < -60 || y > FEED_H + 60) continue;
    const grd = g.createRadialGradient(FEED_W / 2, y, 4, FEED_W / 2, y, FEED_W * 0.36);
    grd.addColorStop(0, 'rgba(60,52,44,0.22)'); grd.addColorStop(0.55, 'rgba(60,52,44,0.08)'); grd.addColorStop(1, 'rgba(60,52,44,0)');
    g.save(); g.translate(0, y); g.scale(1, 0.09); g.translate(0, -y);
    g.fillStyle = grd; g.fillRect(0, y - FEED_W * 0.4, FEED_W, FEED_W * 0.8); g.restore();
  }
}

// ---- the swiping arm -----------------------------------------------------------------------------------------------
// Measured on master.png (plate px): the forearm runs up and right along (0.80, -0.59); the wrist joint (just past the
// cuff, where the hand bends) is at (1045, 250); the fingertip at (490, 618). A flick comes from the wrist: the hand turns about
// the wrist joint while the forearm and cuff move as one piece and lower (down, and a little right, so nothing
// has to come in from past the right edge). Each swipe splits the travel between arm and wrist differently (armK).
// The wrist turn is solved so the fingertip travels exactly with the content.
const ARM = { P: [1525, -104], W: [1045, 250], a: [-0.80, 0.59], F: [490, 618] };
export function solveArm(h) {
  const [Px, Py] = ARM.P, [Wx, Wy] = ARM.W, [ax, ay] = ARM.a, [Fx, Fy] = ARM.F, sc = h.scale;
  const lower = h.reach != null ? 0 : h.armK * h.dy;                 // the forearm's own drop for this swipe
  const t = h.reach != null ? h.reach : 0;
  const T = [t * ax + h.tx + h.hx + 0.35 * lower, t * ay + h.ty + h.hy + lower];
  const tipY = (phi) => {   // texture -> wrist flex about W -> forearm (scale about the elbow, then move)
    const c = Math.cos(phi), sn = Math.sin(phi), fx = Fx - Wx, fy = Fy - Wy;
    const y1 = Wy + sn * fx + c * fy; return Py + sc * (y1 - Py) + T[1];
  };
  let phi = 0;
  if (h.reach == null) {
    const goal = Fy + h.dy + h.ty + h.hy;
    for (let k = 0; k < 12; k++) { const f = tipY(phi) - goal, d = (tipY(phi + 1e-4) - tipY(phi - 1e-4)) / 2e-4; phi -= f / d; }
  }
  return { th: 0, sc, T, phi };
}

// ---- the compositor -------------------------------------------------------------------------------------------
const VS = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const COMP_FS = `
precision highp float;
varying vec2 vUv;
uniform sampler2D tBase, tPhone, tHand, tArmExt, tScreen, tFeed, tLayer, tLogo;
uniform float uPortal, uLogo, uExposure, uSat, uLift, uSoft;
uniform vec3 uTint;
uniform vec2 uArmP; uniform float uArmRot; uniform float uArmS; uniform vec2 uArmT; uniform vec2 uWristP; uniform float uWristRot; uniform vec2 uAxis;
uniform mat3 uPhoneInv; uniform vec2 uEdgeA; uniform vec2 uEdgeB; uniform float uLogoY; uniform mat3 uScrInv; uniform vec2 uRes;
const vec2 PS = vec2(${PW}.0, ${PH}.0);
vec3 neutral(vec3 c){
  const float S = 0.76; const float D = 0.15; c *= uExposure;
  float x = min(c.r, min(c.g, c.b)); float off = x < 0.08 ? x - 6.25*x*x : 0.04; c -= off;
  float p = max(c.r, max(c.g, c.b)); if (p < S) return c;
  float d = 1.0 - S; float np = 1.0 - d*d/(p + d - S); c *= np/p;
  float g = 1.0 - 1.0/(D*(p - np) + 1.0); return mix(c, vec3(np), g);
}
vec3 toSRGB(vec3 c){ c = clamp(c, 0.0, 1.0); return mix(c*12.92, 1.055*pow(c, vec3(1.0/2.4)) - 0.055, step(0.0031308, c)); }
vec4 layerSoft(vec2 uv){
  vec2 px = uSoft / uRes;
  vec4 L = texture2D(tLayer, uv)*0.25;
  L += (texture2D(tLayer, uv + vec2(px.x,0.)) + texture2D(tLayer, uv - vec2(px.x,0.)) + texture2D(tLayer, uv + vec2(0.,px.y)) + texture2D(tLayer, uv - vec2(0.,px.y)))*0.125;
  L += (texture2D(tLayer, uv + px) + texture2D(tLayer, uv - px) + texture2D(tLayer, uv + vec2(px.x,-px.y)) + texture2D(tLayer, uv + vec2(-px.x,px.y)))*0.0625;
  return L;
}
vec3 gradeBox(vec4 L){
  float a = clamp(L.a, 0.0, 1.0);
  vec3 bc = a > 1e-4 ? L.rgb / a : vec3(0.0);
  bc = toSRGB(neutral(bc)); float luma = dot(bc, vec3(0.2126, 0.7152, 0.0722));
  bc = mix(vec3(luma), bc, uSat) * uTint; return uLift + bc*(1.0 - uLift);
}
void main(){
  vec2 q = vec2(vUv.x, 1.0 - vUv.y) * PS;           // plate pixels, y down
  vec3 col = texture2D(tBase, vUv).rgb;
  // 3D boxes over the wall and shelf (premultiplied, linear -> display)
  vec4 L = layerSoft(vUv); float a = clamp(L.a, 0.0, 1.0);
  vec3 bc = gradeBox(L);
  if (uPortal < 0.5) col = bc * a + col * (1.0 - a);
  if (uPortal > 0.5) {
    // phone + holding hand: drifts a little in the hand and gives under the finger's press
    vec2 qp = (uPhoneInv * vec3(q, 1.0)).xy;
    vec2 up = vec2(qp.x, PS.y - qp.y) / PS;
    vec4 ph = texture2D(tPhone, up);
    vec4 sc = texture2D(tScreen, up);              // r: the blank screen's own light, a: screen
    vec3 h = uScrInv * vec3(qp, 1.0); vec2 su = h.xy / h.z;  // 0..1 across the screen
    vec3 feed = texture2D(tFeed, vec2(su.x, 1.0 - su.y)).rgb;
    // the boxes inside the phone: the same 3D render, seen through the glass, moving with the phone
    vec4 Ls = layerSoft(vec2(qp.x, PS.y - qp.y) / PS); float aScr = clamp(Ls.a, 0.0, 1.0);
    vec3 content = mix(feed, gradeBox(Ls), aScr);
    // as filmed: a little dimmer than paper white, the glass carrying the room's reflections
    vec3 lit = content * 0.94 + 0.025 + (sc.r - 0.5) * 0.4;
    vec3 phoneCol = mix(ph.rgb, lit, sc.a);
    col = mix(col, phoneCol, ph.a);
    // the boxes: in front of the phone and the fingers, but only below the screen's bottom edge (above it, the box is
    // still inside the phone and shows through the glass). The edge moves with the phone.
    vec2 ed = uEdgeB - uEdgeA;
    float below = (ed.x * (qp.y - uEdgeA.y) - ed.y * (qp.x - uEdgeA.x)) / length(ed);
    float portal = smoothstep(-2.2, 2.2, below);
    col = bc * a * portal + col * (1.0 - a * portal);
    // the swiping hand: forearm, cuff and hand move as one rigid piece that lowers; the wrist bends past the cuff
    vec2 r1 = q - uArmT - uArmP;
    float ca = cos(-uArmRot), sa = sin(-uArmRot);
    vec2 p1 = uArmP + vec2(ca*r1.x - sa*r1.y, sa*r1.x + ca*r1.y) / uArmS;
    float wf = smoothstep(0.0, 150.0, dot(p1 - uWristP, uAxis));
    float cw = cos(-uWristRot * wf), sw = sin(-uWristRot * wf);
    vec2 r2 = p1 - uWristP;
    vec2 src = uWristP + vec2(cw*r2.x - sw*r2.y, sw*r2.x + cw*r2.y);
    // beyond the frame: the sleeve from the fitted outpaint (assets/layers/arm-ext.png, origin (384,-256), 1024 px)
    vec4 hd;
    if (src.y < 0.0 || src.x > PS.x) hd = texture2D(tArmExt, vec2((src.x - 384.0) / 1024.0, 1.0 - (src.y + 256.0) / 1024.0));
    else hd = texture2D(tHand, vec2(src.x, PS.y - src.y) / PS);
    col = mix(col, hd.rgb, hd.a);
  }
  vec4 lg = texture2D(tLogo, vUv + vec2(0.0, uLogoY / PS.y));
  col = mix(col, lg.rgb, lg.a * uLogo);
  gl_FragColor = vec4(col, 1.0);
}`;
const OUT_FS = `
precision highp float;
varying vec2 vUv; uniform sampler2D tAcc; uniform float uSeed, uGrain;
float hash(vec2 p){ p = fract(p*vec2(443.897, 441.423) + uSeed*0.1031); p += dot(p, p.yx + 19.19); return fract((p.x + p.y)*p.x); }
void main(){
  vec3 c = texture2D(tAcc, vUv).rgb;
  float n = hash(gl_FragCoord.xy) + hash(gl_FragCoord.xy + 17.0) - 1.0;
  c += n * uGrain * (0.55 + 0.45 * (1.0 - abs(dot(c, vec3(0.33)) - 0.5) * 2.0));
  gl_FragColor = vec4(c, 1.0);
}`;

function loadImage(src) { return new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = src; }); }
function imgTex(im, flipY = true) {
  const t = new THREE.Texture(im); t.colorSpace = THREE.NoColorSpace; t.flipY = flipY;
  t.minFilter = THREE.LinearFilter; t.magFilter = THREE.LinearFilter; t.generateMipmaps = false;
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping; t.needsUpdate = true; return t;
}

export async function createReel(canvas, { width = 1080, height = 1920, base = '' } = {}) {
  const { bots } = await M.loadAssets(base);
  const [baseIm, phoneIm, handIm, armIm, screenIm, meta] = await Promise.all([
    loadImage(`${base}assets/layers/base.png`), loadImage(`${base}assets/layers/phone.png`), loadImage(`${base}assets/layers/hand.png`), loadImage(`${base}assets/layers/arm-ext.png`),
    loadImage(`${base}assets/layers/screen.png`), fetch(`${base}assets/layers/layers.json`).then((r) => r.json())]);
  const pageCol = '#e9e8e4';

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1); renderer.setSize(width, height, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.shadowMap.autoUpdate = true;
  const world = M.makeWorld(renderer, width / height, 1024);
  const boxes = {}, pads = {};
  for (const f of M.FLAVOURS) { boxes[f.id] = [M.makeBox(f, bots, renderer), M.makeBox(f, bots, renderer)]; }
  for (const f of M.FLAVOURS) for (const b of boxes[f.id]) { b.visible = false; world.scene.add(b); }
  const padPool = [world.contactFor(), world.contactFor(), world.contactFor(), world.contactFor()];

  const layerRT = new THREE.WebGLRenderTarget(width, height, { type: THREE.HalfFloatType, samples: 4 });
  const accRT = new THREE.WebGLRenderTarget(width, height, { type: THREE.FloatType });
  const feedCv = document.createElement('canvas'); feedCv.width = FEED_W; feedCv.height = FEED_H;
  const feedG = feedCv.getContext('2d');
  const feedTex = new THREE.CanvasTexture(feedCv); feedTex.colorSpace = THREE.NoColorSpace; feedTex.generateMipmaps = false; feedTex.minFilter = THREE.LinearFilter;
  const logoCv = document.createElement('canvas'); logoCv.width = width; logoCv.height = height;
  drawLogo(logoCv.getContext('2d'), width, height);
  const logoTex = new THREE.CanvasTexture(logoCv); logoTex.colorSpace = THREE.NoColorSpace;

  // inverse of the screen homography (unit square -> plate px)
  const Hm = new THREE.Matrix3().set(...meta.screen_H_unit_to_px.flat());
  const Hinv = Hm.clone().invert();

  const comp = new THREE.ShaderMaterial({
    vertexShader: VS, fragmentShader: COMP_FS, depthTest: false, depthWrite: false, transparent: true,
    blending: THREE.AdditiveBlending,
    uniforms: {
      tBase: { value: imgTex(baseIm) }, tPhone: { value: imgTex(phoneIm) }, tHand: { value: imgTex(handIm) }, tArmExt: { value: imgTex(armIm) },
      tScreen: { value: imgTex(screenIm) }, tFeed: { value: feedTex }, tLayer: { value: layerRT.texture }, tLogo: { value: logoTex },
      uPortal: { value: 1 }, uLogo: { value: 0 }, uExposure: { value: 1 }, uSat: { value: 0.86 }, uLift: { value: 0.025 },
      uSoft: { value: 0.75 }, uTint: { value: new THREE.Vector3(1.02, 1.0, 0.95) },
      uArmP: { value: new THREE.Vector2(...ARM.P) }, uArmRot: { value: 0 }, uArmS: { value: 1 }, uArmT: { value: new THREE.Vector2() },
      uWristP: { value: new THREE.Vector2(...ARM.W) }, uWristRot: { value: 0 }, uAxis: { value: new THREE.Vector2(...ARM.a) },
      uPhoneInv: { value: new THREE.Matrix3() }, uEdgeA: { value: new THREE.Vector2(...meta.screen_corners_TL_TR_BR_BL[3]) }, uEdgeB: { value: new THREE.Vector2(...meta.screen_corners_TL_TR_BR_BL[2]) }, uLogoY: { value: 0 }, uScrInv: { value: Hinv },
      uRes: { value: new THREE.Vector2(width, height) }, uWeight: { value: 1 },
    },
  });
  // weight each sub-frame by 1/K through the blend: premultiply in the shader output
  comp.fragmentShader = comp.fragmentShader.replace('gl_FragColor = vec4(col, 1.0);', 'gl_FragColor = vec4(col * uWeight, 1.0);').replace('uniform vec2 uRes;', 'uniform vec2 uRes; uniform float uWeight;');
  const out = new THREE.ShaderMaterial({ vertexShader: VS, fragmentShader: OUT_FS, depthTest: false, depthWrite: false,
    uniforms: { tAcc: { value: accRT.texture }, uSeed: { value: 1 }, uGrain: { value: 0.02 } } });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), comp);
  const qs = new THREE.Scene(); qs.add(quad); const qc = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

  function applyState(st) {
    for (const f of M.FLAVOURS) for (const b of boxes[f.id]) b.visible = false;
    padPool.forEach((p) => (p.visible = false));
    const used = {};
    st.boxes.forEach((b, i) => {
      const slot = used[b.f] || 0; used[b.f] = slot + 1;
      const mesh = boxes[b.f][slot]; mesh.visible = true; mesh.castShadow = !!b.cast; padPool[i].visible = b.lift < 4;
      M.pose(mesh, padPool[i], { x: b.x, z: b.z, lift: b.lift, yaw: b.yaw, tiltZ: b.roll, tiltX: b.tiltX });
    });
    const maxLift = st.boxes.filter((b) => b.cast).reduce((m, b) => Math.max(m, b.lift), 0);
    world.catcher.material.opacity = 0.42 * Math.exp(-maxLift / 3.5);
    const u = comp.uniforms;
    u.uPortal.value = st.scene === 'portal' ? 1 : 0;
    { const A = solveArm(st.hand); u.uArmRot.value = A.th; u.uArmS.value = A.sc; u.uArmT.value.set(A.T[0], A.T[1]); u.uWristRot.value = A.phi; }
    { // inverse of: turn by rot about the phone's centre, then move by (dx, dy)
      const c = Math.cos(st.phone.rot), sn = Math.sin(st.phone.rot), [cx, cy] = PHONE_C, tx = cx + st.phone.dx, ty = cy + st.phone.dy;
      u.uPhoneInv.value.set(c, sn, -c * tx - sn * ty + cx, -sn, c, sn * tx - c * ty + cy, 0, 0, 1);
    }
    u.uLogo.value = st.logo; u.uLogoY.value = st.logoY; u.uExposure.value = st.exposure;
    if (st.scene === 'portal') { drawFeed(feedG, st.feed, pageCol); feedTex.needsUpdate = true; }
  }

  function renderAt(t) {
    const frame = Math.round(t * FPS);
    const st0 = stateAt(t);
    const falling = st0.boxes.some((b) => b.lift > 0.6);
    const K = moving(t) ? (falling ? 48 : 10) : 1;
    renderer.setRenderTarget(accRT); renderer.setClearColor(0x000000, 1); renderer.clear();
    for (let k = 0; k < K; k++) {
      const tk = K === 1 ? t : t + ((k + 0.5) / K - 0.5) * (SHUTTER / FPS);   // shutter centred on the frame
      const st = stateAt(tk);
      st.feedVel = (stateAt(tk + 0.004).feed - stateAt(tk - 0.004).feed) / 0.008;  // pages per second
      applyState(st);
      renderer.setRenderTarget(layerRT); renderer.setClearColor(0x000000, 0); renderer.clear();
      renderer.render(world.scene, world.camera);
      comp.uniforms.uWeight.value = 1 / K;
      quad.material = comp;
      renderer.setRenderTarget(accRT); renderer.autoClear = false; renderer.render(qs, qc); renderer.autoClear = true;
    }
    out.uniforms.uSeed.value = frame + 1;
    quad.material = out;
    renderer.setRenderTarget(null); renderer.render(qs, qc);
    quad.material = comp;
  }
  return { renderAt, stateAt };
}

// The end card: wordmark in espresso ink, "TEA CO." under it, upper third, inside the title-safe band.
function drawLogo(g, w, h) {
  g.clearRect(0, 0, w, h);
  const ink = '#33241a';
  g.fillStyle = ink;
  M.drawWordmark(g, w / 2, h * 0.335, 190, ink);
  g.font = '34px MosslingSans';
  const t = 'TEA CO.'; let x = w / 2; const tr = 12;
  const ws = [...t].map((c) => g.measureText(c).width); const tot = ws.reduce((a, b) => a + b, 0) + tr * (t.length - 1);
  x -= tot / 2; [...t].forEach((c, i) => { g.fillText(c, x, h * 0.335 + 70); x += ws[i] + tr; });
}
