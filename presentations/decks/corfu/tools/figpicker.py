"""Throwaway figure picker for the citation timeline.

    micromamba run -n django-nihar-website python tools/figpicker.py [--port 8765] [--all]

Downloads each paper's arXiv source into tools/.cache/<arxiv>/, renders every
figure to PNG, and serves a page where clicking a thumbnail writes it into
static/timeline/figs/<id>.png and timeline.json. Ctrl-C to stop.
Only papers without a chosen figure are fetched unless --all is given.
"""
import gzip
import html
import io
import json
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
UA = 'nihar-website-timeline/1.0 (mailto:gupten8@gmail.com)'
RASTER = {'.png', '.jpg', '.jpeg'}
VECTOR = {'.pdf', '.eps', '.ps'}


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def fetch_source(arxiv, cache):
    """Download + unpack the e-print into cache/<arxiv>/src (and/or the PDF into cache/<arxiv>/paper.pdf)."""
    d = cache / arxiv.replace('/', '_'); src = d / 'src'
    if (d / '.done').exists():
        return d
    src.mkdir(parents=True, exist_ok=True)
    blob = _get(f'https://arxiv.org/e-print/{arxiv}')
    if blob[:4] == b'%PDF':
        (d / 'paper.pdf').write_bytes(blob)
    else:
        try:
            with tarfile.open(fileobj=io.BytesIO(blob), mode='r:*') as t:
                t.extractall(src, filter='data')
        except tarfile.ReadError:
            try:
                (src / 'main.tex').write_bytes(gzip.decompress(blob))
            except OSError:
                (src / 'blob').write_bytes(blob)
    if not any(p.suffix.lower() in RASTER | VECTOR for p in src.rglob('*')) and not (d / 'paper.pdf').exists():
        time.sleep(3)
        (d / 'paper.pdf').write_bytes(_get(f'https://arxiv.org/pdf/{arxiv}'))
    (d / '.done').write_text('ok')
    return d


def _to_png(path, out):
    if path.suffix.lower() in RASTER:
        shutil.copyfile(path, out)
        return out.exists()
    r = subprocess.run(['pdftocairo', '-png', '-singlefile', '-r', '110', str(path), str(out.with_suffix(''))],
                       capture_output=True, text=True)
    return r.returncode == 0 and out.exists()


def extract_figures(src_dir, out_dir):
    """Every figure-like file under src_dir → PNG in out_dir (flat, path-mangled names)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    figs = []
    for p in sorted(src_dir.rglob('*')) if src_dir.is_dir() else []:
        if not p.is_file() or p.suffix.lower() not in RASTER | VECTOR:
            continue
        rel = p.relative_to(src_dir)
        out = out_dir / ('__'.join(rel.parts)[: -len(p.suffix)] + '.png')
        if out.exists() or _to_png(p, out):
            figs.append(out)
    pdf = src_dir.parent / 'paper.pdf'
    if not figs and pdf.exists():
        subprocess.run(['pdfimages', '-png', str(pdf), str(out_dir / 'img')], capture_output=True)
        figs = sorted(out_dir.glob('img-*.png'))
    return figs


def pick(timeline_path, entry_id, png, caption):
    """Set (png given) or clear (png None) the figure of one entry; copies the PNG next to the JSON."""
    data = json.loads(timeline_path.read_text())
    entry = next((e for e in data['entries'] if e['id'] == entry_id), None)
    if entry is None:
        raise KeyError(entry_id)
    figs = timeline_path.parent / 'figs'; dest = figs / f'{entry_id}.png'
    if png is None:
        if dest.exists():
            dest.unlink()
        entry['figure'], entry['caption'] = None, ''
    else:
        figs.mkdir(exist_ok=True)
        shutil.copyfile(png, dest)
        entry['figure'], entry['caption'] = f'figs/{entry_id}.png', caption.strip()
    timeline_path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    return entry


def render_index(timeline, figs, cache):
    h = html.escape
    rows = []
    for e in sorted(timeline['entries'], key=lambda e: e['v1_date']):
        thumbs = ''.join(
            f'<figure data-id="{h(e["id"])}" data-file="{h(str(f))}" title="{h(f.name)}">'
            f'<img loading="lazy" src="/cache/{h(str(f.relative_to(cache)))}"><figcaption>{h(f.name)}</figcaption></figure>'
            for f in figs.get(e['id'], []))
        chosen = (f'<img class="chosen" src="/figs/{h(e["figure"].split("/")[-1])}?{time.time():.0f}">'
                  if e.get('figure') else '<em>nothing chosen</em>')
        rows.append(f'''<section id="{h(e["id"])}"><header><b>{h(e["first_author"])} {e["v1_date"][:4]}</b> · {h(e["title"])}
          <a href="https://arxiv.org/abs/{h(e["arxiv"])}" target="_blank">arXiv:{h(e["arxiv"])}</a>
          <span class="state">{chosen}</span>
          <label>caption <input class="cap" value="{h(e.get("caption") or "")}" placeholder="Fig. 2 — posterior on e"></label>
          <button class="nofig" data-id="{h(e["id"])}">No figure</button></header>
          <div class="grid">{thumbs or "<em>no figures extracted</em>"}</div></section>''')
    return f'''<!doctype html><meta charset="utf-8"><title>figpicker</title>
<style>body{{font:14px system-ui;margin:1rem 2rem;background:#151515;color:#eee}}section{{margin-bottom:2rem;border-top:1px solid #444;padding-top:.6rem}}
header{{display:flex;gap:.8rem;align-items:center;flex-wrap:wrap;position:sticky;top:0;background:#151515;padding:.4rem 0;z-index:2}}
.grid{{display:flex;flex-wrap:wrap;gap:.6rem}}figure{{margin:0;width:220px;cursor:pointer;border:2px solid transparent;padding:2px}}figure:hover{{border-color:#37b49f}}
img{{max-width:100%;background:#fff}}.chosen{{height:70px;width:auto}}figcaption{{font-size:11px;opacity:.6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
a{{color:#37b49f}}.cap{{width:22rem}}</style>
<h1>Pick a figure per paper</h1><p>Click a thumbnail to choose it (the caption box is saved with it). Ctrl-C the server when done.</p>
{''.join(rows)}
<script>
async function post(id, file, caption){{const r=await fetch('/pick',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{id,file,caption}})}});if(!r.ok)alert(await r.text());else location.reload();}}
document.querySelectorAll('figure').forEach(f=>f.onclick=()=>post(f.dataset.id,f.dataset.file,f.closest('section').querySelector('.cap').value||f.title));
document.querySelectorAll('.nofig').forEach(b=>b.onclick=()=>post(b.dataset.id,null,''));
</script>'''


def serve(deck_dir, port, refresh_all):
    tl_dir = deck_dir / 'static' / 'timeline'; tl_json = tl_dir / 'timeline.json'; cache = deck_dir / 'tools' / '.cache'
    cache.mkdir(parents=True, exist_ok=True)
    load = lambda: json.loads(tl_json.read_text())  # noqa: E731
    figs = {}
    todo = [e for e in load()['entries'] if refresh_all or not e.get('figure')]
    for i, e in enumerate(todo, 1):
        print(f'[{i}/{len(todo)}] {e["arxiv"]} {e["first_author"]} …', flush=True)
        try:
            d = fetch_source(e['arxiv'], cache)
            figs[e['id']] = extract_figures(d / 'src', d / 'png')
            print(f'   {len(figs[e["id"]])} figures')
        except Exception as ex:  # noqa: BLE001 — keep going, the page shows "no figures extracted"
            print(f'   failed: {ex}')
        if i < len(todo) and not (cache / e['arxiv'].replace('/', '_') / '.done').exists():
            time.sleep(3)

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype='text/html; charset=utf-8'):
            self.send_response(code); self.send_header('Content-Type', ctype); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            p = urllib.parse.unquote(self.path.split('?')[0])
            if p == '/':
                return self._send(200, render_index(load(), figs, cache).encode())
            for prefix, base in (('/cache/', cache), ('/figs/', tl_dir / 'figs')):
                if p.startswith(prefix):
                    f = (base / p[len(prefix):]).resolve()
                    if f.is_file() and base.resolve() in f.parents:
                        return self._send(200, f.read_bytes(), 'image/png')
            self._send(404, b'not found', 'text/plain')

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            try:
                pick(tl_json, body['id'], Path(body['file']) if body.get('file') else None, body.get('caption', ''))
            except (KeyError, OSError) as ex:
                return self._send(400, str(ex).encode(), 'text/plain')
            self._send(200, b'ok', 'text/plain')

        def log_message(self, *a):
            pass

    print(f'→ http://localhost:{port}/  (Ctrl-C to stop)')
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 8765
    serve(DECK, port, '--all' in sys.argv)
