"""Throwaway icon picker for the formation-channel cards (slide 05).

    micromamba run -n django-nihar-website python tools/iconpicker.py [--port 8766]

Serves one row per channel with the five line-art variants from static/channels/icons/
(made by tools/channelicons.py). Clicking one writes `"icon": "icons/<file>"` into that
channel in static/channels/channels.json; "none" clears it. Ctrl-C to stop.
"""
import html
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
CH = DECK / 'static' / 'channels'
JSON = CH / 'channels.json'
ICONS = CH / 'icons'


def load():
    return json.loads(JSON.read_text())


def pick(channel_id, icon):
    """Set (icon = 'icons/<file>') or clear (icon None) the icon of one channel."""
    data = load()
    c = next((c for c in data['channels'] if c['id'] == channel_id), None)
    if c is None:
        raise KeyError(channel_id)
    if icon is None:
        c.pop('icon', None)
    else:
        if not (ICONS / Path(icon).name).is_file() or not icon.startswith('icons/'):
            raise FileNotFoundError(icon)
        c['icon'] = icon
    JSON.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    return c


def render_index(data):
    h = html.escape
    rows = []
    for c in data['channels']:
        files = sorted(ICONS.glob(f'{c["id"]}-*.svg'), key=lambda p: p.name)
        cur = c.get('icon')
        figs = ''.join(
            f'<figure class="{"picked" if cur == f"icons/{f.name}" else ""}" data-id="{h(c["id"])}" data-icon="icons/{h(f.name)}" title="{h(f.name)}">'
            f'<img src="/icons/{h(f.name)}"><figcaption>{h(f.name)}</figcaption></figure>' for f in files)
        rows.append(f'''<section id="{h(c["id"])}"><header><b>{h(c["name"])}</b> <code>{h(c["id"])}</code>
          <span class="state">{f'<img class="chosen" src="/{h(cur)}"> {h(cur)}' if cur else '<em>no icon (video face)</em>'}</span>
          <button class="none" data-id="{h(c["id"])}">none</button></header>
          <div class="grid">{figs or "<em>no icons — run tools/channelicons.py</em>"}</div></section>''')
    return f'''<!doctype html><meta charset="utf-8"><title>iconpicker</title>
<style>body{{font:14px system-ui;margin:1rem 2rem;background:#151515;color:#eee}}section{{margin-bottom:1.6rem;border-top:1px solid #444;padding-top:.6rem}}
header{{display:flex;gap:.8rem;align-items:center;flex-wrap:wrap;padding:.3rem 0}}code{{opacity:.6}}
.grid{{display:flex;flex-wrap:wrap;gap:.6rem}}figure{{margin:0;width:180px;cursor:pointer;border:3px solid transparent;padding:2px;position:relative;border-radius:8px}}figure:hover{{border-color:#37b49f}}
figure.picked{{border-color:#e9c46a;background:#e9c46a22}}figure.picked::after{{content:"✓ chosen";position:absolute;top:4px;left:4px;background:#e9c46a;color:#000;font-weight:700;font-size:12px;padding:2px 6px;border-radius:4px}}
figure img{{width:180px;height:180px;display:block;background:#efece5;border-radius:6px}}figcaption{{font-size:11px;opacity:.6;text-align:center}}
.state{{display:flex;align-items:center;gap:.5rem}}.state.saved{{color:#e9c46a;font-weight:700}}.chosen{{height:44px;width:44px;background:#efece5;border-radius:4px}}
button{{background:#333;color:#eee;border:1px solid #666;border-radius:4px;padding:2px 10px;cursor:pointer}}</style>
<h1>Pick an icon per channel</h1><p>Click an icon to use it as the card face (the video still plays on hover). "none" goes back to the video thumbnail. Edits land in <code>static/channels/channels.json</code>. Ctrl-C the server when done.</p>
{''.join(rows)}
<script>
async function post(id, icon, fig){{
  const r=await fetch('/pick',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{id,icon}})}});
  const sec=document.getElementById(id), state=sec.querySelector('.state');
  if(!r.ok){{state.textContent='error: '+await r.text();return;}}
  sec.querySelectorAll('figure.picked').forEach(f=>f.classList.remove('picked'));
  if(fig){{fig.classList.add('picked');state.innerHTML='<img class="chosen" src="/'+icon+'"> '+icon+' saved';}}
  else state.innerHTML='<em>no icon (video face)</em>';
  state.classList.add('saved');setTimeout(()=>state.classList.remove('saved'),1500);
}}
document.querySelectorAll('figure').forEach(f=>f.onclick=()=>post(f.dataset.id,f.dataset.icon,f));
document.querySelectorAll('.none').forEach(b=>b.onclick=()=>post(b.dataset.id,null,null));
</script>'''


def serve(port):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype='text/html; charset=utf-8'):
            self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            p = urllib.parse.unquote(self.path.split('?')[0])
            if p == '/':
                return self._send(200, render_index(load()).encode())
            if p.startswith('/icons/'):
                f = (ICONS / p[len('/icons/'):]).resolve()
                if f.is_file() and f.suffix == '.svg' and ICONS.resolve() in f.parents:
                    return self._send(200, f.read_bytes(), 'image/svg+xml')
            self._send(404, b'not found', 'text/plain')

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            try:
                pick(body['id'], body.get('icon') or None)
            except (KeyError, OSError) as ex:
                return self._send(400, str(ex).encode(), 'text/plain')
            self._send(200, b'ok', 'text/plain')

        def log_message(self, *a):
            pass

    print(f'→ http://localhost:{port}/  (Ctrl-C to stop)')
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    serve(int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 8766)
