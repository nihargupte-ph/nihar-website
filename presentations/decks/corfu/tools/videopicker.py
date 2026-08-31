"""Throwaway picker for the formation-channel animations (slide 05).

    micromamba run -n django-nihar-website python tools/videopicker.py [--port 8767]

One row per channel with every candidate from tools/manim/candidates/<id>-<n>.mp4 (made by
tools/manim/render.sh; VARIANT=n for alternatives). Hover a candidate to play it; click
"choose" to copy it to static/channels/media/<id>.{mp4,png} and point the channel's `media`
at it in channels.json. Ctrl-C to stop.
"""
import html
import json
import re
import shutil
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
CH = DECK / 'static' / 'channels'
JSON = CH / 'channels.json'
MEDIA = CH / 'media'
CAND = DECK / 'tools' / 'manim' / 'candidates'


def load():
    return json.loads(JSON.read_text())


def candidates(cid):
    return sorted(CAND.glob(f'{cid}-*.mp4'), key=lambda p: int(re.search(r'-(\d+)\.mp4$', p.name).group(1)))


def chosen(c):
    return c.get('media', {}).get('candidate')


def pick(cid, name):
    src = CAND / name
    if not src.is_file() or not name.startswith(cid + '-'):
        raise FileNotFoundError(name)
    MEDIA.mkdir(exist_ok=True)
    shutil.copy(src, MEDIA / f'{cid}.mp4')
    shutil.copy(src.with_suffix('.png'), MEDIA / f'{cid}.png')
    data = load()
    c = next(c for c in data['channels'] if c['id'] == cid)
    c['media'] = {'type': 'video', 'src': f'media/{cid}.mp4', 'still': f'media/{cid}.png', 'candidate': name,
                  'credit': f"Manim cartoon (tools/manim/scene_{cid.replace('-', '_')}.py, variant {name.rsplit('-', 1)[1][:-4]})", 'caption': ''}
    JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def render_index():
    rows = []
    for c in load()['channels']:
        cur = chosen(c)
        cards = ''.join(
            f'<figure class="{"on" if p.name == cur else ""}"><video muted loop playsinline preload="metadata" poster="/cand/{p.stem}.png" '
            f'src="/cand/{p.name}" onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0"></video>'
            f'<figcaption>{p.stem.rsplit("-",1)[1]} <button onclick="pick(\'{c["id"]}\',\'{p.name}\',this)">choose</button></figcaption></figure>'
            for p in candidates(c['id']))
        rows.append(f'<section><h2>{html.escape(c["name"])} <small>{c["id"]} · {"chosen: " + cur if cur else "none chosen"}</small></h2><div class="row">{cards or "<em>no candidates yet</em>"}</div></section>')
    return f'''<!doctype html><meta charset="utf-8"><title>video picker</title>
<style>body{{font:14px system-ui;margin:1.5rem;background:#fdfdfd;color:#504c44}}h2{{font-size:1rem;margin:1.4rem 0 .4rem}}small{{font-weight:400;opacity:.6}}
.row{{display:flex;gap:1rem;flex-wrap:wrap}}figure{{margin:0;width:320px;border:2px solid #ddd;border-radius:8px;padding:4px}}figure.on{{border-color:#b3262e}}
video{{width:100%;aspect-ratio:16/9;display:block;background:#fdfdfd}}figcaption{{display:flex;justify-content:space-between;align-items:center;padding:.3rem .2rem 0}}button{{font:inherit;cursor:pointer}}</style>
<h1 style="font-size:1.2rem">Formation-channel animations — hover to play, click <b>choose</b></h1>
{''.join(rows)}
<script>async function pick(id,name,btn){{const r=await fetch('/pick?'+new URLSearchParams({{id,name}}));if(!r.ok){{alert(await r.text());return}}
const fig=btn.closest('figure');fig.parentElement.querySelectorAll('figure').forEach(f=>f.classList.remove('on'));fig.classList.add('on');
fig.closest('section').querySelector('small').textContent=id+' · chosen: '+name}}</script>'''


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype='text/html; charset=utf-8'):
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == '/':
            return self.send(200, render_index().encode())
        if u.path.startswith('/cand/'):
            f = CAND / Path(u.path).name
            if not f.is_file():
                return self.send(404, b'no')
            return self.send(200, f.read_bytes(), 'video/mp4' if f.suffix == '.mp4' else 'image/png')
        if u.path == '/pick':
            try:
                pick(q['id'][0], q['name'][0]); return self.send(200, b'ok', 'text/plain')
            except Exception as e:  # noqa: BLE001
                return self.send(400, str(e).encode(), 'text/plain')
        self.send(404, b'no')


if __name__ == '__main__':
    port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 8767
    print(f'http://localhost:{port}/'); ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
