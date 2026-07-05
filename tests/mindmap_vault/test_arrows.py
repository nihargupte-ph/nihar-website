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
    assert review == []


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
