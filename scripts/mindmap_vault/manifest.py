import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


def _is_dropped(rec):
    return bool((rec.get("ocr") or {}).get("dropped"))


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
