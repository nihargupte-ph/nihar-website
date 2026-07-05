from scripts.mindmap_vault import config
from scripts.mindmap_vault.boxes import _join_components
from scripts.mindmap_vault.geom import (
    bbox_area,
    bbox_contains,
    chord_len,
    dist,
    linearity,
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
        and chord_len(s.points) >= config.ARROW_MIN_LEN
        and linearity(s.points) >= config.ARROW_LINEARITY
        and not any(bbox_contains(b.bbox, _midpoint(s)) for b in boxes)
    ]

    edges, review = [], []
    for chain in _join_components(cands, config.JOIN_TOL):
        e1, e2 = _chain_endpoints(chain)
        i1, _, amb1 = _nearest_box(e1, boxes)
        i2, _, amb2 = _nearest_box(e2, boxes)
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
                              stroke_ids=sids + [h.sid for h in h1] + [h.sid for h in h2]))
    return edges, review
