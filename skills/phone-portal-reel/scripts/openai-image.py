#!/usr/bin/env python3
"""Generate or edit one image with the OpenAI Images API, and log tokens and an estimated cost.

  python3 openai-image.py OUT.png "prompt" [--model gpt-image-2] [--size 1152x2048] [--quality medium]
  python3 openai-image.py OUT.png "prompt" --edit IN.png [--mask MASK.png] [--model gpt-image-1.5 --fidelity high]

The key is OPENAI_API_KEY from the environment, or from a .env in the working folder or any folder above it. It is
never printed. Each call writes OUT.json beside the image and appends one line to openai-ledger.jsonl in OUT's
folder (prompt, model, size, tokens, estimated $). The prices are rough token-rate estimates (EST below); the
OpenAI usage page has the real bill.

Notes (Nov 2026): gpt-image-2 takes any size divisible by 16 but refuses --background transparent and --fidelity.
A mask is RGBA: transparent where the model may paint. The model still redraws the rest, so take an edit only
inside its mask (see blend-edit.py).
"""
import argparse, base64, json, os, pathlib, re, sys, time

EST = {'text_in': 5.0, 'image_in': 8.0, 'image_out': 30.0}  # $ per 1M tokens, rough


def key():
    if os.environ.get('OPENAI_API_KEY'):
        return os.environ['OPENAI_API_KEY']
    here = pathlib.Path.cwd().resolve()
    for d in [here, *here.parents]:
        f = d / '.env'
        if f.is_file():
            for line in f.read_text(encoding='utf-8-sig').splitlines():
                m = re.match(r'\s*(?:export\s+)?OPENAI_API_KEY\s*=\s*["\']?([^"\'\s]+)', line)
                if m:
                    return m.group(1)
    sys.exit('OPENAI_API_KEY is not set, and no .env above the working folder has it')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('out')
    ap.add_argument('prompt')
    ap.add_argument('--model', default='gpt-image-2')
    ap.add_argument('--size', default='1152x2048')
    ap.add_argument('--quality', default='medium', help='high | medium | low')
    ap.add_argument('--edit', nargs='*', default=None, help='input image(s): edit instead of generate')
    ap.add_argument('--mask', default=None, help='RGBA mask, transparent where the model may paint')
    ap.add_argument('--fidelity', default=None, help='input_fidelity for edits: high keeps more of the input (not gpt-image-2)')
    ap.add_argument('--background', default=None, help='transparent | opaque | auto (not gpt-image-2)')
    ap.add_argument('--n', type=int, default=1, help='how many options')
    a = ap.parse_args()

    import openai
    from openai import OpenAI
    c = OpenAI(api_key=key())
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    kw = dict(model=a.model, prompt=a.prompt, size=a.size, quality=a.quality, n=a.n)
    if a.background:
        kw['background'] = a.background
    t0 = time.time()
    try:
        if a.edit:
            files = [open(p, 'rb') for p in a.edit]
            kw['image'] = files if len(files) > 1 else files[0]
            if a.mask:
                kw['mask'] = open(a.mask, 'rb')
            if a.fidelity:
                kw['input_fidelity'] = a.fidelity
            r = c.images.edit(**kw)
        else:
            r = c.images.generate(**kw)
    except openai.APIStatusError as e:
        sys.exit(f'OpenAI {e.status_code}: {getattr(e, "message", e)}')
    secs = time.time() - t0

    paths = []
    for i, d in enumerate(r.data):
        p = out if a.n == 1 else out.with_name(f'{out.stem}-{i + 1}{out.suffix}')
        p.write_bytes(base64.b64decode(d.b64_json))
        paths.append(str(p))

    u = getattr(r, 'usage', None)
    tok, usd = {}, None
    if u:
        det = getattr(u, 'input_tokens_details', None)
        tok = {'input': u.input_tokens, 'output': u.output_tokens,
               'input_text': getattr(det, 'text_tokens', None) if det else None,
               'input_image': getattr(det, 'image_tokens', None) if det else None}
        ti = tok['input_text'] if tok['input_text'] is not None else tok['input']
        ii = tok['input_image'] or 0
        usd = round((ti * EST['text_in'] + ii * EST['image_in'] + tok['output'] * EST['image_out']) / 1e6, 4)

    rec = {'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'out': paths, 'model': a.model, 'size': a.size,
           'quality': a.quality, 'mode': 'edit' if a.edit else 'generate', 'inputs': a.edit, 'mask': a.mask,
           'prompt': a.prompt, 'tokens': tok, 'usd_est': usd, 'seconds': round(secs, 1)}
    out.with_suffix('.json').write_text(json.dumps(rec, indent=2))
    with open(out.parent / 'openai-ledger.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps({'out': paths, 'tokens': tok, 'usd_est': usd, 'seconds': round(secs, 1)}))


if __name__ == '__main__':
    main()
