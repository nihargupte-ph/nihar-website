from scripts.mindmap_vault import config
from scripts.mindmap_vault.geom import (
    bbox_area,
    bbox_iou,
    bbox_of,
    bbox_union,
    dist,
    linearity,
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
    return linearity(s.points)


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
