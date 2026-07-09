from scripts.mindmap_vault import arrows, boxes, parse


def _setup(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    idx = {}
    for i, b in enumerate(bs):
        if b.bbox[0] < 150 and b.bbox[1] < 100:
            idx["A"] = i
        elif b.bbox[0] > 150:
            idx["B"] = i
        else:
            idx["C"] = i
    return r, bs, idx


def test_directed_edge_a_to_b(synthetic_svg):
    r, bs, idx = _setup(synthetic_svg)
    edges, review = arrows.find_edges(r.strokes, bs)
    ab = next(e for e in edges if {e.src, e.dst} == {idx["A"], idx["B"]})
    assert ab.directed
    assert ab.src == idx["A"] and ab.dst == idx["B"]
    assert "arrowAB" in ab.stroke_ids
    assert {"headAB1", "headAB2"} <= set(ab.stroke_ids)


def test_undirected_edge_b_c(synthetic_svg):
    r, bs, idx = _setup(synthetic_svg)
    edges, _ = arrows.find_edges(r.strokes, bs)
    bc = next(e for e in edges if {e.src, e.dst} == {idx["B"], idx["C"]})
    assert not bc.directed


def test_exactly_two_edges_no_review(synthetic_svg):
    r, bs, _ = _setup(synthetic_svg)
    edges, review = arrows.find_edges(r.strokes, bs)
    assert len(edges) == 2
    # "arrowAtoRegA" (the R2 box<->region edge fixture) is a real connector
    # whose far endpoint targets region A, not any of these 3 boxes. Passed
    # only `bs` (boxes, no regions) as this test does, one end resolves to
    # box A and the other resolves to nothing within END_TOL, so it's
    # reported for manual review rather than silently dropped or turned into
    # a spurious box-to-box edge — that's exercised end to end (with regions
    # in play) by tests/mindmap_vault/test_update.py instead.
    assert len(review) == 1
    assert "arrowAtoRegA" in review[0]


def test_dangling_connector_goes_to_review(synthetic_svg):
    r, bs, _ = _setup(synthetic_svg)
    from scripts.mindmap_vault.model import Stroke
    dangling = Stroke(
        sid="dangle", points=[(122.0, 50.0), (170.0, 120.0)],
        bbox=(122.0, 50.0, 170.0, 120.0), color="#fff", width=0.6, layer="Pen",
    )
    edges, review = arrows.find_edges(r.strokes + [dangling], bs)
    assert len(edges) == 2
    assert any("dangle" in msg for msg in review)


def test_double_headed_connector(synthetic_svg):
    r, bs, idx = _setup(synthetic_svg)
    from scripts.mindmap_vault.model import Stroke

    # Construct a connector from A's bottom edge to C's top edge
    connector = Stroke(
        sid="doubleHeadConnector",
        points=[(65.0, 62.0), (65.0, 148.0)],
        bbox=(65.0, 62.0, 65.0, 148.0),
        color="#fff", width=0.6, layer="Pen",
    )

    # Head strokes at the connector start (65.0, 62.0)
    head_start_1 = Stroke(
        sid="head_start_1",
        points=[(60.0, 68.0), (65.0, 62.0)],
        bbox=(60.0, 62.0, 65.0, 68.0),
        color="#fff", width=0.6, layer="Pen",
    )
    head_start_2 = Stroke(
        sid="head_start_2",
        points=[(70.0, 68.0), (65.0, 62.0)],
        bbox=(65.0, 62.0, 70.0, 68.0),
        color="#fff", width=0.6, layer="Pen",
    )

    # Head strokes at the connector end (65.0, 148.0)
    head_end_1 = Stroke(
        sid="head_end_1",
        points=[(60.0, 142.0), (65.0, 148.0)],
        bbox=(60.0, 142.0, 65.0, 148.0),
        color="#fff", width=0.6, layer="Pen",
    )
    head_end_2 = Stroke(
        sid="head_end_2",
        points=[(70.0, 142.0), (65.0, 148.0)],
        bbox=(65.0, 142.0, 70.0, 148.0),
        color="#fff", width=0.6, layer="Pen",
    )

    edges, review = arrows.find_edges(
        r.strokes + [connector, head_start_1, head_start_2, head_end_1, head_end_2],
        bs
    )

    # Find the double-headed edge between A and C
    double_edge = next(
        (e for e in edges if {e.src, e.dst} == {idx["A"], idx["C"]}),
        None
    )
    assert double_edge is not None, "Double-headed connector should create an edge"
    assert not double_edge.directed, "Double-headed connector should be undirected"

    # Verify all stroke IDs are included
    assert "doubleHeadConnector" in double_edge.stroke_ids
    assert "head_start_1" in double_edge.stroke_ids
    assert "head_start_2" in double_edge.stroke_ids
    assert "head_end_1" in double_edge.stroke_ids
    assert "head_end_2" in double_edge.stroke_ids
