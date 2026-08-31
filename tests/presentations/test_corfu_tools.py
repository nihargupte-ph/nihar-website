import importlib.util
import json
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'corfu' / 'tools'


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ATOM = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2009.04771v2</id>
    <published>2020-09-10T15:58:51Z</published>
    <title>GW190521: orbital eccentricity and signatures of dynamical
  formation in a binary black hole merger signal</title>
    <author><name>Isobel M. Romero-Shaw</name></author>
    <author><name>Paul D. Lasky</name></author>
  </entry>
</feed>'''


def test_parse_atom_extracts_entry_fields():
    m = load('arxivmeta')
    [e] = m.parse_atom(ATOM)
    assert e['arxiv'] == '2009.04771'
    assert e['v1_date'] == '2020-09-10'
    assert e['title'] == 'GW190521: orbital eccentricity and signatures of dynamical formation in a binary black hole merger signal'
    assert e['authors'] == ['Isobel M. Romero-Shaw', 'Paul D. Lasky']
    assert e['first_author'] == 'Romero-Shaw'


def test_entry_id_and_make_entry():
    m = load('arxivmeta')
    assert m.entry_id('Romero-Shaw', '2020-09-10') == 'romero-shaw-2020'
    assert m.entry_id('Calderón Bustillo', '2021-01-01') == 'calderon-bustillo-2021'
    e = m.make_entry(m.parse_atom(ATOM)[0], 'real-data')
    assert e['id'] == 'romero-shaw-2020' and e['lane'] == 'real-data'
    assert e['figure'] is None and e['caption'] == ''
    assert e['authors'] == 'Romero-Shaw, Lasky'


PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc0f01f0005000101f9b6a1230000000049454e44ae426082')


def _timeline(tmp_path):
    tl = tmp_path / 'static' / 'timeline'
    tl.mkdir(parents=True)
    (tl / 'timeline.json').write_text(json.dumps({'lanes': [{'id': 'real-data', 'title': 'x'}], 'entries': [
        {'id': 'a-2020', 'lane': 'real-data', 'first_author': 'A', 'authors': 'A', 'title': 't', 'arxiv': '2001.00001',
         'v1_date': '2020-01-01', 'figure': None, 'caption': ''}]}))
    return tl / 'timeline.json'


def test_pick_copies_png_and_updates_json(tmp_path):
    fp = load('figpicker')
    tl = _timeline(tmp_path)
    src = tmp_path / 'fig1.png'; src.write_bytes(PNG)
    e = fp.pick(tl, 'a-2020', src, 'Fig. 1 — thing')
    assert e['figure'] == 'figs/a-2020.png' and e['caption'] == 'Fig. 1 — thing'
    assert (tl.parent / 'figs' / 'a-2020.png').read_bytes() == PNG
    assert json.loads(tl.read_text())['entries'][0]['figure'] == 'figs/a-2020.png'
    e = fp.pick(tl, 'a-2020', None, '')
    assert e['figure'] is None and not (tl.parent / 'figs' / 'a-2020.png').exists()


def test_pick_unknown_entry_raises(tmp_path):
    fp = load('figpicker')
    with pytest.raises(KeyError):
        fp.pick(_timeline(tmp_path), 'nope', None, '')


def test_extract_figures_collects_rasters_and_skips_junk(tmp_path):
    fp = load('figpicker')
    src = tmp_path / 'src'; (src / 'figs').mkdir(parents=True)
    (src / 'figs' / 'plot.png').write_bytes(PNG)
    (src / 'main.tex').write_text('x')
    out = tmp_path / 'out'
    figs = fp.extract_figures(src, out)
    assert [f.name for f in figs] == ['figs__plot.png']
    assert figs[0].read_bytes() == PNG


def test_render_index_lists_papers_and_figures(tmp_path):
    fp = load('figpicker')
    tl = json.loads(_timeline(tmp_path).read_text())
    html = fp.render_index(tl, {'a-2020': [tmp_path / 'x.png']}, tmp_path)
    assert 'a-2020' in html and 'x.png' in html and 'No figure' in html
