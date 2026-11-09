"""Cut master.png into the layers the frame engine composites.

  python3 look/layers.py        (run from the project folder)

Inputs: look/master.png, look/layers/clean-hand.png (swiping hand removed), look/layers/clean-all.png (both hands
and the phone removed), look/layers/polys.json (rough regions).
Outputs, in studio/assets/layers/, all 1152x2048:
  base.png      the empty set: master, with the hands and phone filled from clean-all (aligned, tone-matched)
  phone.png     RGBA: the phone and the holding hand. The parts the swiping hand hid come from clean-hand,
                registered onto the master's phone.
  hand.png      RGBA: the swiping hand, forearm, watch and sleeve
  screen.png    the screen's own light (L channel of the blank screen, high-passed): reflections to lay over the feed
  layers.json   screen corners and homography, fingertip, arm entry point
Debug views go to look/gen/layers-*.png.
"""
import json, pathlib
import numpy as np, cv2
from PIL import Image

ROOT = pathlib.Path('.')
L = ROOT / 'look' / 'layers'
OUT = ROOT / 'studio' / 'assets' / 'layers'
OUT.mkdir(parents=True, exist_ok=True)
GEN = ROOT / 'look' / 'gen'

def load(p): return np.asarray(Image.open(p).convert('RGB')).astype(np.float32)
M = load(ROOT / 'look' / 'master.png'); CH = load(L / 'clean-hand.png'); CA = load(L / 'clean-all.png')
H, W = M.shape[:2]
polys = json.load(open(L / 'polys.json'))

def poly_mask(p, dil=0, ero=0):
    m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [np.array(p, np.int32)], 255)
    if dil: m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dil + 1,) * 2))
    if ero: m = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ero + 1,) * 2))
    return m

def grabcut(img, prob_fg, sure_fg, sure_bg, iters=6):
    mask = np.full((H, W), cv2.GC_BGD, np.uint8)
    mask[prob_fg > 0] = cv2.GC_PR_FGD
    mask[(sure_bg > 0) & (prob_fg == 0)] = cv2.GC_PR_BGD  # inside the outer band but not proposed: maybe; outside: sure BG
    mask[sure_fg > 0] = cv2.GC_FGD
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img.astype(np.uint8)[..., ::-1].copy(), mask, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    return np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

def guided(I, p, r=6, eps=1e-3):
    """Grey guided filter (He et al.): soft, edge-following alpha from a hard mask."""
    I = cv2.cvtColor(I.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255; p = p.astype(np.float32) / 255
    bf = lambda x: cv2.boxFilter(x, -1, (2 * r + 1,) * 2)
    mI, mp, cIp, vI = bf(I), bf(p), bf(I * p), bf(I * I) - bf(I) ** 2
    a = (cIp - mI * mp) / (vI + eps); b = mp - a * mI
    return np.clip(bf(a) * I + bf(b), 0, 1)

def keep_largest(m, n=1):
    k, lab, st, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8))
    if k <= 1: return m
    order = 1 + np.argsort(-st[1:, 4])[:n]
    return np.isin(lab, order).astype(np.uint8) * 255

# ---- mattes: GrabCut only inside a narrow band around each traced outline ----------------------------------
def band_cut(poly_m, band, extra_bg=None):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1,) * 2)
    sure_fg = cv2.erode(poly_m, k); outer = cv2.dilate(poly_m, k)
    if extra_bg is not None:
        sure_fg = cv2.bitwise_and(sure_fg, cv2.bitwise_not(extra_bg)); outer = cv2.bitwise_and(outer, cv2.bitwise_not(extra_bg))
    hard = grabcut(M, outer, sure_fg, outer, iters=5)
    hard = cv2.morphologyEx(hard, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    return keep_largest(cv2.bitwise_or(hard, sure_fg))
hand_poly = poly_mask(polys['hand'])
phone_poly = poly_mask(polys['phone'])
hand_hard = band_cut(hand_poly, 12)
hand_a = guided(M, hand_hard, r=4, eps=4e-4)
phone_hard = band_cut(cv2.bitwise_and(phone_poly, cv2.bitwise_not(hand_poly)), 10, extra_bg=cv2.erode(hand_hard, np.ones((5, 5), np.uint8)))
phone_hard = cv2.bitwise_and(phone_hard, cv2.bitwise_not(hand_hard))
# ---- screen: bright neutral region inside the bezel, plus the part under the finger ------------------------
hsv = cv2.cvtColor(M.astype(np.uint8), cv2.COLOR_RGB2HSV)
scr = ((hsv[..., 1] < 22) & (hsv[..., 2] > 150)).astype(np.uint8) * 255
scr = cv2.bitwise_and(scr, poly_mask([[200, 538], [915, 538], [915, 880], [200, 880]], dil=6))
scr = cv2.bitwise_or(scr, cv2.bitwise_and(hand_hard, poly_mask([[200, 545], [912, 548], [912, 878], [200, 870]])))
scr = cv2.morphologyEx(scr, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)); scr = keep_largest(scr)
# fit the four edges: points on each side of the contour, then a line per side
cnt = max(cv2.findContours(scr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)[:, 0, :]
x0, y0, ww, hh = cv2.boundingRect(cnt)
def side(sel):
    pts = cnt[sel].astype(np.float32); vx, vy, px, py = cv2.fitLine(pts, cv2.DIST_HUBER, 0, 0.01, 0.01).ravel(); return (px, py, vx, vy)
mx, my = 60, 50  # stay clear of the rounded corners
top = side((cnt[:, 1] < y0 + 12) & (cnt[:, 0] > x0 + mx) & (cnt[:, 0] < x0 + ww - mx) & (hand_hard[cnt[:, 1], cnt[:, 0]] == 0))
bot = side((cnt[:, 1] > y0 + hh - 12) & (cnt[:, 0] > x0 + mx) & (cnt[:, 0] < x0 + ww - mx))
lef = side((cnt[:, 0] < x0 + 12) & (cnt[:, 1] > y0 + my) & (cnt[:, 1] < y0 + hh - my))
rig = side((cnt[:, 0] > x0 + ww - 12) & (cnt[:, 1] > y0 + my) & (cnt[:, 1] < y0 + hh - my))
def inter(a, b):
    (p1x, p1y, v1x, v1y), (p2x, p2y, v2x, v2y) = a, b
    A = np.array([[v1x, -v2x], [v1y, -v2y]]); t = np.linalg.solve(A, np.array([p2x - p1x, p2y - p1y]))
    return [float(p1x + v1x * t[0]), float(p1y + v1y * t[0])]
corners = [inter(top, lef), inter(top, rig), inter(bot, rig), inter(bot, lef)]  # TL TR BR BL
screen_a = guided(M, scr, r=2, eps=2e-4)

# ---- clean-all aligned + tone-matched into the hand and phone footprint -> base -----------------------------
def phase_shift(a, b, reg):
    x0_, y0_, x1_, y1_ = reg
    A = cv2.cvtColor(a[y0_:y1_, x0_:x1_], cv2.COLOR_RGB2GRAY).astype(np.float64)
    B = cv2.cvtColor(b[y0_:y1_, x0_:x1_], cv2.COLOR_RGB2GRAY).astype(np.float64)
    (dx, dy), _ = cv2.phaseCorrelate(A, B, cv2.createHanningWindow(A.shape[::-1], cv2.CV_64F)); return dx, dy
dx, dy = phase_shift(M, CA, (0, 60, 170, 1000))  # tiles only: the left strip never had hands
CAa = cv2.warpAffine(CA, np.float32([[1, 0, -dx], [0, 1, -dy]]), (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def tone_match(src, ref, region, ring_px=60, sigma=45):
    """Scale src so its low frequencies match ref, judged on a ring around region, spread inward."""
    ring = cv2.dilate(region, np.ones((ring_px, ring_px), np.uint8)) - region
    w = (ring > 0).astype(np.float32)
    out = src.copy()
    for c in range(3):
        ratio = np.where(w > 0, (ref[..., c] + 4) / (src[..., c] + 4), 0)
        num = cv2.GaussianBlur(ratio * w, (0, 0), sigma); den = cv2.GaussianBlur(w, (0, 0), sigma)
        g = num / np.maximum(den, 1e-4)
        for _ in range(3):  # spread into the region where den is small
            num = cv2.GaussianBlur(g * (den > 1e-3), (0, 0), sigma * 2); dd = cv2.GaussianBlur((den > 1e-3).astype(np.float32), (0, 0), sigma * 2)
            g = np.where(den > 1e-3, g, num / np.maximum(dd, 1e-4))
        out[..., c] = src[..., c] * np.clip(g, 0.7, 1.4)
    return out

fill = cv2.dilate(np.maximum(np.maximum(hand_hard, phone_hard), np.maximum(hand_poly, phone_poly)), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (37, 37)))
CAt = tone_match(CAa, M, fill)
fa = cv2.GaussianBlur(fill.astype(np.float32) / 255, (0, 0), 6)[..., None]
base = M * (1 - fa) + CAt * fa

# ---- phone layer: master where visible, clean-hand (registered) where the hand hid it -----------------------
def screen_corners(img, hand=None):
    hs = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2HSV)
    m = ((hs[..., 1] < 22) & (hs[..., 2] > 150)).astype(np.uint8) * 255
    m = cv2.bitwise_and(m, poly_mask([[190, 520], [925, 520], [925, 900], [190, 900]]))
    if hand is not None: m = cv2.bitwise_or(m, cv2.bitwise_and(hand, poly_mask([[200, 545], [912, 548], [912, 878], [200, 870]])))
    m = keep_largest(cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)))
    c = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)[:, 0, :]
    bx, by, bw, bh = cv2.boundingRect(c)
    def sd(sel):
        pts = c[sel].astype(np.float32); vx, vy, px, py = cv2.fitLine(pts, cv2.DIST_HUBER, 0, 0.01, 0.01).ravel(); return (px, py, vx, vy)
    okh = (hand[c[:, 1], c[:, 0]] == 0) if hand is not None else np.ones(len(c), bool)
    t = sd((c[:, 1] < by + 12) & (c[:, 0] > bx + 60) & (c[:, 0] < bx + bw - 60) & okh)
    b = sd((c[:, 1] > by + bh - 12) & (c[:, 0] > bx + 60) & (c[:, 0] < bx + bw - 60))
    l = sd((c[:, 0] < bx + 12) & (c[:, 1] > by + 50) & (c[:, 1] < by + bh - 50))
    r = sd((c[:, 0] > bx + bw - 12) & (c[:, 1] > by + 50) & (c[:, 1] < by + bh - 50))
    return [inter(t, l), inter(t, r), inter(b, r), inter(b, l)], m
ch_corners, _ = screen_corners(CH)
Hreg = cv2.getPerspectiveTransform(np.float32(ch_corners), np.float32(corners))
CHr = cv2.warpPerspective(CH, Hreg, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
Aff = Hreg; inl = np.ones(4)
# take clean-hand only along the phone's top edge and the holding palm, never the screen interior
yy, xx = np.mgrid[0:H, 0:W]
p0, p1 = np.array(corners[0]), np.array(corners[1])
top_y = p0[1] + (xx - p0[0]) * (p1[1] - p0[1]) / (p1[0] - p0[0])
zone = ((yy < top_y + 22) & (yy > top_y - 75) & (xx > 180) & (xx < 1005)).astype(np.uint8) * 255
zone = np.maximum(zone, ((xx > 180) & (xx < 1005) & (yy > top_y - 75) & (yy < 900)).astype(np.uint8) * 255)  # the screen under the finger too
under = cv2.bitwise_and(cv2.bitwise_and(cv2.dilate(hand_hard, np.ones((7, 7), np.uint8)), zone), cv2.dilate(phone_poly, np.ones((5, 5), np.uint8)))
CHt = tone_match(CHr, M, cv2.dilate(under, np.ones((9, 9), np.uint8)), ring_px=40, sigma=25)
# inside the borrowed strip keep only what is not wall in clean-hand (thumb, palm, bezel), so no tiles ride on the phone
hs2 = cv2.cvtColor(np.clip(CHr, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV)
wall = ((hs2[..., 0] > 18) & (hs2[..., 0] < 45) & (hs2[..., 1] < 60) & (hs2[..., 2] > 140)).astype(np.uint8) * 255
wall = cv2.morphologyEx(wall, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
under = cv2.bitwise_and(under, cv2.bitwise_not(cv2.bitwise_and(wall, cv2.bitwise_not(cv2.dilate(phone_hard, np.ones((3, 3), np.uint8))))))
ua = cv2.GaussianBlur(cv2.dilate(under, np.ones((7, 7), np.uint8)).astype(np.float32) / 255, (0, 0), 2.5)[..., None]
phone_rgb = M * (1 - ua) + CHt * ua
a_m = guided(M, phone_hard, r=4, eps=4e-4); a_u = guided(CHt, cv2.dilate(under, np.ones((5, 5), np.uint8)), r=3, eps=4e-4)
phone_alpha = 1 - (1 - np.clip(a_m, 0, 1)) * (1 - np.clip(a_u, 0, 1))   # union: no dip where the two edges meet
phone_alpha = np.maximum(phone_alpha, screen_a)  # the screen is part of the phone

# ---- screen light: the blank screen's own variation, to lay over the feed ---------------------------------
Lc = cv2.cvtColor(M.astype(np.uint8), cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32)
CHL = cv2.cvtColor(CHt.astype(np.uint8), cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32)
Lc = cv2.inpaint(np.clip(Lc, 0, 255).astype(np.uint8), cv2.dilate(hand_hard, np.ones((15, 15), np.uint8)), 25, cv2.INPAINT_TELEA).astype(np.float32)  # smooth glass where the hand was
scr_mean = float(Lc[scr > 0].mean())
screen_light = np.clip(128 + (Lc - scr_mean) * 1.0, 0, 255) * (scr > 0)

# ---- drop wall-coloured pixels that rode along in either matte (tiles and grout), but keep the white watch face
hsM = cv2.cvtColor(M.astype(np.uint8), cv2.COLOR_RGB2HSV)
wallM = ((hsM[..., 0] > 18) & (hsM[..., 0] < 45) & (hsM[..., 1] < 60) & (hsM[..., 2] > 140)).astype(np.uint8) * 255
wallM = cv2.morphologyEx(wallM, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
wallM[poly_mask([[1025, 160], [1125, 160], [1125, 280], [1025, 280]]) > 0] = 0      # watch face
wallM[cv2.dilate(scr, np.ones((7, 7), np.uint8)) > 0] = 0                          # the screen is light grey too
wall_soft = cv2.GaussianBlur(wallM.astype(np.float32) / 255, (0, 0), 1.5)
hand_a = hand_a * (1 - wall_soft)
keep_ch = cv2.dilate(under, np.ones((5, 5), np.uint8)) > 0
phone_alpha = np.where(keep_ch, phone_alpha, phone_alpha * (1 - wall_soft))

# ---- save ----------------------------------------------------------------------------------------------------
def rgba(rgb, a): return np.dstack([np.clip(rgb, 0, 255), np.clip(a * 255, 0, 255)]).astype(np.uint8)
Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).save(OUT / 'base.png')
Image.fromarray(rgba(phone_rgb, phone_alpha)).save(OUT / 'phone.png')
Image.fromarray(rgba(M, hand_a)).save(OUT / 'hand.png')
Image.fromarray(np.dstack([screen_light.astype(np.uint8), (screen_a * 255).astype(np.uint8)]).astype(np.uint8), 'LA').save(OUT / 'screen.png')
Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), np.float32(corners))
meta = {'size': [W, H], 'screen_corners_TL_TR_BR_BL': corners, 'screen_H_unit_to_px': Hm.tolist(),
        'screen_mean_L': scr_mean, 'fingertip': [490, 618], 'arm_entry': [1160, 120],
        'clean_all_shift': [dx, dy], 'clean_hand_affine': Aff.tolist(), 'sift_inliers': int(inl.sum())}
json.dump(meta, open(OUT / 'layers.json', 'w'), indent=2)
print(json.dumps({k: meta[k] for k in ['screen_corners_TL_TR_BR_BL', 'clean_all_shift', 'sift_inliers']}, indent=1))
print('clean-hand screen corners', np.round(ch_corners, 1).tolist())

# ---- debug views --------------------------------------------------------------------------------------------
dbg = M.copy()
dbg[hand_hard > 0] = dbg[hand_hard > 0] * 0.45 + np.array([255, 40, 40]) * 0.55
dbg[phone_hard > 0] = dbg[phone_hard > 0] * 0.45 + np.array([40, 80, 255]) * 0.55
dbg[under > 0] = dbg[under > 0] * 0.3 + np.array([255, 230, 0]) * 0.7
cv2.polylines(dbg, [np.int32(corners)], True, (0, 255, 0), 2)
Image.fromarray(dbg[:1100].astype(np.uint8)).resize((576, 550)).save(GEN / 'layers-mattes.png')
chk = base.copy()
Image.fromarray(np.clip(chk[:1100], 0, 255).astype(np.uint8)).resize((576, 550)).save(GEN / 'layers-base.png')
# the phone layer alone over grey, to see the filled bezel and thumb
pa = phone_alpha[..., None]
Image.fromarray(np.clip(phone_rgb * pa + 90 * (1 - pa), 0, 255)[380:1000, 150:1152].astype(np.uint8)).save(GEN / 'layers-phone.png')

ha = hand_a[..., None]
Image.fromarray(np.clip(M * ha + np.array([255, 0, 255]) * (1 - ha), 0, 255)[0:700, 380:1152].astype(np.uint8)).save(GEN / 'layers-hand.png')
