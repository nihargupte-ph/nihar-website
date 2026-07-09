from pathlib import Path

import pytest

from scripts.mindmap_vault import arrows, bind, boxes, parse, regions

CS_STAT = Path(__file__).resolve().parents[2] / "static" / "mindmaps" / "cs-stat.svg"

pytestmark = pytest.mark.golden

# The live SVG is the user's evolving notes: exact counts change with every
# re-export, so these assertions are regression FLOORS (catching parser
# breakage like "0 strokes parsed" or "defs images missed"), plus generous
# bands around the last calibration (2026-07-09 export: 89813 strokes,
# 22 images, 161 boxes, 135 regions, 16 box-only edges, 27 combined edges).


@pytest.fixture(scope="module")
def parsed():
    if not CS_STAT.exists():
        pytest.skip("cs-stat.svg not present")
    return parse.parse_svg(CS_STAT)


def test_stroke_count_floor(parsed):
    assert len(parsed.strokes) >= 50_000


def test_image_count_floor(parsed):
    assert len(parsed.images) >= 10


def test_viewbox_plausible(parsed):
    x, y, w, h = parsed.viewbox
    assert w > 5_000 and h > 5_000


def test_box_and_edge_counts(parsed):
    bs = boxes.find_boxes(parsed.strokes)
    edges, review = arrows.find_edges(parsed.strokes, bs)
    assert 100 <= len(bs) <= 260
    assert 10 <= len(edges) <= 40


def test_region_and_combined_edge_counts(parsed):
    bs = boxes.find_boxes(parsed.strokes)
    bind.bind(parsed.strokes, parsed.images, bs, [])
    regs = regions.find_regions(parsed.strokes, bs)
    edges, _ = arrows.find_edges(parsed.strokes, bs + regs)
    assert 100 <= len(regs) <= 260
    assert len(edges) >= 15  # combined edges floor (last calibration observed 27)
