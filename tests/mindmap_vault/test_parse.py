from pathlib import Path
import base64

from scripts.mindmap_vault import parse


def test_parse_counts_and_viewbox(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    assert r.viewbox == (0.0, 0.0, 500.0, 400.0)
    assert len(r.strokes) == 47  # 46 paths + 1 circle
    assert len(r.images) == 1
    assert r.image_defs == {"IMAGE_DEF_aaa": (60.0, 30.0)}


def test_stroke_fields(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    by_id = {s.sid: s for s in r.strokes}
    box_a = by_id["boxA"]
    assert box_a.layer == "Pen"
    assert box_a.color == "#ffcca9"
    assert box_a.bbox == (10.0, 10.0, 120.0, 60.0)
    assert box_a.radius == 0.0
    dot = by_id["dotA"]
    assert dot.radius == 0.4
    assert dot.points == [(95.0, 45.0)]


def test_q_commands_sampled(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    decoy = {s.sid: s for s in r.strokes}["decoy"]
    # 1 M point + per Q: midpoint + endpoint → 1 + 6*2 = 13
    assert len(decoy.points) == 13


def test_image_bbox_from_matrix(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    img = r.images[0]
    assert img.def_id == "IMAGE_DEF_aaa"
    assert img.bbox == (240.0, 20.0, 300.0, 50.0)


def test_load_image_png(synthetic_svg):
    data = parse.load_image_png(synthetic_svg, "IMAGE_DEF_aaa")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_load_image_returns_bytes_and_ext_png(synthetic_svg):
    data, ext = parse.load_image(synthetic_svg, "IMAGE_DEF_aaa")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert ext == "png"


def test_load_image_jpeg_ext(tmp_path):
    # Create a minimal SVG with JPEG image data
    jpeg_b64 = base64.b64encode(b"AAAA").decode()
    svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<defs>
<image id="J" width="1" height="1" xlink:href="data:image/jpeg;base64,{jpeg_b64}"/>
</defs>
</svg>"""
    svg_path = tmp_path / "test_jpeg.svg"
    svg_path.write_text(svg_content, encoding="utf-8")

    data, ext = parse.load_image(svg_path, "J")
    assert data == b"AAAA"
    assert ext == "jpg"
