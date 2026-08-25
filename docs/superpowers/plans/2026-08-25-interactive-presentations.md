# Interactive Presentations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `presentations` Django app that turns a folder of SVG/HTML/video slides plus a `deck.yaml` into a phone-synced, audience-polling talk that freezes into a permanent, commentable reference page.

**Architecture:** One engine app (`presentations/`) holds the only DB tables (audience data), a yaml registry that discovers `presentations/decks/<slug>/deck.yaml`, four pluggable interaction types with pure `aggregate()` functions, three page surfaces (archive / present / phone) and JSON endpoints polled every 1–1.5 s. Deck content never touches the DB; deck slug + yaml ids are the join key.

**Tech Stack:** Django 5.0.7, SQLite, PyYAML, jsonschema, markdown + bleach, qrcode (SVG output), vanilla JS (no bundler), Plotly via CDN in the example deck only, pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-08-25-interactive-presentations-design.md`

## Global Constraints

- Python env: run everything with `micromamba run -n django-nihar-website <cmd>` (memory: feedback_micromamba_env).
- Django 5.0.7; no new Django apps besides `presentations`; no Channels/ASGI; sync is short polling only.
- Deck content lives only in `presentations/decks/<slug>/`; the DB holds only `Session`, `Participant`, `Response`, `Comment`.
- Stage coordinates: rects are `[x, y, w, h]` fractions of a 1920×1080 stage; JS converts with `x*1920`, `y*1080`.
- Interaction states: exactly `hidden | open | closed | revealed`; only staff may change them; phones may respond only while `open` (409 otherwise).
- Comment limits: body ≤ 1000 chars, 5 comments/minute per `ip_hash`, honeypot field named `website` must be empty.
- IPs are stored only as `sha256(settings.SECRET_KEY + ip)` hex.
- Interaction ids and slide ids are stable persistence keys; never auto-renumber.
- Tests: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q` must pass at the end of every task.
- Commit after every task with the trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

## File map

```
presentations/
  __init__.py  apps.py  admin.py  urls.py  models.py
  schema.py         load_deck(): deck.yaml → dataclasses, raises DeckError
  registry.py       all_decks(), get_deck(slug), decks_dir(), clear_cache()
  finders.py        DeckStaticFinder: decks/<slug>/static + slides → /static/decks/<slug>/…
  livecache.py      1-second in-process cache for live state
  textutil.py       render_markdown(), hash_ip(), tokenize_words()
  sanitize.py       sanitize_svg(text) -> text
  theme.py          derive_theme(svg_paths) -> dict
  interactions/__init__.py  base.py  choice.py  numeric.py  distribution.py  text.py
  views/__init__.py  common.py  archive.py  present.py  phone.py
  management/commands/checkdecks.py  newdeck.py
  templates/presentations/
    index.html  archive.html  present.html  phone.html  join.html
    slide_base.html  _deck_chrome.html  _slides.html  _hotspot_card.html
  static/presentations/css/deck.css
  static/presentations/js/
    core.js  sync.js  stage.js  hotspots.js  comments.js
    interactions/choice.js  numeric.js  distribution.js  text.js
    present.js  phone.js  archive.js
  decks/_template/deck.yaml  decks/_template/slides/.gitkeep  decks/_template/static/.gitkeep
  decks/example/  (deck.yaml, slides/*.svg, *.mp4, 05-posterior.html, static/)
tests/presentations/
  conftest.py  test_models.py  test_schema.py  test_interactions.py  test_registry.py
  test_archive.py  test_present.py  test_phone.py  test_lock.py  test_comments.py
  test_tools.py  test_flow.py  test_example_deck.py  js/stage.test.mjs
```

---

### Task 1: App skeleton, dependencies, models, admin, test harness

**Files:**
- Create: `presentations/__init__.py`, `presentations/apps.py`, `presentations/models.py`, `presentations/admin.py`, `presentations/urls.py`, `presentations/views/__init__.py`, `presentations/migrations/__init__.py`
- Create: `tests/presentations/__init__.py`, `tests/presentations/conftest.py`, `tests/presentations/test_models.py`
- Modify: `nihar_website/settings.py:33-44` (INSTALLED_APPS), append `LOGIN_URL`, `PRESENTATIONS_DECKS_DIR`
- Modify: `nihar_website/urls.py:29-33`
- Modify: `requirements.txt`, `environment.yml`, `pytest.ini`

**Interfaces:**
- Produces: models `Session`, `Participant`, `Response`, `Comment` with the fields and methods below; `settings.PRESENTATIONS_DECKS_DIR: Path`; `settings.LOGIN_URL = '/admin/login/'`.
- Produces: fixtures `staff_client`, `anon_client` in `tests/presentations/conftest.py`.

- [ ] **Step 1: Add dependencies**

`requirements.txt` — append:
```
PyYAML==6.0.2
jsonschema==4.23.0
Markdown==3.7
bleach==6.1.0
qrcode==7.4.2
pytest-django==4.9.0
```
`environment.yml` — under `pip:` append `    - jsonschema`, `    - markdown`, `    - bleach`, `    - qrcode`, `    - pytest-django` (PyYAML is already in the env; add `  - pyyaml` under conda deps for explicitness).

Run: `micromamba run -n django-nihar-website pip install jsonschema==4.23.0 Markdown==3.7 bleach==6.1.0 qrcode==7.4.2 pytest-django==4.9.0`

- [ ] **Step 2: pytest-django config**

`pytest.ini`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = nihar_website.settings
testpaths = tests
markers =
    golden: golden checks against the real mindmap SVGs (slow)
```

- [ ] **Step 3: Settings + root urls**

In `nihar_website/settings.py` INSTALLED_APPS, after `'blog'` add `'presentations',`. Append at end of file:
```python
# Presentations app
LOGIN_URL = '/admin/login/'
PRESENTATIONS_DECKS_DIR = BASE_DIR / 'presentations' / 'decks'
```
In `nihar_website/urls.py` add `path('', include('presentations.urls')),` after the blog line.

- [ ] **Step 4: Skeleton files**

`presentations/__init__.py`: empty. `presentations/views/__init__.py`: empty. `presentations/migrations/__init__.py`: empty.

`presentations/apps.py`:
```python
from django.apps import AppConfig


class PresentationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'presentations'
```

`presentations/urls.py` (filled in later tasks; start empty so the include works):
```python
from django.urls import path

app_name = 'presentations'
urlpatterns = []
```

- [ ] **Step 5: Write failing model tests**

`tests/presentations/__init__.py`: empty.

`tests/presentations/conftest.py`:
```python
import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture
def staff_client(db):
    User = get_user_model()
    user = User.objects.create_user('nihar', 'n@example.com', 'pw', is_staff=True)
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def anon_client():
    return Client()
```

`tests/presentations/test_models.py`:
```python
import pytest
from presentations.models import Session, Participant, Response, Comment

pytestmark = pytest.mark.django_db


def test_session_defaults_and_bump():
    s = Session.objects.create(deck_slug='ex')
    assert len(s.join_code) == 6 and s.join_code.isupper()
    assert s.version == 0 and s.is_locked is False and s.ended_at is None
    s.bump()
    assert Session.objects.get(pk=s.pk).version == 1


def test_set_slide_and_interaction_state():
    s = Session.objects.create(deck_slug='ex')
    s.set_slide('orbits')
    s.set_interaction_state('q1', 'open')
    s.refresh_from_db()
    assert s.current_slide_id == 'orbits'
    assert s.interaction_states == {'q1': 'open'}
    assert s.version == 2


def test_invalid_interaction_state_rejected():
    s = Session.objects.create(deck_slug='ex')
    with pytest.raises(ValueError):
        s.set_interaction_state('q1', 'bogus')


def test_lock_reveals_touched_only():
    s = Session.objects.create(deck_slug='ex')
    s.set_interaction_state('a', 'open')
    s.set_interaction_state('b', 'closed')
    s.lock()
    s.refresh_from_db()
    assert s.is_locked and s.ended_at is not None
    assert s.interaction_states == {'a': 'revealed', 'b': 'revealed'}
    s.unlock()
    s.refresh_from_db()
    assert not s.is_locked and s.ended_at is None


def test_open_for_and_archived_for():
    old = Session.objects.create(deck_slug='ex')
    old.lock()
    live = Session.objects.create(deck_slug='ex')
    assert Session.open_for('ex') == live
    assert Session.archived_for('ex') == old
    assert Session.open_for('nope') is None


def test_response_unique_per_participant_interaction():
    s = Session.objects.create(deck_slug='ex')
    p = Participant.objects.create(session=s, expertise_tag='theory')
    assert len(p.token) == 32
    Response.objects.create(participant=p, session=s, interaction_id='q1', payload={'choice': 'A'})
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        Response.objects.create(participant=p, session=s, interaction_id='q1', payload={'choice': 'B'})


def test_comment_visible_manager():
    Comment.objects.create(deck_slug='ex', slide_id='s', body='hi')
    Comment.objects.create(deck_slug='ex', slide_id='s', body='spam', is_hidden=True)
    assert Comment.visible.filter(deck_slug='ex').count() == 1
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_models.py -q`
Expected: ImportError / "cannot import name 'Session'".

- [ ] **Step 7: Implement models**

`presentations/models.py`:
```python
import secrets
import string

from django.db import models
from django.utils import timezone

INTERACTION_STATES = ('hidden', 'open', 'closed', 'revealed')
_CODE_ALPHABET = ''.join(c for c in string.ascii_uppercase + string.digits if c not in 'O0I1')


def make_join_code():
    return ''.join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def make_token():
    return secrets.token_hex(16)


class Session(models.Model):
    deck_slug = models.SlugField(max_length=80, db_index=True)
    join_code = models.CharField(max_length=6, unique=True, default=make_join_code)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    current_slide_id = models.CharField(max_length=80, blank=True, default='')
    interaction_states = models.JSONField(default=dict, blank=True)
    video_state = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.deck_slug} [{self.join_code}]'

    # --- writers (presenter only) ---
    def bump(self):
        self.version = models.F('version') + 1
        self.save()
        self.refresh_from_db(fields=['version'])

    def set_slide(self, slide_id):
        self.current_slide_id = slide_id
        self.bump()

    def set_interaction_state(self, interaction_id, state):
        if state not in INTERACTION_STATES:
            raise ValueError(f'invalid state {state!r}')
        states = dict(self.interaction_states)
        states[interaction_id] = state
        self.interaction_states = states
        self.bump()

    def set_video_state(self, playing, t):
        self.video_state = {'playing': bool(playing), 't': float(t), 'at': timezone.now().timestamp()}
        self.bump()

    def lock(self):
        self.interaction_states = {
            k: ('revealed' if v in ('open', 'closed', 'revealed') else v)
            for k, v in self.interaction_states.items()
        }
        self.is_locked = True
        self.ended_at = timezone.now()
        self.bump()

    def unlock(self):
        self.is_locked = False
        self.ended_at = None
        self.bump()

    def state_for(self, interaction_id):
        return self.interaction_states.get(interaction_id, 'hidden')

    # --- lookups ---
    @classmethod
    def open_for(cls, deck_slug):
        return cls.objects.filter(deck_slug=deck_slug, is_locked=False).order_by('-started_at').first()

    @classmethod
    def archived_for(cls, deck_slug):
        return cls.objects.filter(deck_slug=deck_slug, is_locked=True).order_by('-ended_at').first()


class Participant(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='participants')
    token = models.CharField(max_length=32, unique=True, default=make_token)
    display_name = models.CharField(max_length=60, blank=True, default='')
    expertise_tag = models.CharField(max_length=60)
    joined_at = models.DateTimeField(auto_now_add=True)
    ip_hash = models.CharField(max_length=64, blank=True, default='')

    def __str__(self):
        return self.display_name or f'anon-{self.token[:6]}'


class Response(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='responses')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='responses')
    interaction_id = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['participant', 'interaction_id'], name='uniq_response_per_participant')
        ]


class VisibleCommentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_hidden=False)


class Comment(models.Model):
    deck_slug = models.SlugField(max_length=80, db_index=True)
    slide_id = models.CharField(max_length=80, db_index=True)
    anchor = models.JSONField(null=True, blank=True)   # {"rect":[x,y,w,h]} | {"anchor":"fig-2"} | null
    author_name = models.CharField(max_length=60, blank=True, default='')
    participant = models.ForeignKey(Participant, null=True, blank=True, on_delete=models.SET_NULL)
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_hidden = models.BooleanField(default=False)
    ip_hash = models.CharField(max_length=64, blank=True, default='')

    objects = models.Manager()
    visible = VisibleCommentManager()

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.deck_slug}/{self.slide_id}: {self.body[:40]}'
```

`presentations/admin.py`:
```python
from django.contrib import admin
from .models import Session, Participant, Response, Comment


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('deck_slug', 'join_code', 'started_at', 'ended_at', 'is_locked', 'version')
    list_filter = ('deck_slug', 'is_locked')


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'session', 'expertise_tag', 'joined_at')
    list_filter = ('session__deck_slug', 'expertise_tag')


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('interaction_id', 'participant', 'session', 'updated_at')
    list_filter = ('session__deck_slug', 'interaction_id')


@admin.action(description='Hide selected comments')
def hide_comments(modeladmin, request, queryset):
    queryset.update(is_hidden=True)


@admin.action(description='Unhide selected comments')
def unhide_comments(modeladmin, request, queryset):
    queryset.update(is_hidden=False)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('deck_slug', 'slide_id', 'author_name', 'body', 'created_at', 'is_hidden')
    list_filter = ('deck_slug', 'is_hidden')
    actions = [hide_comments, unhide_comments]
```

- [ ] **Step 8: Make migration and run tests**

Run: `micromamba run -n django-nihar-website python manage.py makemigrations presentations`
Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q`
Expected: 7 passed.

- [ ] **Step 9: Commit**

```bash
git add presentations tests/presentations pytest.ini requirements.txt environment.yml nihar_website/settings.py nihar_website/urls.py
git commit -m "feat(presentations): app skeleton, audience models, admin, test harness"
```

---

### Task 2: deck.yaml schema and loader

**Files:**
- Create: `presentations/schema.py`
- Test: `tests/presentations/test_schema.py`

**Interfaces:**
- Produces:
  ```python
  class DeckError(Exception): path: Path; message: str
  @dataclass class Hotspot: rect: list[float]; title: str; body: str; links: list[dict]
  @dataclass class ShowRef: id: str; rect: list[float] | None
  @dataclass class InteractionDef: id: str; type: str; config: dict     # config = entry minus id/type
  @dataclass class Slide: id: str; kind: str; path: str; poster: str|None; underlay: str|None;
                         hotspots: list[Hotspot]; ask: list[str]; show: list[ShowRef]
  @dataclass class Deck: slug; dir: Path; title; date: str; subtitle: str; transition: str;
                        expertise: list[str]; theme: dict; interactions: list[InteractionDef]; slides: list[Slide]
      slide(id) -> Slide | None; interaction(id) -> InteractionDef | None; slide_index(id) -> int
      interactions_for_slide(slide) -> list[InteractionDef]   # ask ∪ show, in yaml order
  def load_deck(deck_dir: Path, interaction_validator=None) -> Deck
  ```
  `interaction_validator(type_name, config)` is a callable that raises `ValueError`; Task 3 supplies the real one, so this task only checks that `type` is a non-empty string.

- [ ] **Step 1: Write failing tests**

`tests/presentations/test_schema.py`:
```python
from pathlib import Path
import textwrap
import pytest
import yaml

from presentations.schema import load_deck, DeckError

GOOD = """
title: Example
date: 2026-09-12
expertise: [theory, data]
theme: {bg: "#111111", fg: "#eeeeee", accents: ["#37b49f"]}
interactions:
  - id: q1
    type: choice
    prompt: Which?
    options: [A, B]
slides:
  - id: title
    svg: slides/01.svg
    hotspots:
      - rect: [0.1, 0.1, 0.2, 0.2]
        title: Hot
        body: "**bold**"
        links: [{label: L, url: "https://x.y"}]
    ask: [q1]
  - id: results
    svg: slides/02.svg
    show:
      - {id: q1, rect: [0.1, 0.2, 0.8, 0.6]}
  - id: page
    html: page.html
    show: [{id: q1}]
  - id: vid
    video: slides/03.mp4
    poster: slides/03.jpg
"""


def make_deck(tmp_path, text=GOOD, files=('slides/01.svg', 'slides/02.svg', 'page.html', 'slides/03.mp4', 'slides/03.jpg')):
    d = tmp_path / 'ex'
    for f in files:
        p = d / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('x')
    (d / 'deck.yaml').write_text(textwrap.dedent(text))
    return d


def test_good_deck_loads(tmp_path):
    deck = load_deck(make_deck(tmp_path))
    assert deck.slug == 'ex' and deck.title == 'Example'
    assert [s.kind for s in deck.slides] == ['svg', 'svg', 'html', 'video']
    assert deck.slides[0].hotspots[0].title == 'Hot'
    assert deck.slides[0].ask == ['q1']
    assert deck.slides[1].show[0].rect == [0.1, 0.2, 0.8, 0.6]
    assert deck.slides[2].show[0].rect is None
    assert deck.slides[3].poster == 'slides/03.jpg'
    assert deck.interaction('q1').config == {'prompt': 'Which?', 'options': ['A', 'B']}
    assert deck.slide_index('page') == 2
    assert [i.id for i in deck.interactions_for_slide(deck.slides[1])] == ['q1']
    assert deck.transition == 'fade'


def _expect_error(tmp_path, text, needle, **kw):
    with pytest.raises(DeckError) as ei:
        load_deck(make_deck(tmp_path, text, **kw))
    assert needle in str(ei.value)


def test_duplicate_slide_id(tmp_path):
    _expect_error(tmp_path, GOOD.replace('id: results', 'id: title'), 'duplicate slide id')


def test_duplicate_interaction_id(tmp_path):
    bad = GOOD.replace('slides:', "  - id: q1\n    type: choice\n    prompt: p\n    options: [A]\nslides:")
    _expect_error(tmp_path, bad, 'duplicate interaction id')


def test_missing_file(tmp_path):
    _expect_error(tmp_path, GOOD, 'slides/02.svg', files=('slides/01.svg', 'page.html', 'slides/03.mp4', 'slides/03.jpg'))


def test_unresolved_ask(tmp_path):
    _expect_error(tmp_path, GOOD.replace('ask: [q1]', 'ask: [zzz]'), "unknown interaction 'zzz'")


def test_html_show_with_rect_rejected(tmp_path):
    _expect_error(tmp_path, GOOD.replace('show: [{id: q1}]', 'show: [{id: q1, rect: [0,0,1,1]}]'), 'must not give rect')


def test_svg_show_without_rect_rejected(tmp_path):
    _expect_error(tmp_path, GOOD.replace('- {id: q1, rect: [0.1, 0.2, 0.8, 0.6]}', '- {id: q1}'), 'must give rect')


def test_bad_rect(tmp_path):
    _expect_error(tmp_path, GOOD.replace('[0.1, 0.1, 0.2, 0.2]', '[0.1, 0.1, 1.2]'), 'rect')


def test_expertise_bounds(tmp_path):
    _expect_error(tmp_path, GOOD.replace('[theory, data]', '[theory]'), 'expertise')


def test_unknown_slide_kind(tmp_path):
    _expect_error(tmp_path, GOOD.replace('html: page.html', 'pdf: page.html'), 'svg, html or video')


def test_validator_hook_called(tmp_path):
    def v(type_name, config):
        raise ValueError('nope ' + type_name)
    with pytest.raises(DeckError) as ei:
        load_deck(make_deck(tmp_path), interaction_validator=v)
    assert 'nope choice' in str(ei.value)


def test_unasked_interaction_is_warning_not_error(tmp_path):
    text = GOOD.replace('ask: [q1]', '')
    deck = load_deck(make_deck(tmp_path, text))
    assert deck.warnings == ["interaction 'q1' is never asked on any slide"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_schema.py -q`
Expected: ImportError on `presentations.schema`.

- [ ] **Step 3: Implement schema.py**

```python
"""deck.yaml → dataclasses. Pure; no Django imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

TRANSITIONS = ('fade', 'slide', 'none')
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
    transition: str
    expertise: list[str]
    theme: dict
    interactions: list[InteractionDef]
    slides: list[Slide]
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
    return Slide(id=sid, kind=kind, path=rel, poster=poster, underlay=underlay,
                 hotspots=hotspots, ask=ask, show=show)


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

    transition = raw.get('transition', 'fade')
    if transition not in TRANSITIONS:
        raise DeckError(path, f'transition must be one of {TRANSITIONS}')

    theme = dict(DEFAULT_THEME)
    theme.update(raw.get('theme') or {})
    if not isinstance(theme.get('accents'), list) or not theme['accents']:
        raise DeckError(path, 'theme.accents must be a non-empty list')

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

    asked = {a for s in slides for a in s.ask}
    warnings = [f"interaction '{i.id}' is never asked on any slide" for i in interactions if i.id not in asked]

    return Deck(slug=deck_dir.name, dir=deck_dir, title=str(raw['title']), date=str(raw.get('date') or ''),
                subtitle=str(raw.get('subtitle') or ''), transition=transition, expertise=expertise,
                theme=theme, interactions=interactions, slides=slides, warnings=warnings)
```

- [ ] **Step 4: Run tests**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_schema.py -q`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add presentations/schema.py tests/presentations/test_schema.py
git commit -m "feat(presentations): deck.yaml schema loader with validation"
```

---

### Task 3: Interaction plugins (server side)

**Files:**
- Create: `presentations/interactions/__init__.py`, `base.py`, `choice.py`, `numeric.py`, `distribution.py`, `text.py`, `presentations/textutil.py`
- Test: `tests/presentations/test_interactions.py`

**Interfaces:**
- Produces:
  ```python
  # presentations/interactions/base.py
  class Interaction:
      name: str; config_schema: dict; payload_schema: dict
      def validate_config(self, config: dict) -> None          # raises ValueError
      def clean_payload(self, payload: dict, config: dict) -> dict   # raises ValueError
      def aggregate(self, payloads: list[dict], config: dict) -> dict
  # presentations/interactions/__init__.py
  def get(name: str) -> Interaction          # raises ValueError("unknown interaction type …")
  def validate(name: str, config: dict) -> None   # the interaction_validator for load_deck
  def all_types() -> list[str]
  # presentations/textutil.py
  def tokenize_words(text: str) -> list[str]
  def hash_ip(ip: str) -> str
  def render_markdown(text: str) -> str      # bleach-cleaned HTML
  ```

- [ ] **Step 1: Write failing tests**

`tests/presentations/test_interactions.py`:
```python
import pytest
from presentations import interactions as I


def test_registry_has_four_types():
    assert set(I.all_types()) == {'choice', 'numeric', 'distribution', 'text'}
    with pytest.raises(ValueError):
        I.get('nope')


# --- choice ---
CHOICE = {'prompt': 'Which?', 'options': ['A', 'B', 'C'], 'answer': 'B'}


def test_choice_config_validation():
    I.validate('choice', CHOICE)
    with pytest.raises(ValueError):
        I.validate('choice', {'prompt': 'x', 'options': ['A']})          # < 2 options
    with pytest.raises(ValueError):
        I.validate('choice', {'prompt': 'x', 'options': ['A', 'B'], 'answer': 'Z'})


def test_choice_payload_and_aggregate():
    c = I.get('choice')
    assert c.clean_payload({'choice': 'A'}, CHOICE) == {'choice': 'A'}
    with pytest.raises(ValueError):
        c.clean_payload({'choice': 'Z'}, CHOICE)
    agg = c.aggregate([{'choice': 'A'}, {'choice': 'B'}, {'choice': 'B'}], CHOICE)
    assert agg == {'n': 3, 'counts': {'A': 1, 'B': 2, 'C': 0}}
    assert c.aggregate([], CHOICE) == {'n': 0, 'counts': {'A': 0, 'B': 0, 'C': 0}}


# --- numeric ---
NUM = {'prompt': 'rate', 'log': True, 'truth': 23.9}


def test_numeric_payload_and_aggregate():
    n = I.get('numeric')
    assert n.clean_payload({'value': '12.5'}, NUM) == {'value': 12.5}
    assert n.clean_payload({'value': 3, 'err': 1}, NUM) == {'value': 3.0, 'err': 1.0}
    with pytest.raises(ValueError):
        n.clean_payload({'value': -1}, NUM)      # log scale requires > 0
    with pytest.raises(ValueError):
        n.clean_payload({'value': 'abc'}, NUM)
    agg = n.aggregate([{'value': 1}, {'value': 10}, {'value': 100}], NUM)
    assert agg['n'] == 3 and agg['values'] == [1.0, 10.0, 100.0]
    assert agg['median'] == 10.0 and agg['q16'] <= 10.0 <= agg['q84']
    assert n.aggregate([], NUM) == {'n': 0, 'values': [], 'errs': [], 'median': None, 'q16': None, 'q84': None}


def test_numeric_min_max():
    n = I.get('numeric')
    cfg = {'prompt': 'p', 'min': 0, 'max': 10}
    with pytest.raises(ValueError):
        n.clean_payload({'value': 11}, cfg)


# --- distribution ---
DIST = {'prompt': 'prior', 'axis': {'min': 0, 'max': 1, 'bins': 4, 'label': 'e'}}


def test_distribution_payload_normalises():
    d = I.get('distribution')
    out = d.clean_payload({'weights': [1, 1, 2, 0]}, DIST)
    assert out['weights'] == [0.25, 0.25, 0.5, 0.0]
    with pytest.raises(ValueError):
        d.clean_payload({'weights': [1, 1]}, DIST)            # wrong length
    with pytest.raises(ValueError):
        d.clean_payload({'weights': [0, 0, 0, 0]}, DIST)      # all zero
    with pytest.raises(ValueError):
        d.clean_payload({'weights': [1, -1, 1, 1]}, DIST)     # negative


def test_distribution_aggregate():
    d = I.get('distribution')
    agg = d.aggregate([{'weights': [1, 0, 0, 0]}, {'weights': [0, 0, 0, 1]}], DIST)
    assert agg['n'] == 2
    assert agg['mean'] == [0.5, 0.0, 0.0, 0.5]
    assert agg['curves'] == [[1, 0, 0, 0], [0, 0, 0, 1]]
    assert agg['edges'] == [0.0, 0.25, 0.5, 0.75, 1.0]


# --- text ---
TXT = {'prompt': 'one word', 'max_len': 12}


def test_text_payload_and_aggregate():
    t = I.get('text')
    assert t.clean_payload({'text': '  Chaotic!  '}, TXT) == {'text': 'Chaotic!'}
    with pytest.raises(ValueError):
        t.clean_payload({'text': 'way too long for this'}, TXT)
    with pytest.raises(ValueError):
        t.clean_payload({'text': ''}, TXT)
    agg = t.aggregate([{'text': 'chaotic orbits'}, {'text': 'Chaotic'}, {'text': 'the messy'}], TXT)
    assert agg['n'] == 3
    assert agg['counts'] == {'chaotic': 2, 'orbits': 1, 'messy': 1}   # stopword 'the' dropped


def test_text_profanity_rejected():
    t = I.get('text')
    with pytest.raises(ValueError):
        t.clean_payload({'text': 'fuck'}, TXT)


# --- textutil ---
def test_render_markdown_allowlist():
    from presentations.textutil import render_markdown
    html = render_markdown('**b** <script>x</script> [l](https://x.y)')
    assert '<strong>b</strong>' in html and '<script>' not in html
    assert 'rel="nofollow noopener"' in html and 'target="_blank"' in html


def test_hash_ip_is_stable_and_opaque():
    from presentations.textutil import hash_ip
    assert hash_ip('1.2.3.4') == hash_ip('1.2.3.4') and len(hash_ip('1.2.3.4')) == 64
    assert '1.2.3.4' not in hash_ip('1.2.3.4')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_interactions.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement textutil.py**

```python
import hashlib
import re

import bleach
import markdown as md
from django.conf import settings

_ALLOWED_TAGS = ['p', 'em', 'strong', 'code', 'pre', 'a', 'ul', 'ol', 'li', 'blockquote', 'br', 'h3', 'h4']
_ALLOWED_ATTRS = {'a': ['href', 'title', 'rel', 'target']}
_STOPWORDS = set('a an the and or of to in on for is are it its this that with as at by from be'.split())
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")


def _link_attrs(attrs, new=False):
    attrs[(None, 'rel')] = 'nofollow noopener'
    attrs[(None, 'target')] = '_blank'
    return attrs


def render_markdown(text):
    html = md.markdown(text or '', extensions=['nl2br'])
    cleaned = bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)
    return bleach.linkify(cleaned, callbacks=[_link_attrs], skip_tags=['pre', 'code'])


def hash_ip(ip):
    return hashlib.sha256((settings.SECRET_KEY + (ip or '')).encode()).hexdigest()


def tokenize_words(text):
    return [w for w in _WORD_RE.findall((text or '').lower()) if w not in _STOPWORDS]
```

- [ ] **Step 4: Implement interactions package**

`presentations/interactions/base.py`:
```python
import jsonschema


class Interaction:
    name = ''
    config_schema = {'type': 'object'}
    payload_schema = {'type': 'object'}

    def validate_config(self, config):
        try:
            jsonschema.validate(config, self.config_schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f'{self.name} config: {e.message}')
        self.extra_config_checks(config)

    def extra_config_checks(self, config):
        pass

    def clean_payload(self, payload, config):
        if not isinstance(payload, dict):
            raise ValueError('payload must be an object')
        try:
            jsonschema.validate(payload, self.payload_schema)
        except jsonschema.ValidationError as e:
            raise ValueError(e.message)
        return self.normalise(payload, config)

    def normalise(self, payload, config):
        return payload

    def aggregate(self, payloads, config):
        raise NotImplementedError
```

`presentations/interactions/choice.py`:
```python
from .base import Interaction


class Choice(Interaction):
    name = 'choice'
    config_schema = {
        'type': 'object', 'required': ['prompt', 'options'], 'additionalProperties': False,
        'properties': {
            'prompt': {'type': 'string', 'minLength': 1},
            'options': {'type': 'array', 'minItems': 2, 'maxItems': 8, 'items': {'type': 'string'}},
            'answer': {'type': 'string'},
        },
    }
    payload_schema = {'type': 'object', 'required': ['choice'], 'properties': {'choice': {'type': 'string'}}}

    def extra_config_checks(self, config):
        if 'answer' in config and config['answer'] not in config['options']:
            raise ValueError('choice config: answer must be one of options')

    def normalise(self, payload, config):
        if payload['choice'] not in config['options']:
            raise ValueError('choice not in options')
        return {'choice': payload['choice']}

    def aggregate(self, payloads, config):
        counts = {o: 0 for o in config['options']}
        for p in payloads:
            if p.get('choice') in counts:
                counts[p['choice']] += 1
        return {'n': len(payloads), 'counts': counts}
```

`presentations/interactions/numeric.py`:
```python
import statistics

from .base import Interaction


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return None
    pos = (len(sorted_vals) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


class Numeric(Interaction):
    name = 'numeric'
    config_schema = {
        'type': 'object', 'required': ['prompt'], 'additionalProperties': False,
        'properties': {
            'prompt': {'type': 'string', 'minLength': 1},
            'log': {'type': 'boolean'},
            'min': {'type': 'number'}, 'max': {'type': 'number'},
            'truth': {'type': 'number'}, 'unit': {'type': 'string'},
        },
    }
    payload_schema = {'type': 'object', 'required': ['value'],
                      'properties': {'value': {}, 'err': {}}}

    @staticmethod
    def _num(v, what):
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError(f'{what} must be a number')
        if f != f or f in (float('inf'), float('-inf')):
            raise ValueError(f'{what} must be finite')
        return f

    def normalise(self, payload, config):
        value = self._num(payload['value'], 'value')
        if config.get('log') and value <= 0:
            raise ValueError('value must be > 0 on a log scale')
        if 'min' in config and value < config['min']:
            raise ValueError('value below min')
        if 'max' in config and value > config['max']:
            raise ValueError('value above max')
        out = {'value': value}
        if payload.get('err') not in (None, ''):
            err = self._num(payload['err'], 'err')
            if err < 0:
                raise ValueError('err must be >= 0')
            out['err'] = err
        return out

    def aggregate(self, payloads, config):
        values = sorted(float(p['value']) for p in payloads if 'value' in p)
        errs = [p.get('err') for p in payloads if 'value' in p]
        return {
            'n': len(values), 'values': values, 'errs': errs,
            'median': statistics.median(values) if values else None,
            'q16': _quantile(values, 0.16), 'q84': _quantile(values, 0.84),
        }
```

`presentations/interactions/distribution.py`:
```python
from .base import Interaction


class Distribution(Interaction):
    name = 'distribution'
    config_schema = {
        'type': 'object', 'required': ['prompt', 'axis'], 'additionalProperties': False,
        'properties': {
            'prompt': {'type': 'string', 'minLength': 1},
            'axis': {
                'type': 'object', 'required': ['min', 'max', 'bins'], 'additionalProperties': False,
                'properties': {
                    'min': {'type': 'number'}, 'max': {'type': 'number'},
                    'bins': {'type': 'integer', 'minimum': 2, 'maximum': 100},
                    'label': {'type': 'string'}, 'log': {'type': 'boolean'},
                },
            },
        },
    }
    payload_schema = {'type': 'object', 'required': ['weights'],
                      'properties': {'weights': {'type': 'array', 'items': {'type': 'number'}}}}

    def extra_config_checks(self, config):
        if config['axis']['max'] <= config['axis']['min']:
            raise ValueError('distribution config: axis.max must exceed axis.min')

    def normalise(self, payload, config):
        bins = config['axis']['bins']
        w = [float(x) for x in payload['weights']]
        if len(w) != bins:
            raise ValueError(f'weights must have {bins} entries')
        if any(x < 0 for x in w):
            raise ValueError('weights must be >= 0')
        total = sum(w)
        if total <= 0:
            raise ValueError('weights must not be all zero')
        return {'weights': [x / total for x in w]}

    @staticmethod
    def edges(config):
        a = config['axis']
        return [a['min'] + (a['max'] - a['min']) * i / a['bins'] for i in range(a['bins'] + 1)]

    def aggregate(self, payloads, config):
        bins = config['axis']['bins']
        curves = [p['weights'] for p in payloads if len(p.get('weights', [])) == bins]
        mean = [sum(c[i] for c in curves) / len(curves) for i in range(bins)] if curves else [0.0] * bins
        return {'n': len(curves), 'mean': mean, 'curves': curves, 'edges': self.edges(config)}
```

`presentations/interactions/text.py`:
```python
from collections import Counter

from ..textutil import tokenize_words
from .base import Interaction

_BLOCKLIST = {'fuck', 'shit', 'cunt', 'nigger', 'faggot', 'bitch', 'asshole'}


class Text(Interaction):
    name = 'text'
    config_schema = {
        'type': 'object', 'required': ['prompt'], 'additionalProperties': False,
        'properties': {
            'prompt': {'type': 'string', 'minLength': 1},
            'max_len': {'type': 'integer', 'minimum': 1, 'maximum': 80},
        },
    }
    payload_schema = {'type': 'object', 'required': ['text'], 'properties': {'text': {'type': 'string'}}}

    def normalise(self, payload, config):
        text = ' '.join(payload['text'].split())
        max_len = config.get('max_len', 80)
        if not text:
            raise ValueError('text is empty')
        if len(text) > max_len:
            raise ValueError(f'text longer than {max_len} characters')
        if set(tokenize_words(text)) & _BLOCKLIST:
            raise ValueError('text rejected')
        return {'text': text}

    def aggregate(self, payloads, config):
        counts = Counter()
        for p in payloads:
            counts.update(set(tokenize_words(p.get('text', ''))))
        return {'n': len(payloads), 'counts': dict(counts.most_common(60))}
```

`presentations/interactions/__init__.py`:
```python
from .choice import Choice
from .distribution import Distribution
from .numeric import Numeric
from .text import Text

_REGISTRY = {cls.name: cls() for cls in (Choice, Numeric, Distribution, Text)}


def get(name):
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(f"unknown interaction type '{name}' (known: {', '.join(sorted(_REGISTRY))})")


def validate(name, config):
    get(name).validate_config(config)


def all_types():
    return list(_REGISTRY)
```

- [ ] **Step 5: Run tests**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_interactions.py -q`
Expected: 12 passed.

- [ ] **Step 6: Commit**

```bash
git add presentations/interactions presentations/textutil.py tests/presentations/test_interactions.py
git commit -m "feat(presentations): interaction plugins (choice, numeric, distribution, text)"
```

---

### Task 4: Registry, `checkdecks`, static finder, deck index page, navbar

**Files:**
- Create: `presentations/registry.py`, `presentations/finders.py`, `presentations/management/__init__.py`, `presentations/management/commands/__init__.py`, `presentations/management/commands/checkdecks.py`, `presentations/views/common.py`, `presentations/views/archive.py` (index only for now), `presentations/templates/presentations/index.html`, `presentations/decks/_template/deck.yaml`, `presentations/decks/_template/slides/.gitkeep`, `presentations/decks/_template/static/.gitkeep`, `presentations/decks/example/deck.yaml` + placeholder SVGs
- Modify: `presentations/urls.py`, `nihar_website/settings.py` (STATICFILES_FINDERS), `templates/navbar.html:26`
- Test: `tests/presentations/test_registry.py`

**Interfaces:**
- Produces:
  ```python
  # registry.py
  def decks_dir() -> Path                       # settings.PRESENTATIONS_DECKS_DIR
  def all_decks() -> list[Deck]                 # sorted by date desc; skips '_' folders; raises DeckError for a broken deck only when that deck is requested
  def get_deck(slug: str) -> Deck               # raises Http404 if missing, DeckError if invalid
  def clear_cache() -> None
  # views/common.py
  def deck_or_404(slug) -> Deck                 # get_deck; on DeckError renders 500 page 'presentations/deck_error.html' via DeckError → HttpResponseServerError
  ```
- Produces URL names: `presentations:index` (`/presentations/`).
- Static: files in `decks/<slug>/static/**` served at `/static/decks/<slug>/**`; `decks/<slug>/slides/**` at `/static/decks/<slug>/slides/**`.

- [ ] **Step 1: Write failing tests**

`tests/presentations/test_registry.py`:
```python
import pytest
from django.http import Http404

from presentations import registry
from presentations.schema import DeckError
from .test_schema import make_deck, GOOD


@pytest.fixture
def decks(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    yield tmp_path
    registry.clear_cache()


def test_all_decks_sorted_and_skips_underscore(decks):
    make_deck(decks).rename(decks / 'older')
    (decks / 'older' / 'deck.yaml').write_text(GOOD.replace('2026-09-12', '2025-01-01'))
    make_deck(decks)  # 'ex', 2026-09-12
    (decks / '_template').mkdir()
    (decks / '_template' / 'deck.yaml').write_text('title: x')
    assert [d.slug for d in registry.all_decks()] == ['ex', 'older']


def test_get_deck_404_and_error(decks):
    with pytest.raises(Http404):
        registry.get_deck('nope')
    make_deck(decks)
    (decks / 'ex' / 'deck.yaml').write_text('title: broken\n')
    registry.clear_cache()
    with pytest.raises(DeckError):
        registry.get_deck('ex')


def test_all_decks_isolates_broken_deck(decks):
    make_deck(decks)
    (decks / 'bad').mkdir()
    (decks / 'bad' / 'deck.yaml').write_text('title: broken\n')
    slugs = [d.slug for d in registry.all_decks()]
    assert slugs == ['ex']


def test_checkdecks_command(decks, capsys):
    from django.core.management import call_command
    make_deck(decks)
    call_command('checkdecks')
    out = capsys.readouterr().out
    assert 'ex: ok' in out
    (decks / 'bad').mkdir()
    (decks / 'bad' / 'deck.yaml').write_text('title: broken\n')
    registry.clear_cache()
    with pytest.raises(SystemExit):
        call_command('checkdecks')


def test_index_page_lists_decks(decks, anon_client, db):
    make_deck(decks)
    r = anon_client.get('/presentations/')
    assert r.status_code == 200
    assert b'Example' in r.content and b'/presentations/ex/' in r.content


def test_static_finder_maps_deck_static_and_slides(decks):
    from presentations.finders import DeckStaticFinder
    d = make_deck(decks)
    (d / 'static').mkdir()
    (d / 'static' / 'app.js').write_text('1')
    f = DeckStaticFinder()
    assert f.find('decks/ex/app.js') == str(d / 'static' / 'app.js')
    assert f.find('decks/ex/slides/01.svg') == str(d / 'slides' / '01.svg')
    assert f.find('decks/ex/deck.yaml') is None
    listed = {p for p, _ in f.list([])}
    assert 'app.js' in listed and '01.svg' in listed   # slides root yields paths relative to slides/, storage.prefix adds 'decks/ex/slides'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_registry.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement registry.py**

```python
"""Discovers presentations/decks/*/deck.yaml. Cached per process; DEBUG re-reads on mtime change."""
import logging
from pathlib import Path

from django.conf import settings
from django.http import Http404

from . import interactions
from .schema import DeckError, load_deck

log = logging.getLogger(__name__)
_cache = {}   # slug -> (mtime, Deck)


def decks_dir():
    return Path(settings.PRESENTATIONS_DECKS_DIR)


def clear_cache():
    _cache.clear()


def _load(slug):
    d = decks_dir() / slug
    yaml_path = d / 'deck.yaml'
    if not d.is_dir() or not yaml_path.is_file() or slug.startswith('_'):
        raise Http404(f"No presentation '{slug}'")
    mtime = yaml_path.stat().st_mtime
    hit = _cache.get(slug)
    if hit and (hit[0] == mtime or not settings.DEBUG):
        return hit[1]
    deck = load_deck(d, interaction_validator=interactions.validate)
    for w in deck.warnings:
        log.warning('deck %s: %s', slug, w)
    _cache[slug] = (mtime, deck)
    return deck


def get_deck(slug):
    return _load(slug)


def all_decks():
    out = []
    root = decks_dir()
    if not root.is_dir():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('_')):
        try:
            out.append(_load(d.name))
        except (DeckError, Http404) as e:
            log.error('skipping deck %s: %s', d.name, e)
    out.sort(key=lambda dk: dk.date, reverse=True)
    return out
```

- [ ] **Step 4: Implement finders.py and register it**

```python
"""Serves decks/<slug>/static/** at static/decks/<slug>/** and decks/<slug>/slides/** at static/decks/<slug>/slides/**."""
import os

from django.contrib.staticfiles.finders import BaseFinder
from django.core.files.storage import FileSystemStorage

from .registry import decks_dir

_SUBDIRS = {'static': '', 'slides': 'slides'}


class DeckStaticFinder(BaseFinder):
    def _roots(self):
        root = decks_dir()
        if not root.is_dir():
            return
        for d in sorted(root.iterdir()):
            if d.is_dir() and not d.name.startswith('_'):
                for sub, prefix in _SUBDIRS.items():
                    if (d / sub).is_dir():
                        yield d.name, prefix, d / sub

    def check(self, **kwargs):
        return []

    def find(self, path, all=False, **kwargs):
        matches = []
        if path.startswith('decks/'):
            rest = path[len('decks/'):]
            slug, _, rel = rest.partition('/')
            for s, prefix, base in self._roots():
                if s != slug:
                    continue
                if prefix and rel.startswith(prefix + '/'):
                    candidate = base / rel[len(prefix) + 1:]
                elif not prefix and not rel.startswith('slides/'):
                    candidate = base / rel
                else:
                    continue
                if candidate.is_file():
                    matches.append(str(candidate))
        if all:
            return matches
        return matches[0] if matches else None

    def list(self, ignore_patterns):
        for slug, prefix, base in self._roots():
            storage = FileSystemStorage(location=str(base))
            storage.prefix = f'decks/{slug}' + (f'/{prefix}' if prefix else '')
            for dirpath, _dirs, files in os.walk(base):
                for f in files:
                    rel = os.path.relpath(os.path.join(dirpath, f), base)
                    yield rel, storage
```

Note: collectstatic opens each yielded path relative to `storage.location` and prefixes the destination with `storage.prefix`, so each root yields paths relative to itself and `storage.prefix` carries `decks/<slug>` or `decks/<slug>/slides`.

In `nihar_website/settings.py` append:
```python
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'presentations.finders.DeckStaticFinder',
]
```

- [ ] **Step 5: checkdecks command**

`presentations/management/__init__.py`, `presentations/management/commands/__init__.py`: empty.

`presentations/management/commands/checkdecks.py`:
```python
import sys

from django.core.management.base import BaseCommand

from presentations import registry
from presentations.schema import DeckError, load_deck
from presentations import interactions


class Command(BaseCommand):
    help = 'Validate every presentations/decks/*/deck.yaml'

    def handle(self, *args, **options):
        root = registry.decks_dir()
        bad = 0
        for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('_')):
            try:
                deck = load_deck(d, interaction_validator=interactions.validate)
            except DeckError as e:
                bad += 1
                self.stderr.write(f'{d.name}: ERROR {e.message}')
                continue
            self.stdout.write(f'{d.name}: ok ({len(deck.slides)} slides, {len(deck.interactions)} interactions)')
            for w in deck.warnings:
                self.stdout.write(f'  warning: {w}')
        if bad:
            sys.exit(1)
```

- [ ] **Step 6: Index view, template, urls, navbar**

`presentations/views/common.py`:
```python
from django.http import HttpResponseServerError
from django.template.loader import render_to_string

from .. import registry
from ..schema import DeckError


class DeckErrorResponse(Exception):
    """Wraps a DeckError so views can return a readable 500."""
    def __init__(self, err):
        self.err = err


def deck_or_404(slug):
    try:
        return registry.get_deck(slug)
    except DeckError as e:
        raise DeckErrorResponse(e)


def deck_error_response(request, exc):
    html = render_to_string('presentations/deck_error.html', {'error': exc.err}, request=request)
    return HttpResponseServerError(html)
```

Every view in later tasks wraps its body as:
```python
try:
    deck = deck_or_404(slug)
except DeckErrorResponse as e:
    return deck_error_response(request, e)
```

`presentations/views/archive.py` (index only for now):
```python
from django.shortcuts import render

from .. import registry
from ..models import Session


def index(request):
    decks = registry.all_decks()
    rows = []
    for d in decks:
        live = Session.open_for(d.slug)
        archived = Session.archived_for(d.slug)
        status = 'live' if live and live.current_slide_id else ('archived' if archived else 'upcoming')
        rows.append({'deck': d, 'status': status})
    return render(request, 'presentations/index.html', {'rows': rows})
```

`presentations/templates/presentations/index.html`:
```django
{% extends 'homepage/base.html' %}
{% block content %}
<section id="main" class="wrapper" style="padding:4rem 0;">
  <div class="container">
    <h2>Presentations</h2>
    <p>Talks given as interactive, audience-synced decks. Each one stays up afterwards with the room's answers and a comment layer.</p>
    <ul class="pres-list" style="list-style:none;padding:0;">
      {% for row in rows %}
      <li style="margin:1.2rem 0;">
        <a href="{% url 'presentations:archive' row.deck.slug %}" style="font-size:1.3rem;">{{ row.deck.title }}</a>
        <span style="opacity:.7;margin-left:.6rem;">{{ row.deck.date }}{% if row.deck.subtitle %} · {{ row.deck.subtitle }}{% endif %}</span>
        {% if row.status == 'live' %}<span class="pres-badge pres-badge--live">LIVE</span>{% elif row.status == 'archived' %}<span class="pres-badge">archived</span>{% endif %}
      </li>
      {% empty %}
      <li>No presentations yet.</li>
      {% endfor %}
    </ul>
  </div>
</section>
{% endblock %}
```

`presentations/templates/presentations/deck_error.html`:
```django
<!doctype html><meta charset="utf-8"><title>Deck error</title>
<body style="font-family:monospace;padding:2rem;background:#1f2429;color:#f4f1ea">
<h1>deck.yaml problem</h1><p>{{ error.path }}</p><pre>{{ error.message }}</pre></body>
```

`presentations/urls.py`:
```python
from django.urls import path

from .views import archive

app_name = 'presentations'
urlpatterns = [
    path('presentations/', archive.index, name='index'),
]
```
(The test references `presentations:archive`; add a temporary stub route `path('presentations/<slug:slug>/', archive.archive, name='archive')` with `def archive(request, slug): return render(request, 'presentations/index.html', {'rows': []})` — Task 5 replaces it.)

`templates/navbar.html` — after the Posters `</li>` (line 26), inside the Science `<ul>`:
```html
                <li><a href="/presentations/">Presentations</a></li>
```

- [ ] **Step 7: Template deck + example deck placeholder**

`presentations/decks/_template/deck.yaml`:
```yaml
# Copied by `manage.py newdeck`. Everything about a talk lives in this folder.
# ids are persistence keys: renaming a slide id orphans its comments, renaming an
# interaction id orphans its responses. Never renumber them after a session.
title: New talk
date: 2026-01-01
subtitle: ""
transition: fade          # fade | slide | none
expertise:                # 2–6 tags shown on the phone join screen
  - theory
  - data analysis
  - instrumentation
  - not a physicist
theme:                    # newdeck derives these from your SVGs; edit freely
  bg: "#1f2429"
  fg: "#f4f1ea"
  accents: ["#37b49f", "#e9c46a", "#e76f51"]
  font_display: "Montserrat"
  font_body: "Inter"

interactions: []
#  - id: q-example
#    type: choice          # choice | numeric | distribution | text
#    prompt: Which one?
#    options: [A, B, C]
#    answer: B

slides: []
#  - id: title
#    svg: slides/01-title.svg
#    hotspots:
#      - rect: [0.1, 0.1, 0.3, 0.2]     # x, y, w, h as fractions of the 16:9 stage
#        title: A thing
#        body: "Markdown **body**"
#        links: [{label: "arXiv", url: "https://arxiv.org/abs/..."}]
#    ask: [q-example]                    # phone widget appears when opened
#    show:
#      - {id: q-example, rect: [0.5, 0.6, 0.45, 0.35]}   # where the aggregate is drawn
#  - id: page
#    html: 02-page.html                  # free-form template extending presentations/slide_base.html
#    underlay: slides/02-frame.svg       # optional Canva backdrop
#  - id: outro
#    video: slides/03-outro.mp4
#    poster: slides/03-outro.jpg
```

`presentations/decks/example/deck.yaml` (v0 — svg slides only; Task 14 fills it out):
```yaml
title: Example deck
date: 2026-08-25
subtitle: engine reference deck
transition: fade
expertise: [theory, data analysis, instrumentation, not a physicist]
theme:
  bg: "#1f2429"
  fg: "#f4f1ea"
  accents: ["#37b49f", "#e9c46a", "#e76f51"]
  font_display: "Montserrat"
  font_body: "Inter"
interactions:
  - id: q-orbits
    type: choice
    prompt: Which orbit is eccentric?
    options: [A, B, C, D]
    answer: B
slides:
  - id: title
    svg: slides/01-title.svg
  - id: orbits
    svg: slides/02-orbits.svg
    hotspots:
      - rect: [0.55, 0.15, 0.35, 0.4]
        title: Orbit B
        body: "This one has **e ≈ 0.3** at 10 Hz. See the paper."
        links: [{label: "arXiv:2401.01234", url: "https://arxiv.org/abs/2401.01234"}]
    ask: [q-orbits]
  - id: orbits-results
    svg: slides/03-results.svg
    show:
      - {id: q-orbits, rect: [0.1, 0.25, 0.8, 0.65]}
```

Placeholder SVGs — write each with this shape (change the title text and colour per file):
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">
  <rect width="1920" height="1080" fill="#1f2429"/>
  <text x="120" y="200" font-family="Montserrat, sans-serif" font-size="96" fill="#f4f1ea">Example deck</text>
  <circle cx="1400" cy="400" r="180" fill="none" stroke="#37b49f" stroke-width="12"/>
</svg>
```
Files: `slides/01-title.svg` (text "Example deck"), `slides/02-orbits.svg` (text "Which orbit is eccentric?", add an ellipse `<ellipse cx="1400" cy="400" rx="260" ry="150" fill="none" stroke="#e9c46a" stroke-width="12"/>`), `slides/03-results.svg` (text "What the room said").

Add `presentations/decks/**/*.mp4 filter=lfs diff=lfs merge=lfs -text` and the same for `*.webm` to `.gitattributes`.

- [ ] **Step 8: Run tests**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q`
Expected: all pass. Also run `micromamba run -n django-nihar-website python manage.py checkdecks` → `example: ok (3 slides, 1 interactions)`.

- [ ] **Step 9: Commit**

```bash
git add presentations tests/presentations nihar_website/settings.py templates/navbar.html .gitattributes
git commit -m "feat(presentations): deck registry, checkdecks, static finder, index page, navbar link"
```

---

### Task 5: Archive page — slide rendering, stage, hotspots, theme (server side)

**Files:**
- Create: `presentations/render.py`, `presentations/templates/presentations/archive.html`, `_deck_chrome.html`, `_slides.html`, `_hotspot_card.html`, `slide_base.html`, `presentations/static/presentations/css/deck.css`
- Modify: `presentations/views/archive.py`, `presentations/views/common.py`, `presentations/urls.py`
- Test: `tests/presentations/test_archive.py`

**Interfaces:**
- Produces:
  ```python
  # presentations/render.py
  def inline_svg(path: Path) -> str            # safe markup: no xml decl/doctype, viewBox guaranteed, width/height=100%
  def render_html_slide(deck, slide, request) -> str
  def slide_static_url(deck, rel) -> str       # '/static/decks/<slug>/' + rel  (rel like 'slides/x.mp4')
  def rendered_slides(deck, request) -> list[dict]   # per slide: {'slide','index','markup','video_url','poster_url','underlay'}
  def deck_json(deck, session, mode) -> dict   # embedded as <script id="deck-data" type="application/json">
  ```
  `deck_json` shape (JS relies on it):
  ```json
  {"slug":"ex","mode":"archive","transition":"fade","theme":{...},
   "expertise":["theory","data"],
   "slides":[{"id":"orbits","kind":"svg","index":1,
              "hotspots":[{"rect":[..],"title":"..","body_html":"<p>..</p>","links":[{"label":"..","url":".."}]}],
              "ask":["q1"],"show":[{"id":"q1","rect":[..]}]}],
   "interactions":{"q1":{"type":"choice","config":{...},"state":"revealed"}},
   "session":{"code":"ABC123","locked":true,"current":"orbits"} | null,
   "urls":{"aggregate":"/presentations/ex/aggregate/", "comment":"/presentations/ex/comment/", "state": null}}
  ```
- Produces URL names: `presentations:archive` (`/presentations/<slug>/`).
- Templates: `slide_base.html` exposes `{% block slide %}` and wraps content in `<div class="slide-page">`; context has `deck`, `slide`, `theme`, `deck_static` (e.g. `/static/decks/ex/`).

- [ ] **Step 1: Write failing tests**

`tests/presentations/test_archive.py`:
```python
import json
import pytest
from presentations import registry
from .test_schema import make_deck, GOOD

SVG = '<?xml version="1.0"?><!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="10" height="10"/></svg>'
PAGE = '{% extends "presentations/slide_base.html" %}{% block slide %}<h1 data-hotspot="H" data-body="b">Page {{ theme.bg }}</h1><div data-interaction="q1"></div>{% endblock %}'


@pytest.fixture
def deck(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    d = make_deck(tmp_path)
    (d / 'slides' / '01.svg').write_text(SVG)
    (d / 'page.html').write_text(PAGE)
    yield d
    registry.clear_cache()


def test_inline_svg_normalises(deck):
    from presentations.render import inline_svg
    out = inline_svg(deck / 'slides' / '01.svg')
    assert not out.startswith('<?xml') and 'DOCTYPE' not in out
    assert 'viewBox="0 0 1920 1080"' in out
    assert 'width="100%"' in out and 'preserveAspectRatio="xMidYMid meet"' in out


def test_archive_renders_all_kinds(deck, anon_client, db):
    r = anon_client.get('/presentations/ex/')
    assert r.status_code == 200
    html = r.content.decode()
    assert html.count('data-slide-id=') == 4
    assert '<rect width="10" height="10"' in html                     # svg inlined
    assert 'Page #111111' in html                                     # html slide rendered with theme
    assert '<video' in html and '/static/decks/ex/slides/03.mp4' in html
    assert 'poster="/static/decks/ex/slides/03.jpg"' in html
    data = json.loads(html.split('id="deck-data" type="application/json">')[1].split('</script>')[0])
    assert data['mode'] == 'archive' and data['session'] is None
    assert data['slides'][0]['hotspots'][0]['body_html'] == '<p><strong>bold</strong></p>'
    assert data['interactions']['q1']['state'] == 'hidden'
    assert '--bg:#111111' in html.replace(' ', '')


def test_archive_404_for_unknown(anon_client, db, settings, tmp_path):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    assert anon_client.get('/presentations/zzz/').status_code == 404


def test_archive_shows_readable_500_for_broken_deck(deck, anon_client, db):
    (deck / 'deck.yaml').write_text('title: broken\n')
    registry.clear_cache()
    r = anon_client.get('/presentations/ex/')
    assert r.status_code == 500 and b'expertise' in r.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_archive.py -q`
Expected: ImportError on `presentations.render` / assertion failures.

- [ ] **Step 3: Implement render.py**

```python
import json
import re
from pathlib import Path

from django.template import engines
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from .textutil import render_markdown

_XML_DECL = re.compile(r'<\?xml[^>]*\?>', re.S)
_DOCTYPE = re.compile(r'<!DOCTYPE[^>]*>', re.S | re.I)
_ROOT = re.compile(r'<svg\b([^>]*)>', re.S)
_ATTR = re.compile(r'\s(width|height|preserveAspectRatio)\s*=\s*"[^"]*"')
_NUM = re.compile(r'[\d.]+')


def inline_svg(path):
    text = Path(path).read_text(encoding='utf-8')
    text = _DOCTYPE.sub('', _XML_DECL.sub('', text)).strip()
    m = _ROOT.search(text)
    if not m:
        return mark_safe('')
    attrs = m.group(1)
    if 'viewBox' not in attrs:
        w = re.search(r'\swidth="([^"]+)"', attrs)
        h = re.search(r'\sheight="([^"]+)"', attrs)
        wv = _NUM.search(w.group(1)).group(0) if w and _NUM.search(w.group(1)) else '1920'
        hv = _NUM.search(h.group(1)).group(0) if h and _NUM.search(h.group(1)) else '1080'
        attrs += f' viewBox="0 0 {wv} {hv}"'
    attrs = _ATTR.sub('', attrs)
    attrs += ' width="100%" height="100%" preserveAspectRatio="xMidYMid meet" class="slide-svg"'
    text = text[:m.start()] + f'<svg{attrs}>' + text[m.end():]
    return mark_safe(text)


def slide_static_url(deck, rel):
    return static(f'decks/{deck.slug}/{rel}')


def render_html_slide(deck, slide, request):
    src = (deck.dir / slide.path).read_text(encoding='utf-8')
    tpl = engines['django'].from_string(src)
    return tpl.render({
        'deck': deck, 'slide': slide, 'theme': deck.theme,
        'deck_static': static(f'decks/{deck.slug}/'),
    }, request)


def rendered_slides(deck, request):
    out = []
    for n, s in enumerate(deck.slides):
        row = {'slide': s, 'index': n, 'markup': '', 'video_url': '', 'poster_url': '', 'underlay': ''}
        if s.kind == 'svg':
            row['markup'] = inline_svg(deck.dir / s.path)
        elif s.kind == 'html':
            row['markup'] = mark_safe(render_html_slide(deck, s, request))
            if s.underlay:
                row['underlay'] = inline_svg(deck.dir / s.underlay)
        else:
            row['video_url'] = slide_static_url(deck, s.path)
            row['poster_url'] = slide_static_url(deck, s.poster) if s.poster else ''
        out.append(row)
    return out


def theme_css(theme):
    parts = [f"--bg:{theme['bg']}", f"--fg:{theme['fg']}"]
    for i, a in enumerate(theme['accents'], 1):
        parts.append(f'--accent-{i}:{a}')
    parts.append(f"--accent:{theme['accents'][0]}")
    parts.append(f"--font-display:'{theme['font_display']}',sans-serif")
    parts.append(f"--font-body:'{theme['font_body']}',sans-serif")
    return ';'.join(parts)


def deck_json(deck, session, mode, urls):
    states = session.interaction_states if session else {}
    return {
        'slug': deck.slug, 'title': deck.title, 'mode': mode, 'transition': deck.transition,
        'theme': deck.theme, 'expertise': deck.expertise,
        'slides': [{
            'id': s.id, 'kind': s.kind, 'index': n,
            'hotspots': [{'rect': h.rect, 'title': h.title, 'body_html': render_markdown(h.body), 'links': h.links}
                         for h in s.hotspots],
            'ask': s.ask, 'show': [{'id': r.id, 'rect': r.rect} for r in s.show],
        } for n, s in enumerate(deck.slides)],
        'interactions': {i.id: {'type': i.type, 'config': i.config, 'state': states.get(i.id, 'hidden')}
                         for i in deck.interactions},
        'session': ({'code': session.join_code, 'locked': session.is_locked, 'current': session.current_slide_id,
                     'version': session.version} if session else None),
        'urls': urls,
    }


def deck_json_script(data):
    return mark_safe(json.dumps(data).replace('</', '<\\/'))
```

- [ ] **Step 4: Views, urls, templates**

`presentations/views/archive.py` — replace the stub with:
```python
from django.shortcuts import render
from django.urls import reverse

from .. import registry
from ..models import Session
from ..render import deck_json, deck_json_script, rendered_slides, theme_css
from .common import DeckErrorResponse, deck_error_response, deck_or_404


def index(request):
    decks = registry.all_decks()
    rows = []
    for d in decks:
        live = Session.open_for(d.slug)
        archived = Session.archived_for(d.slug)
        status = 'live' if live and live.current_slide_id else ('archived' if archived else 'upcoming')
        rows.append({'deck': d, 'status': status})
    return render(request, 'presentations/index.html', {'rows': rows})


def archive(request, slug):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    session = Session.archived_for(slug)
    live = Session.open_for(slug)
    urls = {
        'aggregate': f'/presentations/{slug}/aggregate/',
        'comment': reverse('presentations:comment', args=[slug]),
        'state': None,
    }
    data = deck_json(deck, session, 'archive', urls)
    return render(request, 'presentations/archive.html', {
        'deck': deck, 'slides': rendered_slides(deck, request), 'theme_css': theme_css(deck.theme),
        'deck_data': deck_json_script(data), 'live': live, 'session': session,
    })
```

`presentations/urls.py` — full list for this task (later tasks add to it; the two named-but-unimplemented routes below get placeholder views returning `HttpResponseNotFound()` in `views/common.py` named `placeholder`, replaced in Tasks 7–9):
```python
from django.urls import path

from .views import archive, common

app_name = 'presentations'
urlpatterns = [
    path('presentations/', archive.index, name='index'),
    path('presentations/<slug:slug>/', archive.archive, name='archive'),
    path('presentations/<slug:slug>/aggregate/<str:iid>/', common.placeholder, name='archive-aggregate'),
    path('presentations/<slug:slug>/comment/', common.placeholder, name='comment'),
]
```
Add to `views/common.py`:
```python
from django.http import HttpResponseNotFound

def placeholder(request, *args, **kwargs):
    return HttpResponseNotFound()
```

`presentations/templates/presentations/_deck_chrome.html`:
```django
<header class="deck-chrome" id="deck-chrome">
  <a class="deck-chrome__home" href="{% url 'presentations:index' %}" title="All presentations">◀</a>
  <span class="deck-chrome__title">{{ deck.title }}</span>
  <span class="deck-chrome__counter"><span id="slide-num">1</span> / {{ deck.slides|length }}</span>
  <span class="deck-chrome__status" id="deck-status">
    {% if mode == 'present' %}<span class="pres-badge pres-badge--live">LIVE</span>{% endif %}
    {% if session and session.is_locked %}<span class="pres-badge">LOCKED</span>{% endif %}
  </span>
  {% block chrome_extra %}{% endblock %}
</header>
```

`presentations/templates/presentations/_slides.html`:
```django
<main class="deck" id="deck" data-transition="{{ deck.transition }}">
  {% for row in slides %}
  <section class="slide slide--{{ row.slide.kind }}" data-slide-id="{{ row.slide.id }}" data-index="{{ row.index }}" {% if row.index != 0 %}hidden{% endif %}>
    {% if row.slide.kind == 'html' %}
      {% if row.underlay %}<div class="stage stage--underlay"><div class="stage__inner">{{ row.underlay }}</div></div>{% endif %}
      {{ row.markup }}
    {% else %}
      <div class="stage">
        <div class="stage__inner">
          {% if row.slide.kind == 'svg' %}{{ row.markup }}{% else %}
          <video class="slide-video" src="{{ row.video_url }}" {% if row.poster_url %}poster="{{ row.poster_url }}"{% endif %} playsinline preload="metadata"></video>
          {% endif %}
          <svg class="overlay" viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid meet"></svg>
          <div class="stage__widgets"></div>
        </div>
      </div>
    {% endif %}
  </section>
  {% endfor %}
</main>
```

`presentations/templates/presentations/_hotspot_card.html`:
```django
<div class="hotspot-card" id="hotspot-card" hidden>
  <div class="hotspot-card__title"></div>
  <div class="hotspot-card__body"></div>
  <div class="hotspot-card__links"></div>
</div>
```

`presentations/templates/presentations/slide_base.html`:
```django
{% load static %}<div class="slide-page">{% block slide %}{% endblock %}</div>
```

`presentations/templates/presentations/archive.html`:
```django
{% load static %}<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ deck.title }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={{ deck.theme.font_display|urlencode }}:wght@600;800&family={{ deck.theme.font_body|urlencode }}:wght@400;600&display=swap">
<link rel="stylesheet" href="{% static 'presentations/css/deck.css' %}">
<style>:root{ {{ theme_css|safe }} }</style>
</head>
<body class="mode-archive">
{% with mode='archive' %}{% include 'presentations/_deck_chrome.html' %}{% endwith %}
{% if live and live.current_slide_id %}<div class="live-banner">This talk is live right now — <a href="/p/{{ live.join_code }}/">join on your phone</a></div>{% endif %}
{% include 'presentations/_slides.html' %}
{% include 'presentations/_hotspot_card.html' %}
<nav class="deck-nav"><button id="prev" aria-label="previous">‹</button><button id="next" aria-label="next">›</button></nav>
<script id="deck-data" type="application/json">{{ deck_data }}</script>
<script src="{% static 'presentations/js/core.js' %}"></script>
<script src="{% static 'presentations/js/sync.js' %}"></script>
<script src="{% static 'presentations/js/stage.js' %}"></script>
<script src="{% static 'presentations/js/hotspots.js' %}"></script>
<script src="{% static 'presentations/js/interactions/choice.js' %}"></script>
<script src="{% static 'presentations/js/interactions/numeric.js' %}"></script>
<script src="{% static 'presentations/js/interactions/distribution.js' %}"></script>
<script src="{% static 'presentations/js/interactions/text.js' %}"></script>
<script src="{% static 'presentations/js/comments.js' %}"></script>
<script src="{% static 'presentations/js/archive.js' %}"></script>
</body></html>
```

`presentations/static/presentations/css/deck.css`:
```css
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font-family:var(--font-body)}
h1,h2,h3{font-family:var(--font-display)}
a{color:var(--accent)}
.deck-chrome{position:fixed;top:0;left:0;right:0;height:40px;display:flex;align-items:center;gap:1rem;padding:0 .8rem;background:rgba(0,0,0,.35);backdrop-filter:blur(6px);font-size:.85rem;z-index:20;transition:opacity .3s}
.deck-chrome--hidden{opacity:0;pointer-events:none}
.deck-chrome__home{text-decoration:none;color:var(--fg);opacity:.7}
.deck-chrome__title{font-family:var(--font-display);font-weight:600}
.deck-chrome__counter{opacity:.7}
.pres-badge{display:inline-block;padding:.1rem .5rem;border-radius:999px;background:rgba(255,255,255,.15);font-size:.7rem;letter-spacing:.06em}
.pres-badge--live{background:#d33;color:#fff}
.live-banner{position:fixed;top:40px;left:0;right:0;padding:.4rem;text-align:center;background:var(--accent);color:#000;z-index:19}
.deck{position:absolute;inset:40px 0 0 0;overflow:hidden}
.slide{position:absolute;inset:0}
.slide[hidden]{display:none}
.deck[data-transition="fade"] .slide{animation:fadein .35s ease}
.deck[data-transition="slide"] .slide{animation:slidein .35s ease}
@keyframes fadein{from{opacity:0}to{opacity:1}}
@keyframes slidein{from{transform:translateX(40px);opacity:0}to{transform:none;opacity:1}}
.slide--html{overflow:auto}
.slide-page{position:relative;min-height:100%;padding:3rem clamp(1rem,6vw,6rem);max-width:1400px;margin:0 auto;z-index:1}
.stage{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.stage--underlay{z-index:0}
.stage__inner{position:relative;aspect-ratio:16/9;width:min(100%,calc((100vh - 40px) * 16 / 9));max-height:100%}
.stage__inner>.slide-svg,.stage__inner>.slide-video{position:absolute;inset:0;width:100%;height:100%;display:block}
.slide-video{object-fit:contain;background:#000}
.overlay{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.overlay .hotspot{fill:transparent;stroke:transparent;pointer-events:all;cursor:pointer;transition:stroke .15s}
.overlay .hotspot:hover,.overlay .hotspot.active{stroke:var(--accent);stroke-width:4;fill:rgba(255,255,255,.04)}
.overlay .hotspot-mark{fill:var(--accent);opacity:.55;pointer-events:none}
.overlay .comment-box{fill:rgba(255,255,255,.03);stroke:var(--accent-2,#e9c46a);stroke-width:3;stroke-dasharray:8 6;pointer-events:all;cursor:pointer}
.overlay .comment-box.active{fill:rgba(255,255,255,.1)}
.overlay .comment-num{font:600 34px var(--font-display);fill:var(--accent-2,#e9c46a);pointer-events:none}
.stage__widgets{position:absolute;inset:0;pointer-events:none}
.stage__widgets .widget{position:absolute;pointer-events:all;background:rgba(0,0,0,.45);border-radius:12px;padding:.6rem;overflow:hidden}
.hotspot-card{position:fixed;z-index:30;max-width:min(420px,90vw);max-height:60vh;overflow:auto;background:#111a;backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.15);border-radius:10px;padding:.8rem 1rem;box-shadow:0 10px 40px #0008;font-size:.95rem}
.hotspot-card[hidden]{display:none}
.hotspot-card__title{font-family:var(--font-display);font-weight:700;margin-bottom:.3rem}
.hotspot-card__links a{display:inline-block;margin:.4rem .6rem 0 0}
.hotspot-card--pinned{border-color:var(--accent)}
[data-hotspot]{border-bottom:2px dotted var(--accent);cursor:help}
.deck-nav{position:fixed;bottom:12px;right:12px;z-index:20;display:flex;gap:.3rem}
.deck-nav button,.btn{background:rgba(255,255,255,.12);color:var(--fg);border:0;border-radius:8px;padding:.35rem .8rem;font-size:1rem;cursor:pointer}
.btn--primary{background:var(--accent);color:#000}
.btn[disabled]{opacity:.4;cursor:default}
.follow-pill{position:fixed;bottom:60px;left:50%;transform:translateX(-50%);z-index:25;background:var(--accent);color:#000;border-radius:999px;padding:.4rem 1rem;font-weight:600;cursor:pointer}
.follow-pill[hidden]{display:none}
.widget h4{margin:0 0 .3rem;font-size:.9rem;opacity:.85}
.widget .bars .bar{display:grid;grid-template-columns:2.2rem 1fr 3rem;align-items:center;gap:.4rem;margin:.2rem 0}
.widget .bars .bar i{display:block;height:1.1rem;background:var(--accent);border-radius:4px;transition:width .4s}
.widget .bars .bar.correct i{background:var(--accent-2,#e9c46a)}
.widget .n{font-size:.75rem;opacity:.7;text-align:right}
.widget .too-small{opacity:.7;font-style:italic;padding:1rem}
.slice{display:flex;gap:.3rem;flex-wrap:wrap;margin-bottom:.3rem}
.slice button{font-size:.7rem;padding:.15rem .5rem}
.slice button.on{background:var(--accent);color:#000}
.wordcloud span{display:inline-block;margin:.15rem .4rem;line-height:1}
.ask-panel{position:fixed;left:0;right:0;bottom:0;max-height:55vh;overflow:auto;background:#000c;backdrop-filter:blur(8px);border-top:1px solid rgba(255,255,255,.15);padding:.8rem 1rem;z-index:26}
.ask-panel[hidden]{display:none}
.ask-panel .ask{margin-bottom:1rem}
.ask-panel .prompt{font-family:var(--font-display);font-weight:600;margin-bottom:.4rem}
.choice-grid{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}
.choice-grid button{padding:.8rem;font-size:1.1rem}
.choice-grid button.picked{background:var(--accent);color:#000}
canvas.draw{width:100%;height:160px;background:rgba(255,255,255,.06);border-radius:8px;touch-action:none}
input.num,input.txt{width:100%;font-size:1.1rem;padding:.5rem;border-radius:8px;border:1px solid #fff3;background:#0006;color:var(--fg)}
.comments-panel{position:fixed;right:0;top:40px;bottom:0;width:min(380px,100vw);background:#000c;backdrop-filter:blur(8px);border-left:1px solid rgba(255,255,255,.15);padding:.8rem;overflow:auto;z-index:24;transform:translateX(100%);transition:transform .25s}
.comments-panel.open{transform:none}
.comment{padding:.5rem 0;border-bottom:1px solid #fff2;font-size:.9rem}
.comment .who{font-weight:600;opacity:.85}
.comment .num{color:var(--accent-2,#e9c46a);font-weight:700;margin-right:.3rem}
.comment-form textarea{width:100%;min-height:70px;border-radius:8px;border:1px solid #fff3;background:#0006;color:var(--fg);padding:.4rem}
.comment-form input[name=website]{position:absolute;left:-9999px}
.comment-toggle{position:fixed;bottom:12px;left:12px;z-index:25}
[data-anchor]{position:relative}
[data-anchor]>.anchor-mark{position:absolute;top:0;right:0;font-size:.75rem;background:#0008;border-radius:999px;padding:.1rem .5rem;cursor:pointer}
.present-bar{position:fixed;bottom:0;left:0;right:0;display:flex;gap:.5rem;align-items:center;padding:.5rem .8rem;background:#000c;backdrop-filter:blur(8px);z-index:26;font-size:.85rem;transition:opacity .3s}
.present-bar--hidden{opacity:0;pointer-events:none}
.present-bar .grow{flex:1}
.present-bar .ia{display:flex;gap:.2rem;align-items:center;padding:.2rem .4rem;border:1px solid #fff2;border-radius:8px}
.present-bar .ia .id{opacity:.7;margin-right:.3rem}
.present-bar .ia button.on{background:var(--accent);color:#000}
.qr-box{position:fixed;top:48px;right:12px;z-index:27;background:#fff;padding:.6rem;border-radius:10px;color:#000;text-align:center;font:600 .9rem var(--font-display)}
.qr-box[hidden]{display:none}
.qr-box svg{width:200px;height:200px;display:block}
.join{max-width:420px;margin:10vh auto;padding:1.5rem}
.join label{display:block;margin:.8rem 0 .3rem;font-weight:600}
.join .tags{display:grid;gap:.4rem}
.join .tags label{display:flex;gap:.5rem;align-items:center;font-weight:400;margin:0;padding:.5rem .7rem;border:1px solid #fff3;border-radius:8px}
@media (max-width:700px){.slide-page{padding:1.2rem 1rem}.deck-chrome__title{max-width:40vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
```

- [ ] **Step 5: Run tests**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q`
Expected: all pass (JS files referenced by the template don't need to exist for these tests).

- [ ] **Step 6: Commit**

```bash
git add presentations tests/presentations
git commit -m "feat(presentations): archive page renders svg/html/video slides with theme and hotspot data"
```

---

### Task 6: Present view — session, presenter actions, live state, QR

**Files:**
- Create: `presentations/views/present.py`, `presentations/livecache.py`, `presentations/templates/presentations/present.html`
- Modify: `presentations/urls.py`
- Test: `tests/presentations/test_present.py`

**Interfaces:**
- Produces URL names (all under `/presentations/<slug>/present/`, staff only):
  - `presentations:present` GET → page; creates a `Session` if none open.
  - `presentations:present-goto` POST `{"slide": id}` → 200 `{ok, v}`; 400 unknown id.
  - `presentations:present-interaction` POST at `interaction/<iid>/<state>/` → 200 `{ok, v}`; 400 unknown/invalid.
  - `presentations:present-video` POST `{"playing": bool, "t": float}` → 200.
  - `presentations:present-lock` / `present-unlock` POST → 200.
  - `presentations:present-state` GET → live state JSON for the open session plus `participants` count.
- Produces `livecache.get_state(session_code, builder)` — 1 s TTL — and `livecache.invalidate(code)`.
- Produces `presentations/views/common.py::live_state(session) -> dict`:
  ```json
  {"v":12,"slide":"orbits","locked":false,"interactions":{"q1":"open"},"video":{...},"participants":37}
  ```
- Produces `qr_svg(url) -> str` in `views/present.py`.

- [ ] **Step 1: Write failing tests**

`tests/presentations/test_present.py`:
```python
import json
import pytest
from presentations import registry
from presentations.models import Session
from .test_schema import make_deck

pytestmark = pytest.mark.django_db


@pytest.fixture
def deck(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    yield make_deck(tmp_path)
    registry.clear_cache()


def test_present_requires_staff(deck, anon_client):
    r = anon_client.get('/presentations/ex/present/')
    assert r.status_code == 302 and '/admin/login/' in r['Location']


def test_present_creates_and_resumes_session(deck, staff_client):
    r = staff_client.get('/presentations/ex/present/')
    assert r.status_code == 200
    s = Session.open_for('ex')
    assert s is not None and s.current_slide_id == 'title'
    assert f'/p/{s.join_code}/' in r.content.decode()
    assert '<svg' in r.content.decode().split('id="qr-box"')[1][:2000]
    staff_client.get('/presentations/ex/present/')
    assert Session.objects.filter(deck_slug='ex').count() == 1


def _post(client, url, body=None):
    return client.post(url, data=json.dumps(body or {}), content_type='application/json')


def test_presenter_actions(deck, staff_client):
    staff_client.get('/presentations/ex/present/')
    s = Session.open_for('ex')
    assert _post(staff_client, '/presentations/ex/present/goto/', {'slide': 'results'}).status_code == 200
    assert _post(staff_client, '/presentations/ex/present/goto/', {'slide': 'nope'}).status_code == 400
    assert _post(staff_client, '/presentations/ex/present/interaction/q1/open/').status_code == 200
    assert _post(staff_client, '/presentations/ex/present/interaction/q1/bogus/').status_code == 400
    assert _post(staff_client, '/presentations/ex/present/interaction/zz/open/').status_code == 400
    assert _post(staff_client, '/presentations/ex/present/video/', {'playing': True, 't': 3.5}).status_code == 200
    s.refresh_from_db()
    assert s.current_slide_id == 'results' and s.interaction_states == {'q1': 'open'}
    assert s.video_state['playing'] is True and s.video_state['t'] == 3.5
    st = staff_client.get('/presentations/ex/present/state/').json()
    assert st['slide'] == 'results' and st['interactions'] == {'q1': 'open'} and st['participants'] == 0
    assert st['v'] == s.version


def test_presenter_actions_reject_anon(deck, anon_client, staff_client):
    staff_client.get('/presentations/ex/present/')
    r = _post(anon_client, '/presentations/ex/present/goto/', {'slide': 'results'})
    assert r.status_code in (302, 403)


def test_lock_and_unlock(deck, staff_client):
    staff_client.get('/presentations/ex/present/')
    _post(staff_client, '/presentations/ex/present/interaction/q1/open/')
    assert _post(staff_client, '/presentations/ex/present/lock/').status_code == 200
    s = Session.objects.get(deck_slug='ex')
    assert s.is_locked and s.interaction_states == {'q1': 'revealed'}
    assert Session.open_for('ex') is None and Session.archived_for('ex') == s
    assert _post(staff_client, '/presentations/ex/present/unlock/').status_code == 200
    assert Session.open_for('ex') == s


def test_livecache_ttl(deck, staff_client, monkeypatch):
    from presentations import livecache
    calls = []
    def builder():
        calls.append(1)
        return {'v': len(calls)}
    t = [1000.0]
    monkeypatch.setattr(livecache.time, 'monotonic', lambda: t[0])
    assert livecache.get_state('ABC', builder) == {'v': 1}
    assert livecache.get_state('ABC', builder) == {'v': 1}
    t[0] += 1.1
    assert livecache.get_state('ABC', builder) == {'v': 2}
    livecache.invalidate('ABC')
    assert livecache.get_state('ABC', builder) == {'v': 3}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_present.py -q`
Expected: 404s / ImportError.

- [ ] **Step 3: livecache.py**

```python
import time

TTL = 1.0
_store = {}   # code -> (expires_at, payload)


def get_state(code, builder):
    now = time.monotonic()
    hit = _store.get(code)
    if hit and hit[0] > now:
        return hit[1]
    payload = builder()
    _store[code] = (now + TTL, payload)
    return payload


def invalidate(code):
    _store.pop(code, None)
```

- [ ] **Step 4: common.live_state + present views**

Append to `presentations/views/common.py`:
```python
import json
from django.http import JsonResponse


def live_state(session):
    return {
        'v': session.version, 'slide': session.current_slide_id, 'locked': session.is_locked,
        'interactions': session.interaction_states, 'video': session.video_state,
        'participants': session.participants.count(),
    }


def json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except ValueError:
        return {}


def bad(msg, status=400):
    return JsonResponse({'error': msg}, status=status)
```

`presentations/views/present.py`:
```python
import io

import qrcode
import qrcode.image.svg
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST

from .. import livecache
from ..models import INTERACTION_STATES, Session
from ..render import deck_json, deck_json_script, rendered_slides, theme_css
from .common import DeckErrorResponse, bad, deck_error_response, deck_or_404, json_body, live_state


def qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = io.BytesIO()
    img.save(buf)
    return mark_safe(buf.getvalue().decode())


def _session(deck):
    s = Session.open_for(deck.slug)
    if s is None:
        s = Session.objects.create(deck_slug=deck.slug, current_slide_id=deck.slides[0].id)
    elif not s.current_slide_id:
        s.set_slide(deck.slides[0].id)
    return s


def _touch(session):
    livecache.invalidate(session.join_code)


@staff_member_required
def present(request, slug):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    session = _session(deck)
    join_url = request.build_absolute_uri(f'/p/{session.join_code}/')
    base = f'/presentations/{slug}/present/'
    urls = {
        'state': base + 'state/', 'goto': base + 'goto/', 'interaction': base + 'interaction/',
        'video': base + 'video/', 'lock': base + 'lock/', 'unlock': base + 'unlock/',
        'aggregate': f'/p/{session.join_code}/aggregate/',
        'comment': reverse('presentations:comment', args=[slug]),
    }
    data = deck_json(deck, session, 'present', urls)
    return render(request, 'presentations/present.html', {
        'deck': deck, 'session': session, 'slides': rendered_slides(deck, request),
        'theme_css': theme_css(deck.theme), 'deck_data': deck_json_script(data),
        'join_url': join_url, 'qr': qr_svg(join_url),
    })


def _open_session_or_400(slug):
    s = Session.open_for(slug)
    return s


@staff_member_required
@require_POST
def goto(request, slug):
    deck = deck_or_404(slug)
    s = _open_session_or_400(slug)
    if s is None:
        return bad('no open session')
    sid = json_body(request).get('slide')
    if deck.slide(sid) is None:
        return bad('unknown slide')
    s.set_slide(sid)
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_POST
def interaction(request, slug, iid, state):
    deck = deck_or_404(slug)
    s = _open_session_or_400(slug)
    if s is None:
        return bad('no open session')
    if deck.interaction(iid) is None:
        return bad('unknown interaction')
    if state not in INTERACTION_STATES:
        return bad('invalid state')
    s.set_interaction_state(iid, state)
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_POST
def video(request, slug):
    s = _open_session_or_400(slug)
    if s is None:
        return bad('no open session')
    body = json_body(request)
    try:
        s.set_video_state(body.get('playing', False), body.get('t', 0))
    except (TypeError, ValueError):
        return bad('bad video state')
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_POST
def lock(request, slug):
    s = Session.open_for(slug)
    if s is None:
        return bad('no open session')
    s.lock()
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_POST
def unlock(request, slug):
    s = Session.archived_for(slug)
    if s is None:
        return bad('nothing to unlock')
    s.unlock()
    _touch(s)
    return JsonResponse({'ok': True, 'v': s.version})


@staff_member_required
@require_GET
def state(request, slug):
    s = Session.open_for(slug) or Session.archived_for(slug)
    if s is None:
        return bad('no session', 404)
    return JsonResponse(live_state(s))
```

`presentations/urls.py` — add:
```python
from .views import present
# …
    path('presentations/<slug:slug>/present/', present.present, name='present'),
    path('presentations/<slug:slug>/present/state/', present.state, name='present-state'),
    path('presentations/<slug:slug>/present/goto/', present.goto, name='present-goto'),
    path('presentations/<slug:slug>/present/interaction/<str:iid>/<str:state>/', present.interaction, name='present-interaction'),
    path('presentations/<slug:slug>/present/video/', present.video, name='present-video'),
    path('presentations/<slug:slug>/present/lock/', present.lock, name='present-lock'),
    path('presentations/<slug:slug>/present/unlock/', present.unlock, name='present-unlock'),
```

`presentations/templates/presentations/present.html` — same head/body as `archive.html` with these differences: `<body class="mode-present">`, `{% with mode='present' %}` for the chrome, no live-banner, and before `deck-data`:
```django
<div class="qr-box" id="qr-box" hidden>{{ qr }}<div>{{ join_url }}</div></div>
<div class="present-bar" id="present-bar">
  <button class="btn" id="prev">‹</button><button class="btn" id="next">›</button>
  <span id="present-interactions"></span>
  <select id="all-interactions" class="btn"><option value="">all interactions…</option>{% for i in deck.interactions %}<option value="{{ i.id }}">{{ i.id }} ({{ i.type }})</option>{% endfor %}</select>
  <span class="grow"></span>
  <span id="participants">0 joined</span>
  <button class="btn" id="qr-toggle">QR</button>
  <button class="btn" id="lock-btn">{% if session.is_locked %}Unlock{% else %}Lock{% endif %}</button>
</div>
```
and load `present.js` instead of `archive.js`.

- [ ] **Step 5: Run tests**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add presentations tests/presentations
git commit -m "feat(presentations): present view, presenter actions, live state, QR"
```

---

### Task 7: Phone — join, mirror page, respond, aggregate endpoints

**Files:**
- Create: `presentations/views/phone.py`, `presentations/templates/presentations/phone.html`, `presentations/templates/presentations/join.html`
- Modify: `presentations/urls.py`
- Test: `tests/presentations/test_phone.py`

**Interfaces:**
- Produces URLs (public):
  - `GET /p/<code>/` → join page if no participant cookie for this session, else phone mirror page. 404 unknown code. If session is locked → redirect to archive.
  - `POST /p/<code>/join/` form fields `expertise_tag` (must be in deck.expertise), `display_name` (optional, ≤60) → sets cookie `pres_<code>=<token>` (1 year, SameSite=Lax) and redirects to `/p/<code>/`.
  - `GET /p/<code>/state/` → `live_state()` through `livecache`; header `Cache-Control: no-store`.
  - `GET /p/<code>/aggregate/<iid>/?tag=<tag|all|not:<tag>>` → `{"n":…, …aggregate…, "tag":…}` — 403 while state is `hidden` or `open` **unless** the requester is staff; `{"n": k, "too_small": true}` when the slice has n < 3 (but not for `all`).
  - `POST /p/<code>/respond/<iid>/` JSON payload → 200 `{ok}`; 401 without valid participant cookie; 409 unless state is `open`; 400 invalid payload.
- Produces helper `views/common.py::participant_from(request, session) -> Participant | None`.
- `deck_json` urls for phone: `{"state": "/p/<code>/state/", "respond": "/p/<code>/respond/", "aggregate": "/p/<code>/aggregate/", "comment": "/presentations/<slug>/comment/"}`.

- [ ] **Step 1: Write failing tests**

`tests/presentations/test_phone.py`:
```python
import json
import pytest
from presentations import registry
from presentations.models import Session, Participant, Response
from .test_schema import make_deck

pytestmark = pytest.mark.django_db


@pytest.fixture
def live(tmp_path, settings, staff_client):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    make_deck(tmp_path)
    staff_client.get('/presentations/ex/present/')
    yield Session.open_for('ex')
    registry.clear_cache()


def join(client, code, tag='theory', name='Ana'):
    return client.post(f'/p/{code}/join/', {'expertise_tag': tag, 'display_name': name})


def test_join_flow(live, anon_client):
    r = anon_client.get(f'/p/{live.join_code}/')
    assert r.status_code == 200 and b'expertise_tag' in r.content and b'theory' in r.content
    assert join(anon_client, live.join_code, tag='nope').status_code == 400
    r = join(anon_client, live.join_code)
    assert r.status_code == 302 and f'pres_{live.join_code}' in r.cookies
    p = Participant.objects.get(session=live)
    assert p.expertise_tag == 'theory' and p.display_name == 'Ana' and p.ip_hash
    r = anon_client.get(f'/p/{live.join_code}/')
    assert r.status_code == 200 and b'id="deck-data"' in r.content and b'expertise_tag' not in r.content
    assert anon_client.get('/p/ZZZZZZ/').status_code == 404


def test_state_endpoint(live, anon_client):
    r = anon_client.get(f'/p/{live.join_code}/state/')
    assert r.status_code == 200 and r['Cache-Control'] == 'no-store'
    assert r.json()['slide'] == 'title' and r.json()['participants'] == 0


def _respond(client, code, iid, payload):
    return client.post(f'/p/{code}/respond/{iid}/', data=json.dumps(payload), content_type='application/json')


def test_respond_state_machine(live, anon_client, staff_client):
    code = live.join_code
    assert _respond(anon_client, code, 'q1', {'choice': 'A'}).status_code == 401
    join(anon_client, code)
    assert _respond(anon_client, code, 'q1', {'choice': 'A'}).status_code == 409      # hidden
    staff_client.post(f'/presentations/ex/present/interaction/q1/open/')
    assert _respond(anon_client, code, 'q1', {'choice': 'Z'}).status_code == 400
    assert _respond(anon_client, code, 'zz', {'choice': 'A'}).status_code == 404
    assert _respond(anon_client, code, 'q1', {'choice': 'A'}).status_code == 200
    assert _respond(anon_client, code, 'q1', {'choice': 'B'}).status_code == 200      # upsert
    assert Response.objects.filter(session=live, interaction_id='q1').count() == 1
    assert Response.objects.get(session=live).payload == {'choice': 'B'}
    staff_client.post(f'/presentations/ex/present/interaction/q1/closed/')
    assert _respond(anon_client, code, 'q1', {'choice': 'A'}).status_code == 409


def test_aggregate_visibility_and_slicing(live, staff_client):
    from django.test import Client
    code = live.join_code
    staff_client.post(f'/presentations/ex/present/interaction/q1/open/')
    clients = []
    for i, (tag, choice) in enumerate([('theory', 'A'), ('theory', 'A'), ('theory', 'B'), ('data', 'B')]):
        c = Client()
        join(c, code, tag=tag, name=f'p{i}')
        _respond(c, code, 'q1', {'choice': choice})
        clients.append(c)
    # phones can't see aggregate while open; staff can
    assert clients[0].get(f'/p/{code}/aggregate/q1/').status_code == 403
    r = staff_client.get(f'/p/{code}/aggregate/q1/')
    assert r.status_code == 200 and r.json()['counts'] == {'A': 2, 'B': 2}
    staff_client.post(f'/presentations/ex/present/interaction/q1/revealed/')
    r = clients[0].get(f'/p/{code}/aggregate/q1/?tag=theory')
    assert r.json()['n'] == 3 and r.json()['counts'] == {'A': 2, 'B': 1}
    r = clients[0].get(f'/p/{code}/aggregate/q1/?tag=data')
    assert r.json() == {'n': 1, 'too_small': True, 'tag': 'data'}
    r = clients[0].get(f'/p/{code}/aggregate/q1/?tag=not:data')
    assert r.json()['n'] == 3
    assert clients[0].get(f'/p/{code}/aggregate/zz/').status_code == 404


def test_locked_session_phone_redirects_to_archive(live, anon_client, staff_client):
    staff_client.post('/presentations/ex/present/lock/')
    r = anon_client.get(f'/p/{live.join_code}/')
    assert r.status_code == 302 and r['Location'] == '/presentations/ex/'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_phone.py -q`
Expected: 404s.

- [ ] **Step 3: Implement**

Append to `presentations/views/common.py`:
```python
from ..models import Participant, Response
from .. import interactions as interaction_types
from ..textutil import hash_ip


def client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return (xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')) or ''


def participant_from(request, session):
    token = request.COOKIES.get(f'pres_{session.join_code}')
    if not token:
        return None
    return Participant.objects.filter(session=session, token=token).first()


def aggregate_payload(deck, session, iid, tag, is_staff):
    idef = deck.interaction(iid)
    if idef is None:
        return None, 404
    state = session.state_for(iid)
    if state in ('hidden', 'open') and not is_staff:
        return {'error': 'not revealed'}, 403
    qs = Response.objects.filter(session=session, interaction_id=iid).select_related('participant')
    tag = tag or 'all'
    if tag.startswith('not:'):
        qs = qs.exclude(participant__expertise_tag=tag[4:])
    elif tag != 'all':
        qs = qs.filter(participant__expertise_tag=tag)
    payloads = [r.payload for r in qs]
    if tag != 'all' and len(payloads) < 3:
        return {'n': len(payloads), 'too_small': True, 'tag': tag}, 200
    agg = interaction_types.get(idef.type).aggregate(payloads, idef.config)
    agg['tag'] = tag
    agg['state'] = state
    return agg, 200
```

`presentations/views/phone.py`:
```python
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .. import interactions as interaction_types
from .. import livecache
from ..models import Participant, Response, Session
from ..render import deck_json, deck_json_script, rendered_slides, theme_css
from ..textutil import hash_ip
from .common import (DeckErrorResponse, aggregate_payload, bad, client_ip, deck_error_response,
                     deck_or_404, json_body, live_state, participant_from)

COOKIE_AGE = 365 * 24 * 3600


def _session(code):
    s = Session.objects.filter(join_code=code.upper()).first()
    if s is None:
        raise Http404('unknown join code')
    return s


def phone(request, code):
    session = _session(code)
    if session.is_locked:
        return redirect(reverse('presentations:archive', args=[session.deck_slug]))
    try:
        deck = deck_or_404(session.deck_slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    participant = participant_from(request, session)
    if participant is None:
        return render(request, 'presentations/join.html', {'deck': deck, 'session': session,
                                                          'theme_css': theme_css(deck.theme)})
    base = f'/p/{session.join_code}/'
    urls = {'state': base + 'state/', 'respond': base + 'respond/', 'aggregate': base + 'aggregate/',
            'comment': reverse('presentations:comment', args=[deck.slug])}
    data = deck_json(deck, session, 'phone', urls)
    data['participant'] = {'name': participant.display_name, 'tag': participant.expertise_tag}
    return render(request, 'presentations/phone.html', {
        'deck': deck, 'session': session, 'slides': rendered_slides(deck, request),
        'theme_css': theme_css(deck.theme), 'deck_data': deck_json_script(data), 'participant': participant,
    })


@require_POST
def join(request, code):
    session = _session(code)
    if session.is_locked:
        return bad('session is locked', 409)
    deck = deck_or_404(session.deck_slug)
    tag = request.POST.get('expertise_tag', '')
    if tag not in deck.expertise:
        return bad('pick one of the listed expertise tags')
    name = request.POST.get('display_name', '').strip()[:60]
    p = Participant.objects.create(session=session, expertise_tag=tag, display_name=name,
                                   ip_hash=hash_ip(client_ip(request)))
    livecache.invalidate(session.join_code)
    resp = redirect(reverse('presentations:phone', args=[session.join_code]))
    resp.set_cookie(f'pres_{session.join_code}', p.token, max_age=COOKIE_AGE, samesite='Lax',
                    secure=request.is_secure(), httponly=True)
    return resp


@require_GET
def state(request, code):
    session = _session(code)
    payload = livecache.get_state(session.join_code, lambda: live_state(Session.objects.get(pk=session.pk)))
    resp = JsonResponse(payload)
    resp['Cache-Control'] = 'no-store'
    return resp


@require_POST
def respond(request, code, iid):
    session = _session(code)
    deck = deck_or_404(session.deck_slug)
    participant = participant_from(request, session)
    if participant is None:
        return bad('join first', 401)
    idef = deck.interaction(iid)
    if idef is None:
        return bad('unknown interaction', 404)
    if session.state_for(iid) != 'open':
        return bad('interaction is not open', 409)
    try:
        payload = interaction_types.get(idef.type).clean_payload(json_body(request), idef.config)
    except ValueError as e:
        return bad(str(e))
    Response.objects.update_or_create(participant=participant, interaction_id=iid,
                                      defaults={'session': session, 'payload': payload})
    return JsonResponse({'ok': True})


@require_GET
def aggregate(request, code, iid):
    session = _session(code)
    deck = deck_or_404(session.deck_slug)
    payload, status = aggregate_payload(deck, session, iid, request.GET.get('tag'), request.user.is_staff)
    if payload is None:
        return bad('unknown interaction', 404)
    resp = JsonResponse(payload, status=status)
    resp['Cache-Control'] = 'no-store'
    return resp
```

`presentations/urls.py` — add:
```python
from .views import phone
# …
    path('p/<str:code>/', phone.phone, name='phone'),
    path('p/<str:code>/join/', phone.join, name='phone-join'),
    path('p/<str:code>/state/', phone.state, name='phone-state'),
    path('p/<str:code>/respond/<str:iid>/', phone.respond, name='phone-respond'),
    path('p/<str:code>/aggregate/<str:iid>/', phone.aggregate, name='phone-aggregate'),
```

`presentations/templates/presentations/join.html`:
```django
{% load static %}<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Join · {{ deck.title }}</title><link rel="stylesheet" href="{% static 'presentations/css/deck.css' %}"><style>:root{ {{ theme_css|safe }} }</style></head>
<body><form class="join" method="post" action="{% url 'presentations:phone-join' session.join_code %}">{% csrf_token %}
<h2>{{ deck.title }}</h2><p style="opacity:.75">{{ deck.date }}{% if deck.subtitle %} · {{ deck.subtitle }}{% endif %}</p>
<label>I mostly do…</label>
<div class="tags">{% for t in deck.expertise %}<label><input type="radio" name="expertise_tag" value="{{ t }}" required> {{ t }}</label>{% endfor %}</div>
<label for="dn">Name (optional)</label><input id="dn" class="txt" name="display_name" maxlength="60" placeholder="used only to sign your comments">
<p><button class="btn btn--primary" type="submit" style="width:100%;padding:.8rem;font-size:1.1rem">Join</button></p>
</form></body></html>
```

`presentations/templates/presentations/phone.html` — same as `archive.html` with `<body class="mode-phone">`, `{% with mode='phone' %}`, no live-banner, plus before `deck-data`:
```django
<button class="follow-pill" id="follow-pill" hidden>⟳ jump to live</button>
<div class="ask-panel" id="ask-panel" hidden></div>
```
and load `phone.js` instead of `archive.js`.

- [ ] **Step 4: Run tests**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add presentations tests/presentations
git commit -m "feat(presentations): phone join, mirror page, respond and aggregate endpoints"
```

---

### Task 8: Archive aggregates for locked sessions

**Files:**
- Modify: `presentations/views/archive.py`, `presentations/urls.py` (replace the `archive-aggregate` placeholder)
- Test: `tests/presentations/test_lock.py`

**Interfaces:**
- Produces `GET /presentations/<slug>/aggregate/<iid>/?tag=` → same payload as the phone aggregate but against `Session.archived_for(slug)`; 404 if no archived session; 403 if the interaction was never revealed (state ≠ `revealed`).

- [ ] **Step 1: Write failing tests**

`tests/presentations/test_lock.py`:
```python
import json
import pytest
from django.test import Client
from presentations import registry
from presentations.models import Session
from .test_schema import make_deck

pytestmark = pytest.mark.django_db


@pytest.fixture
def played(tmp_path, settings, staff_client):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    make_deck(tmp_path)
    staff_client.get('/presentations/ex/present/')
    s = Session.open_for('ex')
    staff_client.post('/presentations/ex/present/interaction/q1/open/')
    for tag, ch in [('theory', 'A'), ('theory', 'B'), ('data', 'B')]:
        c = Client()
        c.post(f'/p/{s.join_code}/join/', {'expertise_tag': tag})
        c.post(f'/p/{s.join_code}/respond/q1/', data=json.dumps({'choice': ch}), content_type='application/json')
    yield s
    registry.clear_cache()


def test_archive_aggregate_needs_locked_session(played, anon_client):
    assert anon_client.get('/presentations/ex/aggregate/q1/').status_code == 404


def test_archive_after_lock(played, anon_client, staff_client):
    staff_client.post('/presentations/ex/present/lock/')
    r = anon_client.get('/presentations/ex/aggregate/q1/')
    assert r.status_code == 200 and r.json()['counts'] == {'A': 1, 'B': 2} and r.json()['state'] == 'revealed'
    page = anon_client.get('/presentations/ex/').content.decode()
    data = json.loads(page.split('id="deck-data" type="application/json">')[1].split('</script>')[0])
    assert data['session']['locked'] is True and data['interactions']['q1']['state'] == 'revealed'
    assert 'LOCKED' in page


def test_never_opened_interaction_stays_hidden(tmp_path, settings, staff_client, anon_client):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    make_deck(tmp_path)
    staff_client.get('/presentations/ex/present/')
    staff_client.post('/presentations/ex/present/lock/')
    assert anon_client.get('/presentations/ex/aggregate/q1/').status_code == 403
    registry.clear_cache()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_lock.py -q`
Expected: 404 where 200 expected.

- [ ] **Step 3: Implement**

Add to `presentations/views/archive.py`:
```python
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from ..models import Session
from .common import aggregate_payload, bad


@require_GET
def archive_aggregate(request, slug, iid):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    session = Session.archived_for(slug)
    if session is None:
        return bad('no archived session', 404)
    if session.state_for(iid) != 'revealed' and deck.interaction(iid) is not None:
        return bad('not revealed', 403)
    payload, status = aggregate_payload(deck, session, iid, request.GET.get('tag'), True)
    if payload is None:
        return bad('unknown interaction', 404)
    return JsonResponse(payload, status=status)
```
In `urls.py` replace the placeholder line with `path('presentations/<slug:slug>/aggregate/<str:iid>/', archive.archive_aggregate, name='archive-aggregate'),`.

- [ ] **Step 4: Run tests, commit**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q` → all pass.
```bash
git add presentations tests/presentations
git commit -m "feat(presentations): archive aggregates from the locked session"
```

---

### Task 9: Comments — endpoint, moderation, rendering

**Files:**
- Create: `presentations/views/comments.py`, `presentations/templates/presentations/_comments.html`
- Modify: `presentations/urls.py`, `presentations/views/archive.py`, `phone.py`, `present.py` (pass comments into templates), `_slides.html`/page templates (include `_comments.html`)
- Test: `tests/presentations/test_comments.py`

**Interfaces:**
- `POST /presentations/<slug>/comment/` JSON `{"slide": id, "anchor": {"rect":[..]} | {"anchor":"fig-2"} | null, "body": str, "author_name": str?, "website": ""}` → 201 `{id, html, author, created_at, anchor, slide, num}`; 400 bad slide / empty / too long / bad anchor; 429 rate-limited; honeypot non-empty → 201 with `{"ok": true}` but nothing stored (silent drop).
- `GET /presentations/<slug>/comments/` → `{"comments":[{id, slide, anchor, author, html, created_at}]}` visible only. Used by all three pages on load and by phone/present every 5 s.
- Author resolution: if the request carries a valid participant cookie for the live or archived session, `participant` is set and `author_name` defaults to `participant.display_name`.

- [ ] **Step 1: Write failing tests**

`tests/presentations/test_comments.py`:
```python
import json
import pytest
from presentations import registry
from presentations.models import Comment
from .test_schema import make_deck

pytestmark = pytest.mark.django_db


@pytest.fixture
def deck(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path
    registry.clear_cache()
    yield make_deck(tmp_path)
    registry.clear_cache()


def post(client, body):
    return client.post('/presentations/ex/comment/', data=json.dumps(body), content_type='application/json')


def test_create_and_list(deck, anon_client):
    r = post(anon_client, {'slide': 'title', 'anchor': {'rect': [0.1, 0.1, 0.2, 0.2]}, 'body': 'why **this**?', 'author_name': 'Ana', 'website': ''})
    assert r.status_code == 201
    j = r.json()
    assert j['html'] == '<p>why <strong>this</strong>?</p>' and j['author'] == 'Ana' and j['num'] == 1
    r = anon_client.get('/presentations/ex/comments/')
    assert r.json()['comments'][0]['anchor'] == {'rect': [0.1, 0.1, 0.2, 0.2]}
    assert Comment.objects.get().ip_hash


def test_validation(deck, anon_client):
    assert post(anon_client, {'slide': 'zzz', 'body': 'x'}).status_code == 400
    assert post(anon_client, {'slide': 'title', 'body': '   '}).status_code == 400
    assert post(anon_client, {'slide': 'title', 'body': 'x' * 1001}).status_code == 400
    assert post(anon_client, {'slide': 'title', 'body': 'x', 'anchor': {'rect': [2, 0, 0, 0]}}).status_code == 400
    assert post(anon_client, {'slide': 'page', 'body': 'x', 'anchor': {'rect': [0, 0, .1, .1]}}).status_code == 400  # html slide → anchor names only
    assert post(anon_client, {'slide': 'page', 'body': 'x', 'anchor': {'anchor': 'fig-2'}}).status_code == 201
    assert post(anon_client, {'slide': 'title', 'body': 'x', 'anchor': None}).status_code == 201


def test_honeypot_silently_drops(deck, anon_client):
    r = post(anon_client, {'slide': 'title', 'body': 'buy stuff', 'website': 'http://spam'})
    assert r.status_code == 201 and Comment.objects.count() == 0


def test_rate_limit(deck, anon_client):
    for i in range(5):
        assert post(anon_client, {'slide': 'title', 'body': f'c{i}'}).status_code == 201
    assert post(anon_client, {'slide': 'title', 'body': 'c6'}).status_code == 429


def test_hidden_not_listed(deck, anon_client):
    post(anon_client, {'slide': 'title', 'body': 'ok'})
    Comment.objects.update(is_hidden=True)
    assert anon_client.get('/presentations/ex/comments/').json()['comments'] == []


def test_participant_signs_comment(deck, anon_client, staff_client):
    from presentations.models import Session
    staff_client.get('/presentations/ex/present/')
    s = Session.open_for('ex')
    anon_client.post(f'/p/{s.join_code}/join/', {'expertise_tag': 'theory', 'display_name': 'Bo'})
    r = post(anon_client, {'slide': 'title', 'body': 'hi'})
    assert r.json()['author'] == 'Bo' and Comment.objects.get().participant is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_comments.py -q`
Expected: 404s.

- [ ] **Step 3: Implement**

`presentations/views/comments.py`:
```python
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from ..models import Comment, Session
from ..textutil import hash_ip, render_markdown
from .common import (DeckErrorResponse, bad, client_ip, deck_error_response, deck_or_404,
                     json_body, participant_from)

RATE_LIMIT = 5
RATE_WINDOW = timedelta(minutes=1)


def _serialize(c, num):
    return {'id': c.id, 'slide': c.slide_id, 'anchor': c.anchor, 'author': c.author_name or 'anon',
            'html': render_markdown(c.body), 'created_at': c.created_at.isoformat(), 'num': num}


def _numbered(qs):
    """Number comments per slide in creation order so the overlay can label boxes ①②③."""
    counters, out = {}, []
    for c in qs:
        counters[c.slide_id] = counters.get(c.slide_id, 0) + 1
        out.append(_serialize(c, counters[c.slide_id]))
    return out


def _valid_anchor(slide, anchor):
    if anchor is None:
        return True
    if not isinstance(anchor, dict) or len(anchor) != 1:
        return False
    if 'rect' in anchor:
        r = anchor['rect']
        return (slide.uses_stage and isinstance(r, list) and len(r) == 4
                and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in r))
    if 'anchor' in anchor:
        return slide.kind == 'html' and isinstance(anchor['anchor'], str) and 0 < len(anchor['anchor']) <= 60
    return False


@require_GET
def list_comments(request, slug):
    try:
        deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    qs = Comment.visible.filter(deck_slug=slug).order_by('created_at')
    return JsonResponse({'comments': _numbered(qs)})


@require_POST
def create(request, slug):
    try:
        deck = deck_or_404(slug)
    except DeckErrorResponse as e:
        return deck_error_response(request, e)
    body = json_body(request)
    if body.get('website'):
        return JsonResponse({'ok': True}, status=201)          # honeypot: pretend
    slide = deck.slide(body.get('slide'))
    if slide is None:
        return bad('unknown slide')
    text = (body.get('body') or '').strip()
    if not text:
        return bad('empty comment')
    if len(text) > 1000:
        return bad('comment too long (max 1000 characters)')
    anchor = body.get('anchor')
    if not _valid_anchor(slide, anchor):
        return bad('bad anchor')
    ip = hash_ip(client_ip(request))
    since = timezone.now() - RATE_WINDOW
    if Comment.objects.filter(ip_hash=ip, created_at__gte=since).count() >= RATE_LIMIT:
        return bad('too many comments, wait a minute', 429)
    participant = None
    for s in (Session.open_for(slug), Session.archived_for(slug)):
        if s is not None:
            participant = participant_from(request, s)
            if participant:
                break
    author = (body.get('author_name') or '').strip()[:60] or (participant.display_name if participant else '')
    c = Comment.objects.create(deck_slug=slug, slide_id=slide.id, anchor=anchor, author_name=author,
                               participant=participant, body=text, ip_hash=ip)
    num = Comment.visible.filter(deck_slug=slug, slide_id=slide.id, created_at__lte=c.created_at).count()
    return JsonResponse(_serialize(c, num), status=201)
```

`urls.py`: replace the comment placeholder with
```python
    path('presentations/<slug:slug>/comment/', comments.create, name='comment'),
    path('presentations/<slug:slug>/comments/', comments.list_comments, name='comments'),
```
and add `'comments': '/presentations/<slug>/comments/'` to the `urls` dict in `archive()`, `present()` and `phone()` (each already builds a dict — add the key with the concrete slug).

`presentations/templates/presentations/_comments.html` (included in all three page templates right after `_hotspot_card.html`):
```django
<button class="btn comment-toggle" id="comment-toggle">💬 <span id="comment-count">0</span></button>
<aside class="comments-panel" id="comments-panel">
  <h3 style="margin:.2rem 0 .6rem">Questions &amp; comments</h3>
  <div id="comment-list"></div>
  <form class="comment-form" id="comment-form" autocomplete="off">
    <p style="font-size:.8rem;opacity:.75" id="comment-target">On this slide</p>
    <input type="text" name="website" tabindex="-1" aria-hidden="true">
    <textarea name="body" maxlength="1000" placeholder="Ask about this slide… (markdown ok)"></textarea>
    <input class="txt" name="author_name" maxlength="60" placeholder="name (optional)" style="margin:.4rem 0">
    <div style="display:flex;gap:.4rem"><button class="btn" type="button" id="comment-box-btn" title="draw a box on the slide">▭ point at something</button><span class="grow" style="flex:1"></span><button class="btn btn--primary" type="submit">Post</button></div>
  </form>
</aside>
```

- [ ] **Step 4: Run tests, commit**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q` → all pass.
```bash
git add presentations tests/presentations
git commit -m "feat(presentations): comments with anchors, honeypot, rate limit, moderation"
```

---

### Task 10: JS toolkit core — `core.js`, `stage.js`, `sync.js`, `hotspots.js`

**Files:**
- Create: `presentations/static/presentations/js/core.js`, `stage.js`, `sync.js`, `hotspots.js`
- Test: `tests/presentations/js/stage.test.mjs` (run with `node`)

**Interfaces (global `window.Presentations`, abbreviated `P`):**
```js
P.data                      // parsed #deck-data
P.$(sel, root?)             // querySelector
P.el(tag, attrs, children)  // element factory; attrs.text sets textContent, attrs.html sets innerHTML
P.api.get(url) -> Promise<json>;  P.api.post(url, body) -> Promise<{status, json}>   // sends X-CSRFToken from cookie
P.escape(str)
P.stage.frac2stage([x,y,w,h]) -> {x,y,w,h}     // ×1920 / ×1080
P.stage.px2frac(stageInnerEl, clientX, clientY) -> [fx, fy]   // accounts for letterboxing of the 16:9 inner box
P.stage.rectEl(kind, rect, attrs) -> SVGRectElement            // <rect class=kind …> in stage units
P.stage.go(indexOrId, {user:boolean}) ; P.stage.current() -> slideId ; P.stage.index() -> n
P.stage.onChange(cb)        // cb(slideId, index, {user})
P.stage.slideEl(id) -> section ; P.stage.overlay(id) -> svg|null ; P.stage.widgets(id) -> div|null
P.sync.start(url, intervalMs) ; P.sync.onState(cb) ; P.sync.stop()   // cb(state) only when state.v increases
P.hotspots.mount()          // draws rects from P.data for stage slides, wires data-hotspot spans, owns #hotspot-card
```

- [ ] **Step 1: Write the stage math test**

`tests/presentations/js/stage.test.mjs`:
```js
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const ctx = { window: {}, document: { addEventListener() {}, querySelector() { return null; }, querySelectorAll() { return []; } } };
ctx.window.Presentations = { data: { slides: [] }, $: () => null };
vm.createContext(ctx);
vm.runInContext(readFileSync(new URL('../../../presentations/static/presentations/js/stage.js', import.meta.url), 'utf8'), ctx);
const S = ctx.window.Presentations.stage;

assert.deepEqual(S.frac2stage([0.5, 0.25, 0.1, 0.2]), { x: 960, y: 270, w: 192, h: 216 });

// letterboxed inner box: element 1000×700 → 16:9 content is 1000×562.5 centred vertically (offset 68.75)
const fake = { getBoundingClientRect: () => ({ left: 100, top: 50, width: 1000, height: 700 }) };
const [fx, fy] = S.px2frac(fake, 100 + 500, 50 + 68.75 + 281.25);
assert.ok(Math.abs(fx - 0.5) < 1e-9 && Math.abs(fy - 0.5) < 1e-9);
const [cx, cy] = S.px2frac(fake, 0, 0);
assert.equal(cx, 0); assert.equal(cy, 0);            // clamped
console.log('stage math ok');
```

Run: `node tests/presentations/js/stage.test.mjs` → fails (file missing).

- [ ] **Step 2: core.js**

```js
(function () {
  const P = (window.Presentations = window.Presentations || {});
  const dataEl = document.querySelector('#deck-data');
  P.data = dataEl ? JSON.parse(dataEl.textContent) : {};
  P.$ = (sel, root) => (root || document).querySelector(sel);
  P.$$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  P.escape = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  P.el = function (tag, attrs, children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'text') e.textContent = v; else if (k === 'html') e.innerHTML = v;
      else if (k === 'class') e.className = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v);
    }
    for (const c of children || []) e.append(c);
    return e;
  };
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  P.api = {
    async get(url) { const r = await fetch(url, { credentials: 'same-origin', cache: 'no-store' }); return r.ok ? r.json() : Promise.reject(await r.json().catch(() => ({ status: r.status }))); },
    async post(url, body) {
      const r = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify(body || {}) });
      return { status: r.status, json: await r.json().catch(() => ({})) };
    },
  };
  P.emit = function (name, detail) { document.dispatchEvent(new CustomEvent('pres:' + name, { detail })); };
  P.on = function (name, cb) { document.addEventListener('pres:' + name, (e) => cb(e.detail)); };
})();
```

- [ ] **Step 3: stage.js**

```js
(function () {
  const P = (window.Presentations = window.Presentations || {});
  const W = 1920, H = 1080, NS = 'http://www.w3.org/2000/svg';
  const S = (P.stage = {});
  let idx = 0; const listeners = [];
  const slides = () => (P.data.slides || []);

  S.frac2stage = ([x, y, w, h]) => ({ x: x * W, y: y * H, w: w * W, h: h * H });
  S.px2frac = function (inner, clientX, clientY) {
    const r = inner.getBoundingClientRect();
    let cw = r.width, ch = r.width * H / W, ox = 0, oy = (r.height - ch) / 2;
    if (ch > r.height) { ch = r.height; cw = r.height * W / H; oy = 0; ox = (r.width - cw) / 2; }
    const fx = Math.min(1, Math.max(0, (clientX - r.left - ox) / cw));
    const fy = Math.min(1, Math.max(0, (clientY - r.top - oy) / ch));
    return [fx, fy];
  };
  S.rectEl = function (kind, rect, attrs) {
    const e = document.createElementNS(NS, 'rect'); const s = S.frac2stage(rect);
    e.setAttribute('x', s.x); e.setAttribute('y', s.y); e.setAttribute('width', s.w); e.setAttribute('height', s.h);
    e.setAttribute('rx', 10); e.setAttribute('class', kind);
    for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
    return e;
  };
  S.textEl = function (x, y, text, cls) {
    const e = document.createElementNS(NS, 'text'); e.setAttribute('x', x); e.setAttribute('y', y); e.setAttribute('class', cls); e.textContent = text; return e;
  };
  S.slideEl = (id) => document.querySelector(`.slide[data-slide-id="${CSS.escape(id)}"]`);
  S.overlay = (id) => { const s = S.slideEl(id); return s ? s.querySelector('.overlay') : null; };
  S.widgets = (id) => { const s = S.slideEl(id); return s ? s.querySelector('.stage__widgets') : null; };
  S.index = () => idx;
  S.current = () => (slides()[idx] || {}).id;
  S.onChange = (cb) => listeners.push(cb);
  S.go = function (target, opts) {
    const list = slides(); let n = typeof target === 'number' ? target : list.findIndex((s) => s.id === target);
    if (n < 0 || n >= list.length) return;
    idx = n;
    document.querySelectorAll('.slide').forEach((el) => { el.hidden = Number(el.dataset.index) !== n; });
    const num = document.querySelector('#slide-num'); if (num) num.textContent = String(n + 1);
    document.querySelectorAll('video').forEach((v) => { if (!v.closest('.slide') || v.closest('.slide').hidden) v.pause(); });
    listeners.forEach((cb) => cb(list[n].id, n, opts || {}));
  };
  S.next = (opts) => S.go(idx + 1, opts); S.prev = (opts) => S.go(idx - 1, opts);
  S.keys = function (onSpace) {
    document.addEventListener('keydown', (e) => {
      if (e.target.matches('input,textarea,select')) return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown') { S.next({ user: true }); e.preventDefault(); }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { S.prev({ user: true }); e.preventDefault(); }
      else if (e.key === ' ') { (onSpace || (() => S.next({ user: true })))(); e.preventDefault(); }
    });
  };
  S.swipe = function () {
    let x0 = null;
    document.addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
    document.addEventListener('touchend', (e) => {
      if (x0 == null) return; const dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (e.target.closest('canvas.draw,.comments-panel,.ask-panel')) return;
      if (dx < -60) S.next({ user: true }); else if (dx > 60) S.prev({ user: true });
    });
  };
  S.buttons = function () {
    const p = document.querySelector('#prev'), n = document.querySelector('#next');
    if (p) p.addEventListener('click', () => S.prev({ user: true }));
    if (n) n.addEventListener('click', () => S.next({ user: true }));
  };
})();
```

Run: `node tests/presentations/js/stage.test.mjs` → `stage math ok`.

- [ ] **Step 4: sync.js**

```js
(function () {
  const P = (window.Presentations = window.Presentations || {});
  const S = (P.sync = {});
  let timer = null, last = -1; const cbs = [];
  S.onState = (cb) => cbs.push(cb);
  S.start = function (url, interval) {
    S.stop();
    const tick = async () => {
      try {
        const st = await P.api.get(url);
        if (st && typeof st.v === 'number' && st.v > last) { last = st.v; cbs.forEach((cb) => cb(st)); }
      } catch (e) { /* offline blip: keep polling */ }
    };
    tick(); timer = setInterval(tick, interval || 1500);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
  };
  S.stop = () => { if (timer) clearInterval(timer); timer = null; };
  S.reset = () => { last = -1; };
})();
```

- [ ] **Step 5: hotspots.js**

```js
(function () {
  const P = (window.Presentations = window.Presentations || {});
  const Hs = (P.hotspots = {});
  const card = () => P.$('#hotspot-card');
  let pinned = null;
  const touch = matchMedia('(hover: none)').matches;

  function place(x, y) {
    const c = card(); const pad = 14; const r = c.getBoundingClientRect();
    let left = x + pad, top = y + pad;
    if (left + r.width > innerWidth - 8) left = Math.max(8, x - r.width - pad);
    if (top + r.height > innerHeight - 8) top = Math.max(48, y - r.height - pad);
    c.style.left = left + 'px'; c.style.top = top + 'px';
  }
  function show(h, x, y, pin) {
    const c = card(); if (!c) return;
    P.$('.hotspot-card__title', c).textContent = h.title;
    P.$('.hotspot-card__body', c).innerHTML = h.body_html || '';
    const links = P.$('.hotspot-card__links', c); links.innerHTML = '';
    (h.links || []).forEach((l) => links.append(P.el('a', { href: l.url, target: '_blank', rel: 'noopener', text: l.label || l.url })));
    c.hidden = false; c.classList.toggle('hotspot-card--pinned', !!pin); place(x, y);
  }
  function hide(force) { if (pinned && !force) return; pinned = null; const c = card(); if (c) { c.hidden = true; c.classList.remove('hotspot-card--pinned'); } document.querySelectorAll('.hotspot.active').forEach((e) => e.classList.remove('active')); }

  function wireRect(el, h) {
    el.addEventListener('pointerenter', (e) => { if (!touch && !pinned) show(h, e.clientX, e.clientY, false); });
    el.addEventListener('pointermove', (e) => { if (!touch && !pinned) place(e.clientX, e.clientY); });
    el.addEventListener('pointerleave', () => { if (!touch) hide(false); });
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      if (pinned === el) { hide(true); return; }
      hide(true); pinned = el; el.classList.add('active'); show(h, e.clientX, e.clientY, true);
    });
  }

  Hs.mount = function () {
    for (const s of P.data.slides || []) {
      const ov = P.stage.overlay(s.id);
      if (ov) for (const h of s.hotspots || []) {
        const r = P.stage.rectEl('hotspot', h.rect); ov.append(r);
        const st = P.stage.frac2stage(h.rect);
        const mark = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        mark.setAttribute('cx', st.x + st.w - 14); mark.setAttribute('cy', st.y + 14); mark.setAttribute('r', 8); mark.setAttribute('class', 'hotspot-mark');
        ov.append(mark); wireRect(r, h);
      }
    }
    P.$$('[data-hotspot]').forEach((el) => {
      const h = { title: el.dataset.hotspot, body_html: el.dataset.body ? P.escape(el.dataset.body).replace(/\n/g, '<br>') : '', links: el.dataset.link ? [{ url: el.dataset.link, label: el.dataset.linkLabel || el.dataset.link }] : [] };
      wireRect(el, h);
    });
    document.addEventListener('click', (e) => { if (!e.target.closest('#hotspot-card')) hide(true); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(true); });
    P.stage.onChange(() => hide(true));
  };
})();
```

- [ ] **Step 6: Smoke in the browser and commit**

Run `micromamba run -n django-nihar-website python manage.py runserver` and open `http://127.0.0.1:8000/presentations/example/`. Expected: title slide visible, arrow keys move, hovering the hotspot box on slide 2 shows the card with a link. (The remaining scripts referenced by the template 404 until Task 11 — the console shows 404s but nothing breaks because each file is self-contained.)
```bash
git add presentations/static/presentations/js tests/presentations/js
git commit -m "feat(presentations): JS toolkit core — stage math, sync client, hotspot popovers"
```

---

### Task 11: JS interaction widgets + page controllers

**Files:**
- Create: `presentations/static/presentations/js/interactions/choice.js`, `numeric.js`, `distribution.js`, `text.js`, `presentations/static/presentations/js/present.js`, `phone.js`, `archive.js`

**Interfaces:**
```js
P.registerInteraction(name, { input(el, config, submit, prior), aggregate(el, config, agg, ctx) })
P.interactions.input(iid, el, submit)      // looks up type from P.data.interactions[iid]
P.interactions.aggregate(iid, el, agg, ctx) // ctx = {revealed:bool, tag:string}
P.widgets.mountShown(slideId, state)        // for a slide: creates/updates .widget boxes at each show rect (stage) or [data-interaction] div (html), fetches aggregate, renders; handles hidden/closed/revealed + slice buttons
```
Aggregate URL: `P.data.urls.aggregate + iid + '/?tag=' + tag`.

- [ ] **Step 1: registry + widgets (put at top of `interactions/choice.js`, since it loads first)**

```js
(function () {
  const P = (window.Presentations = window.Presentations || {});
  const types = {};
  P.registerInteraction = (name, impl) => { types[name] = impl; };
  P.interactions = {
    def: (iid) => (P.data.interactions || {})[iid],
    input(iid, el, submit, prior) { const d = P.interactions.def(iid); types[d.type].input(el, d.config, submit, prior); },
    aggregate(iid, el, agg, ctx) { const d = P.interactions.def(iid); types[d.type].aggregate(el, d.config, agg, ctx); },
  };
  const W = (P.widgets = { tag: {} });
  function box(slide, ref) {
    const iid = ref.id;
    if (slide.kind === 'html') {
      return P.$(`[data-interaction="${CSS.escape(iid)}"]`, P.stage.slideEl(slide.id));
    }
    const host = P.stage.widgets(slide.id); if (!host) return null;
    let el = P.$(`.widget[data-iid="${CSS.escape(iid)}"]`, host);
    if (!el) {
      el = P.el('div', { class: 'widget', 'data-iid': iid }); host.append(el);
      const s = P.stage.frac2stage(ref.rect);
      Object.assign(el.style, { left: (s.x / 19.2) + '%', top: (s.y / 10.8) + '%', width: (s.w / 19.2) + '%', height: (s.h / 10.8) + '%' });
    }
    return el;
  }
  async function render(iid, el, state) {
    el.classList.add('widget'); el.dataset.iid = iid;
    const d = P.interactions.def(iid); if (!d) return;
    if (state === 'hidden') { el.innerHTML = ''; el.style.visibility = 'hidden'; return; }
    el.style.visibility = 'visible';
    const tag = W.tag[iid] || 'all';
    let agg = null;
    try { agg = await P.api.get(P.data.urls.aggregate + encodeURIComponent(iid) + '/?tag=' + encodeURIComponent(tag)); } catch (e) { agg = null; }
    el.innerHTML = '';
    el.append(P.el('h4', { text: d.config.prompt }));
    if (state === 'closed' && P.data.mode !== 'present') { el.append(P.el('div', { class: 'too-small', text: `${agg ? agg.n : '…'} responses — waiting for reveal` })); return; }
    if (state === 'open' && P.data.mode !== 'present') { el.append(P.el('div', { class: 'too-small', text: 'open — answer on your phone' })); return; }
    if (!agg) { el.append(P.el('div', { class: 'too-small', text: 'results not available' })); return; }
    const slice = P.el('div', { class: 'slice' });
    for (const t of ['all', ...(P.data.expertise || [])]) {
      slice.append(P.el('button', { class: 'btn' + (t === tag ? ' on' : ''), text: t, onclick: () => { W.tag[iid] = t; render(iid, el, state); } }));
    }
    el.append(slice);
    const body = P.el('div'); el.append(body);
    if (agg.too_small) { body.append(P.el('div', { class: 'too-small', text: `n = ${agg.n} — too small to show` })); return; }
    P.interactions.aggregate(iid, body, agg, { revealed: state === 'revealed', tag });
    el.append(P.el('div', { class: 'n', text: `n = ${agg.n}` }));
  }
  W.mountShown = function (slideId, states) {
    const slide = (P.data.slides || []).find((s) => s.id === slideId); if (!slide) return;
    for (const ref of slide.show || []) { const el = box(slide, ref); if (el) render(ref.id, el, states[ref.id] || 'hidden'); }
  };
  W.refreshAll = function (states) { P.$$('.widget[data-iid]').forEach((el) => render(el.dataset.iid, el, states[el.dataset.iid] || 'hidden')); };
})();
```

- [ ] **Step 2: choice.js (append to the same file after the registry block)**

```js
Presentations.registerInteraction('choice', {
  input(el, config, submit, prior) {
    const P = Presentations; const grid = P.el('div', { class: 'choice-grid' }); el.append(grid);
    config.options.forEach((o) => {
      const b = P.el('button', { class: 'btn' + (prior && prior.choice === o ? ' picked' : ''), text: o, onclick: () => { grid.querySelectorAll('button').forEach((x) => x.classList.remove('picked')); b.classList.add('picked'); submit({ choice: o }); } });
      grid.append(b);
    });
  },
  aggregate(el, config, agg, ctx) {
    const P = Presentations; const wrap = P.el('div', { class: 'bars' }); el.append(wrap);
    const max = Math.max(1, ...Object.values(agg.counts));
    for (const o of config.options) {
      const c = agg.counts[o] || 0; const pct = agg.n ? Math.round(100 * c / agg.n) : 0;
      const row = P.el('div', { class: 'bar' + (ctx.revealed && config.answer === o ? ' correct' : '') });
      row.append(P.el('b', { text: o }), P.el('span', {}, [Object.assign(P.el('i'), { style: `width:${100 * c / max}%` })]), P.el('span', { text: `${pct}%` }));
      wrap.append(row);
    }
  },
});
```

- [ ] **Step 3: numeric.js**

```js
Presentations.registerInteraction('numeric', {
  input(el, config, submit, prior) {
    const P = Presentations;
    const v = P.el('input', { class: 'num', type: 'number', step: 'any', placeholder: config.unit ? `value (${config.unit})` : 'value', value: prior ? prior.value : '' });
    const e = P.el('input', { class: 'num', type: 'number', step: 'any', min: '0', placeholder: '± uncertainty (optional)', value: prior && prior.err != null ? prior.err : '', style: 'margin-top:.4rem' });
    const b = P.el('button', { class: 'btn btn--primary', text: 'Submit', style: 'margin-top:.5rem', onclick: () => submit({ value: v.value, err: e.value }) });
    el.append(v, e, b);
  },
  aggregate(el, config, agg, ctx) {
    const P = Presentations; const W = 600, H = 140, pad = 40;
    const vals = agg.values; if (!vals.length) { el.append(P.el('div', { class: 'too-small', text: 'no responses' })); return; }
    const all = vals.concat(config.truth != null && ctx.revealed ? [config.truth] : []);
    const f = config.log ? Math.log10 : (x) => x, g = config.log ? (x) => Math.pow(10, x) : (x) => x;
    let lo = Math.min(...all.map(f)), hi = Math.max(...all.map(f)); if (hi === lo) { lo -= 1; hi += 1; }
    const X = (x) => pad + (f(x) - lo) / (hi - lo) * (W - 2 * pad);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.style.width = '100%';
    const add = (tag, a) => { const n = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k, v] of Object.entries(a)) n.setAttribute(k, v); svg.append(n); return n; };
    add('line', { x1: pad, x2: W - pad, y1: H - 30, y2: H - 30, stroke: 'currentColor', 'stroke-opacity': .4 });
    [lo, (lo + hi) / 2, hi].forEach((t) => { const tx = add('text', { x: X(g(t)), y: H - 10, 'text-anchor': 'middle', 'font-size': 12, fill: 'currentColor' }); tx.textContent = Number(g(t).toPrecision(3)); });
    vals.forEach((v, i) => { const err = agg.errs[i]; if (err) add('line', { x1: X(Math.max(v - err, config.log ? v / 10 : v - err)), x2: X(v + err), y1: 50 + (i % 5) * 10, y2: 50 + (i % 5) * 10, stroke: 'var(--accent)', 'stroke-opacity': .35 }); add('circle', { cx: X(v), cy: 50 + (i % 5) * 10, r: 5, fill: 'var(--accent)', 'fill-opacity': .7 }); });
    if (agg.median != null) { add('line', { x1: X(agg.median), x2: X(agg.median), y1: 20, y2: H - 30, stroke: 'var(--fg)', 'stroke-dasharray': '4 3' }); const t = add('text', { x: X(agg.median), y: 14, 'text-anchor': 'middle', 'font-size': 12, fill: 'currentColor' }); t.textContent = 'median ' + Number(agg.median.toPrecision(3)); }
    if (ctx.revealed && config.truth != null) { add('line', { x1: X(config.truth), x2: X(config.truth), y1: 20, y2: H - 30, stroke: 'var(--accent-2, #e9c46a)', 'stroke-width': 3 }); const t = add('text', { x: X(config.truth), y: H - 34, 'text-anchor': 'middle', 'font-size': 12, fill: 'var(--accent-2, #e9c46a)' }); t.textContent = 'true ' + config.truth; }
    el.append(svg);
  },
});
```

- [ ] **Step 4: distribution.js**

```js
Presentations.registerInteraction('distribution', {
  input(el, config, submit, prior) {
    const P = Presentations; const bins = config.axis.bins; const w = prior ? prior.weights.slice() : new Array(bins).fill(0);
    const c = P.el('canvas', { class: 'draw' }); el.append(c);
    const lab = P.el('div', { class: 'n', text: `drag to draw your ${config.axis.label || 'x'} distribution · ${config.axis.min} → ${config.axis.max}` }); el.append(lab);
    const b = P.el('button', { class: 'btn btn--primary', text: 'Submit', style: 'margin-top:.4rem', onclick: () => submit({ weights: w }) }); el.append(b);
    const ctx = c.getContext('2d');
    function draw() {
      c.width = c.clientWidth * devicePixelRatio; c.height = c.clientHeight * devicePixelRatio; ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      const cw = c.clientWidth, ch = c.clientHeight, bw = cw / bins, max = Math.max(1e-9, ...w);
      ctx.clearRect(0, 0, cw, ch); ctx.fillStyle = getComputedStyle(c).getPropertyValue('--accent') || '#37b49f';
      w.forEach((v, i) => { const h = v / max * (ch - 8); ctx.fillRect(i * bw + 1, ch - h, bw - 2, h); });
    }
    let down = false;
    const paint = (e) => { const r = c.getBoundingClientRect(); const i = Math.min(bins - 1, Math.max(0, Math.floor((e.clientX - r.left) / r.width * bins))); w[i] = Math.max(0, 1 - (e.clientY - r.top) / r.height); draw(); };
    c.addEventListener('pointerdown', (e) => { down = true; c.setPointerCapture(e.pointerId); paint(e); });
    c.addEventListener('pointermove', (e) => { if (down) paint(e); });
    c.addEventListener('pointerup', () => { down = false; }); c.addEventListener('pointercancel', () => { down = false; });
    requestAnimationFrame(draw); addEventListener('resize', draw);
  },
  aggregate(el, config, agg, ctx) {
    const P = Presentations; const W = 600, H = 220, pad = 30, bins = config.axis.bins;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.style.width = '100%';
    const add = (tag, a) => { const n = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k, v] of Object.entries(a)) n.setAttribute(k, v); svg.append(n); return n; };
    const max = Math.max(1e-9, ...agg.curves.flat(), ...agg.mean);
    const path = (ws) => ws.map((v, i) => `${i ? 'L' : 'M'}${pad + (i + .5) / bins * (W - 2 * pad)},${H - pad - v / max * (H - 2 * pad)}`).join(' ');
    agg.curves.forEach((ws) => add('path', { d: path(ws), fill: 'none', stroke: 'var(--accent)', 'stroke-opacity': .15, 'stroke-width': 2 }));
    if (agg.n) add('path', { d: path(agg.mean), fill: 'none', stroke: 'var(--accent-2, #e9c46a)', 'stroke-width': 4 });
    add('line', { x1: pad, x2: W - pad, y1: H - pad, y2: H - pad, stroke: 'currentColor', 'stroke-opacity': .4 });
    [agg.edges[0], agg.edges[bins]].forEach((v, k) => { const t = add('text', { x: k ? W - pad : pad, y: H - 8, 'text-anchor': 'middle', 'font-size': 12, fill: 'currentColor' }); t.textContent = v; });
    const lab = add('text', { x: W / 2, y: H - 8, 'text-anchor': 'middle', 'font-size': 12, fill: 'currentColor' }); lab.textContent = config.axis.label || '';
    el.append(svg);
  },
});
```

- [ ] **Step 5: text.js**

```js
Presentations.registerInteraction('text', {
  input(el, config, submit, prior) {
    const P = Presentations;
    const i = P.el('input', { class: 'txt', maxlength: String(config.max_len || 80), placeholder: 'type…', value: prior ? prior.text : '' });
    const b = P.el('button', { class: 'btn btn--primary', text: 'Submit', style: 'margin-top:.5rem', onclick: () => submit({ text: i.value }) });
    i.addEventListener('keydown', (e) => { if (e.key === 'Enter') b.click(); });
    el.append(i, b);
  },
  aggregate(el, config, agg) {
    const P = Presentations; const wrap = P.el('div', { class: 'wordcloud' }); el.append(wrap);
    const entries = Object.entries(agg.counts).sort((a, b) => b[1] - a[1]); const max = entries.length ? entries[0][1] : 1;
    entries.forEach(([w, c], i) => wrap.append(P.el('span', { text: w, style: `font-size:${(0.8 + 2.2 * c / max).toFixed(2)}rem;opacity:${(0.55 + 0.45 * c / max).toFixed(2)};color:var(--accent-${(i % 3) + 1}, var(--accent))` })));
    if (!entries.length) wrap.append(P.el('span', { class: 'too-small', text: 'no words yet' }));
  },
});
```

- [ ] **Step 6: archive.js**

```js
(function () {
  const P = Presentations; const states = {};
  for (const [iid, d] of Object.entries(P.data.interactions || {})) states[iid] = d.state;
  P.stage.keys(); P.stage.swipe(); P.stage.buttons(); P.hotspots.mount();
  P.stage.onChange((id) => { P.widgets.mountShown(id, states); if (P.comments) P.comments.onSlide(id); });
  if (P.comments) P.comments.mount();
  const hash = location.hash.slice(1);
  P.stage.go(hash && P.data.slides.some((s) => s.id === hash) ? hash : 0);
  P.stage.onChange((id) => history.replaceState(null, '', '#' + id));
})();
```

- [ ] **Step 7: phone.js**

```js
(function () {
  const P = Presentations; const U = P.data.urls; let following = true; let live = null; const states = {}; const answered = {};
  const panel = P.$('#ask-panel'), pill = P.$('#follow-pill');
  P.stage.swipe(); P.stage.buttons(); P.hotspots.mount(); if (P.comments) P.comments.mount();
  P.stage.onChange((id, n, o) => { if (o.user) { following = id === live; pill.hidden = following; } P.widgets.mountShown(id, states); if (P.comments) P.comments.onSlide(id); });
  pill.addEventListener('click', () => { following = true; pill.hidden = true; if (live) P.stage.go(live); });
  function renderAsk() {
    const open = Object.entries(states).filter(([, s]) => s === 'open').map(([iid]) => iid);
    panel.hidden = !open.length;
    for (const iid of open) {
      if (P.$(`.ask[data-iid="${CSS.escape(iid)}"]`, panel)) continue;
      const d = P.interactions.def(iid); const box = P.el('div', { class: 'ask', 'data-iid': iid }); panel.append(box);
      box.append(P.el('div', { class: 'prompt', text: d.config.prompt })); const body = P.el('div'); box.append(body); const msg = P.el('div', { class: 'n' }); box.append(msg);
      P.interactions.input(iid, body, async (payload) => {
        const r = await P.api.post(U.respond + encodeURIComponent(iid) + '/', payload);
        msg.textContent = r.status === 200 ? '✓ answered — you can change it while it stays open' : (r.json.error || 'could not submit');
        if (r.status === 200) answered[iid] = payload;
      }, answered[iid]);
    }
    P.$$('.ask', panel).forEach((b) => { if (!open.includes(b.dataset.iid)) b.remove(); });
  }
  P.sync.onState((st) => {
    if (st.locked) { location.href = '/presentations/' + P.data.slug + '/'; return; }
    Object.assign(states, st.interactions || {}); live = st.slide;
    if (following && live && live !== P.stage.current()) P.stage.go(live);
    renderAsk(); P.widgets.refreshAll(states);
    const v = P.$('.slide:not([hidden]) video'); if (v && st.video && st.video.playing === false) v.pause();
  });
  P.stage.go(P.data.session && P.data.session.current ? P.data.session.current : 0);
  P.sync.start(U.state, 1500);
})();
```

- [ ] **Step 8: present.js**

```js
(function () {
  const P = Presentations; const U = P.data.urls; const states = {}; let hideTimer = null;
  for (const [iid, d] of Object.entries(P.data.interactions || {})) states[iid] = d.state;
  const bar = P.$('#present-bar'), chrome = P.$('#deck-chrome'), qr = P.$('#qr-box'), ia = P.$('#present-interactions');
  const STATES = ['hidden', 'open', 'closed', 'revealed'];
  function post(url, body) { return P.api.post(url, body); }
  function iaRow(iid) {
    const row = P.el('span', { class: 'ia', 'data-iid': iid }); row.append(P.el('span', { class: 'id', text: iid }));
    for (const s of STATES) row.append(P.el('button', { class: 'btn' + (states[iid] === s ? ' on' : ''), text: s, onclick: async () => { const r = await post(U.interaction + encodeURIComponent(iid) + '/' + s + '/'); if (r.status === 200) { states[iid] = s; refresh(); } } }));
    return row;
  }
  function refresh() {
    const slide = P.data.slides[P.stage.index()]; ia.innerHTML = '';
    const ids = [...new Set([...(slide.ask || []), ...(slide.show || []).map((r) => r.id), ...(P.$('#all-interactions').value ? [P.$('#all-interactions').value] : [])])];
    ids.forEach((iid) => ia.append(iaRow(iid)));
    P.widgets.mountShown(slide.id, states); P.widgets.refreshAll(states);
  }
  P.$('#all-interactions').addEventListener('change', refresh);
  P.stage.keys(() => { const v = P.$('.slide:not([hidden]) video'); if (v) { v.paused ? v.play() : v.pause(); post(U.video, { playing: !v.paused, t: v.currentTime }); } else P.stage.next({ user: true }); });
  P.stage.buttons(); P.hotspots.mount(); if (P.comments) P.comments.mount();
  P.stage.onChange((id) => { post(U.goto, { slide: id }); refresh(); if (P.comments) P.comments.onSlide(id); });
  P.$('#qr-toggle').addEventListener('click', () => { qr.hidden = !qr.hidden; });
  P.$('#lock-btn').addEventListener('click', async () => {
    const locked = P.$('#lock-btn').textContent === 'Unlock';
    if (!locked && !confirm('Lock this session? Interactions freeze and phones are sent to the archive.')) return;
    const r = await post(locked ? U.unlock : U.lock); if (r.status === 200) location.reload();
  });
  P.$$('video').forEach((v) => { v.addEventListener('play', () => post(U.video, { playing: true, t: v.currentTime })); v.addEventListener('pause', () => post(U.video, { playing: false, t: v.currentTime })); });
  const wake = () => { bar.classList.remove('present-bar--hidden'); chrome.classList.remove('deck-chrome--hidden'); clearTimeout(hideTimer); hideTimer = setTimeout(() => { bar.classList.add('present-bar--hidden'); chrome.classList.add('deck-chrome--hidden'); }, 2000); };
  document.addEventListener('mousemove', wake); wake();
  P.sync.onState((st) => { P.$('#participants').textContent = `${st.participants} joined`; });
  P.sync.start(U.state, 1000);
  P.stage.go(P.data.session && P.data.session.current ? P.data.session.current : 0);
  setInterval(() => { const slide = P.data.slides[P.stage.index()]; if ((slide.show || []).some((r) => states[r.id] === 'open' || states[r.id] === 'closed')) P.widgets.refreshAll(states); }, 2000);
})();
```
Note: `confirm()` here is a real browser dialog on the presenter's own laptop — acceptable; it never runs on phones.

- [ ] **Step 9: Browser smoke test and commit**

Run the dev server, log into `/admin/`, open `/presentations/example/present/` in one window and the QR's `/p/<code>/` URL in a phone-sized window (or your phone on the LAN). Expected: join → mirror follows arrows; on slide 2 click `open` for `q-orbits` → phone shows A/B/C/D; answer; click `revealed` → slide 3 shows bars; slice buttons work.
```bash
git add presentations/static/presentations/js
git commit -m "feat(presentations): interaction widgets and present/phone/archive controllers"
```

---

### Task 12: Comments UI (`comments.js`)

**Files:**
- Create: `presentations/static/presentations/js/comments.js`

**Interfaces:**
```js
P.comments.mount()          // loads /comments/, wires panel, form, box-drawing; polls every 5 s on present/phone
P.comments.onSlide(id)      // re-renders list for the slide, redraws overlay boxes, marks [data-anchor] elements
```

- [ ] **Step 1: Implement**

```js
(function () {
  const P = Presentations; const C = (P.comments = {}); let all = []; let drawing = null; let pendingAnchor = null;
  const panel = () => P.$('#comments-panel'), list = () => P.$('#comment-list'), form = () => P.$('#comment-form');
  const bySlide = (id) => all.filter((c) => c.slide === id);
  async function load() { try { all = (await P.api.get(P.data.urls.comments)).comments; } catch (e) { all = []; } render(); }
  function render() {
    const id = P.stage.current(); const items = bySlide(id); const l = list(); if (!l) return; l.innerHTML = '';
    P.$('#comment-count').textContent = String(all.length);
    items.forEach((c) => { const d = P.el('div', { class: 'comment', 'data-id': c.id }); d.append(P.el('span', { class: 'num', text: c.anchor ? `${c.num}` : '' }), P.el('span', { class: 'who', text: c.author }), P.el('div', { html: c.html })); l.append(d); });
    if (!items.length) l.append(P.el('div', { class: 'too-small', text: 'No questions on this slide yet.' }));
    drawBoxes(id); markAnchors(id);
  }
  function drawBoxes(id) {
    const ov = P.stage.overlay(id); if (!ov) return; P.$$('.comment-box,.comment-num', ov).forEach((e) => e.remove());
    bySlide(id).filter((c) => c.anchor && c.anchor.rect).forEach((c) => {
      const r = P.stage.rectEl('comment-box', c.anchor.rect); ov.append(r); const s = P.stage.frac2stage(c.anchor.rect);
      ov.append(P.stage.textEl(s.x + 10, s.y + 38, String(c.num), 'comment-num'));
      r.addEventListener('click', () => { open(true); const el = P.$(`.comment[data-id="${c.id}"]`); if (el) { el.scrollIntoView({ block: 'center' }); el.style.background = '#fff2'; setTimeout(() => (el.style.background = ''), 1200); } });
    });
  }
  function markAnchors(id) {
    const s = P.stage.slideEl(id); if (!s) return;
    P.$$('[data-anchor]', s).forEach((el) => {
      let m = P.$('.anchor-mark', el); if (!m) { m = P.el('span', { class: 'anchor-mark' }); el.append(m); m.addEventListener('click', () => { pendingAnchor = { anchor: el.dataset.anchor }; P.$('#comment-target').textContent = 'On: ' + el.dataset.anchor; open(true); }); }
      const n = bySlide(id).filter((c) => c.anchor && c.anchor.anchor === el.dataset.anchor).length; m.textContent = '💬 ' + (n || '');
    });
  }
  function open(v) { panel().classList.toggle('open', v); }
  function startDraw() {
    const id = P.stage.current(); const ov = P.stage.overlay(id); if (!ov) { alertText('This slide is a page — use the 💬 marks next to sections.'); return; }
    const inner = ov.parentElement; ov.style.pointerEvents = 'all'; ov.style.cursor = 'crosshair'; let start = null, rect = null;
    const move = (e) => { if (!start) return; const [x, y] = P.stage.px2frac(inner, e.clientX, e.clientY); const r = [Math.min(start[0], x), Math.min(start[1], y), Math.abs(x - start[0]), Math.abs(y - start[1])]; if (rect) rect.remove(); rect = P.stage.rectEl('comment-box active', r); ov.append(rect); drawing = r; };
    const down = (e) => { start = P.stage.px2frac(inner, e.clientX, e.clientY); e.preventDefault(); };
    const up = (e) => {
      if (!start) return; move(e); let r = drawing; if (!r || r[2] < 0.02 || r[3] < 0.02) { const [x, y] = start; r = [Math.max(0, x - 0.1), Math.max(0, y - 0.075), 0.2, 0.15]; if (rect) rect.remove(); rect = P.stage.rectEl('comment-box active', r); ov.append(rect); }
      pendingAnchor = { rect: r.map((v) => Math.round(v * 1000) / 1000) }; P.$('#comment-target').textContent = 'On the boxed region'; start = null;
      ov.style.pointerEvents = ''; ov.style.cursor = ''; ov.removeEventListener('pointerdown', down); ov.removeEventListener('pointermove', move); ov.removeEventListener('pointerup', up); open(true); P.$('textarea', form()).focus();
    };
    ov.addEventListener('pointerdown', down); ov.addEventListener('pointermove', move); ov.addEventListener('pointerup', up); open(false);
  }
  function alertText(t) { const l = list(); l.prepend(P.el('div', { class: 'too-small', text: t })); }
  C.onSlide = () => { pendingAnchor = null; const t = P.$('#comment-target'); if (t) t.textContent = 'On this slide'; render(); };
  C.mount = function () {
    if (!panel()) return; load();
    P.$('#comment-toggle').addEventListener('click', () => open(!panel().classList.contains('open')));
    P.$('#comment-box-btn').addEventListener('click', startDraw);
    form().addEventListener('submit', async (e) => {
      e.preventDefault(); const f = form(); const body = f.body.value.trim(); if (!body) return;
      const r = await P.api.post(P.data.urls.comment, { slide: P.stage.current(), anchor: pendingAnchor, body, author_name: f.author_name.value, website: f.website.value });
      if (r.status === 201) { f.body.value = ''; pendingAnchor = null; P.$('#comment-target').textContent = 'On this slide'; P.$$('.comment-box.active').forEach((x) => x.remove()); await load(); }
      else alertText(r.json.error || 'could not post');
    });
    if (P.data.mode !== 'archive') setInterval(load, 5000);
  };
})();
```

- [ ] **Step 2: Browser smoke test and commit**

On `/presentations/example/`: click 💬, "point at something", drag a box on slide 2, type, Post → box appears with ①, list shows it; reload → persists. In admin, hide it → gone after reload.
```bash
git add presentations/static/presentations/js/comments.js
git commit -m "feat(presentations): comment panel with region boxes and html anchors"
```

---

### Task 13: Tooling — SVG sanitizer, theme derivation, `newdeck`

**Files:**
- Create: `presentations/sanitize.py`, `presentations/theme.py`, `presentations/management/commands/newdeck.py`
- Test: `tests/presentations/test_tools.py`

**Interfaces:**
```python
def sanitize_svg(text: str) -> str          # drops <script>, <foreignObject>, on* attrs, non-#/data: hrefs; keeps everything else; returns serialized svg
def derive_theme(svg_paths: list[Path]) -> dict   # {'bg','fg','accents':[≤3],'font_display','font_body'} always complete
manage.py newdeck <slug> --title T [--from DIR] [--date D]
```

- [ ] **Step 1: Write failing tests**

`tests/presentations/test_tools.py`:
```python
from pathlib import Path
import pytest
import yaml
from django.core.management import call_command

from presentations.sanitize import sanitize_svg
from presentations.theme import derive_theme

DIRTY = '''<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">
<script>alert(1)</script><foreignObject><div>x</div></foreignObject>
<rect width="5" height="5" onclick="evil()" fill="#123456"/>
<a xlink:href="https://evil.example"><text>t</text></a>
<use xlink:href="#ok"/><image href="data:image/png;base64,AAAA"/>
</svg>'''


def test_sanitize_svg():
    out = sanitize_svg(DIRTY)
    assert '<script' not in out and 'foreignObject' not in out and 'onclick' not in out
    assert 'evil.example' not in out and 'href="#ok"' in out and 'data:image/png' in out
    assert 'fill="#123456"' in out and 'viewBox="0 0 10 10"' in out
    assert out.count('<svg') == 1


THEMED = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">
<rect width="1920" height="1080" fill="#101820"/>
<rect x="0" y="0" width="600" height="400" fill="#37b49f"/>
<circle cx="900" cy="500" r="100" fill="#e9c46a"/>
<text fill="#f4f1ea" font-family="Montserrat" x="1" y="1">Hi</text>
<text fill="#f4f1ea" style="font-family: 'Inter', sans-serif" x="1" y="2">there</text>
<path d="M0 0" stroke="#e76f51" fill="none"/>
</svg>'''


def test_derive_theme(tmp_path):
    p = tmp_path / 'a.svg'; p.write_text(THEMED)
    t = derive_theme([p])
    assert t['bg'] == '#101820' and t['fg'] == '#f4f1ea'
    assert t['accents'][:2] == ['#37b49f', '#e9c46a'] and '#e76f51' in t['accents']
    assert t['font_display'] == 'Montserrat' and t['font_body'] == 'Inter'


def test_derive_theme_defaults_when_empty(tmp_path):
    p = tmp_path / 'e.svg'; p.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    t = derive_theme([p])
    assert set(t) == {'bg', 'fg', 'accents', 'font_display', 'font_body'} and t['accents']


def test_newdeck_from_dir(tmp_path, settings):
    settings.PRESENTATIONS_DECKS_DIR = tmp_path / 'decks'
    (tmp_path / 'decks' / '_template' / 'slides').mkdir(parents=True)
    (tmp_path / 'decks' / '_template' / 'static').mkdir()
    (tmp_path / 'decks' / '_template' / 'deck.yaml').write_text('title: x\n')
    src = tmp_path / 'export'; src.mkdir()
    (src / '02-Orbits.svg').write_text(DIRTY)
    (src / '01 Title.svg').write_text(THEMED)
    call_command('newdeck', 'my-talk', '--title', 'My Talk', '--from', str(src), '--date', '2026-10-01')
    d = tmp_path / 'decks' / 'my-talk'
    y = yaml.safe_load((d / 'deck.yaml').read_text())
    assert y['title'] == 'My Talk' and y['date'] == '2026-10-01'
    assert [s['id'] for s in y['slides']] == ['title', 'orbits']
    assert [s['svg'] for s in y['slides']] == ['slides/01-title.svg', 'slides/02-orbits.svg']
    assert y['theme']['bg'] == '#101820'
    assert '<script' not in (d / 'slides' / '02-orbits.svg').read_text()
    assert (d / 'static').is_dir()
    from presentations.schema import load_deck
    assert load_deck(d).title == 'My Talk'
    with pytest.raises(SystemExit):
        call_command('newdeck', 'my-talk', '--title', 'dup')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_tools.py -q` → ImportError.

- [ ] **Step 3: sanitize.py**

```python
import re
import xml.etree.ElementTree as ET

SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'
_BAD_TAGS = {'script', 'foreignObject', 'iframe', 'object', 'embed'}
_HREF_KEYS = ('href', f'{{{XLINK_NS}}}href')
_XML_DECL = re.compile(r'<\?xml[^>]*\?>\s*')


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _safe_href(v):
    v = (v or '').strip()
    return v.startswith('#') or v.lower().startswith('data:')


def sanitize_svg(text):
    ET.register_namespace('', SVG_NS)
    ET.register_namespace('xlink', XLINK_NS)
    root = ET.fromstring(_XML_DECL.sub('', text))
    for parent in list(root.iter()):
        for child in list(parent):
            if _local(child.tag) in _BAD_TAGS:
                parent.remove(child)
    if _local(root.tag) in _BAD_TAGS:
        raise ValueError('root element not allowed')
    for el in root.iter():
        for k in list(el.attrib):
            if _local(k).lower().startswith('on'):
                del el.attrib[k]
            elif k in _HREF_KEYS and not _safe_href(el.attrib[k]):
                del el.attrib[k]
            elif _local(k) == 'style' and 'url(' in el.attrib[k] and 'url(#' not in el.attrib[k]:
                del el.attrib[k]
    return ET.tostring(root, encoding='unicode')
```

- [ ] **Step 4: theme.py**

```python
"""Guess a palette + fonts from SVG exports. Heuristic; newdeck writes the result into deck.yaml for editing."""
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from .schema import DEFAULT_THEME

_HEX = re.compile(r'#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b')
_STYLE_FILL = re.compile(r'fill\s*:\s*([^;]+)')
_STYLE_FONT = re.compile(r"font-family\s*:\s*([^;]+)")


def _norm(c):
    m = _HEX.match((c or '').strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    return '#' + h.lower()


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))))


def _lum(h):
    r, g, b = (v / 255 for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _num(v, default=0.0):
    m = re.match(r'[-\d.]+', str(v or ''))
    try:
        return float(m.group(0)) if m else default
    except ValueError:
        return default


def _area(el):
    t = el.tag.rsplit('}', 1)[-1]
    if t == 'rect':
        return _num(el.get('width')) * _num(el.get('height'))
    if t == 'circle':
        return math.pi * _num(el.get('r')) ** 2
    if t == 'ellipse':
        return math.pi * _num(el.get('rx')) * _num(el.get('ry'))
    return 1.0


def _fill_of(el):
    f = el.get('fill')
    if not f:
        m = _STYLE_FILL.search(el.get('style') or '')
        f = m.group(1) if m else None
    return _norm(f)


def _font_of(el):
    f = el.get('font-family')
    if not f:
        m = _STYLE_FONT.search(el.get('style') or '')
        f = m.group(1) if m else None
    if not f:
        return None
    return f.split(',')[0].strip().strip('\'"') or None


def derive_theme(svg_paths):
    area = Counter()
    text_fill = Counter()
    fonts = Counter()
    for p in svg_paths:
        try:
            root = ET.fromstring(Path(p).read_text(encoding='utf-8'))
        except ET.ParseError:
            continue
        for el in root.iter():
            tag = el.tag.rsplit('}', 1)[-1]
            c = _fill_of(el)
            if c and c != 'none':
                area[c] += _area(el)
                if tag in ('text', 'tspan'):
                    text_fill[c] += 1
            s = _norm(el.get('stroke'))
            if s:
                area[s] += 1.0
            f = _font_of(el)
            if f and tag in ('text', 'tspan'):
                fonts[f] += 1
    theme = dict(DEFAULT_THEME)
    if not area:
        return theme
    bg = area.most_common(1)[0][0]
    if text_fill:
        fg = text_fill.most_common(1)[0][0]
    else:
        cands = [c for c, _ in area.most_common(8) if c != bg]
        fg = max(cands, key=lambda c: abs(_lum(c) - _lum(bg))) if cands else DEFAULT_THEME['fg']
    accents = []
    for c, _ in area.most_common():
        if c in (bg, fg) or any(_dist(c, a) < 40 for a in accents) or _dist(c, bg) < 40 or _dist(c, fg) < 40:
            continue
        accents.append(c)
        if len(accents) == 3:
            break
    theme.update({'bg': bg, 'fg': fg, 'accents': accents or list(DEFAULT_THEME['accents'])})
    ranked = [f for f, _ in fonts.most_common()]
    if ranked:
        theme['font_display'] = ranked[0]
        theme['font_body'] = ranked[1] if len(ranked) > 1 else ranked[0]
    return theme
```

- [ ] **Step 5: newdeck.py**

```python
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from presentations import registry
from presentations.sanitize import sanitize_svg
from presentations.theme import derive_theme

_VIDEO = {'.mp4', '.webm'}


def slug_from_filename(name):
    stem = Path(name).stem
    stem = re.sub(r'^\d+[\s_-]*', '', stem)          # drop leading number
    s = re.sub(r'[^a-z0-9]+', '-', stem.lower()).strip('-')
    return s or 'slide'


class Command(BaseCommand):
    help = 'Scaffold presentations/decks/<slug>/ (optionally from a folder of SVG/MP4 exports)'

    def add_arguments(self, parser):
        parser.add_argument('slug')
        parser.add_argument('--title', required=True)
        parser.add_argument('--from', dest='src', default=None)
        parser.add_argument('--date', default='2026-01-01')

    def handle(self, slug, title, src, date, **opts):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', slug):
            raise CommandError('slug must be lowercase letters, digits and dashes')
        root = registry.decks_dir()
        dest = root / slug
        if dest.exists():
            self.stderr.write(f'{dest} already exists')
            sys.exit(1)
        template = root / '_template'
        shutil.copytree(template, dest)
        (dest / 'slides').mkdir(exist_ok=True)
        (dest / 'static').mkdir(exist_ok=True)

        slides, used, svgs = [], set(), []
        if src:
            files = sorted(Path(src).iterdir(), key=lambda p: p.name.lower())
            n = 0
            for f in files:
                ext = f.suffix.lower()
                if ext not in {'.svg'} | _VIDEO:
                    continue
                n += 1
                sid = slug_from_filename(f.name)
                base = sid
                k = 2
                while sid in used:
                    sid = f'{base}-{k}'
                    k += 1
                used.add(sid)
                out = dest / 'slides' / f'{n:02d}-{sid}{ext}'
                if ext == '.svg':
                    out.write_text(sanitize_svg(f.read_text(encoding='utf-8')), encoding='utf-8')
                    svgs.append(out)
                    slides.append({'id': sid, 'svg': f'slides/{out.name}'})
                else:
                    shutil.copy2(f, out)
                    entry = {'id': sid, 'video': f'slides/{out.name}'}
                    poster = out.with_suffix('.jpg')
                    if shutil.which('ffmpeg'):
                        r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(out), '-frames:v', '1', str(poster)])
                        if r.returncode == 0 and poster.exists():
                            entry['poster'] = f'slides/{poster.name}'
                    slides.append(entry)
        theme = derive_theme(svgs) if svgs else None

        deck = {
            'title': title, 'date': date, 'subtitle': '', 'transition': 'fade',
            'expertise': ['theory', 'data analysis', 'instrumentation', 'not a physicist'],
        }
        if theme:
            deck['theme'] = theme
        deck['interactions'] = []
        deck['slides'] = slides
        header = (dest / 'deck.yaml').read_text() if (dest / 'deck.yaml').exists() else ''
        comments = '\n'.join(l for l in header.splitlines() if l.startswith('#'))
        body = yaml.safe_dump(deck, sort_keys=False, allow_unicode=True)
        (dest / 'deck.yaml').write_text(comments + '\n' + body + _EXAMPLES, encoding='utf-8')
        registry.clear_cache()
        self.stdout.write(f'created {dest} with {len(slides)} slides; edit deck.yaml, then `manage.py checkdecks`')


_EXAMPLES = '''
# --- examples (uncomment and adapt) ---
#interactions:
#  - id: q-example
#    type: choice          # choice | numeric | distribution | text
#    prompt: Which one?
#    options: [A, B, C]
#    answer: B
#slides:
#  - id: orbits
#    svg: slides/02-orbits.svg
#    hotspots:
#      - rect: [0.1, 0.1, 0.3, 0.2]
#        title: A thing
#        body: "Markdown **body**"
#        links: [{label: "arXiv", url: "https://arxiv.org/abs/..."}]
#    ask: [q-example]
#    show: [{id: q-example, rect: [0.5, 0.6, 0.45, 0.35]}]
#  - id: page
#    html: 03-page.html
#    underlay: slides/03-frame.svg
'''
```

- [ ] **Step 6: Run tests, commit**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q` → all pass.
```bash
git add presentations tests/presentations
git commit -m "feat(presentations): svg sanitizer, theme derivation, newdeck scaffolder"
```

---

### Task 14: Example deck, end-to-end flow test, ops, docs

**Files:**
- Modify: `presentations/decks/example/deck.yaml`; create `presentations/decks/example/04-prior.svg`… (see below), `presentations/decks/example/05-posterior.html`, `presentations/decks/example/static/posterior.json`, `presentations/decks/example/static/posterior.js`, `presentations/decks/example/slides/07-outro.mp4` (+ `.jpg`)
- Modify: `deploy/update.sh`, `CLAUDE.md`
- Test: `tests/presentations/test_example_deck.py`, `tests/presentations/test_flow.py`

- [ ] **Step 1: Fill out the example deck**

Final `presentations/decks/example/deck.yaml`:
```yaml
title: Example deck
date: 2026-08-25
subtitle: engine reference deck — one of everything
transition: fade
expertise: [theory, data analysis, instrumentation, not a physicist]
theme:
  bg: "#1f2429"
  fg: "#f4f1ea"
  accents: ["#37b49f", "#e9c46a", "#e76f51"]
  font_display: "Montserrat"
  font_body: "Inter"

interactions:
  - id: q-orbits
    type: choice
    prompt: Which orbit is eccentric?
    options: [A, B, C, D]
    answer: B
  - id: q-prior
    type: distribution
    prompt: Your prior on e at 10 Hz
    axis: {min: 0, max: 1, bins: 20, label: "e"}
  - id: q-rate
    type: numeric
    prompt: BBH merger rate (Gpc⁻³ yr⁻¹)
    log: true
    truth: 23.9
  - id: q-word
    type: text
    prompt: One word for eccentric orbits
    max_len: 30

slides:
  - id: title
    svg: slides/01-title.svg
  - id: orbits
    svg: slides/02-orbits.svg
    hotspots:
      - rect: [0.55, 0.15, 0.35, 0.4]
        title: Orbit B
        body: "This one has **e ≈ 0.3** at 10 Hz. Notice the precessing periapsis."
        links: [{label: "arXiv:2401.01234", url: "https://arxiv.org/abs/2401.01234"}]
      - rect: [0.05, 0.6, 0.4, 0.3]
        title: Why it matters
        body: "Eccentricity is a fingerprint of dynamical formation."
    ask: [q-orbits]
  - id: orbits-results
    svg: slides/03-results.svg
    show:
      - {id: q-orbits, rect: [0.1, 0.25, 0.8, 0.65]}
  - id: prior
    svg: slides/04-prior.svg
    ask: [q-prior]
    show:
      - {id: q-prior, rect: [0.1, 0.3, 0.8, 0.6]}
  - id: posterior
    html: 05-posterior.html
    underlay: slides/05-frame.svg
    ask: [q-rate]
    show: [{id: q-rate}]
  - id: words
    svg: slides/06-words.svg
    ask: [q-word]
    show:
      - {id: q-word, rect: [0.05, 0.25, 0.9, 0.65]}
  - id: outro
    video: slides/07-outro.mp4
    poster: slides/07-outro.jpg
```

Placeholder SVGs `04-prior.svg`, `05-frame.svg`, `06-words.svg`: same template as Task 4 with titles "Your prior on e", "" (frame: just the bg rect plus a thin `<rect x="60" y="60" width="1800" height="960" fill="none" stroke="#37b49f" stroke-width="6" rx="24"/>`), "One word".

Video: generate a 4-second test clip and poster (both tracked via LFS per `.gitattributes`):
```bash
ffmpeg -y -f lavfi -i "color=c=0x1f2429:s=1280x720:d=4" -vf "drawtext=text='Thanks':fontcolor=0xf4f1ea:fontsize=96:x=(w-text_w)/2:y=(h-text_h)/2" -pix_fmt yuv420p presentations/decks/example/slides/07-outro.mp4
ffmpeg -y -i presentations/decks/example/slides/07-outro.mp4 -frames:v 1 presentations/decks/example/slides/07-outro.jpg
```
(If `drawtext` is unavailable in this ffmpeg build, drop the `-vf` flag — a plain colour clip is fine.)

`presentations/decks/example/static/posterior.json`:
```json
{"e": [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4],
 "p": [0.02, 0.08, 0.2, 0.3, 0.22, 0.11, 0.05, 0.015, 0.005]}
```

`presentations/decks/example/05-posterior.html`:
```django
{% extends "presentations/slide_base.html" %}
{% block slide %}
<h1>The posterior on <span data-hotspot="Eccentricity" data-body="Orbital eccentricity measured at a reference frequency of 10 Hz." data-link="https://arxiv.org/abs/2401.01234">e</span></h1>
<p>This is an <em>html</em> slide: it scrolls, it can run anything, and it inherits the deck theme. Drag the slider to change the smoothing.</p>
<section data-anchor="posterior-plot" style="margin:1rem 0">
  <div id="posterior-plot" style="height:360px"></div>
  <label>Smoothing <input id="smooth" type="range" min="0" max="3" step="1" value="0"></label>
</section>
<section data-anchor="rate-question">
  <h3>How many BBH mergers per Gpc³ per year?</h3>
  <div data-interaction="q-rate"></div>
</section>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<script src="{{ deck_static }}posterior.js" defer></script>
{% endblock %}
```

`presentations/decks/example/static/posterior.js`:
```js
(async function () {
  const data = await (await fetch('/static/decks/example/posterior.json')).json();
  const css = getComputedStyle(document.documentElement);
  const accent = css.getPropertyValue('--accent').trim() || '#37b49f';
  const fg = css.getPropertyValue('--fg').trim() || '#eee';
  function smooth(y, k) { if (!k) return y; const out = y.map((_, i) => { let s = 0, n = 0; for (let j = i - k; j <= i + k; j++) if (y[j] != null) { s += y[j]; n++; } return s / n; }); return out; }
  function draw() {
    const k = Number(document.getElementById('smooth').value);
    Plotly.react('posterior-plot', [{ x: data.e, y: smooth(data.p, k), type: 'scatter', fill: 'tozeroy', line: { color: accent } }],
      { paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: fg }, margin: { t: 10, r: 10 }, xaxis: { title: 'e' }, yaxis: { title: 'p(e)' } }, { displayModeBar: false, responsive: true });
  }
  document.getElementById('smooth').addEventListener('input', draw);
  draw();
})();
```

- [ ] **Step 2: Example-deck and end-to-end tests**

`tests/presentations/test_example_deck.py`:
```python
from pathlib import Path
from django.core.management import call_command
from presentations.schema import load_deck
from presentations import interactions

ROOT = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'example'


def test_example_deck_is_valid():
    deck = load_deck(ROOT, interaction_validator=interactions.validate)
    assert {s.kind for s in deck.slides} == {'svg', 'html', 'video'}
    assert {i.type for i in deck.interactions} == {'choice', 'numeric', 'distribution', 'text'}
    assert deck.warnings == []
    asked = {a for s in deck.slides for a in s.ask}
    shown = {r.id for s in deck.slides for r in s.show}
    assert 'q-orbits' in asked and 'q-orbits' in shown
    assert any(r.id == 'q-orbits' for s in deck.slides if s.id == 'orbits-results' for r in s.show)


def test_checkdecks_passes_on_repo(capsys):
    call_command('checkdecks')
    assert 'example: ok' in capsys.readouterr().out
```

`tests/presentations/test_flow.py`:
```python
import json
import pytest
from django.test import Client
from presentations import registry
from presentations.models import Session, Comment

pytestmark = pytest.mark.django_db


def test_full_session_flow(staff_client, settings):
    registry.clear_cache()
    # 1. presenter opens the deck → session exists, QR points at /p/<code>/
    page = staff_client.get('/presentations/example/present/').content.decode()
    s = Session.open_for('example'); code = s.join_code
    assert f'/p/{code}/' in page
    # 2. two phones join with different tags
    phones = []
    for tag, name in [('theory', 'Ana'), ('data analysis', 'Bo'), ('theory', 'Cy')]:
        c = Client(); r = c.post(f'/p/{code}/join/', {'expertise_tag': tag, 'display_name': name})
        assert r.status_code == 302; phones.append(c)
    assert staff_client.get('/presentations/example/present/state/').json()['participants'] == 3
    # 3. presenter goes to 'orbits', opens q-orbits; phones see it open and answer
    staff_client.post('/presentations/example/present/goto/', data=json.dumps({'slide': 'orbits'}), content_type='application/json')
    staff_client.post('/presentations/example/present/interaction/q-orbits/open/')
    st = phones[0].get(f'/p/{code}/state/').json()
    assert st['slide'] == 'orbits' and st['interactions']['q-orbits'] == 'open'
    for c, ch in zip(phones, ['B', 'A', 'B']):
        assert c.post(f'/p/{code}/respond/q-orbits/', data=json.dumps({'choice': ch}), content_type='application/json').status_code == 200
    # 4. distribution + numeric + text round trip
    staff_client.post('/presentations/example/present/interaction/q-prior/open/')
    assert phones[0].post(f'/p/{code}/respond/q-prior/', data=json.dumps({'weights': [1] * 20}), content_type='application/json').status_code == 200
    staff_client.post('/presentations/example/present/interaction/q-rate/open/')
    assert phones[0].post(f'/p/{code}/respond/q-rate/', data=json.dumps({'value': 20, 'err': 5}), content_type='application/json').status_code == 200
    staff_client.post('/presentations/example/present/interaction/q-word/open/')
    assert phones[1].post(f'/p/{code}/respond/q-word/', data=json.dumps({'text': 'chaotic'}), content_type='application/json').status_code == 200
    # 5. reveal on the results slide; slice by expertise
    staff_client.post('/presentations/example/present/goto/', data=json.dumps({'slide': 'orbits-results'}), content_type='application/json')
    staff_client.post('/presentations/example/present/interaction/q-orbits/revealed/')
    agg = phones[0].get(f'/p/{code}/aggregate/q-orbits/?tag=all').json()
    assert agg['counts'] == {'A': 1, 'B': 2, 'C': 0, 'D': 0}
    # 6. a phone comment on a region while live
    r = phones[2].post('/presentations/example/comment/', data=json.dumps({'slide': 'orbits', 'anchor': {'rect': [.5, .1, .3, .3]}, 'body': 'is B precessing?'}), content_type='application/json')
    assert r.status_code == 201 and r.json()['author'] == 'Cy'
    # 7. lock → phones bounce to archive; archive shows frozen aggregates; never-opened stays hidden
    staff_client.post('/presentations/example/present/lock/')
    assert phones[0].get(f'/p/{code}/').status_code == 302
    arch = phones[0].get('/presentations/example/').content.decode()
    data = json.loads(arch.split('id="deck-data" type="application/json">')[1].split('</script>')[0])
    assert data['session']['locked'] and data['interactions']['q-orbits']['state'] == 'revealed'
    assert data['interactions']['q-prior']['state'] == 'revealed'
    a = phones[0].get('/presentations/example/aggregate/q-orbits/?tag=theory').json()
    assert a['n'] == 2 and a['counts']['B'] == 2
    assert phones[0].get('/presentations/example/aggregate/q-orbits/?tag=data%20analysis').json()['too_small']
    # 8. comments persist and later visitors can add more
    listed = Client().get('/presentations/example/comments/').json()['comments']
    assert len(listed) == 1 and listed[0]['slide'] == 'orbits'
    assert Client().post('/presentations/example/comment/', data=json.dumps({'slide': 'posterior', 'anchor': {'anchor': 'posterior-plot'}, 'body': 'nice'}), content_type='application/json').status_code == 201
    assert Comment.visible.count() == 2
```

- [ ] **Step 3: Ops + docs**

`deploy/update.sh` — before "Running migrations...":
```bash
echo "Backing up database..."
mkdir -p "${PROJECT_DIR}/backups"
cp "${PROJECT_DIR}/db.sqlite3" "${PROJECT_DIR}/backups/db-$(date +%F-%H%M).sqlite3"
ls -1t "${PROJECT_DIR}/backups"/db-*.sqlite3 | tail -n +15 | xargs -r rm --
```
Add `backups/` to `.gitignore`.

`CLAUDE.md` — add under Django Apps:
```
- **presentations**: interactive, audience-synced talks. Engine in `presentations/`; each talk is a folder `presentations/decks/<slug>/` with a `deck.yaml` (see `decks/_template/deck.yaml` and `decks/example/`). Scaffold with `python manage.py newdeck <slug> --title "…" --from <svg-export-dir>`; validate with `python manage.py checkdecks`. Spec: `docs/superpowers/specs/2026-08-25-interactive-presentations-design.md`.
```

- [ ] **Step 4: Run the whole suite, collectstatic dry-run, browser pass**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q` → all pass.
Run: `micromamba run -n django-nihar-website python manage.py collectstatic --noinput --dry-run | grep decks/example | head` → lists `decks/example/posterior.js`, `decks/example/slides/07-outro.mp4`.
Browser: walk `/presentations/example/present/` through every slide with a phone joined; check the html slide's Plotly renders, `q-rate` aggregate mounts into the page, the video plays on Space, lock sends the phone to the archive.

- [ ] **Step 5: Commit**

```bash
git add presentations deploy/update.sh CLAUDE.md .gitignore tests/presentations
git commit -m "feat(presentations): complete example deck, end-to-end flow test, db backup on deploy"
```

---

## Self-review notes

- Spec §5 validation rules → Task 2; §6 slide kinds → Task 5; §7 overlay → Tasks 5/10/12; §8 lifecycle/plugins/slicing → Tasks 3/6/7/11; §9 sync → Tasks 6/7/10; §10 surfaces → Tasks 5/6/7; §11 model → Task 1; §12 identity/moderation → Tasks 7/9/13; §13 theme → Task 13; §14 newdeck/checkdecks → Tasks 4/13; §15 navbar → Task 4; §16 ops → Tasks 4 (.gitattributes), 14; §17 tests → each task; §18 example deck → Tasks 4/14.
- Known simplification vs spec §9: live state carries `interactions: {id: state}` (a dict) rather than a single `interaction` object, because several may be open at once (spec §8).
