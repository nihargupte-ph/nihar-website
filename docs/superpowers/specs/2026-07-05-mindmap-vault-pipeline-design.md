# Mindmap → Obsidian Vault Pipeline + Website Search/Notes Layer — Design

**Date:** 2026-07-05
**Status:** Approved design, pending implementation plan

## Purpose

Convert handwritten mindmaps (SVG exports from the Concepts iOS app, e.g.
`static/mindmaps/cs-stat.svg`, `static/mindmaps/physics.svg`) into:

1. An **Obsidian vault** of short, faithful markdown notes — one note per
   hand-drawn concept box, wikilinked according to the hand-drawn arrows, so
   the Obsidian graph mirrors the physical mindmap.
2. A **website layer** on the existing mindmap viewer: full-text search that
   jumps/pans the SVG to matching boxes, and an interactive side panel that
   renders each concept's note and lets visitors walk the arrow graph.
3. A **single re-runnable update script** that incrementally re-ingests an SVG
   after the notes change, re-OCRing only new/changed boxes.

This is a ground-up redesign replacing the v1 pipeline in
`/home/n/Documents/vault/classic_research` (vision-based box detection had
poor extraction quality: 16/120 boxes ingested, no arrow edges).

## Core insight driving the architecture

The Concepts export is fully vectorized: every pen stroke is a
`<path id="STROKE_<uuid>">` with absolute canvas coordinates, color, width,
and a named layer group; pasted photos are `<g id="IMAGE_...">` elements with
affine transforms. Therefore **box detection, text-to-box binding, and arrow
detection are deterministic geometry problems** — no vision needed. A vision
model (Claude API) is required only to read the handwriting inside each box.

## Approach chosen

**Geometry-first pipeline** (chosen over v1-style vision-first detection, and
over a hybrid with a mandatory vision audit):

- Geometry gives exact bboxes, exhaustive coverage, and zero API cost for
  detection; vision-first was imprecise and expensive — the source of v1's
  quality problems.
- The OCR call doubles as validation: the model can flag a crop that is not
  actually a concept box, catching classifier false positives.
- An optional vision `--audit` sweep (Claude scans a low-res render for boxes
  geometry missed) is a **deferred add-on**, built only if real misses are
  observed. Multi-stroke rectangles are handled in the geometry classifier,
  not deferred to the audit.

## Components

### 1. Pipeline package — `scripts/mindmap_vault/` (in the website repo)

Runs under the existing `django-nihar-website` micromamba env. Standalone
script; no Django dependency. Requires `ANTHROPIC_API_KEY` for OCR stages.

Stages, each a separately testable module:

1. **Parse** (`parse.py`) — stream the SVG (files are 50–60 MB; do not load
   base64 image defs into memory). Extract per stroke: id, polyline points,
   bbox, color, stroke width, layer. Extract per image: id, transform, bbox,
   PNG bytes (decoded lazily only when exporting assets).
2. **Box classification** (`boxes.py`) — identify concept boxes:
   - Single-stroke boxes: stroke whose path approximately traces the
     perimeter of its own bbox (path length ≈ 2·(w+h) within tolerance),
     with bbox large relative to handwriting scale.
   - Multi-stroke boxes: groups of 2–4 long, nearly axis-aligned strokes
     whose union traces a rectangle perimeter.
   - Output: box records with exact bbox and the stroke ids forming the
     border.
3. **Text binding** (`bind.py`) — every non-box, non-arrow stroke whose bbox
   center falls inside a box belongs to that box's handwriting. Pasted images
   inside a box attach to it as assets. Strokes outside all boxes are
   recorded as loose annotations (attached to the nearest box within a
   threshold, else ignored).
4. **Arrow detection** (`arrows.py`) — a connector is a long stroke (or small
   chain of strokes) whose two endpoints each land within a threshold of two
   *different* boxes' borders, and whose body lies outside both boxes.
   Direction: arrowhead = 1–3 short strokes clustered at one endpoint; if no
   arrowhead is found the edge is stored as undirected. Output: edge list
   `(from_box, to_box, directed?)`.
5. **Crop rendering** (`render.py`) — for each box, render only its member
   strokes (border + handwriting + images) to a small PNG via `resvg` or
   `cairosvg` at a resolution adequate for handwriting OCR (~1000 px wide).
   Crops cached in `.pipeline/crops/`.
6. **OCR** (`ocr.py`) — send each crop to the Claude API
   (`claude-sonnet-5`, vision). Structured response per box:
   - `title`: short concept name (from the box's heading line)
   - `text`: verbatim transcription of the handwriting; equations in LaTeX
   - `is_concept_box`: false if the crop is not actually a concept box
     (classifier false positive → box dropped, logged)
   - `context`: optional ≤1 sentence added only when the note would
     otherwise be cryptic — kept clearly separate from the transcription.
   Retries with backoff; failures leave the box in state `ocr_pending` so a
   re-run resumes cleanly.
7. **Emit** (`emit.py`) — write vault notes, MOC, index.md updates, and the
   website JSON index (see schemas below). Wikilink targets resolved from
   arrow edges; undirected edges emit links in both notes.
8. **Manifest & incremental update** (`manifest.py`) — see Update workflow.

Orchestrated by `update.py`:

```bash
micromamba run -n django-nihar-website \
  python scripts/mindmap_vault/update.py static/mindmaps/cs-stat.svg
```

### 2. Vault — `/home/n/Documents/vault/classic_research`

Existing v1 contents are archived to
`/home/n/Documents/vault/classic_research_v1_backup/` before the first run,
then the vault is regenerated fresh.

```
classic_research/
├── index.md                    # hub: lists each ingested mindmap + stats
├── concepts/<slug>.md          # one short note per box
│   └── _archived/              # notes whose boxes disappeared from the SVG
├── mocs/<mindmap>.md           # one MOC per SVG: full concept/edge listing
├── assets/<box_id>_<n>.png     # photos pasted into the mindmap, cropped
└── .pipeline/
    ├── manifest.json           # canonical state; drives incremental updates
    └── crops/<mindmap>/<box_id>.png
```

**Concept note format** (short and faithful; the user's words dominate):

```markdown
---
id: cs-stat/b012
source: cs-stat
bbox: [3644, 262, 3790, 318]
---
# Importance Sampling

<verbatim transcription, typically 1–5 lines; LaTeX for equations>

*context:* <≤1 sentence, only if needed>

→ [[evidence_lower_bound]] [[effective_sample_size]]
```

Slugs are kebab/snake-case of the title, deduplicated with numeric suffixes.
Note filenames are stable across re-ingests (keyed by box id, not title), so
Obsidian links and website URLs don't break when handwriting is edited.

**Vault ↔ repo:** the vault stays at the path above for now; it may be copied
into the website repo later. Nothing in the design depends on its location —
the website consumes only the JSON index, which is written into the repo.

### 3. Website JSON index — `static/mindmaps/<name>-index.json`

Written by the pipeline on every run:

```json
{
  "svg": "cs-stat.svg",
  "generated": "2026-07-05T…",
  "concepts": [
    {
      "id": "b012",
      "slug": "importance_sampling",
      "title": "Importance Sampling",
      "text": "…verbatim transcription…",
      "context": "…or null…",
      "bbox": [3644.9, 262.2, 3790.1, 318.0],
      "links_out": ["b007", "b019"],
      "links_in": ["b003"]
    }
  ]
}
```

Bbox coordinates are in SVG viewBox units so the viewer can map them directly.

### 4. Website viewer layer — `mindmap_viewer.html`

Enhancements to the existing pan/zoom viewer (SVG untouched; overlays are
positioned from index bboxes and kept in sync with the viewer's transform):

- **Search bar** (top of viewer). Client-side fuzzy substring search over
  title + text; index is a few hundred KB, loaded with the page, no backend.
  - Results dropdown lists **every** match: title + snippet with the match
    highlighted. Arrow-key and click navigation.
  - All matching boxes get a dimmed highlight on the canvas simultaneously;
    the selected match is brightest. An "n of N" counter with next/prev
    buttons cycles matches without reopening the dropdown.
  - Selecting a match pans/zooms to its bbox and flashes a highlight.
- **Click targets**: each concept bbox gets an invisible overlay rectangle;
  clicking opens the concept panel.
- **Concept panel** (slide-in side panel; bottom sheet on mobile):
  - Renders the note: title, transcription (KaTeX for LaTeX spans), optional
    context line.
  - **Links section**: every connected concept as a clickable chip, outgoing
    (arrows drawn from this box) and backlinks (arrows into it) labeled
    separately. Clicking a chip pans/zooms the viewer to that box and swaps
    the panel to its note — walking the arrow graph from the panel.
  - Back button returns to the previously viewed concept (history stack).
- Missing/empty index → viewer behaves exactly as today (search UI hidden).

## Update workflow (incremental re-ingest)

Box identity across runs: `box_id` is assigned on first sight and persisted in
`manifest.json` keyed by a **stroke-set hash** (hash of the sorted member
stroke ids + quantized geometry). On re-run:

- **Unchanged box** (hash match): keeps id, note, OCR — zero API cost.
- **Moved box** (same stroke ids, new coords): keeps id and OCR; bbox and
  index updated.
- **Changed box** (strokes added/removed inside): keeps id; re-OCR'd; note
  body rewritten, frontmatter and inbound links preserved.
- **New box**: new id, OCR'd, note created.
- **Deleted box**: note moved to `concepts/_archived/`, links to it removed
  from other notes' link lines; never hard-deleted.

Every run finishes by regenerating the MOC, index.md stats, and the JSON
index, then printing a summary:
`+3 boxes, ~1 changed, −0 removed, 2 edges added, $0.04 API, 14s`.

## Error handling

- **Parse**: malformed path data → skip stroke, log id; never abort the run.
- **OCR**: API errors retry ×3 with backoff; persistent failure marks the box
  `ocr_pending` in the manifest (note gets a stub body) and the run exits
  nonzero with a count, so re-running resumes only the pending boxes.
- **Classifier false positives**: dropped when OCR returns
  `is_concept_box: false`, logged to the run summary.
- **Ambiguous arrows** (endpoint near >2 boxes or neither endpoint clearly
  attached): logged with coordinates to a `review.md` sidecar rather than
  guessed.
- **Website**: fetch failure or absent index degrades to the current viewer.

## Testing

- **Unit tests** (pytest, no network): parse/boxes/bind/arrows tested against
  small synthetic SVGs (hand-authored: 3 boxes, 2 arrows, one multi-stroke
  box, one decoy squiggle) with exact expected outputs.
- **Golden checks**: box/edge counts on the real cs-stat.svg asserted within
  a tolerance band, catching classifier regressions.
- **OCR mock**: `ocr.py` takes an injectable client; tests use a canned-
  response fake, so the full pipeline runs offline in CI.
- **Manifest round-trip test**: run twice on the same SVG → second run makes
  zero API calls and produces byte-identical outputs.
- **Website**: manual verification via the dev server (search, jump,
  panel, link-walking, mobile sheet), plus a JSON-schema sanity check of the
  emitted index in the pipeline tests.

## Out of scope (YAGNI)

- Vision `--audit` sweep (add only if geometry provably misses boxes).
- Force-directed graph page on the website (panel-on-SVG chosen instead).
- Serving the vault markdown itself via Django; only the JSON index is used.
- Handwriting OCR of loose annotations outside boxes.
- Automatic ingestion of physics.svg — same command works for it, but it is
  run manually after cs-stat validates the pipeline.
