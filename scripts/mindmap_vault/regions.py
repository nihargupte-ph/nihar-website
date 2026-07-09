from scripts.mindmap_vault import config
from scripts.mindmap_vault.geom import (
    bbox_expand,
    bbox_intersects,
    bbox_union,
    chord_len,
    linearity,
    polyline_len,
)
from scripts.mindmap_vault.model import Box

# Grid cell size for the bucket prefilter: two strokes can only merge if
# their REGION_GAP-expanded bboxes intersect, so a cell needs to comfortably
# cover an expansion on both sides (2 * REGION_GAP) plus some headroom for a
# typical stroke's own bbox span, or a stroke will spill into neighboring
# cells too often and multiply the pair-count we still have to check.
_CELL = 2 * config.REGION_GAP + 40.0


def _is_connector(s):
    """Same connector-shape test arrows.py uses for edge candidates."""
    return (
        chord_len(s.points) >= config.ARROW_MIN_LEN
        and linearity(s.points) >= config.ARROW_LINEARITY
    )


def _bucket_range(bbox):
    x0, y0, x1, y1 = bbox
    return (
        int(x0 // _CELL), int(y0 // _CELL),
        int(x1 // _CELL), int(y1 // _CELL),
    )


class _UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, i):
        parent = self.parent
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(self, i, j):
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.parent[ri] = rj


def _cluster(cands):
    """Union-find over candidate strokes: merge i, j when their
    REGION_GAP-expanded bboxes intersect. Grid-bucketed so this stays near
    O(n) instead of O(n^2) over tens of thousands of strokes."""
    n = len(cands)
    uf = _UnionFind(n)
    expanded = [bbox_expand(s.bbox, config.REGION_GAP) for s in cands]

    buckets = {}
    for i, b in enumerate(expanded):
        cx0, cy0, cx1, cy1 = _bucket_range(b)
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                buckets.setdefault((cx, cy), []).append(i)

    checked = set()
    for members in buckets.values():
        for a in range(len(members)):
            i = members[a]
            for b_idx in range(a + 1, len(members)):
                j = members[b_idx]
                pair = (i, j) if i < j else (j, i)
                if pair in checked:
                    continue
                checked.add(pair)
                if uf.find(i) == uf.find(j):
                    continue
                if bbox_intersects(expanded[i], expanded[j]):
                    uf.union(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)
    return list(groups.values())


def find_regions(strokes, boxes):
    """Cluster strokes that belong to no box and are not connector-shaped
    into region Box records (border_ids=[]). Clusters below the ink/stroke
    thresholds (stray marks) are dropped."""
    taken = {sid for b in boxes for sid in b.border_ids}
    taken |= {sid for b in boxes for sid in b.member_ids}
    cands = [s for s in strokes if s.sid not in taken and not _is_connector(s)]
    if not cands:
        return []

    regions = []
    for idxs in _cluster(cands):
        members = [cands[i] for i in idxs]
        if len(members) < config.REGION_MIN_STROKES:
            continue
        ink = sum(polyline_len(s.points) for s in members)
        if ink < config.REGION_MIN_INK:
            continue
        bb = members[0].bbox
        for s in members[1:]:
            bb = bbox_union(bb, s.bbox)
        regions.append(Box(
            border_ids=[],
            bbox=bb,
            member_ids=sorted(s.sid for s in members),
        ))

    regions.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
    return regions
