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
