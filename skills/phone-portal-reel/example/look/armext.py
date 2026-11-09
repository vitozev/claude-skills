"""The swiping arm beyond the frame: when the arm reaches toward the phone, sleeve from outside the photo slides into
view. This builds that sleeve from an outpaint (look/layers/arm-ext15.png, gpt-image-1.5), fitted to our own arm.

  python3 look/armext.py        (run from the project folder)

The outpaint redrew the whole picture (its watch moved 48 px), so only its sleeve OUTSIDE the frame is used:
1. matte the arm in both images (sleeve and skin against the sage wall),
2. fit the outpaint's arm silhouette to ours with an affine ECC, only in a band along the top and right edges,
3. tone-match it to our sleeve on that band,
4. write studio/assets/layers/arm-ext.png: plate x 384..1408, y -256..768 (1024 px square, origin (384, -256)).
   Inside the frame it is our hand layer, cross-faded to the fitted outpaint over the last 18 px before the edge;
   outside the frame it is the fitted outpaint.
"""
import json, pathlib
import numpy as np, cv2
from PIL import Image

ROOT = pathlib.Path('.')
OX, OY, S = 384, -256, 1024                     # ext canvas origin in plate px, and its size
BAND = 18

hand = np.asarray(Image.open(ROOT / 'studio/assets/layers/hand.png').convert('RGBA')).astype(np.float32)
B = np.asarray(Image.open(ROOT / 'look/layers/arm-ext15.png').convert('RGB')).astype(np.float32)
H, W = hand.shape[:2]

# our hand layer placed on the ext canvas (plate y 0..768 -> canvas 256..1024, plate x 384..1152 -> canvas 0..768)
ours = np.zeros((S, S, 4), np.float32)
ours[-OY:S, 0:W - OX] = hand[0:S + OY, OX:W]
inside = np.zeros((S, S), bool); inside[-OY:S, 0:W - OX] = True

def arm_matte(rgb):
    """Arm (oatmeal knit, skin, watch) against the sage wall: the wall is greener than red, the arm is not."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = ((r - g) > 1.5).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    return m

def guided(I, p, r=5, eps=4e-4):
    I = cv2.cvtColor(np.clip(I, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255; p = p.astype(np.float32) / 255
    bf = lambda x: cv2.boxFilter(x, -1, (2 * r + 1,) * 2)
    mI, mp, cIp, vI = bf(I), bf(p), bf(I * p), bf(I * I) - bf(I) ** 2
    a = (cIp - mI * mp) / (vI + eps); bb = mp - a * mI
    return np.clip(bf(a) * I + bf(bb), 0, 1)

mB = arm_matte(B)
# only the outpaint's arm that reaches the top or right edge of the canvas (drop stray specks)
k, lab, st, _ = cv2.connectedComponentsWithStats((mB > 0).astype(np.uint8))
keep = [i for i in range(1, k) if st[i, 4] > 4000]
mB = np.isin(lab, keep).astype(np.uint8) * 255
mOurs = (ours[..., 3] > 127).astype(np.uint8) * 255

# fit B's arm silhouette to ours, judged only on a band along the top and right edges of the frame
yy, xx = np.mgrid[0:S, 0:S]
px, py = xx + OX, yy + OY
band = inside & (px > 880) & ((px > W - 200) | (py < 200))
# rigid fit (turn + shift, no scaling): maximise silhouette overlap on the band, coarse-to-fine at 1/4 size
q = 4
T = cv2.resize((mOurs > 0).astype(np.float32), (S // q, S // q), interpolation=cv2.INTER_AREA)
Bm = (mB > 0).astype(np.float32)
bd = cv2.resize(band.astype(np.float32), (S // q, S // q), interpolation=cv2.INTER_AREA) > 0.5
piv = (W - OX - 80, -OY + 120)                  # turn about a point on our sleeve near the corner (canvas px)
def warp_of(ang, dx, dy):
    M = cv2.getRotationMatrix2D(piv, ang, 1.0); M[0, 2] += dx; M[1, 2] += dy; return M     # maps B -> ours
def score(ang, dx, dy):
    w = cv2.warpAffine(Bm, warp_of(ang, dx, dy), (S, S), flags=cv2.INTER_LINEAR)
    w = cv2.resize(w, (S // q, S // q), interpolation=cv2.INTER_AREA)
    a_, b_ = T[bd] > 0.5, w[bd] > 0.5
    return (a_ & b_).sum() / max(1, (a_ | b_).sum())
best = (-1, 0, 0, 0)
for ang in np.arange(-16, 16.1, 2):
    for dx in range(-40, 141, 10):
        for dy in range(-120, 61, 10):
            sc = score(ang, dx, dy)
            if sc > best[0]: best = (sc, ang, dx, dy)
_, A0, X0, Y0 = best
for ang in np.arange(A0 - 2, A0 + 2.01, 0.5):
    for dx in range(X0 - 10, X0 + 11, 2):
        for dy in range(Y0 - 10, Y0 + 11, 2):
            sc = score(ang, dx, dy)
            if sc > best[0]: best = (sc, ang, dx, dy)
cc, ang, dx, dy = best
Mfit = warp_of(ang, dx, dy)
print(f'rigid fit IoU {cc:.3f}: turn {ang:+.1f} deg, shift ({dx:+d},{dy:+d}) px')
Bw = cv2.warpAffine(B, Mfit, (S, S), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
mBw = cv2.warpAffine(mB, Mfit, (S, S), flags=cv2.INTER_LINEAR)
aBw = guided(Bw, mBw, r=4)

# tone-match the outpaint's sleeve to ours on the band (per channel gain, smooth)
both = band & (mOurs > 0) & (mBw > 127)
gain = np.array([ours[..., c][both].mean() / max(1.0, Bw[..., c][both].mean()) for c in range(3)])
Bt = np.clip(Bw * gain, 0, 255)
print('band px', int(both.sum()), 'gain', np.round(gain, 3).tolist())

# silhouette continuity at the edge (how far the fitted outline sits from ours, along the frame edges)
def edge_rows(m, col):  return np.where(m[:, col] > 127)[0]
c_edge = W - OX - 2
a_, b_ = edge_rows(mOurs, c_edge), edge_rows(mBw, c_edge)
print('right edge, arm rows ours', (a_.min() + OY, a_.max() + OY) if len(a_) else None, ' fitted', (b_.min() + OY, b_.max() + OY) if len(b_) else None)
r_edge = -OY + 2
a2, b2 = np.where(mOurs[r_edge] > 127)[0], np.where(mBw[r_edge] > 127)[0]
print('top edge, arm cols ours', (a2.min() + OX, a2.max() + OX) if len(a2) else None, ' fitted', (b2.min() + OX, b2.max() + OX) if len(b2) else None)

# compose: inside = ours, fading to the fitted outpaint over the last BAND px before the top/right edge; outside = fitted
dist = np.minimum(np.where(px < W, W - px, 0), np.where(py >= 0, py, 0)).astype(np.float32)
f = np.clip(dist / BAND, 0, 1)
f[~inside] = 0
# outside the frame, our own silhouette also continues along the arm's axis (reflected back from the edge), so the
# outline never has a notch where the outpaint's sleeve is a little narrower; the outpaint's knit wins where it exists
up = np.array([0.80, -0.59])
back = np.maximum(np.where(py < 0, -py / 0.59, 0), np.where(px > W - 1, (px - (W - 1)) / 0.80, 0))
refl = back + np.minimum(back, 22)           # reflect at most 22 px deep: the cuff covering the watch's edge, never the watch
sx = np.clip(px - refl * up[0], 0, W - 1) - OX; sy = np.clip(py - refl * up[1], 0, H - 1) - OY
ext = cv2.remap(ours, sx.astype(np.float32), sy.astype(np.float32), cv2.INTER_LINEAR)
aE = ext[..., 3] / 255
# where the arm leaves through the right edge below plate y~40 it is our ribbed cuff: its ribs run along the arm, so
# carrying it on along the axis keeps them unbroken. Above that (plain knit) the outpaint's sleeve is used.
by = py - back * up[1]                                          # where this pixel's axis line crosses the frame edge
w_ext = np.where(px > W - 1, np.clip((by - 28) / 24, 0, 1), 0.0)
rgbP = Bt * aBw[..., None] + ext[..., :3] * (1 - aBw[..., None])
rgbO = rgbP * (1 - w_ext[..., None]) + ext[..., :3] * w_ext[..., None]
aO = np.maximum(aBw, aE) * (1 - w_ext) + aE * w_ext
# drop specks outside the frame (wall bits the matte let through)
sp = ((aO > 0.5) & ~inside).astype(np.uint8)
k2, lab2, st2, _ = cv2.connectedComponentsWithStats(sp)
small = np.isin(lab2, [i for i in range(1, k2) if st2[i, 4] < 3000])
aO = np.where(small, 0, aO)
# just past the edge, continue our own sleeve (reflected along the arm, at most 14 px deep) and blend into the
# outpaint over 14 px, so no seam shows where the frame used to end
wo = np.clip(back / 14.0, 0, 1)[..., None]
rgbO = ext[..., :3] * (1 - wo) + rgbO * wo
aO = aE * (1 - wo[..., 0]) + aO * wo[..., 0]
rgb = np.where(inside[..., None], ours[..., :3], rgbO)
alpha = np.where(inside, ours[..., 3] / 255, aO)
out = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8)
Image.fromarray(out).save(ROOT / 'studio/assets/layers/arm-ext.png')
meta = json.load(open(ROOT / 'studio/assets/layers/layers.json'))
meta['arm_ext'] = {'origin': [OX, OY], 'size': S, 'band': BAND, 'ecc': float(cc)}
json.dump(meta, open(ROOT / 'studio/assets/layers/layers.json', 'w'), indent=2)
# debug: the ext over magenta, frame edges marked
dbg = out[..., :3].astype(np.float32) * (out[..., 3:] / 255) + np.array([255, 0, 255]) * (1 - out[..., 3:] / 255)
dbg = dbg.astype(np.uint8).copy()
cv2.line(dbg, (W - OX, 0), (W - OX, S), (0, 255, 255), 1); cv2.line(dbg, (0, -OY), (S, -OY), (0, 255, 255), 1)
Image.fromarray(dbg).save(ROOT / 'look/gen/arm-ext-debug.png')
print('wrote studio/assets/layers/arm-ext.png')
