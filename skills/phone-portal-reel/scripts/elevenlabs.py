#!/usr/bin/env python3
"""Generate a reel's music bed and sound effects with ElevenLabs, cache them, and log the credits spent.

  python3 elevenlabs.py SPEC.json OUTDIR
  python3 elevenlabs.py --credits            (show the account's counter, spends nothing)

SPEC.json (see example/sound/spec.json):
  {"music": [{"name": "bed", "prompt": "... exactly 112 BPM, starts on the downbeat, no intro ...", "seconds": 14}],
   "sfx":   [{"name": "thud_a", "prompt": "a small cardboard box lands flat on a walnut shelf ...", "seconds": 0.6}]}

Each sound is saved as OUTDIR/<name>-<hash of prompt and length>.mp3, so a rerun with the same prompt spends nothing
and a changed prompt makes a new file. Music uses POST /v1/music (music_v2_5, instrumental); effects use
/v1/sound-generation. Credits are read from the subscription counter before and after (it lags, so it waits and
reads again) and appended to OUTDIR/credits.json.

The key is ELEVENLABS_API_KEY from the environment, or from a .env in the working folder or any folder above it.
It is never printed.
"""
import argparse, hashlib, json, os, pathlib, re, sys, time, urllib.error, urllib.request


def key():
    if os.environ.get('ELEVENLABS_API_KEY'):
        return os.environ['ELEVENLABS_API_KEY']
    here = pathlib.Path.cwd().resolve()
    for d in [here, *here.parents]:
        f = d / '.env'
        if f.is_file():
            for line in f.read_text(encoding='utf-8-sig').splitlines():
                m = re.match(r'\s*(?:export\s+)?ELEVENLABS_API_KEY\s*=\s*["\']?([^"\'\s]+)', line)
                if m:
                    return m.group(1)
    sys.exit('ELEVENLABS_API_KEY is not set, and no .env above the working folder has it')


def api(path, body=None, timeout=300):
    req = urllib.request.Request('https://api.elevenlabs.io' + path,
                                 headers={'xi-api-key': key(), 'Content-Type': 'application/json'})
    if body is not None:
        req.data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f'ElevenLabs {e.code} on {path}: {e.read()[:400].decode(errors="ignore")}')


def counter():
    s = json.loads(api('/v1/user/subscription'))
    return s['character_count'], s['character_limit']


def file_for(outdir, item):
    h = hashlib.sha1(f'{item["prompt"]}|{item["seconds"]}'.encode()).hexdigest()[:8]
    return outdir / f'{item["name"]}-{h}.mp3'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec', nargs='?')
    ap.add_argument('outdir', nargs='?')
    ap.add_argument('--credits', action='store_true', help='print the credit counter and stop')
    a = ap.parse_args()
    if a.credits:
        used, limit = counter()
        print(f'ElevenLabs: {used} of {limit} credits used this period')
        return
    if not (a.spec and a.outdir):
        ap.error('give SPEC.json and OUTDIR')
    spec = json.loads(pathlib.Path(a.spec).read_text())
    out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

    todo = [p for kind in ('sfx', 'music') for p in (file_for(out, i) for i in spec.get(kind, [])) if not p.exists()]
    if not todo:
        print('all cached in', out, '- this run used 0 credits')
        return
    before, limit = counter()
    t0, made = time.time(), []
    for item in spec.get('sfx', []):
        p = file_for(out, item)
        if p.exists():
            print('cached', p.name); continue
        p.write_bytes(api('/v1/sound-generation?output_format=mp3_44100_128',
                          {'text': item['prompt'], 'duration_seconds': item['seconds'],
                           'prompt_influence': item.get('influence', 0.5)}))
        made.append(p.name); print('made', p.name)
    for item in spec.get('music', []):
        p = file_for(out, item)
        if p.exists():
            print('cached', p.name); continue
        p.write_bytes(api('/v1/music?output_format=mp3_44100_192',
                          {'prompt': item['prompt'], 'music_length_ms': int(item['seconds'] * 1000),
                           'force_instrumental': item.get('instrumental', True),
                           'model_id': item.get('model_id', 'music_v2_5')}, timeout=600))
        made.append(p.name); print('made', p.name)

    after = before
    for i in range(6):  # the counter lags a little
        if not made:
            break
        time.sleep(4 + 3 * i)
        after, _ = counter()
        if after > before:
            break
    rec = {'when': time.strftime('%Y-%m-%d %H:%M'), 'made': made, 'credits': after - before,
           'counter_before': before, 'counter_after': after, 'limit': limit, 'seconds': round(time.time() - t0, 1)}
    log = out / 'credits.json'
    rows = json.loads(log.read_text()) if log.exists() else []
    rows.append(rec); log.write_text(json.dumps(rows, indent=1))
    print(f'ElevenLabs: this run used {rec["credits"]} credits; {sum(r["credits"] for r in rows)} so far in {out}')


if __name__ == '__main__':
    main()
