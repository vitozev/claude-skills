#!/usr/bin/env python3
"""Fix one region of a photo with an image edit, without letting the edit move anything else.

Image models redraw the whole picture even with a mask: objects shift by tens of pixels and the light changes. So
edit a crop, then take the result back only inside the mask, registered to the photo and tone-matched to it.

  1. python3 blend-edit.py crop MASTER.png MASK.png X0 Y0 N OUTDIR
       MASK is a full-size greyscale image, white where the edit may change things. This writes OUTDIR/crop.png and
       OUTDIR/editmask.png, both 1024x1024 (the API mask is transparent where the model may paint).
  2. python3 openai-image.py OUTDIR/edit.png "the same photo, with ..." --edit OUTDIR/crop.png \
       --mask OUTDIR/editmask.png --model gpt-image-1.5 --fidelity high --size 1024x1024
  3. python3 blend-edit.py blend MASTER.png OUTDIR/edit.png MASK.png X0 Y0 N OUT.png [--layer HAND.png HAND_OUT.png]
       This registers the edit to the crop by ECC (translation) on the area outside the mask, gains it to match a
       ring just outside the mask, and blends it in only inside the mask, with a 2.5 px feather. --layer applies the
       same pixels to an RGBA layer cut from MASTER, keeping its alpha. It also writes OUT-check.png (before | after).

Pick X0, Y0, N so the crop holds the whole thing to fix with a margin. Mask the WHOLE object: a watch's strap
under the wrist, a buckle, its shadow. Run a second, smaller pass on whatever survives, and check the result at
full size.
"""
import argparse, pathlib, sys
import numpy as np, cv2
from PIL import Image

E = 1024  # the size the crop is edited at


def rgb(p):
    return np.asarray(Image.open(p).convert('RGB')).astype(np.float32)


def grey_mask(p, shape):
    m = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    if m is None:
        sys.exit(f'cannot read mask {p}')
    if m.shape != shape:
        sys.exit(f'mask is {m.shape[::-1]}, the photo is {shape[::-1]}: they must match')
    return m


def crop(a):
    M = rgb(a.master)
    mask = grey_mask(a.mask, M.shape[:2])
    X0, Y0, N = a.x0, a.y0, a.n
    if X0 < 0 or Y0 < 0 or X0 + N > M.shape[1] or Y0 + N > M.shape[0]:
        sys.exit('the crop runs outside the photo')
    out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    c = cv2.resize(M[Y0:Y0 + N, X0:X0 + N], (E, E), interpolation=cv2.INTER_LANCZOS4)
    Image.fromarray(np.clip(c, 0, 255).astype(np.uint8)).save(out / 'crop.png')
    mc = cv2.resize(mask[Y0:Y0 + N, X0:X0 + N], (E, E), interpolation=cv2.INTER_NEAREST)
    mc = cv2.dilate(mc, np.ones((9, 9), np.uint8))           # a little room at the edge of what may change
    em = np.dstack([np.zeros((E, E, 3), np.uint8), np.where(mc > 0, 0, 255).astype(np.uint8)])
    Image.fromarray(em, 'RGBA').save(out / 'editmask.png')
    print(f'wrote {out / "crop.png"} and {out / "editmask.png"} ({N} px crop at {X0},{Y0}, scaled to {E})')


def blend(a):
    M = rgb(a.master)
    mask = grey_mask(a.mask, M.shape[:2])
    X0, Y0, N = a.x0, a.y0, a.n
    Ed = np.asarray(Image.open(a.edit).convert('RGB').resize((N, N), Image.LANCZOS)).astype(np.float32)
    crop = M[Y0:Y0 + N, X0:X0 + N].copy()
    mc = mask[Y0:Y0 + N, X0:X0 + N]
    # register on what the edit should have left alone
    outside = (cv2.dilate(mc, np.ones((21, 21), np.uint8)) == 0).astype(np.uint8)
    g1 = cv2.cvtColor(crop.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(Ed.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    try:
        cc, warp = cv2.findTransformECC(g1, g2, np.eye(2, 3, dtype=np.float32), cv2.MOTION_TRANSLATION,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), outside, 5)
    except cv2.error:
        sys.exit('ECC did not converge: the edit moved too much, or the mask leaves too little untouched area')
    Ew = cv2.warpAffine(Ed, warp, (N, N), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
    # tone: a per-channel gain measured on a ring just outside the mask, spread smoothly
    ring = (cv2.dilate(mc, np.ones((25, 25), np.uint8)) > 0) & (mc == 0)
    if ring.sum() < 50:
        sys.exit('the mask has no untouched ring around it inside the crop: make the crop bigger')
    gain = np.ones((N, N, 3), np.float32)
    for c in range(3):
        r = np.where(ring, (crop[..., c] + 4) / (Ew[..., c] + 4), 0).astype(np.float32)
        num = cv2.GaussianBlur(r, (0, 0), 18); den = cv2.GaussianBlur(ring.astype(np.float32), (0, 0), 18)
        gain[..., c] = np.where(den > 0.02, num / np.maximum(den, 1e-4), float(r[ring].mean()))
    Et = np.clip(Ew * np.clip(gain, 0.8, 1.25), 0, 255)
    al = cv2.GaussianBlur((mc > 0).astype(np.float32), (0, 0), 2.5)[..., None]
    after = M.copy()
    after[Y0:Y0 + N, X0:X0 + N] = crop * (1 - al) + Et * al
    Image.fromarray(np.clip(after, 0, 255).astype(np.uint8)).save(a.out)
    if a.layer:
        L = np.asarray(Image.open(a.layer[0]).convert('RGBA')).astype(np.float32)
        if L.shape[:2] != M.shape[:2]:
            sys.exit('the layer must be the same size as the photo')
        L[Y0:Y0 + N, X0:X0 + N, :3] = L[Y0:Y0 + N, X0:X0 + N, :3] * (1 - al) + Et * al
        Image.fromarray(np.clip(L, 0, 255).astype(np.uint8), 'RGBA').save(a.layer[1])
        print('wrote', a.layer[1])
    side = np.concatenate([crop, after[Y0:Y0 + N, X0:X0 + N]], 1).astype(np.uint8)
    chk = pathlib.Path(a.out).with_name(pathlib.Path(a.out).stem + '-check.png')
    Image.fromarray(side).resize((N * 4, N * 2), Image.LANCZOS).save(chk)
    print(f'ECC {cc:.4f} (above 0.9 is a good fit), shift {[round(float(v), 2) for v in warp[:, 2]]} px; wrote {a.out} and {chk}')


def main():
    ap = argparse.ArgumentParser(description='Edit one region of a photo; take the edit back only inside its mask.',
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('crop', help='write the crop and the API mask to edit')
    c.add_argument('master'); c.add_argument('mask')
    c.add_argument('x0', type=int); c.add_argument('y0', type=int); c.add_argument('n', type=int)
    c.add_argument('outdir')
    b = sub.add_parser('blend', help='register the edited crop and blend it in inside the mask')
    b.add_argument('master'); b.add_argument('edit'); b.add_argument('mask')
    b.add_argument('x0', type=int); b.add_argument('y0', type=int); b.add_argument('n', type=int)
    b.add_argument('out')
    b.add_argument('--layer', nargs=2, metavar=('LAYER', 'LAYER_OUT'), help='also patch an RGBA layer cut from MASTER')
    a = ap.parse_args()
    crop(a) if a.cmd == 'crop' else blend(a)


if __name__ == '__main__':
    main()
