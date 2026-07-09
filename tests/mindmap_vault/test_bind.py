from scripts.mindmap_vault import arrows, bind, boxes, parse


def _pipeline(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    edges, _ = arrows.find_edges(r.strokes, bs)
    bind.bind(r.strokes, r.images, bs, edges)
    return r, bs


def _box_at(bs, x, y):
    return next(b for b in bs if b.bbox[0] <= x <= b.bbox[2] and b.bbox[1] <= y <= b.bbox[3])


def test_text_bound_to_boxes(synthetic_svg):
    _, bs = _pipeline(synthetic_svg)
    a = _box_at(bs, 60, 35)
    assert set(a.member_ids) == {"txtA1", "txtA2", "txtA3", "dotA"}
    c = _box_at(bs, 75, 180)
    assert set(c.member_ids) == {"txtC1"}


def test_image_bound_to_box_b(synthetic_svg):
    _, bs = _pipeline(synthetic_svg)
    b = _box_at(bs, 260, 40)
    assert b.image_ids == ["img1"]
    # "arrowAtoRegA" (box A -> region A connector, added for the R2
    # box<->region edge fixture) has a bbox center that falls within
    # ATTACH_DIST of box B. In this test's own pipeline, find_edges only
    # sees boxes (no regions), so the connector's endpoints don't attach to
    # anything within END_TOL and it lands in `review`, not `edges` — bind()
    # therefore doesn't exclude it, and it binds to box B same as any other
    # loose annotation would.
    assert set(b.member_ids) == {"txtB1", "arrowAtoRegA"}


def test_edge_and_decoy_strokes_not_members(synthetic_svg):
    _, bs = _pipeline(synthetic_svg)
    members = {sid for b in bs for sid in b.member_ids}
    for sid in ("arrowAB", "headAB1", "headAB2", "lineBC", "decoy"):
        assert sid not in members
