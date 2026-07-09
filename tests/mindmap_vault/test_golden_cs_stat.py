from pathlib import Path

import pytest

from scripts.mindmap_vault import arrows, bind, boxes, parse, regions

CS_STAT = Path(__file__).resolve().parents[2] / "static" / "mindmaps" / "cs-stat.svg"

pytestmark = pytest.mark.golden


@pytest.fixture(scope="module")
def parsed():
    if not CS_STAT.exists():
        pytest.skip("cs-stat.svg not present")
    return parse.parse_svg(CS_STAT)


def test_stroke_count(parsed):
    assert len(parsed.strokes) == 77461 + 4069


def test_image_count(parsed):
    assert len(parsed.images) == 20


def test_viewbox(parsed):
    assert parsed.viewbox == (-5725.477, -3022.085, 11890.705, 10977.893)


def test_box_and_edge_counts(parsed):
    bs = boxes.find_boxes(parsed.strokes)
    edges, review = arrows.find_edges(parsed.strokes, bs)
    # Calibrated against the real export (Task 11). Observed at calibration
    # time: 142 boxes, 16 edges (config.py: ARROW_MIN_LEN/ARROW_LINEARITY
    # now use chord length + straightness instead of raw arc length, and
    # END_TOL widened to 20 to catch hand-drawn multi-segment arrows whose
    # tips land a bit short of the box border). Band is ±10% around the
    # observed values, not exact, to allow small future threshold
    # refinements without test churn.
    assert 128 <= len(bs) <= 157
    assert 14 <= len(edges) <= 18


def test_region_and_combined_edge_counts(parsed):
    # Calibrated after R2 (unboxed-region ingestion). Observed: 132 regions,
    # 29 raw geometric edges over boxes+regions (the pipeline reports 22
    # after excluding edges touching dropped records). Bands are ±10%.
    bs = boxes.find_boxes(parsed.strokes)
    bind.bind(parsed.strokes, parsed.images, bs, [])
    regs = regions.find_regions(parsed.strokes, bs)
    edges, _ = arrows.find_edges(parsed.strokes, bs + regs)
    assert 119 <= len(regs) <= 145
    assert 26 <= len(edges) <= 32
