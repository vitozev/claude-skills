// Mossling Tea Co.: the label art, 3D boxes and a camera matched to the set plate.
// Units are centimetres. The shelf top is y = 0, the wall is at z = -117 and the shelf front edge at z = -72.
// The camera sits at (0, 10.8, 0), looks straight down -z, vertical FOV 40°. Fitted to master.png:
// the back edge projects to y=1283 and the front edge to y=1445 of 2048.
import * as THREE from 'three';
import { RoundedBoxGeometry } from './three/RoundedBoxGeometry.js';
import { RoomEnvironment } from './three/RoomEnvironment.js';

export const FLAVOURS = [
  { id: 'chamomile', name: 'Chamomile', base: '#e2b94f', ink: '#4a3214', notes: 'Egyptian chamomile, honeyed and calm', brew: '5 min · 95°C', blend: 'Herbal · caffeine free' },
  { id: 'earlgrey', name: 'Earl Grey', base: '#6c8cad', ink: '#f4eee2', notes: 'Ceylon black tea, cold-pressed bergamot', brew: '4 min · 95°C', blend: 'Black tea' },
  { id: 'hibiscus', name: 'Hibiscus', base: '#b3305a', ink: '#f7e7e1', notes: 'Hibiscus calyx, rosehip, a little orange peel', brew: '6 min · 100°C', blend: 'Herbal · caffeine free' },
  { id: 'chai', name: 'Chai', base: '#58383e', ink: '#ecd9b6', notes: 'Assam, cinnamon, cardamom, ginger, clove', brew: '5 min · 100°C', blend: 'Spiced black tea' },
  { id: 'rooibos', name: 'Rooibos', base: '#c05e39', ink: '#f7eada', notes: 'Cederberg red bush, vanilla, honeybush', brew: '6 min · 100°C', blend: 'Herbal · caffeine free' },
];
export const byId = Object.fromEntries(FLAVOURS.map((f) => [f.id, f]));

export const BOX = { w: 15, h: 7.5, d: 7 }; // cm
export const SET = { camY: 10.8, fov: 40, wallZ: -117, frontZ: -72 };

// ---- seeded noise ----------------------------------------------------------------------------------------
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---- assets ----------------------------------------------------------------------------------------------
const FONT_FILES = [
  ['MosslingWord', 'assets/fonts/MosslingWord.ttf'],
  ['MosslingItalic', 'assets/fonts/MosslingItalic.ttf'],
  ['MosslingSerifText', 'assets/fonts/MosslingSerifText.ttf'],
  ['MosslingSans', 'assets/fonts/MosslingSans.ttf'],
  ['MosslingSansReg', 'assets/fonts/MosslingSansReg.ttf'],
];
export async function loadAssets(base = '') {
  await Promise.all(FONT_FILES.map(async ([fam, url]) => {
    const ff = new FontFace(fam, `url(${base}${url})`);
    await ff.load();
    document.fonts.add(ff);
  }));
  const bots = {};
  await Promise.all(FLAVOURS.map((f) => new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => { bots[f.id] = im; res(); };
    im.onerror = rej;
    im.src = `${base}assets/bot/${f.id}.png`;
  })));
  return { bots };
}

// ---- label drawing ---------------------------------------------------------------------------------------
function tinted(img, color, w, h) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d');
  g.drawImage(img, 0, 0, w, h);
  g.globalCompositeOperation = 'source-in';
  g.fillStyle = color; g.fillRect(0, 0, w, h);
  return c;
}

// "Mossling" with a leaf for the dot of the i.
export function drawWordmark(g, x, y, size, color, align = 'center') {
  g.save();
  g.fillStyle = color;
  g.font = `${size}px MosslingWord`;
  g.textBaseline = 'alphabetic';
  const a = 'Mossl', i = 'ı', b = 'ng';
  const wa = g.measureText(a).width, wi = g.measureText(i).width, wb = g.measureText(b).width;
  const total = wa + wi + wb - size * 0.02;
  let x0 = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
  g.fillText(a, x0, y);
  g.fillText(i, x0 + wa - size * 0.01, y);
  g.fillText(b, x0 + wa + wi - size * 0.02, y);
  // leaf on a short stem sprouting from the i: base at the stem top, blade leaning up-right
  const sx = x0 + wa + wi * 0.5 - size * 0.012, sy = y - size * 0.55;
  g.translate(sx, sy);
  g.lineCap = 'round';
  g.strokeStyle = color; g.lineWidth = size * 0.028;
  g.beginPath(); g.moveTo(0, 0); g.quadraticCurveTo(size * 0.0, -size * 0.08, size * 0.02, -size * 0.14); g.stroke();
  g.translate(size * 0.02, -size * 0.14); g.rotate(-0.95);
  const L = size * 0.24, W = size * 0.105;
  g.beginPath();
  g.moveTo(0, 0);
  g.bezierCurveTo(L * 0.25, -W, L * 0.8, -W * 0.85, L, 0);
  g.bezierCurveTo(L * 0.75, W * 0.7, L * 0.2, W * 0.75, 0, 0);
  g.fill();
  g.globalCompositeOperation = 'destination-out';
  g.lineWidth = size * 0.011; g.beginPath(); g.moveTo(L * 0.1, 0); g.quadraticCurveTo(L * 0.5, -W * 0.12, L * 0.86, -W * 0.02); g.stroke();
  g.restore();
  return total;
}

function spaced(g, text, x, y, tracking, align = 'center') {
  const chars = [...text];
  const widths = chars.map((ch) => g.measureText(ch).width);
  const total = widths.reduce((s, w) => s + w, 0) + tracking * (chars.length - 1);
  let cx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
  chars.forEach((ch, k) => { g.fillText(ch, cx, y); cx += widths[k] + tracking; });
  return total;
}

// Uncoated card: a little fibre and ink unevenness, seeded per face so every box differs a hair.
function paper(g, w, h, seed, strength = 1) {
  const rnd = mulberry32(seed);
  const img = g.getImageData(0, 0, w, h);
  const d = img.data;
  for (let k = 0; k < d.length; k += 4) {
    const n = (rnd() - 0.5) * 9 * strength;
    d[k] += n; d[k + 1] += n; d[k + 2] += n;
  }
  g.putImageData(img, 0, 0);
  g.save();
  g.globalAlpha = 0.05 * strength;
  for (let k = 0; k < 900; k++) {
    g.strokeStyle = rnd() < 0.5 ? '#000' : '#fff';
    g.lineWidth = 0.6 + rnd();
    const x = rnd() * w, y = rnd() * h, a = rnd() * Math.PI, l = 6 + rnd() * 22;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke();
  }
  g.restore();
}

function canvas(w, h) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; return [c, c.getContext('2d')];
}

export function drawFront(f, bots, w = 2048, h = 1024, seed = 1) {
  const [c, g] = canvas(w, h);
  g.fillStyle = f.base; g.fillRect(0, 0, w, h);
  // botanical, big and cropped by the left edge, like a print run off the panel
  // fitted inside the left 36% (taller drawings run a little off the bottom edge, wide ones stay clear of the type)
  const bot = bots[f.id];
  const sc = Math.min((h * 1.0) / bot.height, (w * 0.36) / bot.width);
  const bw = bot.width * sc, bh = bot.height * sc;
  g.globalAlpha = 0.92;
  g.drawImage(tinted(bot, f.ink, Math.round(bw), Math.round(bh)), w * 0.035, h * 0.06 + (h * 1.0 - bh) * 0.5);
  g.globalAlpha = 1;
  // type block, centred in the right 62%
  const cx = w * 0.67;
  g.fillStyle = f.ink;
  drawWordmark(g, cx, h * 0.46, h * 0.27, f.ink);
  g.font = `${h * 0.032}px MosslingSans`;
  spaced(g, 'TEA CO.', cx, h * 0.555, h * 0.012);
  g.fillRect(cx - h * 0.16, h * 0.605, h * 0.32, h * 0.006);
  g.font = `${h * 0.115}px MosslingItalic`;
  g.textAlign = 'center';
  g.fillText(f.name, cx, h * 0.735);
  g.textAlign = 'left';
  g.font = `${h * 0.03}px MosslingSans`;
  spaced(g, 'LOOSE-LEAF TEA · 20 PYRAMID BAGS', cx, h * 0.83, h * 0.008);
  paper(g, w, h, seed);
  return c;
}

export function drawBack(f, bots, w = 2048, h = 1024, seed = 2) {
  const [c, g] = canvas(w, h);
  g.fillStyle = f.base; g.fillRect(0, 0, w, h);
  g.fillStyle = f.ink;
  drawWordmark(g, w * 0.08, h * 0.3, h * 0.16, f.ink, 'left');
  g.font = `${h * 0.07}px MosslingItalic`;
  g.fillText(f.name, w * 0.08, h * 0.45);
  g.font = `${h * 0.04}px MosslingSerifText`;
  g.fillText(f.notes + '.', w * 0.08, h * 0.56);
  g.fillText(f.blend + '.', w * 0.08, h * 0.62);
  g.font = `${h * 0.036}px MosslingSans`;
  spaced(g, 'BREW ' + f.brew.toUpperCase(), w * 0.08, h * 0.74, h * 0.006, 'left');
  g.font = `${h * 0.03}px MosslingSansReg`;
  g.fillText('Packed by hand in small batches. Keep dry, keep the lid closed.', w * 0.08, h * 0.84);
  const bot = bots[f.id]; const bh = h * 0.7, bw = bot.width * (bh / bot.height);
  g.globalAlpha = 0.85; g.drawImage(tinted(bot, f.ink, Math.round(bw), Math.round(bh)), w * 0.94 - bw, h * 0.15); g.globalAlpha = 1;
  paper(g, w, h, seed);
  return c;
}

export function drawTop(f, bots, w = 2048, h = 956, seed = 3) {
  const [c, g] = canvas(w, h);
  g.fillStyle = f.base; g.fillRect(0, 0, w, h);
  const bot = bots[f.id]; const s = h * 0.34, bw = bot.width * (s / bot.height);
  const t = tinted(bot, f.ink, Math.round(bw), Math.round(s));
  g.globalAlpha = 0.16;
  const rnd = mulberry32(seed * 7);
  for (let row = -1; row < 4; row++) for (let col = -1; col < 9; col++) {
    const x = col * bw * 1.25 + (row % 2) * bw * 0.6, y = row * s * 0.9;
    g.save(); g.translate(x + bw / 2, y + s / 2); g.rotate((rnd() - 0.5) * 0.5); g.drawImage(t, -bw / 2, -s / 2); g.restore();
  }
  g.globalAlpha = 1;
  // the tuck flap crease along the back edge
  g.strokeStyle = 'rgba(0,0,0,0.18)'; g.lineWidth = 3;
  g.beginPath(); g.moveTo(0, h * 0.06); g.lineTo(w, h * 0.06); g.stroke();
  paper(g, w, h, seed);
  return c;
}

export function drawEnd(f, bots, w = 956, h = 1024, seed = 4) {
  const [c, g] = canvas(w, h);
  g.fillStyle = f.base; g.fillRect(0, 0, w, h);
  g.fillStyle = f.ink;
  drawWordmark(g, w / 2, h * 0.42, h * 0.17, f.ink);
  g.font = `${h * 0.085}px MosslingItalic`;
  g.textAlign = 'center'; g.fillText(f.name, w / 2, h * 0.58); g.textAlign = 'left';
  g.font = `${h * 0.032}px MosslingSans`;
  spaced(g, f.brew.toUpperCase(), w / 2, h * 0.7, h * 0.006);
  // tuck-end flap: crease, slit and a thumb notch
  g.strokeStyle = 'rgba(0,0,0,0.22)'; g.lineWidth = 3;
  g.beginPath(); g.moveTo(w * 0.04, h * 0.1); g.lineTo(w * 0.96, h * 0.1); g.stroke();
  g.fillStyle = 'rgba(0,0,0,0.25)';
  g.beginPath(); g.ellipse(w / 2, h * 0.1, w * 0.07, h * 0.035, 0, 0, Math.PI); g.fill();
  paper(g, w, h, seed);
  return c;
}

export function drawBottom(f, w = 2048, h = 956, seed = 5) {
  const [c, g] = canvas(w, h);
  g.fillStyle = f.base; g.fillRect(0, 0, w, h);
  paper(g, w, h, seed);
  return c;
}

// ---- 3D -------------------------------------------------------------------------------------------------
function tex(canvasEl, renderer) {
  const t = new THREE.CanvasTexture(canvasEl);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return t;
}

const matCache = new Map();
export function boxMaterials(f, bots, renderer) {
  if (matCache.has(f.id)) return matCache.get(f.id);
  const card = (cv) => new THREE.MeshPhysicalMaterial({
    map: tex(cv, renderer), roughness: 0.62, metalness: 0, sheen: 0.25, sheenRoughness: 0.8,
    sheenColor: new THREE.Color('#ffffff'), envMapIntensity: 0.55,
  });
  const end = drawEnd(f, bots);
  // BoxGeometry face order: +x, -x, +y, -y, +z, -z
  const mats = [card(end), card(drawEnd(f, bots, 956, 1024, 9)), card(drawTop(f, bots)), card(drawBottom(f)),
    card(drawFront(f, bots)), card(drawBack(f, bots))];
  matCache.set(f.id, mats);
  return mats;
}

let sharedGeo = null;
export function makeBox(f, bots, renderer) {
  if (!sharedGeo) sharedGeo = new RoundedBoxGeometry(BOX.w, BOX.h, BOX.d, 3, 0.14);
  const m = new THREE.Mesh(sharedGeo, boxMaterials(f, bots, renderer));
  m.castShadow = true;
  return m;
}

// A soft dark pad under the box: contact shadow / ambient occlusion on the walnut.
function contactTexture() {
  const [c, g] = canvas(256, 256);
  const grd = g.createRadialGradient(128, 128, 10, 128, 128, 128);
  grd.addColorStop(0, 'rgba(0,0,0,1)'); grd.addColorStop(0.55, 'rgba(0,0,0,0.55)'); grd.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grd; g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(c); return t;
}

// The grade pass: the 3D layer (linear, premultiplied) is tone-mapped, softened to the plate's sharpness,
// pulled toward the plate's colour, laid over the plate and grained. Everything happens in one place, so every
// layer shares the same softness and grain.
const GRADE_VS = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const GRADE_FS = `
precision highp float;
varying vec2 vUv;
uniform sampler2D tLayer; uniform sampler2D tPlate; uniform float hasPlate;
uniform vec2 uRes; uniform float uSeed; uniform float uExposure; uniform float uSat; uniform vec3 uTint;
uniform float uLift; uniform float uSoft; uniform float uGrain;
vec3 neutral(vec3 c){
  const float S = 0.76; const float D = 0.15;
  c *= uExposure;
  float x = min(c.r, min(c.g, c.b)); float off = x < 0.08 ? x - 6.25*x*x : 0.04; c -= off;
  float p = max(c.r, max(c.g, c.b)); if (p < S) return c;
  float d = 1.0 - S; float np = 1.0 - d*d/(p + d - S); c *= np/p;
  float g = 1.0 - 1.0/(D*(p - np) + 1.0); return mix(c, vec3(np), g);
}
vec3 toSRGB(vec3 c){ c = clamp(c, 0.0, 1.0); return mix(c*12.92, 1.055*pow(c, vec3(1.0/2.4)) - 0.055, step(0.0031308, c)); }
float hash(vec2 p){ p = fract(p*vec2(443.897, 441.423) + uSeed*0.1031); p += dot(p, p.yx + 19.19); return fract((p.x + p.y)*p.x); }
void main(){
  vec2 px = 1.0/uRes;
  // 9-tap soft blur of the premultiplied layer
  vec4 L = texture2D(tLayer, vUv)*0.25;
  L += (texture2D(tLayer, vUv + vec2(px.x,0.)*uSoft) + texture2D(tLayer, vUv - vec2(px.x,0.)*uSoft)
      + texture2D(tLayer, vUv + vec2(0.,px.y)*uSoft) + texture2D(tLayer, vUv - vec2(0.,px.y)*uSoft))*0.125;
  L += (texture2D(tLayer, vUv + px*uSoft) + texture2D(tLayer, vUv - px*uSoft)
      + texture2D(tLayer, vUv + vec2(px.x,-px.y)*uSoft) + texture2D(tLayer, vUv + vec2(-px.x,px.y)*uSoft))*0.0625;
  float a = clamp(L.a, 0.0, 1.0);
  vec3 col = a > 0.0001 ? L.rgb / a : vec3(0.0);
  col = toSRGB(neutral(col));
  float luma = dot(col, vec3(0.2126, 0.7152, 0.0722));
  col = mix(vec3(luma), col, uSat) * uTint;
  col = uLift + col*(1.0 - uLift);
  vec3 plate = hasPlate > 0.5 ? texture2D(tPlate, vUv).rgb : vec3(0.5);
  vec3 outc = col*a + plate*(1.0 - a);
  float n = (hash(gl_FragCoord.xy) + hash(gl_FragCoord.xy + 17.0) - 1.0);
  outc += n * uGrain * (0.35 + 0.65*a);
  gl_FragColor = vec4(outc, 1.0);
}`;

export function makeWorld(renderer, aspect, shadowSize = 2048) {
  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.55;

  const camera = new THREE.PerspectiveCamera(SET.fov, aspect, 1, 400);
  camera.position.set(0, SET.camY, 0);
  camera.lookAt(0, SET.camY, -100);

  // The window: a near, soft point light off frame left and a little in front. Being near, it falls off across
  // the front face (brighter on the left), lights the left end and throws the shadow back and to the right.
  const key = new THREE.PointLight('#fff1dc', 5200, 0, 2);
  key.position.set(-62, 34, -62);
  key.castShadow = true;
  key.shadow.mapSize.set(shadowSize, shadowSize);
  key.shadow.radius = 14; key.shadow.blurSamples = 24; key.shadow.bias = -0.002;
  key.shadow.camera.near = 5; key.shadow.camera.far = 300;
  scene.add(key);
  // sky from the window plus a warm bounce off the walnut
  scene.add(new THREE.HemisphereLight('#e9efe6', '#8a5f3c', 0.85));
  const bounce = new THREE.DirectionalLight('#c98b5a', 0.25); bounce.position.set(0, -10, 20); scene.add(bounce);

  // shadow catcher on the shelf top
  const catcher = new THREE.Mesh(new THREE.PlaneGeometry(120, 45), new THREE.ShadowMaterial({ opacity: 0.42 }));
  catcher.rotation.x = -Math.PI / 2; catcher.position.set(0, 0, (SET.wallZ + SET.frontZ) / 2);
  catcher.receiveShadow = true;
  scene.add(catcher);

  const contactTex = contactTexture();
  function contactFor(box) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({ map: contactTex, color: 0x000000, transparent: true, opacity: 0.55, depthWrite: false }));
    m.rotation.x = -Math.PI / 2; m.renderOrder = -1;
    scene.add(m);
    return m;
  }
  return { scene, camera, key, catcher, contactFor };
}

export function makeStage(canvasEl, width, height) {
  const renderer = new THREE.WebGLRenderer({ canvas: canvasEl, alpha: false, antialias: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);
  renderer.setClearColor(0x000000, 0);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const layerRT = new THREE.WebGLRenderTarget(width, height, { type: THREE.HalfFloatType, samples: 4 });
  const grade = new THREE.ShaderMaterial({
    vertexShader: GRADE_VS, fragmentShader: GRADE_FS, depthTest: false, depthWrite: false,
    uniforms: {
      tLayer: { value: layerRT.texture }, tPlate: { value: null }, hasPlate: { value: 0 },
      uRes: { value: new THREE.Vector2(width, height) }, uSeed: { value: 1 }, uExposure: { value: 1.0 },
      uSat: { value: 0.86 }, uTint: { value: new THREE.Vector3(1.02, 1.0, 0.95) }, uLift: { value: 0.025 },
      uSoft: { value: 0.75 }, uGrain: { value: 0.022 },
    },
  });
  const quadScene = new THREE.Scene();
  const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  quadScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), grade));
  function setPlate(img) {
    const t = new THREE.Texture(img); t.colorSpace = THREE.NoColorSpace; t.needsUpdate = true;
    t.minFilter = THREE.LinearFilter; t.generateMipmaps = false;
    grade.uniforms.tPlate.value = t; grade.uniforms.hasPlate.value = 1;
  }

  const { scene, camera, key, catcher, contactFor } = makeWorld(renderer, width / height);
  function render(seed = 1) {
    renderer.setRenderTarget(layerRT);
    renderer.setClearColor(0x000000, 0); renderer.clear();
    renderer.render(scene, camera);
    renderer.setRenderTarget(null);
    grade.uniforms.uSeed.value = seed;
    renderer.render(quadScene, quadCam);
  }
  return { renderer, scene, camera, key, catcher, contactFor, setPlate, render, grade };
}

// Place a box and its contact pad. lift = cm above the shelf; yaw in radians.
export function pose(box, pad, { x = 0, z = -95, lift = 0, yaw = 0, tiltZ = 0, tiltX = 0 }) {
  box.position.set(x, BOX.h / 2 + lift, z);
  box.rotation.set(tiltX, yaw, tiltZ, 'YXZ');
  if (pad) {
    const spread = 1 + lift * 0.18;
    const c = Math.abs(Math.cos(yaw)), s = Math.abs(Math.sin(yaw));
    pad.position.set(x, 0.02, z);
    pad.rotation.z = -yaw;
    pad.scale.set(BOX.w * 1.18 * spread, BOX.d * 1.5 * spread, 1);
    pad.material.opacity = 0.55 / (1 + lift * 0.6);
    void c; void s;
  }
}

// Product photos for the phone feed: each box on a light-grey sweep, a touch from above, soft top light.
export function packshots(bots, w = 1024, h = 560) {
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
  const r = new THREE.WebGLRenderer({ canvas: cv, antialias: true, preserveDrawingBuffer: true, alpha: false });
  r.setPixelRatio(1); r.setSize(w, h, false);
  r.outputColorSpace = THREE.SRGBColorSpace; r.toneMapping = THREE.NeutralToneMapping; r.toneMappingExposure = 1.05;
  r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFSoftShadowMap;
  const sc = new THREE.Scene(); sc.background = new THREE.Color('#e7e6e2');
  const pm = new THREE.PMREMGenerator(r); sc.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; sc.environmentIntensity = 0.7;
  const cam = new THREE.PerspectiveCamera(24, w / h, 1, 500); cam.position.set(0, 8.36, 28.08); cam.lookAt(0, 3.5, 0);
  const soft = new THREE.DirectionalLight('#ffffff', 1.5); soft.position.set(-6, 70, 40); soft.castShadow = true;
  soft.shadow.mapSize.set(1024, 1024); Object.assign(soft.shadow.camera, { left: -20, right: 20, top: 20, bottom: -20 }); soft.shadow.radius = 16; soft.shadow.blurSamples = 25;
  sc.add(soft, new THREE.HemisphereLight('#ffffff', '#d8d4cc', 1.1));
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.ShadowMaterial({ opacity: 0.15 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; sc.add(floor);
  const out = {};
  for (const f of FLAVOURS) {
    const m = new THREE.Mesh(new RoundedBoxGeometry(BOX.w, BOX.h, BOX.d, 3, 0.14), boxMaterials(f, bots, r));
    m.castShadow = true; m.position.set(0, BOX.h / 2, 0); m.rotation.y = -0.2; sc.add(m);
    r.render(sc, cam);
    const c2 = document.createElement('canvas'); c2.width = w; c2.height = h; c2.getContext('2d').drawImage(cv, 0, 0);
    out[f.id] = c2; sc.remove(m);
  }
  // materials stay cached: three uploads each texture once per renderer, so the main renderer can reuse them
  r.dispose();
  return out;
}
