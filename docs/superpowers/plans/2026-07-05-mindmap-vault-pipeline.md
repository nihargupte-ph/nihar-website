# Mindmap → Vault Pipeline + Website Search Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Concepts-app SVG mindmaps into an Obsidian vault of wikilinked concept notes plus a website search/panel layer, driven by one re-runnable incremental script.

**Architecture:** A geometry-first Python pipeline (`scripts/mindmap_vault/`) parses SVG strokes directly, classifies hand-drawn boxes and arrows deterministically, renders per-box PNG crops with PIL, OCRs handwriting via the Claude API, and emits vault markdown + a JSON index. The existing Django mindmap viewer gains a search bar, bbox overlays, and a concept side panel that consume the JSON index client-side.

**Tech Stack:** Python 3.11 (micromamba env `django-nihar-website`), PIL, `anthropic` SDK, pytest; Django 5 template + vanilla JS + @panzoom/panzoom + KaTeX (CDN).

**Spec:** `docs/superpowers/specs/2026-07-05-mindmap-vault-pipeline-design.md`

## Global Constraints

- All Python runs via `micromamba run -n django-nihar-website python …` / `… pytest`.
- Vault output root: `/home/n/Documents/vault/classic_research`; existing contents archived once to `/home/n/Documents/vault/classic_research_v1_backup` before first write.
- OCR model: `claude-sonnet-5` (vision), env var `ANTHROPIC_API_KEY`; OCR must be injectable so tests never hit the network.
- Notes stay faithful: verbatim transcription; model additions only in a `*context:*` line ≤1 sentence.
- Note filenames keyed by stable box id, never renamed by title changes.
- Coordinates everywhere are SVG viewBox units (pt); JSON index bboxes are `[x0, y0, x1, y1]`.
- Website degrades to the current viewer when the index JSON is missing (client-side fetch failure → hide new UI).
- SVG facts (verified): every stroke is `<path id="STROKE_<uuid>">` with only `M`/`L`/`Q` absolute commands, or `<circle id="STROKE_…">` dots; images are `<g id="IMAGE_…" transform="matrix(…)">` wrapping `<use xlink:href="#<def>">`, defs hold base64 PNGs. cs-stat.svg: 77461 paths + 4069 circles, viewBox `-5725.477 -3022.085 11890.705 10977.893`.
- Frequent commits; message prefixes `feat:` / `test:` / `chore:`.

## File Structure

```
scripts/
├── __init__.py
└── mindmap_vault/
    ├── __init__.py
    ├── config.py        # every tunable threshold, one place
    ├── model.py         # Stroke, ImageRef, Box, Edge, OcrResult dataclasses
    ├── geom.py          # bbox/polyline primitives (pure functions)
    ├── parse.py         # SVG text → strokes/images/viewbox; base64 loader
    ├── boxes.py         # box classification (single- and multi-stroke)
    ├── arrows.py        # connector/arrowhead detection → edges + review list
    ├── bind.py          # remaining strokes/images → owning boxes
    ├── render.py        # PIL crop per box
    ├── ocr.py           # Claude API wrapper + Fake for tests
    ├── manifest.py      # stable ids, incremental reconcile
    ├── emit.py          # vault notes/MOC/index.md/JSON index/assets
    └── update.py        # CLI orchestrator
tests/
├── conftest.py          # sys.path + synthetic SVG fixture
└── mindmap_vault/
    ├── test_geom.py … test_emit.py   # one file per module
    ├── test_update.py               # offline integration + round-trip
    └── test_golden_cs_stat.py       # counts vs the real SVG (marker: golden)
homepage/views.py                    # + index_path per mindmap
homepage/tests.py                    # viewer index-url test
homepage/templates/homepage/mindmap_viewer.html  # wrapper div, overlay, search, panel
static/assets/js/mindmap_notes.js    # all new viewer JS
static/mindmaps/<stem>-index.json    # pipeline output (committed)
```

---

### Task 1: Package scaffold, dependencies, geometry primitives

**Files:**
- Create: `scripts/__init__.py`, `scripts/mindmap_vault/__init__.py`, `scripts/mindmap_vault/config.py`, `scripts/mindmap_vault/geom.py`, `scripts/mindmap_vault/model.py`, `pytest.ini`, `tests/conftest.py` (sys.path shim only for now)
- Test: `tests/mindmap_vault/test_geom.py`

**Interfaces:**
- Produces: `geom` functions used by every later task — `bbox_of(points)->tuple`, `bbox_union(a,b)`, `bbox_area(b)`, `bbox_center(b)`, `bbox_expand(b,m)`, `bbox_iou(a,b)`, `bbox_contains(b,pt)`, `polyline_len(pts)`, `chord_len(pts)`, `dist(p,q)`, `point_bbox_dist(pt,b)` (0 inside), `point_rect_outline_dist(pt,b)`.
- Produces: dataclasses `Stroke(sid, points, bbox, color, width, layer, radius=0.0)`, `ImageRef(iid, def_id, bbox)`, `Box(border_ids, bbox, member_ids=[], image_ids=[], box_id="")`, `Edge(src, dst, directed, stroke_ids=[])` (src/dst are indices into the box list until manifest assigns ids), `OcrResult(title, text, is_concept_box, context=None)`.
- Produces: `config` constants (exact values below; Task 11 may retune them).

- [ ] **Step 1: Install missing deps into the env**

```bash
micromamba run -n django-nihar-website pip install anthropic pytest
```
Expected: both install without error (PIL and numpy already present).

- [ ] **Step 2: Create scaffold files**

`scripts/__init__.py` and `scripts/mindmap_vault/__init__.py`: empty files.

`pytest.ini` (repo root):
```ini
[pytest]
testpaths = tests
markers =
    golden: golden checks against the real mindmap SVGs (slow)
```

`tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

`scripts/mindmap_vault/config.py`:
```python
"""All tunable thresholds. Units are SVG viewBox pt unless noted."""

# --- box classification ---
MIN_BOX_W = 25.0          # smaller than any real concept box, larger than glyphs (~6pt)
MIN_BOX_H = 12.0
RECT_RATIO_LO = 0.75      # polyline length / bbox perimeter
RECT_RATIO_HI = 1.35
CLOSURE_FRAC = 0.20       # start-end gap as fraction of perimeter (single-stroke)
PERIM_HUG = 0.20          # mean point→outline distance < PERIM_HUG * min(w, h)
SEG_MIN_LEN = 15.0        # multi-stroke box side candidates
SEG_LINEARITY = 0.85      # chord/arc ratio for "straight" strokes
JOIN_TOL = 6.0            # endpoint proximity when chaining strokes
MULTI_MAX_STROKES = 6
DEDUP_IOU = 0.8

# --- arrows ---
ARROW_MIN_LEN = 12.0
END_TOL = 10.0            # endpoint→box distance to count as attached
AMBIG_RATIO = 1.5         # 2nd-nearest closer than ratio*nearest → ambiguous
HEAD_MAX_LEN = 8.0
HEAD_TOL = 5.0

# --- binding ---
ATTACH_DIST = 12.0        # loose annotation → nearest box

# --- rendering ---
CROP_MARGIN = 8.0
CROP_TARGET_W = 1200      # px
CROP_MAX_H = 1600         # px
CROP_MAX_SCALE = 40.0     # px per pt
CROP_BG = "#1F2429"

# --- ocr ---
OCR_MODEL = "claude-sonnet-5"
OCR_MAX_TOKENS = 1500
OCR_RETRIES = 3
OCR_COST_ESTIMATE = 0.015  # $ per call, for the summary line only
```

`scripts/mindmap_vault/model.py`:
```python
from dataclasses import dataclass, field


@dataclass
class Stroke:
    sid: str
    points: list
    bbox: tuple
    color: str
    width: float
    layer: str
    radius: float = 0.0  # >0 for <circle> dot strokes


@dataclass
class ImageRef:
    iid: str
    def_id: str
    bbox: tuple


@dataclass
class Box:
    border_ids: list
    bbox: tuple
    member_ids: list = field(default_factory=list)
    image_ids: list = field(default_factory=list)
    box_id: str = ""


@dataclass
class Edge:
    src: int
    dst: int
    directed: bool
    stroke_ids: list = field(default_factory=list)


@dataclass
class OcrResult:
    title: str
    text: str
    is_concept_box: bool
    context: str | None = None
```

- [ ] **Step 3: Write the failing geometry tests**

`tests/mindmap_vault/test_geom.py`:
```python
import math

from scripts.mindmap_vault import geom


def test_bbox_of_and_center():
    pts = [(0, 0), (4, 2), (2, 6)]
    assert geom.bbox_of(pts) == (0, 0, 4, 6)
    assert geom.bbox_center((0, 0, 4, 6)) == (2, 3)


def test_bbox_union_area_expand():
    assert geom.bbox_union((0, 0, 1, 1), (2, 2, 3, 4)) == (0, 0, 3, 4)
    assert geom.bbox_area((1, 1, 3, 5)) == 8
    assert geom.bbox_expand((1, 1, 3, 5), 1) == (0, 0, 4, 6)


def test_bbox_iou():
    assert geom.bbox_iou((0, 0, 2, 2), (0, 0, 2, 2)) == 1.0
    assert geom.bbox_iou((0, 0, 2, 2), (1, 0, 3, 2)) == 0.5 / 1.5
    assert geom.bbox_iou((0, 0, 1, 1), (5, 5, 6, 6)) == 0.0


def test_bbox_contains():
    assert geom.bbox_contains((0, 0, 4, 4), (2, 2))
    assert not geom.bbox_contains((0, 0, 4, 4), (5, 2))


def test_polyline_and_chord_len():
    pts = [(0, 0), (3, 0), (3, 4)]
    assert geom.polyline_len(pts) == 7
    assert geom.chord_len(pts) == 5
    assert geom.polyline_len([(1, 1)]) == 0


def test_point_bbox_dist():
    b = (0, 0, 4, 4)
    assert geom.point_bbox_dist((2, 2), b) == 0
    assert geom.point_bbox_dist((7, 2), b) == 3
    assert math.isclose(geom.point_bbox_dist((7, 8), b), 5.0)


def test_point_rect_outline_dist():
    b = (0, 0, 10, 10)
    assert geom.point_rect_outline_dist((5, 1), b) == 1      # inside, near bottom edge
    assert geom.point_rect_outline_dist((12, 5), b) == 2     # outside
    assert geom.point_rect_outline_dist((0, 5), b) == 0      # on outline
```

- [ ] **Step 4: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_geom.py -v
```
Expected: FAIL — `ModuleNotFoundError`/`AttributeError` (geom missing).

- [ ] **Step 5: Implement `scripts/mindmap_vault/geom.py`**

```python
import math


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def bbox_of(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def bbox_union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def bbox_area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def bbox_center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def bbox_expand(b, m):
    return (b[0] - m, b[1] - m, b[2] + m, b[3] + m)


def bbox_iou(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    union = bbox_area(a) + bbox_area(b) - inter
    return inter / union if union > 0 else 0.0


def bbox_contains(b, pt):
    return b[0] <= pt[0] <= b[2] and b[1] <= pt[1] <= b[3]


def polyline_len(pts):
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def chord_len(pts):
    return dist(pts[0], pts[-1]) if len(pts) > 1 else 0.0


def point_bbox_dist(pt, b):
    dx = max(b[0] - pt[0], 0.0, pt[0] - b[2])
    dy = max(b[1] - pt[1], 0.0, pt[1] - b[3])
    return math.hypot(dx, dy)


def point_rect_outline_dist(pt, b):
    out = point_bbox_dist(pt, b)
    if out > 0:
        return out
    return min(pt[0] - b[0], b[2] - pt[0], pt[1] - b[1], b[3] - pt[1])
```

- [ ] **Step 6: Run tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_geom.py -v
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/ tests/ pytest.ini
git commit -m "feat: mindmap_vault scaffold with geometry primitives and config"
```

---

### Task 2: Synthetic SVG fixture and the parser

**Files:**
- Create: `scripts/mindmap_vault/parse.py`
- Modify: `tests/conftest.py` (add fixture)
- Test: `tests/mindmap_vault/test_parse.py`

**Interfaces:**
- Consumes: `model.Stroke/ImageRef`, `geom.bbox_of`.
- Produces: `parse.parse_svg(path) -> ParseResult` where `ParseResult` is a dataclass with `strokes: list[Stroke]`, `images: list[ImageRef]`, `viewbox: tuple[float, float, float, float]`, `image_defs: dict[str, tuple[float, float]]` (def id → (w, h)).
- Produces: `parse.load_image_png(svg_path, def_id) -> bytes` (decoded PNG for one def).
- Produces: fixture `synthetic_svg(tmp_path_factory)` returning a `Path` to a small Concepts-style SVG whose exact contents are defined below; every later geometry test uses it.

- [ ] **Step 1: Add the synthetic SVG fixture to `tests/conftest.py`**

The fixture mimics the real export: viewBox, `<defs>` with one base64 PNG, layer groups, `STROKE_` paths with M/L/Q, a `STROKE_` circle, an `IMAGE_` group. Layout (viewBox `0 0 500 400`):

- **Box A** — single-stroke rectangle (10,10)–(120,60), slight closure gap; contains 3 short "handwriting" strokes and 1 dot circle.
- **Box B** — single-stroke rectangle (200,10)–(320,70); contains the embedded image (240,20)–(300,50) and 1 text stroke.
- **Box C** — four separate straight strokes forming rectangle (10,150)–(140,210) (multi-stroke box); contains 1 text stroke.
- **Arrow A→B** — line (122,35)→(198,35) plus two short arrowhead strokes ending at (198,35).
- **Line B–C** (no head, undirected) — (250,72)→(100,148).
- **Decoy** — a wavy open squiggle far away at (400,300), must NOT classify as box or arrow.

Append to `tests/conftest.py`:
```python
import base64
import io

import pytest

_PNG_1PX = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
    )
).decode()


def _stroke(sid, d, color="#ffcca9", width=0.6):
    return (
        f'<path id="STROKE_{sid}" opacity="1.000" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" d="{d}"/>'
    )


def _rect_d(x0, y0, x1, y1, gap=1.0):
    return (
        f"M {x0} {y0} L {x1} {y0} L {x1} {y1} L {x0} {y1} L {x0} {y0 + gap}"
    )


def _squiggle_d(x, y, n=6, step=4.0):
    parts = [f"M {x} {y}"]
    for i in range(n):
        parts.append(
            f"Q {x + step * (2 * i + 1)} {y + (8 if i % 2 else -8)} {x + step * (2 * i + 2)} {y}"
        )
    return " ".join(parts)


SYNTHETIC_SVG = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="500pt" height="400pt" version="1.1" viewBox="0 0 500 400">
<title>SYNTH</title>
<defs>
<image id="IMAGE_DEF_aaa" width="60" height="30" xlink:href="data:image/png;base64,{_PNG_1PX}"/>
</defs>
<g id="Image" opacity="1.000">
<g id="IMAGE_img1" opacity="1.000" transform="matrix(1.0 0.0 0.0 1.0 240.0 20.0)">
<use xlink:href="#IMAGE_DEF_aaa"/>
</g>
</g>
<g id="Pen" opacity="1.000">
{_stroke("boxA", _rect_d(10, 10, 120, 60))}
{_stroke("txtA1", _squiggle_d(20, 30, n=2, step=2.0))}
{_stroke("txtA2", _squiggle_d(45, 30, n=2, step=2.0))}
{_stroke("txtA3", _squiggle_d(70, 45, n=2, step=2.0))}
<circle id="STROKE_dotA" fill="#ffcca9" stroke="#ffcca9" stroke-width="0.1" cx="95" cy="45" r="0.4"/>
{_stroke("boxB", _rect_d(200, 10, 320, 70))}
{_stroke("txtB1", _squiggle_d(210, 60, n=2, step=2.0))}
{_stroke("boxC_top", "M 10 150 L 140 150")}
{_stroke("boxC_right", "M 140 150 L 140 210")}
{_stroke("boxC_bot", "M 140 210 L 10 210")}
{_stroke("boxC_left", "M 10 210 L 10 150")}
{_stroke("txtC1", _squiggle_d(30, 180, n=2, step=2.0))}
{_stroke("arrowAB", "M 122 35 L 198 35")}
{_stroke("headAB1", "M 192 30 L 198 35")}
{_stroke("headAB2", "M 192 40 L 198 35")}
{_stroke("lineBC", "M 250 72 L 100 148")}
{_stroke("decoy", _squiggle_d(400, 300, n=6, step=4.0))}
</g>
</svg>
"""


@pytest.fixture(scope="session")
def synthetic_svg(tmp_path_factory):
    p = tmp_path_factory.mktemp("svg") / "synth.svg"
    p.write_text(SYNTHETIC_SVG, encoding="utf-8")
    return p
```

- [ ] **Step 2: Write the failing parser tests**

`tests/mindmap_vault/test_parse.py`:
```python
from scripts.mindmap_vault import parse


def test_parse_counts_and_viewbox(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    assert r.viewbox == (0.0, 0.0, 500.0, 400.0)
    assert len(r.strokes) == 17  # 16 paths + 1 circle
    assert len(r.images) == 1
    assert r.image_defs == {"IMAGE_DEF_aaa": (60.0, 30.0)}


def test_stroke_fields(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    by_id = {s.sid: s for s in r.strokes}
    box_a = by_id["boxA"]
    assert box_a.layer == "Pen"
    assert box_a.color == "#ffcca9"
    assert box_a.bbox == (10.0, 10.0, 120.0, 60.0)
    assert box_a.radius == 0.0
    dot = by_id["dotA"]
    assert dot.radius == 0.4
    assert dot.points == [(95.0, 45.0)]


def test_q_commands_sampled(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    decoy = {s.sid: s for s in r.strokes}["decoy"]
    # 1 M point + per Q: midpoint + endpoint → 1 + 6*2 = 13
    assert len(decoy.points) == 13


def test_image_bbox_from_matrix(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    img = r.images[0]
    assert img.def_id == "IMAGE_DEF_aaa"
    assert img.bbox == (240.0, 20.0, 300.0, 50.0)


def test_load_image_png(synthetic_svg):
    data = parse.load_image_png(synthetic_svg, "IMAGE_DEF_aaa")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_parse.py -v
```
Expected: FAIL — `parse` module missing.

- [ ] **Step 4: Implement `scripts/mindmap_vault/parse.py`**

```python
import base64
import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.mindmap_vault.geom import bbox_of
from scripts.mindmap_vault.model import ImageRef, Stroke

_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_TAG = re.compile(r"<g\b[^>]*>|</g>|<path\b[^>]*?/>|<circle\b[^>]*?/>|<use\b[^>]*?/>")
_CMD = re.compile(r"([MLQ])([^MLQ]*)")


@dataclass
class ParseResult:
    strokes: list = field(default_factory=list)
    images: list = field(default_factory=list)
    viewbox: tuple = (0.0, 0.0, 0.0, 0.0)
    image_defs: dict = field(default_factory=dict)


def _attr(tag, name):
    m = re.search(rf'{name}="([^"]*)"', tag)
    return m.group(1) if m else None


def _sample_d(d):
    pts = []
    cur = None
    for m in _CMD.finditer(d):
        cmd = m.group(1)
        nums = [float(x) for x in _NUM.findall(m.group(2))]
        if cmd in ("M", "L"):
            for i in range(0, len(nums) - 1, 2):
                cur = (nums[i], nums[i + 1])
                pts.append(cur)
        elif cmd == "Q":
            for i in range(0, len(nums) - 3, 4):
                cx, cy, x, y = nums[i : i + 4]
                x0, y0 = cur
                pts.append(((x0 + 2 * cx + x) / 4.0, (y0 + 2 * cy + y) / 4.0))
                cur = (x, y)
                pts.append(cur)
    return pts


def _matrix_bbox(matrix, w, h):
    a, b, c, d, e, f = matrix
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    tx = [a * x + c * y + e for x, y in corners]
    ty = [b * x + d * y + f for x, y in corners]
    return (min(tx), min(ty), max(tx), max(ty))


def parse_svg(path):
    text = Path(path).read_text(encoding="utf-8")
    result = ParseResult()

    vb = re.search(r'viewBox="([^"]+)"', text[:3000])
    result.viewbox = tuple(float(v) for v in _NUM.findall(vb.group(1)))

    defs_end = text.find("</defs>")
    defs_end = 0 if defs_end < 0 else defs_end
    for m in re.finditer(r"<image\b[^>]*?>", text[:defs_end]):
        tag = m.group(0)
        did = _attr(tag, "id")
        if did:
            result.image_defs[did] = (float(_attr(tag, "width")), float(_attr(tag, "height")))

    stack = []  # (kind, name, matrix)
    layer = "root"
    for m in _TAG.finditer(text, defs_end):
        tag = m.group(0)
        if tag.startswith("</g"):
            if stack:
                stack.pop()
            layer = next((n for k, n, _ in reversed(stack) if k == "layer"), "root")
        elif tag.startswith("<g"):
            gid = _attr(tag, "id") or ""
            tr = _attr(tag, "transform")
            if gid.startswith("IMAGE_") and tr and tr.startswith("matrix("):
                matrix = tuple(float(v) for v in _NUM.findall(tr))
                stack.append(("image", gid, matrix))
            else:
                stack.append(("layer", gid, None))
                layer = gid
        elif tag.startswith("<use"):
            img = next(((n, mx) for k, n, mx in reversed(stack) if k == "image"), None)
            href = _attr(tag, "xlink:href") or _attr(tag, "href") or ""
            def_id = href.lstrip("#")
            if img and def_id in result.image_defs:
                w, h = result.image_defs[def_id]
                result.images.append(
                    ImageRef(iid=img[0], def_id=def_id, bbox=_matrix_bbox(img[1], w, h))
                )
        elif tag.startswith("<path"):
            sid = (_attr(tag, "id") or "")
            if not sid.startswith("STROKE_"):
                continue
            pts = _sample_d(_attr(tag, "d") or "")
            if len(pts) < 1:
                continue
            result.strokes.append(
                Stroke(
                    sid=sid[len("STROKE_"):],
                    points=pts,
                    bbox=bbox_of(pts),
                    color=_attr(tag, "stroke") or "#ffffff",
                    width=float(_attr(tag, "stroke-width") or 1.0),
                    layer=layer,
                )
            )
        elif tag.startswith("<circle"):
            sid = (_attr(tag, "id") or "")
            if not sid.startswith("STROKE_"):
                continue
            cx, cy = float(_attr(tag, "cx")), float(_attr(tag, "cy"))
            r = float(_attr(tag, "r"))
            result.strokes.append(
                Stroke(
                    sid=sid[len("STROKE_"):],
                    points=[(cx, cy)],
                    bbox=(cx - r, cy - r, cx + r, cy + r),
                    color=_attr(tag, "fill") or _attr(tag, "stroke") or "#ffffff",
                    width=r * 2,
                    layer=layer,
                    radius=r,
                )
            )
    return result


def load_image_png(path, def_id):
    text = Path(path).read_text(encoding="utf-8")
    m = re.search(
        rf'<image id="{re.escape(def_id)}"[^>]*?href="data:image/png;base64,([^"]+)"',
        text,
    )
    if not m:
        raise KeyError(f"image def {def_id!r} not found in {path}")
    return base64.b64decode(m.group(1))
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_parse.py -v
```
Expected: all PASS. If the decoy point-count assertion is off by the M-handling detail, fix the test's expected value to match `_sample_d`'s actual contract (1 point per M coordinate pair, 2 per Q segment), not the implementation.

- [ ] **Step 6: Commit**

```bash
git add scripts/mindmap_vault/parse.py tests/
git commit -m "feat: SVG parser for Concepts exports with synthetic fixture"
```

---

### Task 3: Box classification

**Files:**
- Create: `scripts/mindmap_vault/boxes.py`
- Test: `tests/mindmap_vault/test_boxes.py`

**Interfaces:**
- Consumes: `parse.parse_svg`, `geom`, `config`, `model.Box`.
- Produces: `boxes.find_boxes(strokes) -> list[Box]` — each with `border_ids` (stroke sids) and exact `bbox`; deduplicated; deterministic order (sorted by (y0, x0)).

- [ ] **Step 1: Write the failing tests**

`tests/mindmap_vault/test_boxes.py`:
```python
from scripts.mindmap_vault import boxes, parse


def _find(bs, x, y):
    return next(b for b in bs if b.bbox[0] <= x <= b.bbox[2] and b.bbox[1] <= y <= b.bbox[3])


def test_finds_three_boxes(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    assert len(bs) == 3


def test_single_stroke_box_bbox(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    a = _find(bs, 60, 35)
    assert a.border_ids == ["boxA"]
    assert a.bbox == (10.0, 10.0, 120.0, 60.0)


def test_multi_stroke_box(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    c = _find(bs, 75, 180)
    assert sorted(c.border_ids) == ["boxC_bot", "boxC_left", "boxC_right", "boxC_top"]
    assert c.bbox == (10.0, 150.0, 140.0, 210.0)


def test_decoy_and_text_not_boxes(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    all_border = {sid for b in bs for sid in b.border_ids}
    assert "decoy" not in all_border
    assert "txtA1" not in all_border
    assert "arrowAB" not in all_border


def test_deterministic_order(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    b1 = [b.bbox for b in boxes.find_boxes(r.strokes)]
    b2 = [b.bbox for b in boxes.find_boxes(r.strokes)]
    assert b1 == b2
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_boxes.py -v
```
Expected: FAIL — `boxes` module missing.

- [ ] **Step 3: Implement `scripts/mindmap_vault/boxes.py`**

```python
from scripts.mindmap_vault import config
from scripts.mindmap_vault.geom import (
    bbox_area,
    bbox_iou,
    bbox_of,
    bbox_union,
    chord_len,
    dist,
    point_rect_outline_dist,
    polyline_len,
)
from scripts.mindmap_vault.model import Box


def _rect_metrics(points, bbox):
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if w < config.MIN_BOX_W or h < config.MIN_BOX_H:
        return None
    per = polyline_len(points)
    ratio = per / (2 * (w + h))
    if not (config.RECT_RATIO_LO <= ratio <= config.RECT_RATIO_HI):
        return None
    hug = sum(point_rect_outline_dist(p, bbox) for p in points) / len(points)
    if hug >= config.PERIM_HUG * min(w, h):
        return None
    return per


def _is_single_box(s):
    per = _rect_metrics(s.points, s.bbox)
    if per is None:
        return False
    return dist(s.points[0], s.points[-1]) <= config.CLOSURE_FRAC * per


def _linearity(s):
    arc = polyline_len(s.points)
    return chord_len(s.points) / arc if arc > 0 else 0.0


def _join_components(strokes, tol):
    """Union-find over strokes whose endpoints are within tol."""
    parent = list(range(len(strokes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    ends = [(s.points[0], s.points[-1]) for s in strokes]
    for i in range(len(strokes)):
        for j in range(i + 1, len(strokes)):
            if any(dist(a, b) <= tol for a in ends[i] for b in ends[j]):
                parent[find(i)] = find(j)

    comps = {}
    for i in range(len(strokes)):
        comps.setdefault(find(i), []).append(strokes[i])
    return list(comps.values())


def _multi_stroke_boxes(strokes):
    segs = [
        s for s in strokes
        if not s.radius
        and polyline_len(s.points) >= config.SEG_MIN_LEN
        and _linearity(s) >= config.SEG_LINEARITY
    ]
    out = []
    for comp in _join_components(segs, config.JOIN_TOL):
        if not (2 <= len(comp) <= config.MULTI_MAX_STROKES):
            continue
        bb = comp[0].bbox
        for s in comp[1:]:
            bb = bbox_union(bb, s.bbox)
        pts = [p for s in comp for p in s.points]
        if _rect_metrics(pts, bb) is not None:
            out.append(Box(border_ids=[s.sid for s in comp], bbox=bb))
    return out


def _dedup(candidates):
    kept = []
    for c in sorted(candidates, key=lambda b: -bbox_area(b.bbox)):
        if all(bbox_iou(c.bbox, k.bbox) < config.DEDUP_IOU for k in kept):
            kept.append(c)
    return kept


def find_boxes(strokes):
    singles = [
        Box(border_ids=[s.sid], bbox=s.bbox)
        for s in strokes
        if not s.radius and _is_single_box(s)
    ]
    used = {sid for b in singles for sid in b.border_ids}
    rest = [s for s in strokes if s.sid not in used]
    result = _dedup(singles + _multi_stroke_boxes(rest))
    result.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
    return result
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_boxes.py -v
```
Expected: all PASS. Note: `_join_components` is O(n²); acceptable because only long *linear* strokes qualify (a few hundred on real maps). If the multi-stroke box test fails, debug by printing `_linearity` and `_rect_metrics` values for the four `boxC_*` strokes — do not loosen constants blindly.

- [ ] **Step 5: Commit**

```bash
git add scripts/mindmap_vault/boxes.py tests/mindmap_vault/test_boxes.py
git commit -m "feat: geometric box classification (single- and multi-stroke)"
```

---

### Task 4: Arrow / edge detection

**Files:**
- Create: `scripts/mindmap_vault/arrows.py`
- Test: `tests/mindmap_vault/test_arrows.py`

**Interfaces:**
- Consumes: `boxes.find_boxes` output, strokes, `geom`, `config`, `model.Edge`.
- Produces: `arrows.find_edges(strokes, boxes) -> tuple[list[Edge], list[str]]` — edges hold box indices (`src`, `dst`) into the passed box list, `directed=True` when an arrowhead marks the destination end, and `stroke_ids` covering the connector *and* consumed arrowhead strokes; second element is a list of human-readable ambiguity messages for `review.md`.

- [ ] **Step 1: Write the failing tests**

`tests/mindmap_vault/test_arrows.py`:
```python
from scripts.mindmap_vault import arrows, boxes, parse


def _setup(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    idx = {}
    for i, b in enumerate(bs):
        if b.bbox[0] < 150 and b.bbox[1] < 100:
            idx["A"] = i
        elif b.bbox[0] > 150:
            idx["B"] = i
        else:
            idx["C"] = i
    return r, bs, idx


def test_directed_edge_a_to_b(synthetic_svg):
    r, bs, idx = _setup(synthetic_svg)
    edges, review = arrows.find_edges(r.strokes, bs)
    ab = next(e for e in edges if {e.src, e.dst} == {idx["A"], idx["B"]})
    assert ab.directed
    assert ab.src == idx["A"] and ab.dst == idx["B"]
    assert "arrowAB" in ab.stroke_ids
    assert {"headAB1", "headAB2"} <= set(ab.stroke_ids)


def test_undirected_edge_b_c(synthetic_svg):
    r, bs, idx = _setup(synthetic_svg)
    edges, _ = arrows.find_edges(r.strokes, bs)
    bc = next(e for e in edges if {e.src, e.dst} == {idx["B"], idx["C"]})
    assert not bc.directed


def test_exactly_two_edges_no_review(synthetic_svg):
    r, bs, _ = _setup(synthetic_svg)
    edges, review = arrows.find_edges(r.strokes, bs)
    assert len(edges) == 2
    assert review == []


def test_dangling_connector_goes_to_review(synthetic_svg):
    r, bs, _ = _setup(synthetic_svg)
    from scripts.mindmap_vault.model import Stroke
    dangling = Stroke(
        sid="dangle", points=[(122.0, 50.0), (170.0, 120.0)],
        bbox=(122.0, 50.0, 170.0, 120.0), color="#fff", width=0.6, layer="Pen",
    )
    edges, review = arrows.find_edges(r.strokes + [dangling], bs)
    assert len(edges) == 2
    assert any("dangle" in msg for msg in review)
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_arrows.py -v
```
Expected: FAIL — `arrows` module missing.

- [ ] **Step 3: Implement `scripts/mindmap_vault/arrows.py`**

```python
from scripts.mindmap_vault import config
from scripts.mindmap_vault.boxes import _join_components
from scripts.mindmap_vault.geom import (
    bbox_area,
    bbox_contains,
    dist,
    point_bbox_dist,
    polyline_len,
)
from scripts.mindmap_vault.model import Edge


def _midpoint(s):
    return s.points[len(s.points) // 2]


def _nearest_box(pt, boxes):
    """Return (index, dist, ambiguous). Inside a box counts as dist 0
    (smallest containing box wins). Returns (None, inf, False) if nothing
    is within END_TOL."""
    containing = [
        (bbox_area(b.bbox), i) for i, b in enumerate(boxes) if bbox_contains(b.bbox, pt)
    ]
    if containing:
        return (min(containing)[1], 0.0, False)
    ds = sorted((point_bbox_dist(pt, b.bbox), i) for i, b in enumerate(boxes))
    if not ds or ds[0][0] > config.END_TOL:
        return (None, float("inf"), False)
    ambiguous = (
        len(ds) > 1
        and ds[1][0] <= config.END_TOL
        and ds[1][0] < config.AMBIG_RATIO * max(ds[0][0], 1e-6)
    )
    return (ds[0][1], ds[0][0], ambiguous)


def _chain_endpoints(chain):
    pts = [p for s in chain for p in (s.points[0], s.points[-1])]
    best = (0.0, pts[0], pts[0])
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = dist(pts[i], pts[j])
            if d > best[0]:
                best = (d, pts[i], pts[j])
    return best[1], best[2]


def find_edges(strokes, boxes):
    border = {sid for b in boxes for sid in b.border_ids}
    heads = [
        s for s in strokes
        if s.sid not in border and not s.radius
        and 0 < polyline_len(s.points) <= config.HEAD_MAX_LEN
    ]
    cands = [
        s for s in strokes
        if s.sid not in border and not s.radius
        and polyline_len(s.points) >= config.ARROW_MIN_LEN
        and not any(bbox_contains(b.bbox, _midpoint(s)) for b in boxes)
    ]

    edges, review = [], []
    for chain in _join_components(cands, config.JOIN_TOL):
        e1, e2 = _chain_endpoints(chain)
        i1, d1, amb1 = _nearest_box(e1, boxes)
        i2, d2, amb2 = _nearest_box(e2, boxes)
        sids = [s.sid for s in chain]
        if i1 is None and i2 is None:
            continue  # stray mark, not attached to anything
        if i1 is None or i2 is None or i1 == i2:
            review.append(
                f"connector {sids} endpoints {e1} -> {e2}: "
                f"attached boxes ({i1}, {i2}) — needs manual review"
            )
            continue
        if amb1 or amb2:
            review.append(
                f"connector {sids} endpoints {e1} -> {e2}: ambiguous nearest box"
            )
            continue

        h1 = [h for h in heads if min(dist(h.points[0], e1), dist(h.points[-1], e1)) <= config.HEAD_TOL]
        h2 = [h for h in heads if min(dist(h.points[0], e2), dist(h.points[-1], e2)) <= config.HEAD_TOL]
        if h2 and not h1:
            edges.append(Edge(src=i1, dst=i2, directed=True,
                              stroke_ids=sids + [h.sid for h in h2]))
        elif h1 and not h2:
            edges.append(Edge(src=i2, dst=i1, directed=True,
                              stroke_ids=sids + [h.sid for h in h1]))
        else:
            edges.append(Edge(src=min(i1, i2), dst=max(i1, i2), directed=False,
                              stroke_ids=sids))
    return edges, review
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_arrows.py -v
```
Expected: all PASS. Watch one trap: the arrowhead strokes (`headAB*`, length ~7.8) must not themselves become connector candidates — `ARROW_MIN_LEN=12 > HEAD_MAX_LEN=8` guarantees the sets are disjoint; keep that invariant if constants are retuned in Task 11.

- [ ] **Step 5: Commit**

```bash
git add scripts/mindmap_vault/arrows.py tests/mindmap_vault/test_arrows.py
git commit -m "feat: arrow detection with direction and ambiguity review list"
```

---

### Task 5: Text / image binding

**Files:**
- Create: `scripts/mindmap_vault/bind.py`
- Test: `tests/mindmap_vault/test_bind.py`

**Interfaces:**
- Consumes: strokes, images, boxes (mutated in place), edges.
- Produces: `bind.bind(strokes, images, boxes, edges) -> None` — fills each `Box.member_ids` (handwriting strokes, order preserved from input) and `Box.image_ids`; strokes already used as borders or edge/head strokes are excluded; loose strokes within `ATTACH_DIST` of a box attach to it; others are ignored.

- [ ] **Step 1: Write the failing tests**

`tests/mindmap_vault/test_bind.py`:
```python
from scripts.mindmap_vault import arrows, bind, boxes, parse


def _pipeline(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    edges, _ = arrows.find_edges(r.strokes, bs)
    bind.bind(r.strokes, r.images, bs, edges)
    return r, bs


def _box_at(bs, x, y):
    return next(b for b in bs if b.bbox[0] <= x <= b.bbox[2] and b.bbox[1] <= y <= b.bbox[3])


def test_text_bound_to_boxes(synthetic_svg):
    _, bs = _pipeline(synthetic_svg)
    a = _box_at(bs, 60, 35)
    assert set(a.member_ids) == {"txtA1", "txtA2", "txtA3", "dotA"}
    c = _box_at(bs, 75, 180)
    assert set(c.member_ids) == {"txtC1"}


def test_image_bound_to_box_b(synthetic_svg):
    _, bs = _pipeline(synthetic_svg)
    b = _box_at(bs, 260, 40)
    assert b.image_ids == ["img1"]
    assert set(b.member_ids) == {"txtB1"}


def test_edge_and_decoy_strokes_not_members(synthetic_svg):
    _, bs = _pipeline(synthetic_svg)
    members = {sid for b in bs for sid in b.member_ids}
    for sid in ("arrowAB", "headAB1", "headAB2", "lineBC", "decoy"):
        assert sid not in members
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_bind.py -v
```
Expected: FAIL — `bind` module missing.

- [ ] **Step 3: Implement `scripts/mindmap_vault/bind.py`**

```python
from scripts.mindmap_vault import config
from scripts.mindmap_vault.geom import bbox_area, bbox_center, bbox_contains, point_bbox_dist


def _owner(center, boxes):
    containing = [
        (bbox_area(b.bbox), i)
        for i, b in enumerate(boxes)
        if bbox_contains(b.bbox, center)
    ]
    if containing:
        return min(containing)[1]
    ds = sorted((point_bbox_dist(center, b.bbox), i) for i, b in enumerate(boxes))
    if ds and ds[0][0] <= config.ATTACH_DIST:
        return ds[0][1]
    return None


def bind(strokes, images, boxes, edges):
    taken = {sid for b in boxes for sid in b.border_ids}
    taken |= {sid for e in edges for sid in e.stroke_ids}
    for s in strokes:
        if s.sid in taken:
            continue
        i = _owner(bbox_center(s.bbox), boxes)
        if i is not None:
            boxes[i].member_ids.append(s.sid)
    for img in images:
        i = _owner(bbox_center(img.bbox), boxes)
        if i is not None:
            boxes[i].image_ids.append(img.iid)
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_bind.py -v
```
Expected: all PASS. The decoy at (400,300) stays unbound because it is farther than `ATTACH_DIST` from every box.

- [ ] **Step 5: Commit**

```bash
git add scripts/mindmap_vault/bind.py tests/mindmap_vault/test_bind.py
git commit -m "feat: bind handwriting strokes and images to owning boxes"
```

---

### Task 6: Crop rendering with PIL

**Files:**
- Create: `scripts/mindmap_vault/render.py`
- Test: `tests/mindmap_vault/test_render.py`

**Interfaces:**
- Consumes: a `Box`, `dict[sid -> Stroke]`, `list[ImageRef]`, svg path (for base64 loading), `config`.
- Produces: `render.render_box(box, strokes_by_id, images_by_id, svg_path, bg=config.CROP_BG) -> PIL.Image.Image` — dark background, strokes drawn in their original colors, embedded images pasted, sized so crop width ≈ `CROP_TARGET_W`.

- [ ] **Step 1: Write the failing tests**

`tests/mindmap_vault/test_render.py`:
```python
from scripts.mindmap_vault import arrows, bind, boxes, parse, render


def _box_b(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    edges, _ = arrows.find_edges(r.strokes, bs)
    bind.bind(r.strokes, r.images, bs, edges)
    strokes_by_id = {s.sid: s for s in r.strokes}
    images_by_id = {i.iid: i for i in r.images}
    b = next(x for x in bs if x.image_ids)
    return b, strokes_by_id, images_by_id


def test_render_size_and_content(synthetic_svg):
    box, strokes_by_id, images_by_id = _box_b(synthetic_svg)
    img = render.render_box(box, strokes_by_id, images_by_id, synthetic_svg)
    # bbox (200,10)-(320,70) + margin 8 → 136 x 76 pt, scaled to target width
    assert img.width == 1200
    assert 600 <= img.height <= 720
    colors = img.getcolors(maxcolors=1_000_000)
    assert len(colors) > 1  # not a blank canvas


def test_render_respects_max_scale():
    # tiny box: scale would exceed CROP_MAX_SCALE, must clamp
    from scripts.mindmap_vault.model import Box, Stroke
    s = Stroke(sid="t", points=[(0.0, 0.0), (10.0, 10.0)],
               bbox=(0.0, 0.0, 10.0, 10.0), color="#fff", width=0.6, layer="Pen")
    b = Box(border_ids=[], bbox=(0.0, 0.0, 10.0, 10.0), member_ids=["t"])
    img = render.render_box(b, {"t": s}, {}, None)
    assert img.width <= (10 + 16) * 40 + 1  # (w + 2*margin) * CROP_MAX_SCALE
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_render.py -v
```
Expected: FAIL — `render` module missing.

- [ ] **Step 3: Implement `scripts/mindmap_vault/render.py`**

```python
import io

from PIL import Image, ImageDraw

from scripts.mindmap_vault import config, parse
from scripts.mindmap_vault.geom import bbox_expand


def render_box(box, strokes_by_id, images_by_id, svg_path, bg=config.CROP_BG):
    x0, y0, x1, y1 = bbox_expand(box.bbox, config.CROP_MARGIN)
    w, h = x1 - x0, y1 - y0
    scale = min(config.CROP_TARGET_W / w, config.CROP_MAX_H / h, config.CROP_MAX_SCALE)
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)

    def to_px(p):
        return ((p[0] - x0) * scale, (p[1] - y0) * scale)

    for iid in box.image_ids:
        ref = images_by_id[iid]
        png = Image.open(io.BytesIO(parse.load_image_png(svg_path, ref.def_id)))
        bx0, by0 = to_px((ref.bbox[0], ref.bbox[1]))
        bx1, by1 = to_px((ref.bbox[2], ref.bbox[3]))
        tw, th = max(1, round(bx1 - bx0)), max(1, round(by1 - by0))
        img.paste(png.convert("RGB").resize((tw, th)), (round(bx0), round(by0)))

    for sid in list(box.border_ids) + list(box.member_ids):
        s = strokes_by_id[sid]
        if s.radius > 0:
            cx, cy = to_px(s.points[0])
            r = max(1.0, s.radius * scale)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=s.color)
        elif len(s.points) >= 2:
            draw.line(
                [to_px(p) for p in s.points],
                fill=s.color,
                width=max(2, round(s.width * scale)),
                joint="curve",
            )
    return img
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_render.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/mindmap_vault/render.py tests/mindmap_vault/test_render.py
git commit -m "feat: PIL crop rendering for concept boxes"
```

---

### Task 7: OCR client (Claude API, injectable)

**Files:**
- Create: `scripts/mindmap_vault/ocr.py`
- Test: `tests/mindmap_vault/test_ocr.py`

**Interfaces:**
- Consumes: PNG bytes, `config`, `model.OcrResult`; `anthropic` SDK at runtime only.
- Produces: `ocr.ClaudeOcr(client=None)` with `.transcribe(png_bytes) -> OcrResult` (raises `ocr.OcrError` after `OCR_RETRIES` failures) and `.calls` (int, for cost reporting); `ocr.FakeOcr(results)` with the same interface for tests — pops queued `OcrResult`s.

- [ ] **Step 1: Write the failing tests**

`tests/mindmap_vault/test_ocr.py`:
```python
import types

import pytest

from scripts.mindmap_vault import ocr
from scripts.mindmap_vault.model import OcrResult


class _StubBlock:
    type = "tool_use"

    def __init__(self, data):
        self.input = data


class _StubMessages:
    def __init__(self, responses):
        self._responses = responses
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return types.SimpleNamespace(content=[_StubBlock(r)])


def _client(responses):
    return types.SimpleNamespace(messages=_StubMessages(responses))


def test_transcribe_parses_tool_output():
    client = _client([{"title": "Bayes", "text": "$p(a|b)$", "is_concept_box": True}])
    o = ocr.ClaudeOcr(client=client)
    r = o.transcribe(b"png")
    assert r == OcrResult(title="Bayes", text="$p(a|b)$", is_concept_box=True, context=None)
    assert o.calls == 1
    req = client.messages.requests[0]
    assert req["model"] == "claude-sonnet-5"
    assert req["tool_choice"]["name"] == "record_transcription"


def test_transcribe_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(ocr.time, "sleep", lambda s: None)
    client = _client([RuntimeError("boom"),
                      {"title": "T", "text": "x", "is_concept_box": True}])
    r = ocr.ClaudeOcr(client=client).transcribe(b"png")
    assert r.title == "T"


def test_transcribe_raises_after_retries(monkeypatch):
    monkeypatch.setattr(ocr.time, "sleep", lambda s: None)
    client = _client([RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])
    with pytest.raises(ocr.OcrError):
        ocr.ClaudeOcr(client=client).transcribe(b"png")


def test_fake_ocr_pops_in_order():
    f = ocr.FakeOcr([OcrResult("A", "a", True), OcrResult("B", "b", False)])
    assert f.transcribe(b"1").title == "A"
    assert f.transcribe(b"2").title == "B"
    assert f.calls == 2
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_ocr.py -v
```
Expected: FAIL — `ocr` module missing.

- [ ] **Step 3: Implement `scripts/mindmap_vault/ocr.py`**

```python
import base64
import time

from scripts.mindmap_vault import config
from scripts.mindmap_vault.model import OcrResult


class OcrError(Exception):
    pass


_PROMPT = """This image is a crop of ONE hand-drawn concept box from a physics/CS research mindmap.
Transcribe the handwriting verbatim — do not paraphrase, expand, or correct it.
Use LaTeX ($...$) for equations and mathematical symbols.
- title: the box's heading (usually the first or most prominent line)
- text: the full transcription, preserving line breaks
- is_concept_box: false if this is NOT actually a concept box with handwritten notes
  (e.g. a stray mark, an underline, or a frame around a photo with no writing)
- context: at most ONE short sentence of clarification, ONLY if the transcription
  alone would be cryptic; otherwise omit it entirely."""

_TOOL = {
    "name": "record_transcription",
    "description": "Record the transcription of one handwritten concept box.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "text": {"type": "string"},
            "is_concept_box": {"type": "boolean"},
            "context": {"type": "string"},
        },
        "required": ["title", "text", "is_concept_box"],
    },
}


class ClaudeOcr:
    def __init__(self, client=None, model=config.OCR_MODEL):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.calls = 0

    def transcribe(self, png_bytes):
        last = None
        for attempt in range(config.OCR_RETRIES):
            try:
                self.calls += 1
                msg = self.client.messages.create(
                    model=self.model,
                    max_tokens=config.OCR_MAX_TOKENS,
                    tools=[_TOOL],
                    tool_choice={"type": "tool", "name": "record_transcription"},
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {
                                "type": "base64", "media_type": "image/png",
                                "data": base64.b64encode(png_bytes).decode()}},
                            {"type": "text", "text": _PROMPT},
                        ],
                    }],
                )
                block = next(b for b in msg.content if b.type == "tool_use")
                d = block.input
                return OcrResult(
                    title=d["title"],
                    text=d["text"],
                    is_concept_box=bool(d["is_concept_box"]),
                    context=d.get("context") or None,
                )
            except Exception as e:  # noqa: BLE001 — retry any API failure
                last = e
                time.sleep(2 ** attempt)
        raise OcrError(f"OCR failed after {config.OCR_RETRIES} attempts: {last}")


class FakeOcr:
    """Test double: returns queued OcrResults in order."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def transcribe(self, png_bytes):
        self.calls += 1
        return self._results.pop(0)
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_ocr.py -v
```
Expected: all PASS (no network involved).

- [ ] **Step 5: Commit**

```bash
git add scripts/mindmap_vault/ocr.py tests/mindmap_vault/test_ocr.py
git commit -m "feat: Claude API OCR client with retries and test fake"
```

---

### Task 8: Manifest and incremental reconcile

**Files:**
- Create: `scripts/mindmap_vault/manifest.py`
- Test: `tests/mindmap_vault/test_manifest.py`

**Interfaces:**
- Consumes: boxes (with member/border/image ids), a manifest dict.
- Produces:
  - `manifest.load(vault_path) -> dict` / `manifest.save(vault_path, data)` — file at `<vault>/.pipeline/manifest.json`; `load` returns `{"version": 2, "sources": {}}` when absent.
  - `manifest.content_hash(box) -> str` — sha256 hex[:16] of sorted border+member+image ids.
  - `manifest.reconcile(source, boxes) -> tuple[list[Decision], list[str]]` where `source` is `data["sources"][stem]` (created by caller as `{"next_box": 1, "boxes": {}}` when new). `Decision` is a dataclass `(state, box_id, box, ocr)` with `state ∈ {"unchanged","moved","changed","new"}` and `ocr` the reusable OCR dict or `None` (None ⇔ needs OCR: states changed/new, or a prior `pending`). Second element: deleted box_ids. `reconcile` also rewrites `source["boxes"]` to the new geometry (preserving `slug` and `ocr` where reused) and bumps `next_box`.

- [ ] **Step 1: Write the failing tests**

`tests/mindmap_vault/test_manifest.py`:
```python
import copy

from scripts.mindmap_vault import manifest
from scripts.mindmap_vault.model import Box


def _box(border, members, bbox):
    return Box(border_ids=border, bbox=bbox, member_ids=members)


def _fresh_source():
    return {"next_box": 1, "boxes": {}}


def test_load_missing(tmp_path):
    assert manifest.load(tmp_path) == {"version": 2, "sources": {}}


def test_save_load_roundtrip(tmp_path):
    data = {"version": 2, "sources": {"cs": {"next_box": 3, "boxes": {}}}}
    manifest.save(tmp_path, data)
    assert manifest.load(tmp_path) == data


def test_new_boxes_get_sequential_ids():
    src = _fresh_source()
    decisions, deleted = manifest.reconcile(
        src, [_box(["a"], ["t1"], (0, 0, 10, 10)), _box(["b"], [], (20, 0, 30, 10))]
    )
    assert [d.state for d in decisions] == ["new", "new"]
    assert [d.box_id for d in decisions] == ["b001", "b002"]
    assert deleted == []
    assert src["next_box"] == 3


def test_unchanged_box_reuses_ocr():
    src = _fresh_source()
    b = _box(["a"], ["t1"], (0, 0, 10, 10))
    manifest.reconcile(src, [b])
    src["boxes"]["b001"]["ocr"] = {"title": "T", "text": "x", "context": None, "pending": False}
    decisions, _ = manifest.reconcile(src, [copy.deepcopy(b)])
    d = decisions[0]
    assert d.state == "unchanged"
    assert d.box_id == "b001"
    assert d.ocr == {"title": "T", "text": "x", "context": None, "pending": False}


def test_moved_box_keeps_ocr_updates_bbox():
    src = _fresh_source()
    b = _box(["a"], ["t1"], (0, 0, 10, 10))
    manifest.reconcile(src, [b])
    src["boxes"]["b001"]["ocr"] = {"title": "T", "text": "x", "context": None, "pending": False}
    moved = _box(["a"], ["t1"], (100, 100, 110, 110))
    decisions, _ = manifest.reconcile(src, [moved])
    assert decisions[0].state == "moved"
    assert decisions[0].ocr is not None
    assert src["boxes"]["b001"]["bbox"] == [100, 100, 110, 110]


def test_changed_box_keeps_id_drops_ocr():
    src = _fresh_source()
    manifest.reconcile(src, [_box(["a"], ["t1", "t2", "t3"], (0, 0, 10, 10))])
    src["boxes"]["b001"]["ocr"] = {"title": "T", "text": "x", "context": None, "pending": False}
    changed = _box(["a"], ["t1", "t2", "t4"], (0, 0, 10, 10))
    decisions, _ = manifest.reconcile(src, [changed])
    assert decisions[0].state == "changed"
    assert decisions[0].box_id == "b001"
    assert decisions[0].ocr is None


def test_deleted_box_reported():
    src = _fresh_source()
    manifest.reconcile(src, [_box(["a"], [], (0, 0, 10, 10)), _box(["b"], [], (20, 0, 30, 10))])
    decisions, deleted = manifest.reconcile(src, [_box(["a"], [], (0, 0, 10, 10))])
    assert deleted == ["b002"]
    assert "b002" not in src["boxes"]


def test_pending_ocr_forces_redo():
    src = _fresh_source()
    b = _box(["a"], [], (0, 0, 10, 10))
    manifest.reconcile(src, [b])
    src["boxes"]["b001"]["ocr"] = {"title": "", "text": "", "context": None, "pending": True}
    decisions, _ = manifest.reconcile(src, [copy.deepcopy(b)])
    assert decisions[0].ocr is None
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_manifest.py -v
```
Expected: FAIL — `manifest` module missing.

- [ ] **Step 3: Implement `scripts/mindmap_vault/manifest.py`**

```python
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Decision:
    state: str          # unchanged | moved | changed | new
    box_id: str
    box: object         # model.Box
    ocr: dict | None    # reusable OCR payload, or None if OCR is needed


def _path(vault):
    return Path(vault) / ".pipeline" / "manifest.json"


def load(vault):
    p = _path(vault)
    if not p.exists():
        return {"version": 2, "sources": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def save(vault, data):
    p = _path(vault)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")


def _all_ids(box):
    return sorted(list(box.border_ids) + list(box.member_ids) + list(box.image_ids))


def content_hash(box):
    return hashlib.sha256(",".join(_all_ids(box)).encode()).hexdigest()[:16]


def _jaccard(a, b):
    a, b = set(a), set(b)
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def reconcile(source, boxes):
    old = source["boxes"]
    by_hash = {rec["hash"]: bid for bid, rec in old.items()}
    decisions = []
    matched_old = set()
    unmatched_new = []

    for box in boxes:
        h = content_hash(box)
        bid = by_hash.get(h)
        if bid is not None and bid not in matched_old:
            rec = old[bid]
            state = "unchanged" if list(rec["bbox"]) == list(box.bbox) else "moved"
            ocr = rec.get("ocr")
            if ocr is not None and ocr.get("pending"):
                ocr = None
            decisions.append(Decision(state, bid, box, ocr))
            matched_old.add(bid)
        else:
            unmatched_new.append(box)

    for box in unmatched_new:
        ids = _all_ids(box)
        best, best_j = None, 0.0
        for bid, rec in old.items():
            if bid in matched_old:
                continue
            j = _jaccard(ids, rec["stroke_ids"])
            if j > best_j:
                best, best_j = bid, j
        if best is not None and best_j > 0.5:
            decisions.append(Decision("changed", best, box, None))
            matched_old.add(best)
        else:
            bid = f"b{source['next_box']:03d}"
            source["next_box"] += 1
            decisions.append(Decision("new", bid, box, None))

    deleted = sorted(bid for bid in old if bid not in matched_old)

    new_boxes = {}
    for d in decisions:
        prev = old.get(d.box_id, {})
        new_boxes[d.box_id] = {
            "hash": content_hash(d.box),
            "stroke_ids": _all_ids(d.box),
            "bbox": list(d.box.bbox),
            "slug": prev.get("slug"),
            "ocr": d.ocr,  # None means: OCR still to run this pass
        }
        d.box.box_id = d.box_id
    source["boxes"] = new_boxes

    order = {bid: i for i, bid in enumerate(new_boxes)}
    decisions.sort(key=lambda d: order[d.box_id])
    return decisions, deleted
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_manifest.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/mindmap_vault/manifest.py tests/mindmap_vault/test_manifest.py
git commit -m "feat: manifest with stable box ids and incremental reconcile"
```

---

### Task 9: Vault + JSON emitter

**Files:**
- Create: `scripts/mindmap_vault/emit.py`
- Test: `tests/mindmap_vault/test_emit.py`

**Interfaces:**
- Consumes: `source` manifest dict (each `boxes[bid]` now has non-None `ocr` unless pending), edges as `list[tuple[src_bid, dst_bid, directed]]`, vault path, stem (e.g. `"cs-stat"`), viewbox, json output path.
- Produces: `emit.emit(vault, stem, source, edges, viewbox, json_path, assets)` where `assets` is `dict[bid -> list[(filename, png_bytes)]]`. Behavior:
  - Assigns/keeps `source["boxes"][bid]["slug"]` — slugify title on first assignment, unique across the whole `concepts/` dir, never changed once set.
  - Writes every active note to `<vault>/concepts/<slug>.md` (format below), regenerated deterministically each run.
  - `emit.archive(vault, source_slugs, deleted_bids)` — not needed as separate API; instead `emit.emit` takes `deleted_slugs: list[str]` and moves those files into `concepts/_archived/`.
  - Writes `<vault>/mocs/<stem>.md`, regenerates `<vault>/index.md`, writes assets to `<vault>/assets/`, writes the JSON index to `json_path`.
- Note format (exact):

```
---
id: <stem>/<bid>
source: <stem>
bbox: [x0, y0, x1, y1]
---
# <Title>

<text>

*context:* <context>          ← line present only when context is non-empty

→ [[slug_a]] [[slug_b]]       ← line present only when the box has outgoing/undirected links
```

- JSON index format (exact, written with `json.dumps(..., indent=1)`):

```json
{
  "svg": "<stem>.svg",
  "viewBox": [x, y, w, h],
  "concepts": [
    {"id": "b001", "slug": "...", "title": "...", "text": "...", "context": null,
     "bbox": [x0, y0, x1, y1], "links_out": ["b002"], "links_in": []}
  ]
}
```
  `links_out` = directed edges from this box + undirected edges touching it; `links_in` = directed edges into this box + undirected edges touching it (undirected appears in both lists on both ends). Boxes with `ocr.pending` or `ocr` missing get `title: "(pending OCR)"`, empty text, and are still included (bbox is valid).

- [ ] **Step 1: Write the failing tests**

`tests/mindmap_vault/test_emit.py`:
```python
import json

from scripts.mindmap_vault import emit


def _source():
    return {
        "next_box": 3,
        "boxes": {
            "b001": {"hash": "h1", "stroke_ids": ["a"], "bbox": [0, 0, 10, 10],
                     "slug": None,
                     "ocr": {"title": "Bayes Theorem", "text": "$p(a|b)p(b)=p(b|a)p(a)$",
                             "context": None, "pending": False}},
            "b002": {"hash": "h2", "stroke_ids": ["b"], "bbox": [20, 0, 30, 10],
                     "slug": None,
                     "ocr": {"title": "Prior", "text": "belief before data",
                             "context": "Refers to Bayesian priors.", "pending": False}},
        },
    }


def test_emit_writes_notes_and_json(tmp_path):
    vault = tmp_path / "vault"
    json_path = tmp_path / "cs-stat-index.json"
    src = _source()
    emit.emit(vault, "cs-stat", src, [("b001", "b002", True)],
              (0, 0, 500, 400), json_path, assets={}, deleted_slugs=[])

    note = (vault / "concepts" / "bayes_theorem.md").read_text()
    assert "id: cs-stat/b001" in note
    assert "# Bayes Theorem" in note
    assert "$p(a|b)p(b)=p(b|a)p(a)$" in note
    assert "→ [[prior]]" in note
    assert "*context:*" not in note

    prior = (vault / "concepts" / "prior.md").read_text()
    assert "*context:* Refers to Bayesian priors." in prior
    assert "→" not in prior  # no outgoing links

    idx = json.loads(json_path.read_text())
    assert idx["svg"] == "cs-stat.svg"
    assert idx["viewBox"] == [0, 0, 500, 400]
    c1 = next(c for c in idx["concepts"] if c["id"] == "b001")
    assert c1["links_out"] == ["b002"] and c1["links_in"] == []
    c2 = next(c for c in idx["concepts"] if c["id"] == "b002")
    assert c2["links_in"] == ["b001"] and c2["links_out"] == []

    assert src["boxes"]["b001"]["slug"] == "bayes_theorem"
    assert (vault / "mocs" / "cs-stat.md").exists()
    assert (vault / "index.md").exists()


def test_undirected_links_both_ways(tmp_path):
    src = _source()
    emit.emit(tmp_path / "v", "cs-stat", src, [("b001", "b002", False)],
              (0, 0, 500, 400), tmp_path / "i.json", assets={}, deleted_slugs=[])
    note1 = (tmp_path / "v" / "concepts" / "bayes_theorem.md").read_text()
    note2 = (tmp_path / "v" / "concepts" / "prior.md").read_text()
    assert "[[prior]]" in note1
    assert "[[bayes_theorem]]" in note2


def test_slug_stable_and_unique(tmp_path):
    src = _source()
    src["boxes"]["b002"]["slug"] = "bayes_theorem"  # simulate collision from earlier run
    emit.emit(tmp_path / "v", "cs-stat", src, [], (0, 0, 1, 1),
              tmp_path / "i.json", assets={}, deleted_slugs=[])
    assert src["boxes"]["b002"]["slug"] == "bayes_theorem"      # untouched
    assert src["boxes"]["b001"]["slug"] == "bayes_theorem_2"    # deduped


def test_archive_moves_note(tmp_path):
    vault = tmp_path / "v"
    src = _source()
    emit.emit(vault, "cs-stat", src, [], (0, 0, 1, 1), tmp_path / "i.json",
              assets={}, deleted_slugs=[])
    # reconcile would have removed the deleted record before emit runs again
    del src["boxes"]["b002"]
    emit.emit(vault, "cs-stat", src, [], (0, 0, 1, 1), tmp_path / "i.json",
              assets={}, deleted_slugs=["prior"])
    assert not (vault / "concepts" / "prior.md").exists()
    assert (vault / "concepts" / "_archived" / "prior.md").exists()


def test_pending_box_included_with_stub(tmp_path):
    src = _source()
    src["boxes"]["b001"]["ocr"] = None
    emit.emit(tmp_path / "v", "cs-stat", src, [], (0, 0, 1, 1),
              tmp_path / "i.json", assets={}, deleted_slugs=[])
    idx = json.loads((tmp_path / "i.json").read_text())
    c1 = next(c for c in idx["concepts"] if c["id"] == "b001")
    assert c1["title"] == "(pending OCR)"


def test_assets_written(tmp_path):
    src = _source()
    emit.emit(tmp_path / "v", "cs-stat", src, [], (0, 0, 1, 1), tmp_path / "i.json",
              assets={"b001": [("b001_1.png", b"\x89PNGdata")]}, deleted_slugs=[])
    assert (tmp_path / "v" / "assets" / "b001_1.png").read_bytes() == b"\x89PNGdata"
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_emit.py -v
```
Expected: FAIL — `emit` module missing.

- [ ] **Step 3: Implement `scripts/mindmap_vault/emit.py`**

```python
import json
import re
from pathlib import Path


def _slugify(title, taken):
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "concept"
    slug = base
    n = 2
    while slug in taken:
        slug = f"{base}_{n}"
        n += 1
    return slug


def _assign_slugs(vault, source):
    concepts = Path(vault) / "concepts"
    taken = {p.stem for p in concepts.glob("*.md")} if concepts.exists() else set()
    taken |= {p.stem for p in (concepts / "_archived").glob("*.md")} if (concepts / "_archived").exists() else set()
    taken |= {rec["slug"] for rec in source["boxes"].values() if rec.get("slug")}
    for rec in source["boxes"].values():
        if rec.get("slug"):
            continue
        title = (rec.get("ocr") or {}).get("title") or "concept"
        rec["slug"] = _slugify(title, taken)
        taken.add(rec["slug"])


def _link_maps(box_ids, edges):
    out = {b: [] for b in box_ids}
    inc = {b: [] for b in box_ids}
    for src_bid, dst_bid, directed in edges:
        if src_bid not in out or dst_bid not in out:
            continue
        out[src_bid].append(dst_bid)
        inc[dst_bid].append(src_bid)
        if not directed:
            out[dst_bid].append(src_bid)
            inc[src_bid].append(dst_bid)
    return out, inc


def _note(stem, bid, rec, out_slugs):
    ocr = rec.get("ocr") or {}
    pending = rec.get("ocr") is None or ocr.get("pending")
    title = "(pending OCR)" if pending else ocr["title"]
    text = "" if pending else ocr["text"]
    bbox = ", ".join(str(round(v, 1)) for v in rec["bbox"])
    lines = [
        "---",
        f"id: {stem}/{bid}",
        f"source: {stem}",
        f"bbox: [{bbox}]",
        "---",
        f"# {title}",
        "",
    ]
    if text:
        lines += [text, ""]
    if not pending and ocr.get("context"):
        lines += [f"*context:* {ocr['context']}", ""]
    if out_slugs:
        lines += ["→ " + " ".join(f"[[{s}]]" for s in out_slugs), ""]
    return "\n".join(lines)


def emit(vault, stem, source, edges, viewbox, json_path, assets, deleted_slugs):
    vault = Path(vault)
    concepts = vault / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    (vault / "mocs").mkdir(exist_ok=True)
    (vault / "assets").mkdir(exist_ok=True)

    archived = concepts / "_archived"
    for slug in deleted_slugs:
        src_file = concepts / f"{slug}.md"
        if src_file.exists():
            archived.mkdir(exist_ok=True)
            src_file.rename(archived / f"{slug}.md")

    _assign_slugs(vault, source)
    boxes = source["boxes"]
    out, inc = _link_maps(list(boxes), edges)
    slug_of = {bid: rec["slug"] for bid, rec in boxes.items()}

    for bid, rec in boxes.items():
        out_slugs = [slug_of[t] for t in out[bid]]
        (concepts / f"{rec['slug']}.md").write_text(
            _note(stem, bid, rec, out_slugs), encoding="utf-8"
        )

    for bid, files in assets.items():
        for fname, data in files:
            (vault / "assets" / fname).write_bytes(data)

    moc = [f"# MOC — {stem}", "",
           f"Generated from `{stem}.svg` — {len(boxes)} concepts, {len(edges)} edges.",
           "", "## Concepts", ""]
    moc += [f"- [[{rec['slug']}]] ({bid})" for bid, rec in sorted(boxes.items())]
    moc += ["", "## Edges", ""]
    for src_bid, dst_bid, directed in edges:
        if src_bid in slug_of and dst_bid in slug_of:
            arrow = "→" if directed else "—"
            moc.append(f"- [[{slug_of[src_bid]}]] {arrow} [[{slug_of[dst_bid]}]]")
    (vault / "mocs" / f"{stem}.md").write_text("\n".join(moc) + "\n", encoding="utf-8")

    hub = ["# Index — classic_research", "",
           "Knowledge graph generated from handwritten mindmaps (Concepts app exports).", ""]
    for moc_file in sorted((vault / "mocs").glob("*.md")):
        hub.append(f"- [[mocs/{moc_file.stem}]]")
    (vault / "index.md").write_text("\n".join(hub) + "\n", encoding="utf-8")

    index = {
        "svg": f"{stem}.svg",
        "viewBox": list(viewbox),
        "concepts": [],
    }
    for bid, rec in sorted(boxes.items()):
        ocr = rec.get("ocr") or {}
        pending = rec.get("ocr") is None or ocr.get("pending")
        index["concepts"].append({
            "id": bid,
            "slug": rec["slug"],
            "title": "(pending OCR)" if pending else ocr["title"],
            "text": "" if pending else ocr["text"],
            "context": None if pending else ocr.get("context"),
            "bbox": [round(v, 1) for v in rec["bbox"]],
            "links_out": out[bid],
            "links_in": inc[bid],
        })
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(index, indent=1), encoding="utf-8")
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_emit.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/mindmap_vault/emit.py tests/mindmap_vault/test_emit.py
git commit -m "feat: vault note/MOC/JSON-index emitter with stable slugs"
```

---

### Task 10: Orchestrator CLI + offline integration tests

**Files:**
- Create: `scripts/mindmap_vault/update.py`
- Test: `tests/mindmap_vault/test_update.py`

**Interfaces:**
- Consumes: every previous module.
- Produces: `update.run(svg_path, vault, ocr_client=None, dry_run=False, limit=None, bg=config.CROP_BG) -> dict` summary (`{"new": int, "changed": int, "unchanged": int, "moved": int, "deleted": int, "edges": int, "review": int, "ocr_calls": int, "pending": int}`), and a `main()` CLI:

```
python -m scripts.mindmap_vault.update <svg> [--vault PATH] [--dry-run] [--limit N] [--bg COLOR]
```
  - JSON index path: `<repo_root>/static/mindmaps/<stem>-index.json` (repo root = `Path(__file__).resolve().parents[2]`).
  - v1 backup: if vault exists, is non-empty, and has no `.pipeline/manifest.json`, rename the whole directory to `<vault name>_v1_backup` next to it (abort with a clear error if the backup already exists), then create a fresh vault dir.
  - Crops cached at `<vault>/.pipeline/crops/<stem>/<bid>.png`; re-rendered only for decisions needing OCR.
  - Review messages written to `<vault>/.pipeline/review.md` (overwritten per run).
  - OCR failures (`OcrError`) and boxes beyond `--limit` → `ocr = {"title": "", "text": "", "context": None, "pending": True}`; process exits 2 when `pending > 0`, else 0.
  - Boxes whose OCR returns `is_concept_box=False` are removed from `source["boxes"]` and from edges (logged in the summary as part of `review` count? No — tracked separately: add `"dropped": int` to the summary).
  - Assets: for each decision needing OCR whose box has `image_ids`, decode each image def and pass `{bid: [(f"{bid}_{n}.png", bytes), ...]}` to emit.

- [ ] **Step 1: Write the failing tests**

`tests/mindmap_vault/test_update.py`:
```python
import json

from scripts.mindmap_vault import update
from scripts.mindmap_vault.model import OcrResult
from scripts.mindmap_vault.ocr import FakeOcr


def _fake3():
    return FakeOcr([
        OcrResult("Alpha", "alpha text", True),
        OcrResult("Beta", "beta text $x^2$", True),
        OcrResult("Gamma", "gamma text", True),
    ])


def test_full_run_offline(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "static" / "synth-index.json"
    summary = update.run(synthetic_svg, vault, ocr_client=_fake3(), json_path=json_out)
    assert summary["new"] == 3
    assert summary["edges"] == 2
    assert summary["pending"] == 0
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 3
    titles = {c["title"] for c in idx["concepts"]}
    assert titles == {"Alpha", "Beta", "Gamma"}
    notes = list((vault / "concepts").glob("*.md"))
    assert len(notes) == 3


def test_second_run_zero_ocr_and_stable_output(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    json_out = tmp_path / "static" / "synth-index.json"
    update.run(synthetic_svg, vault, ocr_client=_fake3(), json_path=json_out)
    first = json_out.read_text()
    first_notes = {p.name: p.read_text() for p in (vault / "concepts").glob("*.md")}

    empty_fake = FakeOcr([])  # would raise IndexError if any OCR happened
    summary = update.run(synthetic_svg, vault, ocr_client=empty_fake, json_path=json_out)
    assert summary["unchanged"] == 3
    assert empty_fake.calls == 0
    assert json_out.read_text() == first
    assert {p.name: p.read_text() for p in (vault / "concepts").glob("*.md")} == first_notes


def test_non_concept_box_dropped(synthetic_svg, tmp_path):
    fake = FakeOcr([
        OcrResult("Alpha", "a", True),
        OcrResult("junk", "", False),
        OcrResult("Gamma", "g", True),
    ])
    json_out = tmp_path / "i.json"
    summary = update.run(synthetic_svg, tmp_path / "vault", ocr_client=fake,
                         json_path=json_out)
    assert summary["dropped"] == 1
    idx = json.loads(json_out.read_text())
    assert len(idx["concepts"]) == 2


def test_dry_run_marks_pending(synthetic_svg, tmp_path):
    json_out = tmp_path / "i.json"
    summary = update.run(synthetic_svg, tmp_path / "vault", ocr_client=None,
                         json_path=json_out, dry_run=True)
    assert summary["pending"] == 3
    assert summary["ocr_calls"] == 0
    idx = json.loads(json_out.read_text())
    assert all(c["title"] == "(pending OCR)" for c in idx["concepts"])


def test_v1_backup(synthetic_svg, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "old_note.md").write_text("v1 content")
    update.run(synthetic_svg, vault, ocr_client=_fake3(), json_path=tmp_path / "i.json")
    backup = tmp_path / "vault_v1_backup"
    assert (backup / "old_note.md").read_text() == "v1 content"
    assert not (vault / "old_note.md").exists()
    assert (vault / ".pipeline" / "manifest.json").exists()
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_update.py -v
```
Expected: FAIL — `update` module missing.

- [ ] **Step 3: Implement `scripts/mindmap_vault/update.py`**

```python
import argparse
import io
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.mindmap_vault import (  # noqa: E402
    arrows, bind, boxes, config, emit, manifest, parse, render,
)
from scripts.mindmap_vault.ocr import ClaudeOcr, OcrError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = Path("/home/n/Documents/vault/classic_research")


def _backup_v1(vault):
    vault = Path(vault)
    if not vault.exists():
        return
    if (vault / ".pipeline" / "manifest.json").exists():
        return
    if not any(vault.iterdir()):
        return
    backup = vault.parent / f"{vault.name}_v1_backup"
    if backup.exists():
        raise SystemExit(
            f"refusing to overwrite existing backup at {backup}; move it aside first"
        )
    vault.rename(backup)
    print(f"archived pre-pipeline vault to {backup}")


def run(svg_path, vault, ocr_client=None, json_path=None, dry_run=False,
        limit=None, bg=config.CROP_BG):
    svg_path = Path(svg_path)
    vault = Path(vault)
    stem = svg_path.stem
    if json_path is None:
        json_path = REPO_ROOT / "static" / "mindmaps" / f"{stem}-index.json"

    _backup_v1(vault)
    vault.mkdir(parents=True, exist_ok=True)

    parsed = parse.parse_svg(svg_path)
    found = boxes.find_boxes(parsed.strokes)
    edge_list, review = arrows.find_edges(parsed.strokes, found)
    bind.bind(parsed.strokes, parsed.images, found, edge_list)

    data = manifest.load(vault)
    source = data["sources"].setdefault(stem, {"next_box": 1, "boxes": {}})
    # capture slugs before reconcile rewrites the boxes dict (deleted records vanish)
    old_slugs = {bid: rec.get("slug") for bid, rec in source["boxes"].items()}
    decisions, deleted = manifest.reconcile(source, found)
    deleted_slugs = [old_slugs[bid] for bid in deleted if old_slugs.get(bid)]

    strokes_by_id = {s.sid: s for s in parsed.strokes}
    images_by_id = {i.iid: i for i in parsed.images}
    crops_dir = vault / ".pipeline" / "crops" / stem
    crops_dir.mkdir(parents=True, exist_ok=True)

    if ocr_client is None and not dry_run:
        ocr_client = ClaudeOcr()

    summary = {"new": 0, "changed": 0, "unchanged": 0, "moved": 0,
               "deleted": len(deleted), "edges": 0, "review": len(review),
               "ocr_calls": 0, "pending": 0, "dropped": 0}
    assets = {}
    dropped_bids = set()

    for n, d in enumerate(decisions):
        summary[d.state] += 1
        if d.ocr is not None:
            source["boxes"][d.box_id]["ocr"] = d.ocr
            continue
        crop = render.render_box(d.box, strokes_by_id, images_by_id, svg_path, bg=bg)
        crop.save(crops_dir / f"{d.box_id}.png")
        over_limit = limit is not None and summary["ocr_calls"] >= limit
        if dry_run or over_limit:
            source["boxes"][d.box_id]["ocr"] = {
                "title": "", "text": "", "context": None, "pending": True}
            summary["pending"] += 1
            continue
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        try:
            r = ocr_client.transcribe(buf.getvalue())
            summary["ocr_calls"] += 1
        except OcrError as e:
            print(f"  OCR failed for {d.box_id}: {e}", file=sys.stderr)
            source["boxes"][d.box_id]["ocr"] = {
                "title": "", "text": "", "context": None, "pending": True}
            summary["pending"] += 1
            continue
        if not r.is_concept_box:
            dropped_bids.add(d.box_id)
            summary["dropped"] += 1
            continue
        source["boxes"][d.box_id]["ocr"] = {
            "title": r.title, "text": r.text, "context": r.context, "pending": False}
        for i, iid in enumerate(d.box.image_ids, start=1):
            ref = images_by_id[iid]
            assets.setdefault(d.box_id, []).append(
                (f"{d.box_id}_{i}.png", parse.load_image_png(svg_path, ref.def_id)))

    for bid in dropped_bids:
        source["boxes"].pop(bid, None)

    # Edge.src/dst index into `found`; reconcile stamped .box_id onto those
    # same Box objects, so the mapping is direct.
    id_edges = []
    for e in edge_list:
        s_bid = found[e.src].box_id
        d_bid = found[e.dst].box_id
        if s_bid in source["boxes"] and d_bid in source["boxes"]:
            id_edges.append((s_bid, d_bid, e.directed))
    summary["edges"] = len(id_edges)

    review_path = vault / ".pipeline" / "review.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(
        "# Ambiguous connectors\n\n" + "\n".join(f"- {m}" for m in review) + "\n",
        encoding="utf-8")

    emit.emit(vault, stem, source, id_edges, parsed.viewbox, json_path,
              assets, deleted_slugs)
    manifest.save(vault, data)

    cost = summary["ocr_calls"] * config.OCR_COST_ESTIMATE
    print(f"{stem}: +{summary['new']} new, ~{summary['changed']} changed, "
          f"={summary['unchanged']} unchanged, {summary['moved']} moved, "
          f"-{summary['deleted']} deleted, {summary['dropped']} dropped, "
          f"{summary['edges']} edges, {summary['review']} to review, "
          f"{summary['ocr_calls']} OCR calls (~${cost:.2f}), "
          f"{summary['pending']} pending")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ingest/update a mindmap SVG into the vault.")
    ap.add_argument("svg")
    ap.add_argument("--vault", default=str(DEFAULT_VAULT))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--bg", default=config.CROP_BG)
    args = ap.parse_args(argv)
    summary = run(args.svg, args.vault, dry_run=args.dry_run,
                  limit=args.limit, bg=args.bg)
    return 2 if summary["pending"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run all pipeline tests, verify they pass**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/ -v
```
Expected: all PASS, including the round-trip test proving a second run makes zero OCR calls and byte-identical output.

- [ ] **Step 5: Commit**

```bash
git add scripts/mindmap_vault/update.py tests/mindmap_vault/test_update.py
git commit -m "feat: incremental update orchestrator CLI with v1 backup"
```

---

### Task 11: Calibration against the real cs-stat.svg + golden test

**Files:**
- Create: `tests/mindmap_vault/test_golden_cs_stat.py`
- Possibly modify: `scripts/mindmap_vault/config.py` (threshold tuning)

**Interfaces:**
- Consumes: the real `static/mindmaps/cs-stat.svg` and the whole pipeline in `--dry-run` mode (no API key needed).
- Produces: frozen golden counts in the test; tuned constants.

- [ ] **Step 1: Write the golden parse test (counts already verified)**

`tests/mindmap_vault/test_golden_cs_stat.py`:
```python
from pathlib import Path

import pytest

from scripts.mindmap_vault import arrows, boxes, parse

CS_STAT = Path(__file__).resolve().parents[2] / "static" / "mindmaps" / "cs-stat.svg"

pytestmark = pytest.mark.golden


@pytest.fixture(scope="module")
def parsed():
    if not CS_STAT.exists():
        pytest.skip("cs-stat.svg not present")
    return parse.parse_svg(CS_STAT)


def test_stroke_count(parsed):
    assert len(parsed.strokes) == 77461 + 4069


def test_image_count(parsed):
    assert len(parsed.images) == 20


def test_viewbox(parsed):
    assert parsed.viewbox == (-5725.477, -3022.085, 11890.705, 10977.893)


def test_box_and_edge_counts(parsed):
    bs = boxes.find_boxes(parsed.strokes)
    edges, review = arrows.find_edges(parsed.strokes, bs)
    # FROZEN during calibration (Step 3). Band, not exact, to allow small
    # threshold refinements without churn.
    assert 80 <= len(bs) <= 160
    assert len(edges) >= 20
```

- [ ] **Step 2: Run the golden test**

```bash
micromamba run -n django-nihar-website pytest tests/mindmap_vault/test_golden_cs_stat.py -v -m golden
```
Expected: parse-count tests PASS immediately. The box/edge test may fail — that is the calibration signal, not a defect in the test.

- [ ] **Step 3: Calibrate**

Run a dry-run ingest into a scratch vault and eyeball the crops:

```bash
micromamba run -n django-nihar-website python -m scripts.mindmap_vault.update \
  static/mindmaps/cs-stat.svg --vault /tmp/claude-cal-vault --dry-run --bg '#000000'
ls /tmp/claude-cal-vault/.pipeline/crops/cs-stat | head -30
```

Open ~15 crops with an image viewer (or the Read tool). Verify each crop is one concept box with legible handwriting. Iterate on `config.py` constants if you see:
- Boxes missed (drawn sloppily) → widen `RECT_RATIO_*`/`PERIM_HUG`/`CLOSURE_FRAC` slightly.
- Text lines misclassified as boxes → raise `MIN_BOX_H` or tighten `PERIM_HUG`.
- Arrows missed → raise `END_TOL`; arrows hallucinated between near boxes → lower it.
Keep the invariant `ARROW_MIN_LEN > HEAD_MAX_LEN`. Re-run the dry-run after each change. Check `/tmp/claude-cal-vault/.pipeline/review.md` — ambiguous connectors listed there are acceptable; silent wrong edges are not.

- [ ] **Step 4: Freeze the golden numbers**

Update `test_box_and_edge_counts` with the calibrated actual counts as a ±10% band around observed values. Run the full suite:

```bash
micromamba run -n django-nihar-website pytest tests/ -v
```
Expected: all PASS (synthetic tests must still pass with tuned constants — if a constant change breaks them, adjust the synthetic fixture geometry to stay representative, not the assertion).

- [ ] **Step 5: Commit**

```bash
git add scripts/mindmap_vault/config.py tests/mindmap_vault/test_golden_cs_stat.py
git commit -m "test: golden counts for cs-stat calibrated against real export"
```

---

### Task 12: Real ingest of cs-stat (uses the API)

**Files:**
- Create (generated): `static/mindmaps/cs-stat-index.json`, vault contents at `/home/n/Documents/vault/classic_research`

**Interfaces:**
- Consumes: `ANTHROPIC_API_KEY` in the environment (ask the user to provide it if unset — do not proceed without it).
- Produces: the committed JSON index the website tasks consume.

- [ ] **Step 1: Preflight**

```bash
test -n "$ANTHROPIC_API_KEY" && echo ok || echo "MISSING KEY - ask user"
ls /home/n/Documents/vault/classic_research
```
If the key is missing, stop and ask the user. The vault still holds v1 content; the first run will archive it to `classic_research_v1_backup` automatically.

- [ ] **Step 2: Smoke-run with a small limit first**

```bash
micromamba run -n django-nihar-website python -m scripts.mindmap_vault.update \
  static/mindmaps/cs-stat.svg --bg '#000000' --limit 5
```
Expected: exit code 2 (pending remain), 5 OCR calls, summary printed. Read 2–3 generated notes in `/home/n/Documents/vault/classic_research/concepts/` and compare against their crops in `.pipeline/crops/cs-stat/` — transcriptions must be faithful. If titles/text look wrong, fix the OCR prompt before burning API budget on the full run.

- [ ] **Step 3: Full run**

```bash
micromamba run -n django-nihar-website python -m scripts.mindmap_vault.update \
  static/mindmaps/cs-stat.svg --bg '#000000'
```
Expected: exit 0, all boxes OCR'd (pending resume automatically). Cost ≈ box_count × $0.015.

- [ ] **Step 4: Sanity checks**

```bash
micromamba run -n django-nihar-website python - <<'EOF'
import json
idx = json.load(open("static/mindmaps/cs-stat-index.json"))
n = len(idx["concepts"])
linked = sum(1 for c in idx["concepts"] if c["links_out"] or c["links_in"])
pend = sum(1 for c in idx["concepts"] if c["title"] == "(pending OCR)")
print(f"{n} concepts, {linked} linked, {pend} pending")
EOF
```
Expected: 0 pending; concept count matching the golden band. Spot-read 5 notes against crops. Suggest the user open the vault in Obsidian to see the graph.

- [ ] **Step 5: Commit the index (vault lives outside the repo)**

```bash
git add static/mindmaps/cs-stat-index.json
git commit -m "feat: generated cs-stat concept index from real ingest"
```

---

### Task 13: Django view passes the index URL

**Files:**
- Modify: `homepage/views.py` (the `mindmap_viewer` function, `mindmaps` dict)
- Modify: `homepage/templates/homepage/mindmap_viewer.html` (one attribute)
- Test: `homepage/tests.py`

**Interfaces:**
- Produces: template context key `index_path` (e.g. `'mindmaps/cs-stat-index.json'`) and `data-index-url` attribute on `#svg-object`, consumed by `mindmap_notes.js`.

- [ ] **Step 1: Write the failing test**

`homepage/tests.py` (replace the default stub file):
```python
from django.test import TestCase


class MindmapViewerIndexTest(TestCase):
    def test_cs_viewer_exposes_index_url(self):
        r = self.client.get("/mindmap/cs/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "data-index-url")
        self.assertContains(r, "cs-stat-index.json")

    def test_physics_viewer_exposes_index_url(self):
        r = self.client.get("/mindmap/physics/")
        self.assertContains(r, "physics-index.json")
```

- [ ] **Step 2: Run test, verify it fails**

```bash
micromamba run -n django-nihar-website python manage.py test homepage -v 2
```
Expected: FAIL — `data-index-url` not found.

- [ ] **Step 3: Implement**

In `homepage/views.py`, add to each entry of the `mindmaps` dict in `mindmap_viewer`:
```python
        'physics': {
            # … existing keys …
            'index_path': 'mindmaps/physics-index.json',
        },
        'cs': {
            # … existing keys …
            'index_path': 'mindmaps/cs-stat-index.json',
        },
```
and to the context:
```python
        'index_path': mindmap['index_path'],
```

In `mindmap_viewer.html`, change the object tag:
```html
<object id="svg-object" type="image/svg+xml" data="{% static svg_path %}"
        data-index-url="{% static index_path %}">
```

- [ ] **Step 4: Run test, verify it passes**

```bash
micromamba run -n django-nihar-website python manage.py test homepage -v 2
```
Expected: PASS (physics-index.json doesn't exist as a file yet — that's fine, the URL is emitted regardless and the JS degrades on 404).

- [ ] **Step 5: Commit**

```bash
git add homepage/views.py homepage/tests.py homepage/templates/homepage/mindmap_viewer.html
git commit -m "feat: expose concept index URL to mindmap viewer"
```

---

### Task 14: Viewer restructure — panzoom wrapper, overlay layer, JS bootstrap

**Files:**
- Modify: `homepage/templates/homepage/mindmap_viewer.html`
- Create: `static/assets/js/mindmap_notes.js`

**Interfaces:**
- Produces: `window.MindmapNotes.init({panzoom, content, container, wrapper})` global, called from the template after Panzoom initializes; `#panzoom-content` div wrapping `#svg-object` + `#overlay-layer`; Panzoom instance now targets `#panzoom-content`.
- Coordinate contract for later tasks (implemented here): `vbToEl(x, y)` maps viewBox coords → element-space pixels inside `#panzoom-content` using letterbox math for `preserveAspectRatio="xMidYMid meet"`:
  `s = min(W/vbW, H/vbH); ox = (W - s*vbW)/2; oy = (H - s*vbH)/2; ex = (x - vbX)*s + ox; ey = (y - vbY)*s + oy` where W,H are `svgObject.clientWidth/Height`.
- Pan calibration contract: `panFactor()` — measured once by nudging `panzoom.pan(x+10, y)` (animate:false) and reading the change in the content's `getBoundingClientRect().left`, then restoring; converts desired screen deltas into pan units regardless of panzoom's internal transform order.

- [ ] **Step 1: Restructure the template**

In `mindmap_viewer.html`:

1. Replace the `#svg-container` inner markup:
```html
<div id="svg-container">
    <div id="panzoom-content">
        <object id="svg-object" type="image/svg+xml" data="{% static svg_path %}"
                data-index-url="{% static index_path %}">
            Your browser does not support SVG
        </object>
        <div id="overlay-layer"></div>
    </div>
</div>
```
2. Add CSS (inside the existing `<style>` block):
```css
#panzoom-content {
    width: 100%;
    height: 100%;
    position: relative;
}
#overlay-layer {
    position: absolute;
    inset: 0;
    pointer-events: none;
}
.concept-target {
    position: absolute;
    pointer-events: auto;
    cursor: pointer;
}
.concept-target.hit {
    background: rgba(74, 158, 255, 0.18);
    border-radius: 2px;
}
.concept-target.hit-active {
    background: rgba(74, 158, 255, 0.38);
}
.concept-target.hit-flash {
    animation: hitflash 0.9s ease-out 2;
}
@keyframes hitflash {
    0%, 100% { background: rgba(74, 158, 255, 0.38); }
    50% { background: rgba(123, 104, 238, 0.6); }
}
```
3. Change the Panzoom target (existing line `panzoomInstance = Panzoom(svgObject, {...})`):
```javascript
        const panzoomContent = document.getElementById('panzoom-content');
        panzoomInstance = Panzoom(panzoomContent, {
            maxScale: 50,
            minScale: 0.1,
            startScale: 10,
            contain: false,
            cursor: 'grab',
        });
```
4. At the end of the `load` handler (after the keyboard shortcuts block), add:
```javascript
        if (window.MindmapNotes) {
            MindmapNotes.init({
                panzoom: panzoomInstance,
                content: panzoomContent,
                container: container,
                wrapper: viewerWrapper,
            });
        }
```
5. Before the existing inline `<script>`, load the new file:
```html
<script src="{% static 'assets/js/mindmap_notes.js' %}"></script>
```

- [ ] **Step 2: Create `static/assets/js/mindmap_notes.js` bootstrap**

```javascript
/* Concept search + notes layer for the mindmap viewer.
   Degrades to a plain viewer when the index JSON is missing. */
window.MindmapNotes = (function () {
    'use strict';

    let panzoom, content, container, wrapper, svgObject;
    let index = null;          // parsed <stem>-index.json
    let byId = {};             // concept id -> concept
    let targets = {};          // concept id -> overlay div
    let panFactorCache = null;

    function vbToEl(x, y) {
        const vb = index.viewBox;
        const W = svgObject.clientWidth, H = svgObject.clientHeight;
        const s = Math.min(W / vb[2], H / vb[3]);
        const ox = (W - s * vb[2]) / 2, oy = (H - s * vb[3]) / 2;
        return [(x - vb[0]) * s + ox, (y - vb[1]) * s + oy];
    }

    function buildOverlays() {
        const layer = document.getElementById('overlay-layer');
        layer.innerHTML = '';
        targets = {};
        for (const c of index.concepts) {
            const [x0, y0] = vbToEl(c.bbox[0], c.bbox[1]);
            const [x1, y1] = vbToEl(c.bbox[2], c.bbox[3]);
            const div = document.createElement('div');
            div.className = 'concept-target';
            div.style.left = x0 + 'px';
            div.style.top = y0 + 'px';
            div.style.width = (x1 - x0) + 'px';
            div.style.height = (y1 - y0) + 'px';
            div.dataset.conceptId = c.id;
            layer.appendChild(div);
            targets[c.id] = div;
        }
    }

    function panFactor() {
        if (panFactorCache) return panFactorCache;
        const before = content.getBoundingClientRect().left;
        const p = panzoom.getPan();
        panzoom.pan(p.x + 10, p.y, { animate: false });
        const after = content.getBoundingClientRect().left;
        panzoom.pan(p.x, p.y, { animate: false });
        panFactorCache = (after - before) / 10 || 1;
        return panFactorCache;
    }

    function centerOn(concept) {
        const [x0, y0] = vbToEl(concept.bbox[0], concept.bbox[1]);
        const [x1, y1] = vbToEl(concept.bbox[2], concept.bbox[3]);
        const cRect = container.getBoundingClientRect();
        const targetScale = Math.min(
            50,
            Math.max(0.1, 0.4 * Math.min(cRect.width / (x1 - x0), cRect.height / (y1 - y0)))
        );
        panzoom.zoom(targetScale, { animate: false });
        panFactorCache = null; // scale change may change the factor
        requestAnimationFrame(function () {
            const el = targets[concept.id].getBoundingClientRect();
            const dx = (cRect.left + cRect.width / 2) - (el.left + el.width / 2);
            const dy = (cRect.top + cRect.height / 2) - (el.top + el.height / 2);
            const f = panFactor();
            const p = panzoom.getPan();
            panzoom.pan(p.x + dx / f, p.y + dy / f, { animate: true });
        });
    }

    function flash(id) {
        const el = targets[id];
        if (!el) return;
        el.classList.remove('hit-flash');
        void el.offsetWidth; // restart animation
        el.classList.add('hit-flash');
    }

    function init(opts) {
        panzoom = opts.panzoom;
        content = opts.content;
        container = opts.container;
        wrapper = opts.wrapper;
        svgObject = document.getElementById('svg-object');
        const url = svgObject.dataset.indexUrl;
        if (!url) return;
        fetch(url)
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(function (data) {
                index = data;
                for (const c of index.concepts) byId[c.id] = c;
                buildOverlays();
                window.addEventListener('resize', buildOverlays);
                if (window.MindmapNotes._onIndexLoaded) {
                    window.MindmapNotes._onIndexLoaded();
                }
            })
            .catch(function () { /* no index — plain viewer */ });
    }

    return {
        init: init,
        centerOn: centerOn,
        flash: flash,
        _state: function () { return { index: index, byId: byId, targets: targets }; },
    };
})();
```

- [ ] **Step 3: Manually verify the viewer still works and overlays land on boxes**

```bash
micromamba run -n django-nihar-website python manage.py runserver
```
Open `http://127.0.0.1:8000/mindmap/cs/` in the browser (use claude-in-chrome tools if available, else ask the user to check):
1. Pan/zoom/pinch/fullscreen all behave exactly as before the change.
2. In devtools console: `MindmapNotes._state().index.concepts.length` returns the concept count.
3. Temporarily add `document.querySelectorAll('.concept-target').forEach(e => e.style.background='rgba(255,0,0,0.3)')` in the console — red rectangles must sit on top of the hand-drawn boxes at every zoom level. This validates `vbToEl`. Remove by reloading.
4. `MindmapNotes.centerOn(MindmapNotes._state().index.concepts[0])` — view animates to the first box, roughly centered.

If overlays are offset, the letterbox math vs the object's actual render box is wrong — check `svgObject.clientWidth` vs container size before debugging further.

- [ ] **Step 4: Run Django tests (regression)**

```bash
micromamba run -n django-nihar-website python manage.py test homepage -v 2
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add homepage/templates/homepage/mindmap_viewer.html static/assets/js/mindmap_notes.js
git commit -m "feat: overlay layer with viewBox mapping and centerOn for mindmap viewer"
```

---

### Task 15: Search UI

**Files:**
- Modify: `homepage/templates/homepage/mindmap_viewer.html` (markup + CSS)
- Modify: `static/assets/js/mindmap_notes.js`

**Interfaces:**
- Consumes: `index.concepts`, `centerOn`, `flash`, overlay `targets`.
- Produces: search box with dropdown of ALL matches, canvas highlighting (`hit` on all matches, `hit-active` on the selected one), "n of N" counter with prev/next, keyboard navigation (ArrowUp/Down/Enter/Escape). Selecting a match centers the view and (Task 17) opens the panel via `window.MindmapNotes._onSelect(concept)` hook if defined.

- [ ] **Step 1: Add markup and CSS to the template**

Inside `.viewer-wrapper`, directly after `.viewer-controls`:
```html
<div class="search-bar" id="search-bar" hidden>
    <input type="text" id="concept-search" placeholder="Search concepts…"
           autocomplete="off" spellcheck="false">
    <div class="search-nav" id="search-nav" hidden>
        <button id="search-prev" title="Previous match">‹</button>
        <span id="search-counter"></span>
        <button id="search-next" title="Next match">›</button>
    </div>
    <div class="search-results" id="search-results" hidden></div>
</div>
```
CSS (in the `<style>` block):
```css
.search-bar {
    position: absolute;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1001;
    width: min(420px, calc(100% - 130px));
}
#concept-search {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid #444;
    border-radius: 6px;
    background: rgba(20, 24, 32, 0.92);
    color: #eee;
    font-size: 14px;
}
#concept-search:focus { outline: 1px solid #4a9eff; }
.search-nav {
    position: absolute;
    right: 6px;
    top: 5px;
    display: flex;
    align-items: center;
    gap: 4px;
    color: #aaa;
    font-size: 12px;
}
.search-nav button {
    background: none;
    border: none;
    color: #4a9eff;
    font-size: 16px;
    cursor: pointer;
    padding: 0 4px;
}
.search-results {
    margin-top: 4px;
    max-height: 40vh;
    overflow-y: auto;
    background: rgba(20, 24, 32, 0.97);
    border: 1px solid #444;
    border-radius: 6px;
}
.search-result {
    padding: 8px 12px;
    cursor: pointer;
    border-bottom: 1px solid #2a2f3a;
}
.search-result:last-child { border-bottom: none; }
.search-result.selected, .search-result:hover { background: rgba(74, 158, 255, 0.15); }
.search-result .sr-title { color: #eee; font-size: 13px; font-weight: 600; }
.search-result .sr-snippet { color: #999; font-size: 12px; }
.search-result mark { background: rgba(74, 158, 255, 0.4); color: #fff; }
```

- [ ] **Step 2: Add search logic to `mindmap_notes.js`**

Add inside the IIFE (new functions + wiring in `init` after the index loads — show `#search-bar` by removing `hidden`):
```javascript
    let matches = [], activeIdx = -1;

    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function snippet(text, q) {
        const i = text.toLowerCase().indexOf(q);
        if (i < 0) return '';
        const a = Math.max(0, i - 40), b = Math.min(text.length, i + q.length + 40);
        const pre = escapeHtml(text.slice(a, i));
        const hit = escapeHtml(text.slice(i, i + q.length));
        const post = escapeHtml(text.slice(i + q.length, b));
        return (a > 0 ? '…' : '') + pre + '<mark>' + hit + '</mark>' + post +
               (b < text.length ? '…' : '');
    }

    function search(q) {
        q = q.trim().toLowerCase();
        clearHits();
        matches = [];
        activeIdx = -1;
        const results = document.getElementById('search-results');
        const nav = document.getElementById('search-nav');
        if (q.length < 2) {
            results.hidden = true;
            nav.hidden = true;
            return;
        }
        const inTitle = [], inText = [];
        for (const c of index.concepts) {
            if (c.title.toLowerCase().includes(q)) inTitle.push(c);
            else if (c.text.toLowerCase().includes(q)) inText.push(c);
        }
        matches = inTitle.concat(inText);
        results.innerHTML = '';
        for (const c of matches) {
            const div = document.createElement('div');
            div.className = 'search-result';
            div.innerHTML = '<div class="sr-title">' + escapeHtml(c.title) + '</div>' +
                '<div class="sr-snippet">' + (snippet(c.text, q) || snippet(c.title, q)) + '</div>';
            div.addEventListener('mousedown', function (e) {
                e.preventDefault();
                selectMatch(matches.indexOf(c), true);
            });
            results.appendChild(div);
            if (targets[c.id]) targets[c.id].classList.add('hit');
        }
        results.hidden = matches.length === 0;
        nav.hidden = matches.length === 0;
        updateCounter();
    }

    function clearHits() {
        for (const id in targets) {
            targets[id].classList.remove('hit', 'hit-active');
        }
    }

    function updateCounter() {
        document.getElementById('search-counter').textContent =
            matches.length ? (activeIdx + 1) + ' of ' + matches.length : '';
        const rows = document.querySelectorAll('.search-result');
        rows.forEach(function (r, i) { r.classList.toggle('selected', i === activeIdx); });
        if (activeIdx >= 0 && rows[activeIdx]) rows[activeIdx].scrollIntoView({ block: 'nearest' });
    }

    function selectMatch(i, closeDropdown) {
        if (!matches.length) return;
        activeIdx = (i + matches.length) % matches.length;
        const c = matches[activeIdx];
        for (const id in targets) targets[id].classList.remove('hit-active');
        if (targets[c.id]) targets[c.id].classList.add('hit-active');
        updateCounter();
        centerOn(c);
        flash(c.id);
        if (closeDropdown) document.getElementById('search-results').hidden = true;
        if (window.MindmapNotes._onSelect) window.MindmapNotes._onSelect(c);
    }

    function initSearch() {
        document.getElementById('search-bar').hidden = false;
        const input = document.getElementById('concept-search');
        input.addEventListener('input', function () { search(input.value); });
        input.addEventListener('keydown', function (e) {
            const results = document.getElementById('search-results');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                results.hidden = false;
                selectMatch(activeIdx + 1, false);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectMatch(activeIdx - 1, false);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                selectMatch(Math.max(activeIdx, 0), true);
            } else if (e.key === 'Escape') {
                results.hidden = true;
                input.blur();
            }
        });
        document.getElementById('search-prev').addEventListener('click', function () {
            selectMatch(activeIdx - 1, false);
        });
        document.getElementById('search-next').addEventListener('click', function () {
            selectMatch(activeIdx + 1, false);
        });
    }
```
Call `initSearch()` inside the fetch success handler in `init` (after `buildOverlays()`).

Note the existing keyboard-shortcut handler in the template already ignores keys when `e.target.tagName === 'INPUT'` — typing in search won't trigger zoom shortcuts.

- [ ] **Step 3: Manual verification**

With the dev server running, on `/mindmap/cs/`:
1. Type a word known to appear in several concepts (pick one from `cs-stat-index.json`). Dropdown lists all matches with highlighted snippets; all matching boxes glow on canvas.
2. Enter → view flies to the first match, dropdown closes, counter shows "1 of N"; ‹ › cycle through matches.
3. ArrowDown/ArrowUp move the selection with the map following.
4. Clearing the input removes all highlights.
5. Nonsense query → no dropdown, no highlights.

- [ ] **Step 4: Commit**

```bash
git add homepage/templates/homepage/mindmap_viewer.html static/assets/js/mindmap_notes.js
git commit -m "feat: concept search with multi-match dropdown and canvas highlights"
```

---

### Task 16: Concept panel with links, history, KaTeX

**Files:**
- Modify: `homepage/templates/homepage/mindmap_viewer.html` (markup + CSS + KaTeX CDN)
- Modify: `static/assets/js/mindmap_notes.js`

**Interfaces:**
- Consumes: `byId`, `centerOn`, `flash`, `_onSelect` hook, overlay click targets.
- Produces: slide-in panel (right side desktop, bottom sheet ≤768px) rendering title/text/context with KaTeX, Links (→) and Backlinks (←) chips, back/close buttons. Clicking any overlay target opens the panel without moving the view; selecting a search match opens/updates it; clicking a chip centers the view and swaps the panel.

- [ ] **Step 1: Add KaTeX, markup, CSS to the template**

After the Panzoom script tag:
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
```
Inside `.viewer-wrapper`, after the search bar:
```html
<aside class="concept-panel" id="concept-panel" hidden>
    <div class="panel-header">
        <button id="panel-back" title="Back" hidden>←</button>
        <h3 id="panel-title"></h3>
        <button id="panel-close" title="Close">×</button>
    </div>
    <div class="panel-body">
        <div id="panel-text"></div>
        <p id="panel-context" hidden></p>
        <div id="panel-links-out" class="panel-links" hidden>
            <h4>→ Links</h4><div class="chips"></div>
        </div>
        <div id="panel-links-in" class="panel-links" hidden>
            <h4>← Backlinks</h4><div class="chips"></div>
        </div>
    </div>
</aside>
```
CSS:
```css
.concept-panel {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 340px;
    max-width: 85%;
    background: rgba(16, 20, 28, 0.96);
    border-left: 1px solid #333;
    z-index: 1002;
    display: flex;
    flex-direction: column;
    color: #ddd;
}
.panel-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 14px;
    border-bottom: 1px solid #2a2f3a;
}
.panel-header h3 { flex: 1; margin: 0; font-size: 1em; color: #fff; }
.panel-header button {
    background: none;
    border: none;
    color: #4a9eff;
    font-size: 18px;
    cursor: pointer;
    padding: 0 4px;
}
.panel-body { padding: 14px; overflow-y: auto; font-size: 14px; line-height: 1.5; }
#panel-context { color: #999; font-style: italic; font-size: 13px; }
.panel-links h4 { margin: 14px 0 6px; font-size: 12px; color: #888; text-transform: none; }
.panel-links .chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
    background: rgba(74, 158, 255, 0.15);
    border: 1px solid rgba(74, 158, 255, 0.4);
    color: #9cc7ff;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 12px;
    cursor: pointer;
}
.chip:hover { background: rgba(74, 158, 255, 0.35); }
@media (max-width: 768px) {
    .concept-panel {
        top: auto;
        left: 0;
        right: 0;
        width: 100%;
        max-width: 100%;
        height: 45vh;
        border-left: none;
        border-top: 1px solid #333;
    }
}
```

- [ ] **Step 2: Add panel logic to `mindmap_notes.js`**

Add inside the IIFE:
```javascript
    let history = [];

    function renderMath(el) {
        if (window.renderMathInElement) {
            renderMathInElement(el, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false },
                ],
                throwOnError: false,
            });
        }
    }

    function chipRow(rowEl, ids) {
        const chips = rowEl.querySelector('.chips');
        chips.innerHTML = '';
        rowEl.hidden = ids.length === 0;
        for (const id of ids) {
            const c = byId[id];
            if (!c) continue;
            const b = document.createElement('button');
            b.className = 'chip';
            b.textContent = c.title;
            b.addEventListener('click', function () {
                centerOn(c);
                flash(c.id);
                openPanel(c, true);
            });
            chips.appendChild(b);
        }
    }

    function openPanel(concept, push) {
        const panel = document.getElementById('concept-panel');
        const current = panel.dataset.conceptId;
        if (push && current && current !== concept.id) history.push(current);
        panel.dataset.conceptId = concept.id;
        panel.hidden = false;
        document.getElementById('panel-back').hidden = history.length === 0;
        document.getElementById('panel-title').textContent = concept.title;
        const textEl = document.getElementById('panel-text');
        textEl.innerHTML = escapeHtml(concept.text).replace(/\n/g, '<br>');
        renderMath(textEl);
        const ctx = document.getElementById('panel-context');
        ctx.hidden = !concept.context;
        ctx.textContent = concept.context || '';
        chipRow(document.getElementById('panel-links-out'), concept.links_out);
        chipRow(document.getElementById('panel-links-in'), concept.links_in);
    }

    function initPanel() {
        document.getElementById('panel-close').addEventListener('click', function () {
            document.getElementById('concept-panel').hidden = true;
            document.getElementById('concept-panel').dataset.conceptId = '';
            history = [];
        });
        document.getElementById('panel-back').addEventListener('click', function () {
            const prev = history.pop();
            if (prev && byId[prev]) {
                centerOn(byId[prev]);
                openPanel(byId[prev], false);
            }
            document.getElementById('panel-back').hidden = history.length === 0;
        });
        // clicks on overlay targets — but not drags
        let downXY = null;
        container.addEventListener('mousedown', function (e) {
            downXY = [e.clientX, e.clientY];
        });
        container.addEventListener('click', function (e) {
            if (downXY && Math.hypot(e.clientX - downXY[0], e.clientY - downXY[1]) > 5) return;
            const t = e.target.closest('.concept-target');
            if (t && byId[t.dataset.conceptId]) {
                openPanel(byId[t.dataset.conceptId], true);
            }
        });
    }

    window.MindmapNotes._onSelect = function (c) { openPanel(c, true); };
```
Call `initPanel()` in the fetch success handler (after `initSearch()`). Also move the `_onSelect` assignment inside `initPanel` so it's only active with an index loaded.

- [ ] **Step 3: Manual verification**

On `/mindmap/cs/`:
1. Click a hand-drawn box → panel slides in with faithful transcription; `$…$` spans render as math.
2. Chips listed under "→ Links" / "← Backlinks" match the arrows drawn on paper; clicking one flies to that box and swaps the panel; Back returns.
3. Search → Enter also opens the panel for the selected match.
4. Dragging across a box does NOT open the panel; a clean click does.
5. Narrow the window below 768px → panel becomes a bottom sheet; pan/pinch still work above it.
6. Close panel; history resets.

- [ ] **Step 4: Commit**

```bash
git add homepage/templates/homepage/mindmap_viewer.html static/assets/js/mindmap_notes.js
git commit -m "feat: concept panel with wikilink chips, history, and KaTeX rendering"
```

---

### Task 17: End-to-end verification and wrap-up

**Files:**
- Possibly modify: anything surfaced by verification.

- [ ] **Step 1: Full automated suite**

```bash
micromamba run -n django-nihar-website pytest tests/ -v -m "not golden"
micromamba run -n django-nihar-website pytest tests/ -v -m golden
micromamba run -n django-nihar-website python manage.py test homepage -v 2
```
Expected: all PASS.

- [ ] **Step 2: Idempotence check on the real vault**

```bash
micromamba run -n django-nihar-website python -m scripts.mindmap_vault.update \
  static/mindmaps/cs-stat.svg --bg '#000000'
git diff --stat static/mindmaps/cs-stat-index.json
```
Expected: summary shows all boxes `unchanged`, 0 OCR calls, and the JSON diff is empty.

- [ ] **Step 3: Degradation check**

Visit `/mindmap/physics/` (no physics-index.json exists yet): the viewer must behave exactly as before this project — no search bar, no console errors beyond the failed fetch.

- [ ] **Step 4: Use the verify skill**

Invoke the `verify` skill to drive the changed flows end-to-end (viewer search → jump → panel → chip navigation) before claiming completion.

- [ ] **Step 5: Final commit and options**

```bash
git status
git add -A && git commit -m "chore: mindmap vault pipeline wrap-up"
```
Then follow superpowers:finishing-a-development-branch. Remaining follow-ups to offer the user (explicitly out of scope here): ingest `physics.svg` (same command, `--bg '#1F2429'`), copy the vault into the repo if desired, and the optional `--audit` vision sweep.
