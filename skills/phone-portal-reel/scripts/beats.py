"""Find a music bed's tempo and beat grid. Prints the BPM, the first strong downbeat and per-beat band energies
(kick: 30-160 Hz, clap: 1.5-8 kHz), and writes BED.beats.json beside the file. It looks for 90-140 BPM.

  python3 beats.py BED.mp3

Stretch the bed to a tempo where a beat is a whole number of frames (ffmpeg atempo = target / measured), then
measure the stretched file's transients against the frame grid again before you trust it.
"""
import subprocess, sys, json
import numpy as np

SR = 44100
if len(sys.argv) != 2 or sys.argv[1] in ('-h', '--help'):
    sys.exit(__doc__)
src = sys.argv[1]
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
x = np.frombuffer(raw, np.float32).astype(np.float64)
print(f'length {len(x) / SR:.2f} s')
hop, win = 220, 2048                     # 5 ms hops
n = (len(x) - win) // hop
w = np.hanning(win)
frames = np.stack([x[i * hop: i * hop + win] * w for i in range(n)])
S = np.abs(np.fft.rfft(frames, axis=1))
f = np.fft.rfftfreq(win, 1 / SR)
def flux(lo, hi):
    b = S[:, (f >= lo) & (f < hi)]
    d = np.maximum(np.diff(np.log1p(b * 10), axis=0), 0).sum(1)
    return np.r_[0, d]
on = flux(30, 8000); low = flux(30, 160); hi = flux(1500, 8000)
on = (on - on.mean()) / (on.std() + 1e-9)
fps = SR / hop
# tempo: autocorrelation of the onset envelope over 90..140 BPM
ac = np.correlate(on, on, 'full')[len(on) - 1:]
lags = np.arange(len(ac)) / fps
cand = [(60 / l, ac[i]) for i, l in enumerate(lags) if 60 / 140 <= l <= 60 / 90]
bpm0 = max(cand, key=lambda c: c[1])[0]
# refine bpm and phase with a comb over a fine grid
best = None
for bpm in np.arange(bpm0 - 3, bpm0 + 3, 0.02):
    P = 60 / bpm * fps
    for ph in np.arange(0, P, 0.5):
        idx = (ph + P * np.arange(int((len(on) - ph) / P))).astype(int)
        s = on[idx].sum() / len(idx)
        if best is None or s > best[0]:
            best = (s, bpm, ph)
_, bpm, ph = best
P = 60 / bpm
beats = [ph / fps + k * P for k in range(int((len(x) / SR - ph / fps) / P))]
def at(env, t):
    i = int(t * fps); return float(env[max(0, i - 4): i + 6].max())
rows = [(round(t, 3), round(at(low, t), 1), round(at(hi, t), 1)) for t in beats]
print(f'tempo {bpm:.2f} BPM, beat {P * 1000:.1f} ms, first beat at {beats[0]:.3f} s')
print('beat  time   kick   clap')
for k, (t, l, h) in enumerate(rows[:24]): print(f'{k:3d} {t:6.3f} {l:6.1f} {h:6.1f}')
# downbeat: the beat phase (mod 4) with the strongest kick and weakest clap
sc = [np.mean([rows[k][1] - 0.5 * rows[k][2] for k in range(m, len(rows), 4)]) for m in range(4)]
m = int(np.argmax(sc))
print('downbeat phase (0-3):', m, 'scores', np.round(sc, 1).tolist(), ' first downbeat at', rows[m][0], 's')
json.dump({'bpm': bpm, 'beat_s': P, 'first_beat': beats[0], 'downbeat_phase': m, 'first_downbeat': rows[m][0], 'beats': [r[0] for r in rows]},
          open(src.rsplit('.', 1)[0] + '.beats.json', 'w'), indent=1)
