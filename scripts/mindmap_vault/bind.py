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
