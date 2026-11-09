"""Does each sound land on the frame where its thing happens? Claude can't listen, but it can look: this cuts the five
frames around every sound hit (-2 .. +2, the hit frame outlined) into sheets, one row per hit. Read each row: the
contact, impact or cut should be on the outlined frame. One frame off is fine; three is visible.

  python3 sync-sheet.py VIDEO --cues cues.json                     [{"t": 1.23 | "frame": 37, "label": "box lands"}, ...]
  python3 sync-sheet.py VIDEO --audio sfx_stem.wav [--min-db 18]   hits found in an effects stem

Writes VIDEO-stem.sync-1.jpg, -2.jpg ... (12 hits a sheet) next to the video, or under --out DIR.
"""
import argparse, json, pathlib, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw

ROWS, W = 12, 300


def probe(video):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height,r_frame_rate', '-of', 'json', video],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)['streams'][0]
    n, d = s['r_frame_rate'].split('/')
    return s['width'], s['height'], float(n) / float(d)


def stem_hits(path, min_db, fps):
    sr, hop = 16000, 160
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vn', '-ac', '1', '-ar', str(sr), '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    fr = x[:len(x) // hop * hop].reshape(-1, hop)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-6)
    hits, last = [], -99
    for i in range(1, len(db)):
        floor = np.percentile(db[max(0, i - 30):i + 1], 20)
        if db[i] - floor >= min_db and db[i] > -45 and db[i] - db[i - 1] > 3 and i - last > 12:
            j = i + int(np.argmax(db[i:i + 5]))
            hits.append({'frame': round(j * hop / sr * fps), 'label': f'hit {j * hop / sr:.2f}s'})
            last = j
    return hits


def frames_at(video, w, h, fps, f0):
    t = max(0, f0 - 2) / fps
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.4f}', '-i', video, '-frames:v', '5', '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    n = len(raw) // (w * h * 3)
    return [Image.frombytes('RGB', (w, h), raw[k * w * h * 3:(k + 1) * w * h * 3]) for k in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--cues')
    g.add_argument('--audio')
    ap.add_argument('--min-db', type=float, default=18)
    ap.add_argument('--out')
    a = ap.parse_args()

    w, h, fps = probe(a.video)
    if a.cues:
        cues = [{'frame': c['frame'] if 'frame' in c else round(c['t'] * fps), 'label': c.get('label', '')}
                for c in json.load(open(a.cues))]
    else:
        cues = stem_hits(a.audio, a.min_db, fps)
    cues.sort(key=lambda c: c['frame'])
    if not cues:
        print('No hits to check.')
        return 1

    th = round(W * h / w)
    vid = pathlib.Path(a.video)
    out = pathlib.Path(a.out) if a.out else vid.parent
    out.mkdir(parents=True, exist_ok=True)
    pages = [cues[i:i + ROWS] for i in range(0, len(cues), ROWS)]
    for p, page in enumerate(pages, 1):
        sheet = Image.new('RGB', (5 * (W + 6) + 6, len(page) * (th + 26) + 6), '#111')
        d = ImageDraw.Draw(sheet)
        for r, c in enumerate(page):
            y = 6 + r * (th + 26)
            first = max(0, c['frame'] - 2)
            for k, im in enumerate(frames_at(a.video, w, h, fps, c['frame'])):
                x = 6 + k * (W + 6)
                sheet.paste(im.resize((W, th)), (x, y))
                if first + k == c['frame']:
                    d.rectangle([x - 3, y - 3, x + W + 2, y + th + 2], outline='#FF9F1C', width=3)
            d.text((8, y + th + 6), f"frame {c['frame']}  ({c['frame'] / fps:.2f}s)  {c['label']}", fill='#FFD9A0')
        path = out / f'{vid.stem}.sync-{p}.jpg'
        sheet.save(path, quality=85)
        print(path)
    print(f'{len(cues)} hits on {len(pages)} sheet(s). The outlined frame is where the sound peaks.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
