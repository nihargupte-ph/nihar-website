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
ARROW_MIN_LEN = 15.0      # chord (straight-line) length, not arc length
ARROW_LINEARITY = 0.9     # chord/arc; excludes squiggly handwriting/glyph strokes
END_TOL = 20.0            # endpoint→box distance to count as attached
AMBIG_RATIO = 1.5         # 2nd-nearest closer than ratio*nearest → ambiguous
HEAD_MAX_LEN = 8.0
HEAD_TOL = 5.0

# --- binding ---
ATTACH_DIST = 12.0        # loose annotation → nearest box

# --- unboxed regions ---
REGION_GAP = 25.0         # bbox expansion (each side) before merge test
REGION_MIN_INK = 150.0    # total polyline length to keep a cluster
REGION_MIN_STROKES = 12   # stroke count to keep a cluster

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
