from scripts.mindmap_vault import arrows, bind, boxes, parse, render


def _box_b(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    edges, _ = arrows.find_edges(r.strokes, bs)
    bind.bind(r.strokes, r.images, bs, edges)
    strokes_by_id = {s.sid: s for s in r.strokes}
    images_by_id = {i.iid: i for i in r.images}
    b = next(x for x in bs if x.image_ids)
    return b, strokes_by_id, images_by_id


def test_render_size_and_content(synthetic_svg):
    box, strokes_by_id, images_by_id = _box_b(synthetic_svg)
    img = render.render_box(box, strokes_by_id, images_by_id, synthetic_svg)
    # bbox (200,10)-(320,70) + margin 8 → 136 x 76 pt, scaled to target width
    assert img.width == 1200
    assert 600 <= img.height <= 720
    colors = img.getcolors(maxcolors=1_000_000)
    assert len(colors) > 1  # not a blank canvas


def test_render_respects_max_scale():
    # tiny box: scale would exceed CROP_MAX_SCALE, must clamp
    from scripts.mindmap_vault.model import Box, Stroke
    s = Stroke(sid="t", points=[(0.0, 0.0), (10.0, 10.0)],
               bbox=(0.0, 0.0, 10.0, 10.0), color="#fff", width=0.6, layer="Pen")
    b = Box(border_ids=[], bbox=(0.0, 0.0, 10.0, 10.0), member_ids=["t"])
    img = render.render_box(b, {"t": s}, {}, None)
    assert img.width <= (10 + 16) * 40 + 1  # (w + 2*margin) * CROP_MAX_SCALE
