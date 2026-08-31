"""deck.yaml → dataclasses. Pure; no Django imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

import re

TRANSITIONS = ('fade', 'slide', 'none')
DEFAULT_FOOTER = {'bg': '#e8e6e1', 'fg': '#444444'}
_HEX_COLOUR = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
DEFAULT_THEME = {
    'bg': '#1f2429', 'fg': '#f4f1ea', 'accents': ['#37b49f', '#e9c46a', '#e76f51'],
    'font_display': 'Montserrat', 'font_body': 'Inter',
}


class DeckError(Exception):
    def __init__(self, path, message):
        self.path = Path(path)
        self.message = message
        super().__init__(f'{self.path}: {message}')


@dataclass
class Hotspot:
    rect: list[float]
    title: str
    body: str = ''
    links: list[dict] = field(default_factory=list)


@dataclass
class ShowRef:
    id: str
    rect: list[float] | None = None


@dataclass
class InteractionDef:
    id: str
    type: str
    config: dict


@dataclass
class Slide:
    id: str
    kind: str
    path: str
    poster: str | None = None
    underlay: str | None = None
    hotspots: list[Hotspot] = field(default_factory=list)
    ask: list[str] = field(default_factory=list)
    show: list[ShowRef] = field(default_factory=list)
    footer: bool = True
    continues: bool = False   # reveal step: same logical slide as the previous one
    number: int = 0           # logical slide number, set by load_deck

    @property
    def uses_stage(self):
        return self.kind in ('svg', 'video')


@dataclass
class Deck:
    slug: str
    dir: Path
    title: str
    date: str
    subtitle: str
    venue: str            # where the talk was given, e.g. 'GR-Amaldi @ Glasgow, UK'
    transition: str
    expertise: list[str]
    theme: dict
    interactions: list[InteractionDef]
    slides: list[Slide]
    footer: dict | None = None
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def slide(self, slide_id):
        return next((s for s in self.slides if s.id == slide_id), None)

    def interaction(self, iid):
        return next((i for i in self.interactions if i.id == iid), None)

    def slide_index(self, slide_id):
        for n, s in enumerate(self.slides):
            if s.id == slide_id:
                return n
        return -1

    def interactions_for_slide(self, slide):
        ids = list(slide.ask) + [r.id for r in slide.show]
        seen, out = set(), []
        for i in self.interactions:
            if i.id in ids and i.id not in seen:
                seen.add(i.id)
                out.append(i)
        return out


def _rect(value, where, path):
    if (not isinstance(value, list) or len(value) != 4
            or not all(isinstance(v, (int, float)) for v in value)
            or not all(0 <= v <= 1 for v in value)):
        raise DeckError(path, f'{where}: rect must be [x, y, w, h] fractions in 0..1, got {value!r}')
    return [float(v) for v in value]


def _require_file(deck_dir, rel, where, path):
    if not isinstance(rel, str) or not (deck_dir / rel).is_file():
        raise DeckError(path, f'{where}: file not found: {rel}')
    return rel


def _parse_hotspot(h, where, path):
    if not isinstance(h, dict) or 'rect' not in h or 'title' not in h:
        raise DeckError(path, f'{where}: hotspot needs rect and title')
    links = h.get('links') or []
    for l in links:
        if not isinstance(l, dict) or 'url' not in l:
            raise DeckError(path, f'{where}: hotspot link needs url')
        l.setdefault('label', l['url'])
    return Hotspot(rect=_rect(h['rect'], where, path), title=str(h['title']),
                   body=str(h.get('body') or ''), links=links)


def _parse_slide(entry, n, deck_dir, path, interaction_ids):
    where = f'slides[{n}]'
    if not isinstance(entry, dict) or not entry.get('id'):
        raise DeckError(path, f'{where}: slide needs an id')
    sid = str(entry['id'])
    where = f"slide '{sid}'"
    kinds = [k for k in ('svg', 'html', 'video') if k in entry]
    if len(kinds) != 1:
        raise DeckError(path, f'{where}: give exactly one of svg, html or video')
    kind = kinds[0]
    rel = _require_file(deck_dir, entry[kind], where, path)
    poster = entry.get('poster')
    if poster is not None:
        _require_file(deck_dir, poster, where, path)
    underlay = entry.get('underlay')
    if underlay is not None:
        if kind != 'html':
            raise DeckError(path, f'{where}: underlay is only valid on html slides')
        _require_file(deck_dir, underlay, where, path)
    hotspots = [_parse_hotspot(h, where, path) for h in (entry.get('hotspots') or [])]
    if hotspots and kind == 'html':
        raise DeckError(path, f'{where}: html slides use data-hotspot markup, not a hotspots list')
    ask = [str(a) for a in (entry.get('ask') or [])]
    for a in ask:
        if a not in interaction_ids:
            raise DeckError(path, f"{where}: ask: unknown interaction '{a}'")
    show = []
    for s in (entry.get('show') or []):
        if not isinstance(s, dict) or 'id' not in s:
            raise DeckError(path, f'{where}: show entries need an id')
        if s['id'] not in interaction_ids:
            raise DeckError(path, f"{where}: show: unknown interaction '{s['id']}'")
        rect = s.get('rect')
        if kind == 'html' and rect is not None:
            raise DeckError(path, f"{where}: show '{s['id']}': html slides must not give rect (use data-interaction markup)")
        if kind != 'html' and rect is None:
            raise DeckError(path, f"{where}: show '{s['id']}': svg/video slides must give rect")
        show.append(ShowRef(id=str(s['id']), rect=_rect(rect, where, path) if rect is not None else None))
    footer = entry.get('footer', True)
    if not isinstance(footer, bool):
        raise DeckError(path, f'{where}: footer must be true or false')
    continues = entry.get('continues', False)
    if not isinstance(continues, bool):
        raise DeckError(path, f'{where}: continues must be true or false')
    if continues and n == 0:
        raise DeckError(path, f'{where}: the first slide cannot continue a previous one')
    return Slide(id=sid, kind=kind, path=rel, poster=poster, underlay=underlay,
                 hotspots=hotspots, ask=ask, show=show, footer=footer, continues=continues)


def _parse_footer(raw, path):
    """Bottom bar: name · affiliation · page number. Absent or false → no bar."""
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise DeckError(path, 'footer must be a mapping with name and affiliation, or false')
    if not raw.get('name'):
        raise DeckError(path, 'footer: name is required')
    footer = {'name': str(raw['name']), 'affiliation': str(raw.get('affiliation') or '')}
    for key in ('bg', 'fg'):
        value = raw.get(key, DEFAULT_FOOTER[key])
        if not isinstance(value, str) or not _HEX_COLOUR.match(value):
            raise DeckError(path, f"footer.{key} must be a hex colour like '#e8e6e1', got {value!r}")
        footer[key] = value
    return footer


def load_deck(deck_dir, interaction_validator=None):
    deck_dir = Path(deck_dir)
    path = deck_dir / 'deck.yaml'
    if not path.is_file():
        raise DeckError(path, 'deck.yaml not found')
    try:
        raw = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as e:
        raise DeckError(path, f'yaml parse error: {e}')
    if not isinstance(raw, dict):
        raise DeckError(path, 'top level must be a mapping')
    if not raw.get('title'):
        raise DeckError(path, 'title is required')

    expertise = raw.get('expertise')
    if not isinstance(expertise, list) or not (2 <= len(expertise) <= 6):
        raise DeckError(path, 'expertise must be a list of 2–6 tags')
    expertise = [str(e) for e in expertise]

    transition = raw.get('transition', 'none')
    if transition not in TRANSITIONS:
        raise DeckError(path, f'transition must be one of {TRANSITIONS}')

    theme = dict(DEFAULT_THEME)
    theme.update(raw.get('theme') or {})
    if not isinstance(theme.get('accents'), list) or not theme['accents']:
        raise DeckError(path, 'theme.accents must be a non-empty list')

    footer = _parse_footer(raw.get('footer'), path)

    interactions, ids = [], set()
    for n, entry in enumerate(raw.get('interactions') or []):
        if not isinstance(entry, dict) or not entry.get('id') or not entry.get('type'):
            raise DeckError(path, f'interactions[{n}]: needs id and type')
        iid, itype = str(entry['id']), str(entry['type'])
        if iid in ids:
            raise DeckError(path, f"duplicate interaction id '{iid}'")
        ids.add(iid)
        config = {k: v for k, v in entry.items() if k not in ('id', 'type')}
        if interaction_validator is not None:
            try:
                interaction_validator(itype, config)
            except ValueError as e:
                raise DeckError(path, f"interaction '{iid}': {e}")
        interactions.append(InteractionDef(id=iid, type=itype, config=config))

    slides, sids = [], set()
    for n, entry in enumerate(raw.get('slides') or []):
        s = _parse_slide(entry, n, deck_dir, path, ids)
        if s.id in sids:
            raise DeckError(path, f"duplicate slide id '{s.id}'")
        sids.add(s.id)
        slides.append(s)
    if not slides:
        raise DeckError(path, 'slides must contain at least one slide')
    number = 0
    for s in slides:
        if not s.continues:
            number += 1
        s.number = number

    asked = {a for s in slides for a in s.ask}
    warnings = [f"interaction '{i.id}' is never asked on any slide" for i in interactions if i.id not in asked]

    return Deck(slug=deck_dir.name, dir=deck_dir, title=str(raw['title']), date=str(raw.get('date') or ''),
                subtitle=str(raw.get('subtitle') or ''), venue=str(raw.get('venue') or ''), transition=transition, expertise=expertise,
                theme=theme, interactions=interactions, slides=slides, footer=footer, page_count=number,
                warnings=warnings)
