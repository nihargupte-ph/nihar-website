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


def bbox_intersects(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


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


def linearity(pts):
    """chord / arc length: 1.0 for a straight stroke, near 0 for a squiggle."""
    arc = polyline_len(pts)
    return chord_len(pts) / arc if arc > 0 else 0.0


def point_bbox_dist(pt, b):
    dx = max(b[0] - pt[0], 0.0, pt[0] - b[2])
    dy = max(b[1] - pt[1], 0.0, pt[1] - b[3])
    return math.hypot(dx, dy)


def point_rect_outline_dist(pt, b):
    out = point_bbox_dist(pt, b)
    if out > 0:
        return out
    return min(pt[0] - b[0], b[2] - pt[0], pt[1] - b[1], b[3] - pt[1])
