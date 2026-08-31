"""Citation graph for the formation-channel slide, from INSPIRE.

    python tools/channelgraph.py --fetch   # query INSPIRE for every paper in tools/.cache/channels/intro_cites.json
    python tools/channelgraph.py           # build static/channels/graph.json from the cached answers

`intro_cites.json` lists the papers cited per channel in the introduction of arXiv:2603.29019
(channels: 1 isolated, 2 field triples, 3 dense clusters, 4 AGN disks; 0 = cited only outside the
list). The graph per channel = those papers + the external references that at least MIN_SHARED of
them cite, with an edge for every citation among the drawn nodes. The INSPIRE answers are cached in
tools/.cache/channels/ (gitignored) so the graph can be rebuilt offline.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache' / 'channels'
OUT = HERE.parent / 'static' / 'channels' / 'graph.json'
UA = 'nihar-website-channels/1.0 (mailto:gupten8@gmail.com)'
FIELDS = ('control_number,titles,arxiv_eprints,earliest_date,citation_count,authors.full_name,'
          'references.record,references.reference.arxiv_eprint,references.reference.title')
MIN_SHARED = 3      # an external paper is drawn when this many of the channel's papers cite it
MAX_EXTERNAL = 7    # per channel
CHANNELS = {1: 'isolated', 2: 'triples', 3: 'clusters', 4: 'agn'}


def api(query, size=1):
    url = 'https://inspirehep.net/api/literature?' + urllib.parse.urlencode({'q': query, 'size': size, 'fields': FIELDS})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=60) as r:
                return json.load(r)['hits']['hits']
        except Exception as exc:  # noqa: BLE001
            err = exc
            time.sleep(3 * (attempt + 1))
    print('FAIL', query, err, file=sys.stderr)
    return []


def node_of(meta):
    authors = [a.get('full_name', '') for a in meta.get('authors', [])]
    first = authors[0].split(',')[0] if authors else ''
    return {'recid': str(meta['control_number']), 'title': meta['titles'][0]['title'],
            'arxiv': (meta.get('arxiv_eprints') or [{}])[0].get('value'),
            'year': int((meta.get('earliest_date') or '0')[:4]) or None,
            'cites': meta.get('citation_count', 0), 'first': first,
            'label': first + ('+' if len(authors) > 2 else (' & ' + authors[1].split(',')[0] if len(authors) == 2 else '')),
            'refs': [str((r.get('record') or {}).get('$ref', '').rsplit('/', 1)[-1]) for r in meta.get('references', [])]}


def fetch():
    cites = json.load(open(CACHE / 'intro_cites.json'))
    found = {}
    for key, v in cites.items():
        chans = [c for c in v['channels'] if c]
        if not chans:
            continue
        if v['eprint']:
            q = 'arxiv:' + v['eprint']
        elif v['doi']:
            q = 'doi:' + v['doi'].split('doi.org/')[-1]
        else:
            q = 't:"' + re.sub(r'[{}]', '', v['title']) + '"'
        hits = api(q)
        if not hits:
            print('not on INSPIRE:', key, q)
            continue
        found[key] = {**node_of(hits[0]['metadata']), 'channels': chans}
        print(key, found[key]['recid'], len(found[key]['refs']), 'refs')
        time.sleep(1)
    json.dump(found, open(CACHE / 'papers.json', 'w'), indent=1)
    # external references shared by >= MIN_SHARED papers of any one channel
    wanted = set()
    for ch in CHANNELS:
        cnt = Counter(r for p in found.values() if ch in p['channels'] for r in set(p['refs']))
        wanted |= {r for r, n in cnt.items() if n >= MIN_SHARED and r not in {p['recid'] for p in found.values()}}
    ext = {}
    wanted = sorted(wanted)
    for i in range(0, len(wanted), 20):
        for h in api(' or '.join(f'control_number:{r}' for r in wanted[i:i + 20]), size=50):
            n = node_of(h['metadata']); n.pop('refs'); ext[n['recid']] = n
        time.sleep(1)
    json.dump(ext, open(CACHE / 'external.json', 'w'), indent=1)
    print(len(found), 'papers,', len(ext), 'shared external references cached')


def build():
    papers = json.load(open(CACHE / 'papers.json'))
    ext = json.load(open(CACHE / 'external.json'))
    graphs = {}
    for ch, name in CHANNELS.items():
        mine = {k: p for k, p in papers.items() if ch in p['channels']}
        recid_key = {p['recid']: k for k, p in papers.items()}
        cnt = Counter(r for p in mine.values() for r in set(p['refs']) if r in ext)
        shared = [r for r, n in cnt.most_common() if n >= MIN_SHARED][:MAX_EXTERNAL]
        nodes, edges = [], []
        for k, p in sorted(mine.items(), key=lambda kv: kv[1]['year'] or 0):
            nodes.append({'id': k, 'label': p['label'], 'year': p['year'], 'arxiv': p['arxiv'], 'title': p['title'], 'cites': p['cites'], 'kind': 'cited'})
        for r in shared:
            e = ext[r]
            nodes.append({'id': 'ext:' + r, 'label': e['label'], 'year': e['year'], 'arxiv': e['arxiv'], 'title': e['title'], 'cites': e['cites'], 'kind': 'shared', 'n': cnt[r]})
        ids = {n['id'] for n in nodes}
        for k, p in mine.items():
            for r in set(p['refs']):
                tgt = recid_key.get(r) if r in recid_key else ('ext:' + r if 'ext:' + r in ids else None)
                if tgt and tgt in ids and tgt != k:
                    edges.append([k, tgt])
        graphs[name] = {'nodes': nodes, 'edges': edges}
        print(name, len(nodes), 'nodes', len(edges), 'edges')
    # flat reference table for every intro-cited paper, including the ones INSPIRE does not know
    cites = json.load(open(CACHE / 'intro_cites.json'))
    refs = {}
    for key, v in cites.items():
        if not [c for c in v['channels'] if c]:
            continue
        p = papers.get(key)
        year = p['year'] if p else (int(m.group(1)) if (m := re.search(r'(18|19|20)\d\d', key)) else None)
        title = re.sub(r'[{}]', '', p['title'] if p else v['title'])
        author = re.sub(r'[{}]', '', v['author']).split(' and ')[0].split(',')[0].strip()
        refs[key] = {'label': p['label'] if p else author + ('+' if ' and ' in v['author'] else ''), 'title': title, 'year': year,
                     'arxiv': (p or {}).get('arxiv') or (v['eprint'] or None), 'doi': v['doi'] or None, 'cites': (p or {}).get('cites')}
    graphs['refs'] = refs
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(graphs, open(OUT, 'w'), indent=1)
    print('wrote', OUT)


if __name__ == '__main__':
    fetch() if '--fetch' in sys.argv else build()
