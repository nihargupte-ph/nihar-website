"""arXiv API → timeline entry dicts.

    python tools/arxivmeta.py 2009.04771 2108.01284 … [--lane=real-data]

Prints a JSON list of timeline entries (figure: null) for the given arXiv ids,
with v1_date taken from the API's `published` field (= first version).
"""
import json
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

NS = {'a': 'http://www.w3.org/2005/Atom'}
API = 'http://export.arxiv.org/api/query?id_list={}&max_results=200'
UA = 'nihar-website-timeline/1.0 (mailto:gupten8@gmail.com)'


def _surname(full):
    return full.strip().split()[-1]


def parse_atom(xml_text):
    out = []
    for e in ET.fromstring(xml_text).findall('a:entry', NS):
        aid = e.findtext('a:id', '', NS).rsplit('/', 1)[-1]
        aid = re.sub(r'v\d+$', '', aid)
        title = ' '.join(e.findtext('a:title', '', NS).split())
        authors = [' '.join(a.findtext('a:name', '', NS).split()) for a in e.findall('a:author', NS)]
        if not aid or not authors:
            continue
        out.append({'arxiv': aid, 'title': title, 'authors': authors,
                    'first_author': _surname(authors[0]),
                    'v1_date': e.findtext('a:published', '', NS)[:10]})
    return out


def fetch(ids):
    metas = []
    for i in range(0, len(ids), 50):
        url = API.format(','.join(ids[i:i + 50]))
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            metas.extend(parse_atom(r.read().decode('utf-8')))
        if i + 50 < len(ids):
            time.sleep(3)
    return metas


def entry_id(first_author, v1_date):
    s = unicodedata.normalize('NFKD', first_author).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return f'{s}-{v1_date[:4]}'


def make_entry(meta, lane):
    return {'id': entry_id(meta['first_author'], meta['v1_date']), 'lane': lane,
            'first_author': meta['first_author'],
            'authors': ', '.join(_surname(a) for a in meta['authors']),
            'title': meta['title'], 'arxiv': meta['arxiv'], 'v1_date': meta['v1_date'],
            'figure': None, 'caption': ''}


if __name__ == '__main__':
    lane = 'real-data'
    ids = []
    for a in sys.argv[1:]:
        if a.startswith('--lane='):
            lane = a.split('=', 1)[1]
        else:
            ids.append(a)
    print(json.dumps([make_entry(m, lane) for m in fetch(ids)], indent=1, ensure_ascii=False))
