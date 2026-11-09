"""Mix the reel's sound onto the picture's frames and master it.

  python3 sound/mix.py        (from the project folder, after elevenlabs.py sound/spec.json sound/sfx and
                               beats.py on the bed)

Writes studio/assets/audio/mix.wav (48 kHz stereo, -14 LUFS, true peak under -1 dBTP) and sound/stems/*.wav
(music, sfx) so sync-sheet.py --audio sound/stems/sfx.wav can check every hit. Frame numbers come from studio/lib/reel.js (DROPS, CUT, LOGO_IN).
"""
import json, pathlib, re, subprocess
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE / 'sfx'                     # where elevenlabs.py wrote the bed and the effects
OUT = HERE.parent / 'studio' / 'assets' / 'audio'; OUT.mkdir(parents=True, exist_ok=True)
STEMS = HERE / 'stems'; STEMS.mkdir(exist_ok=True)
SR, FPS, DUR = 48000, 30, 9.0
N = int(SR * DUR)

def dec(path, ch=2, af=None):
    cmd = ['ffmpeg', '-v', 'error', '-i', str(path)]
    if af: cmd += ['-af', af]
    cmd += ['-f', 'f32le', '-ac', str(ch), '-ar', str(SR), '-']
    x = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).astype(np.float64)
    return x.reshape(-1, ch)

def lufs(x):
    tmp = STEMS / '_m.wav'; write(tmp, x)
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(tmp), '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True)
    s = r.stderr[r.stderr.rfind('Summary:'):]
    i = re.search(r'I:\s+(-?[\d.]+) LUFS', s); p = re.search(r'Peak:\s+(-?[\d.]+) dBFS', s)
    return float(i.group(1)) if i else -70.0, float(p.group(1)) if p else -70.0

def write(path, x):
    import wave
    x = np.clip(x, -1, 1)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(x.shape[1]); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())

def sfx(name, trim=True):
    m = sorted(LIB.glob(f'{name}-*.mp3'))
    x = dec(m[-1])
    if trim:  # nothing before the impact: start 4 ms ahead of the attack, with a 2 ms fade-in
        a0 = max(0, attack(x) - int(0.004 * SR)); x = x[a0:].copy()
        r = int(0.002 * SR); x[:r] *= np.linspace(0, 1, r)[:, None]
    return x

def attack(x, frac=0.3):
    """Sample index of the attack of the clip's LOUDEST transient: walk back from the peak (at most 40 ms) to where the
    envelope rises through frac of it. A take that opens with a small tick is aligned on the real impact."""
    env = np.convolve(np.abs(x).max(1), np.ones(96) / 96, 'same')
    pk = int(np.argmax(env)); i = pk; lim = max(0, pk - int(0.04 * SR))
    while i > lim and env[i] >= frac * env[pk]:
        i -= 1
    return i

def place(bus, clip, frame, gain_db=0.0, align='attack'):
    off = attack(clip) if align == 'attack' else 0
    i0 = int(round(frame / FPS * SR)) - off
    a, b = max(0, i0), min(N, i0 + len(clip))
    if b > a: bus[a:b] += clip[a - i0: b - i0] * 10 ** (gain_db / 20)
    return i0 + off

def fade(x, a, b, up):
    n = b - a
    if n <= 0: return
    r = np.linspace(0, 1, n)[:, None] ** 2
    x[a:b] *= r if up else r[::-1]

# ---- the picture's script (kept in step with reel.js) ---------------------------------------------------------
js = (HERE.parent / 'studio' / 'lib' / 'reel.js').read_text()
lands = [int(v) for v in re.findall(r"land: (\d+)", js)]
CUT = int(re.search(r'export const CUT = (\d+)', js).group(1))
LOGO_IN = int(re.search(r'export const LOGO_IN = (\d+)', js).group(1))
STOP0, STOP1 = 96, lands[-1]            # the dead stop: after Chai's landing beat, until Rooibos lands
TAPE0, TAPE_LEN = 208, 1.25             # the bed winds down under the wordmark

# ---- music: 112.0 -> 112.5 BPM so a beat is exactly 16 frames ---------------------------------------------------
BED = sorted(LIB.glob('bed_v1-*.mp3'))[-1]
beats = json.load(open(BED.with_suffix('.beats.json')))
ratio = 112.5 / beats['bpm']
music = dec(BED, af=f'atempo={ratio:.6f}')
lead = beats['first_beat'] % beats['beat_s'] / ratio   # where its beat grid sits after the stretch
lead = lead if lead < beats['beat_s'] / ratio / 2 else lead - beats['beat_s'] / ratio
NUDGE = 0.025                           # measured: the stretched bed's transients sat 25 ms after the frame grid
shift = int(round((lead + NUDGE) * SR)) # positive: the grid starts late, so trim
music = music[shift:] if shift > 0 else np.vstack([np.zeros((-shift, 2)), music])
music = np.vstack([music, np.zeros((max(0, N - len(music)), 2))])[:N].copy()

# the dead stop: a clean cut (6 ms) out and straight back in on the landing
a, b = int(STOP0 / FPS * SR), int(STOP1 / FPS * SR)
k = int(0.006 * SR)
fade(music, a, a + k, up=False); music[a + k: b] = 0; fade(music, b, b + k // 2, up=True)

# tape stop: playback speed falls from 1 to 0 over TAPE_LEN; the read head slows, pitch drops with it
t0 = int(TAPE0 / FPS * SR); L = int(TAPE_LEN * SR)
src = music.copy()
u = np.arange(L) / L
speed = (1 - u) ** 1.6
pos = t0 + np.cumsum(speed)
for c in range(2):
    music[t0:t0 + L, c] = np.interp(pos, np.arange(len(src)), src[:, c])
music[t0 + L:] = 0
env = np.ones(L); env[int(L * 0.55):] = np.linspace(1, 0, L - int(L * 0.55)) ** 1.5
music[t0:t0 + L] *= env[:, None]
# a little low-pass as it slows (tape loses its top end): a one-pole filter whose cutoff slides smoothly, no blocks
seg = music[t0:t0 + L].copy()
cut = 16000 * (1 - u) ** 1.3 + 400
alpha = 1 - np.exp(-2 * np.pi * cut / SR)
y = np.zeros(2)
for i in range(L):
    y = y + alpha[i] * (seg[i] - y); seg[i] = y
music[t0:t0 + L] = seg

# ---- effects ----------------------------------------------------------------------------------------------------
music_lufs, _ = lufs(music[:int(6.9 * SR)])
sfx_bus = np.zeros((N, 2))
hits = []
names = ['box_thud_a', 'box_thud_b', 'box_thud_c', 'box_thud_d', 'box_thud_heavy']
SHAPE = {'box_thud_d': 0.07}   # this take tumbles (three knocks in 130 ms); the box lands once, so keep one knock
for fr, nm in zip(lands, names):
    clip = sfx(nm)
    if nm in SHAPE:
        a0 = attack(clip); keep = a0 + int(SHAPE[nm] * SR); tail = np.exp(-np.arange(len(clip) - keep) / (0.018 * SR))
        clip[keep:] *= tail[:, None]
    cl, _ = lufs(clip)
    target = music_lufs - (3.5 if 'heavy' in nm else 6.5)   # under the music; the heavy landing stands out a bit
    at = place(sfx_bus, clip, fr, gain_db=target - cl)
    hits.append({'frame': fr, 'label': nm, 'attack_sample': at})
rise = sfx('logo_rise', trim=False)
rl, _ = lufs(rise)
at = place(sfx_bus, rise, LOGO_IN + 3, gain_db=(music_lufs - 7.5) - rl)   # the bell blooms as the wordmark arrives
hits.append({'frame': LOGO_IN + 3, 'label': 'logo_rise', 'attack_sample': at})
room = sfx('shop_roomtone', trim=False)
room = np.vstack([room] * 3)[:N]
rml, _ = lufs(room)
room *= 10 ** (((music_lufs - 30) - rml) / 20)
room_env = np.full(N, 1.0); r0 = int((TAPE0 - 10) / FPS * SR); room_env[r0:] = np.linspace(1, 2.2, N - r0)
room *= room_env[:, None]      # comes up a touch once the music has gone

# ---- master -----------------------------------------------------------------------------------------------------
mix = music + sfx_bus + room
write(STEMS / 'music.wav', music); write(STEMS / 'sfx.wav', sfx_bus); write(STEMS / 'room.wav', room)
pre = STEMS / 'premaster.wav'; write(pre, mix)
TARGET = -13.6   # the render's AAC encode loses about 0.5 LU, so the delivered file lands near -14
out = OUT / 'mix.wav'
I, _ = lufs(mix); gain = TARGET - I
for it in range(4):   # the limiter eats level, so iterate the gain until the limited mix measures TARGET
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(pre), '-af',
                    f'volume={gain:.2f}dB,alimiter=limit=0.79:attack=1:release=40:level=false,aresample=48000',
                    '-ar', str(SR), '-ac', '2', str(out)], check=True)
    r0 = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(out), '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True)
    got = float(re.search(r'I:\s+(-?[\d.]+) LUFS', r0.stderr[r0.stderr.rfind('Summary:'):]).group(1))
    if abs(got - TARGET) < 0.1: break
    gain += TARGET - got
r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(out), '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True)
s = r.stderr[r.stderr.rfind('Summary:'):]
print('music', round(music_lufs, 1), 'LUFS (before master); master gain', round(gain, 2), 'dB')
print(re.sub(r'\s+', ' ', s)[:300])
json.dump({'hits': hits, 'cues': [{'frame': h['frame'], 'label': h['label']} for h in hits]}, open(HERE / 'cues.json', 'w'), indent=1)
json.dump([{'frame': h['frame'], 'label': h['label']} for h in hits], open(HERE / 'cues-sync.json', 'w'), indent=1)
print('hits', [(h['label'], h['frame']) for h in hits])
