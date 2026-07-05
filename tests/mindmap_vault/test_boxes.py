from scripts.mindmap_vault import boxes, parse


def _find(bs, x, y):
    return next(b for b in bs if b.bbox[0] <= x <= b.bbox[2] and b.bbox[1] <= y <= b.bbox[3])


def test_finds_three_boxes(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    assert len(bs) == 3


def test_single_stroke_box_bbox(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    a = _find(bs, 60, 35)
    assert a.border_ids == ["boxA"]
    assert a.bbox == (10.0, 10.0, 120.0, 60.0)


def test_multi_stroke_box(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    c = _find(bs, 75, 180)
    assert sorted(c.border_ids) == ["boxC_bot", "boxC_left", "boxC_right", "boxC_top"]
    assert c.bbox == (10.0, 150.0, 140.0, 210.0)


def test_decoy_and_text_not_boxes(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    all_border = {sid for b in bs for sid in b.border_ids}
    assert "decoy" not in all_border
    assert "txtA1" not in all_border
    assert "arrowAB" not in all_border


def test_deterministic_order(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    b1 = [b.bbox for b in boxes.find_boxes(r.strokes)]
    b2 = [b.bbox for b in boxes.find_boxes(r.strokes)]
    assert b1 == b2
