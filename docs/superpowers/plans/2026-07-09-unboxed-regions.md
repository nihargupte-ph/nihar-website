# Unboxed Regions + Dropped-Box Recheck — Plan Addendum

> Extends the 2026-07-05 mindmap-vault pipeline. Same conventions (TDD,
> micromamba env, commit per task). Diagnosis: only 27% of cs-stat ink is
> searchable; 59% is in no box; 6% in dropped boxes.

**Goal:** Nearly all handwriting searchable. Unboxed strokes cluster into
"regions" that flow through the existing box lifecycle (manifest id,
crop, OCR, note, JSON index, search). Edge detection reruns over
boxes+regions. Dropped boxes get an in-session second look.

## Design decisions (approved)

- Region = spatial cluster of strokes that are in no box and are not
  connector-shaped (chord ≥ ARROW_MIN_LEN and linearity ≥ ARROW_LINEARITY
  excluded from clustering).
- Clustering: union-find; two strokes merge when their bboxes, each
  expanded by REGION_GAP (25.0 pt), intersect. Grid-bucket prefilter so
  it's not O(n²) over ~47k strokes.
- Keep clusters with total ink ≥ REGION_MIN_INK (150.0 pt) and
  ≥ REGION_MIN_STROKES (12); smaller clusters are stray marks, ignored.
- A region reuses the Box dataclass with border_ids=[]; region ids are
  "r%03d" via a separate source["next_region"] counter (default when
  missing). content_hash/reconcile/crop/OCR machinery unchanged.
- kind: manifest record gains "kind": "box"|"region" (default box when
  absent); note frontmatter gains `kind: region` for regions; JSON index
  concepts gain "kind". Website overlay for kind=region uses a dimmer
  hit style (new CSS class concept-target--region + .hit opacity tweak);
  otherwise identical behavior.
- Pipeline order in update.run: parse → find_boxes → bind(boxes) →
  find_regions(leftover strokes) → find_edges(strokes, boxes+regions)
  (single edge pass; edge indices map over the combined list) →
  reconcile(combined) → crops/OCR/emit as today.
  NOTE: edge stroke_ids no longer feed bind (bind runs before edges);
  connector-shaped strokes are excluded from region clustering by shape
  instead. Boxes: bind excludes them via border sets as today; a
  connector stroke whose midpoint sits inside a box may bind as member —
  same as current behavior, acceptable.
- OCR prompt for regions: same faithfulness contract; is_concept_box
  interpreted as "contains transcribable content" (diagrams with labels →
  true, transcribe the labels; pure unlabeled curves → false/dropped).
- Dropped-box recheck is operational, not code: re-read the 52 dropped
  crops in-session, resurrect via apply_ocr (existing lifecycle supports
  it: dropped record + real ocr → slug + note on next emit).

## Tasks

- R1: scripts/mindmap_vault/regions.py (find_regions(strokes, boxes) ->
  list[Box] with border_ids=[]), config constants, synthetic-fixture
  loose-stroke additions, unit tests (cluster split/merge, connector
  exclusion, min-ink filter, determinism).
- R2: integration — update.py new order + region ids/kind; manifest
  "kind" + next_region; emit kind passthrough (frontmatter + JSON);
  arrows unchanged but now receives combined list; viewer CSS/JS for
  kind=region; tests incl. round-trip determinism and region+box edge.
- R3: calibrate on real cs-stat (region count/crops eyeballed, constants
  tuned, golden band extended), then dry-run → in-session OCR of region
  crops + dropped-box recheck → apply_ocr → emit → website verify →
  commit index.
