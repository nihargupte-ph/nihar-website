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
