import time
from pathlib import Path

import pytest

from scripts.mindmap_vault import arrows, bind, boxes, parse, regions
from tests.conftest import REGION_A_IDS, REGION_B_IDS, REGION_BRIDGE_ID, REGION_C_IDS

CS_STAT = Path(__file__).resolve().parents[2] / "static" / "mindmaps" / "cs-stat.svg"


def _pipeline(synthetic_svg):
    r = parse.parse_svg(synthetic_svg)
    bs = boxes.find_boxes(r.strokes)
    edges, _ = arrows.find_edges(r.strokes, bs)
    bind.bind(r.strokes, r.images, bs, edges)
    return r, bs


def test_two_clusters_become_two_regions(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    assert len(rs) == 2


def test_region_membership_matches_clusters(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    member_sets = [set(rg.member_ids) for rg in rs]
    assert set(REGION_A_IDS) in member_sets
    assert set(REGION_B_IDS) in member_sets


def test_regions_have_no_border_and_blank_box_id(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    for rg in rs:
        assert rg.border_ids == []
        assert rg.box_id == ""


def test_region_member_ids_sorted(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    for rg in rs:
        assert rg.member_ids == sorted(rg.member_ids)


def test_region_bbox_is_union_of_members(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    by_id = {s.sid: s for s in r.strokes}
    for rg in rs:
        xs0 = [by_id[sid].bbox[0] for sid in rg.member_ids]
        ys0 = [by_id[sid].bbox[1] for sid in rg.member_ids]
        xs1 = [by_id[sid].bbox[2] for sid in rg.member_ids]
        ys1 = [by_id[sid].bbox[3] for sid in rg.member_ids]
        assert rg.bbox == (min(xs0), min(ys0), max(xs1), max(ys1))


def test_connector_excluded_and_does_not_bridge_clusters(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    all_members = {sid for rg in rs for sid in rg.member_ids}
    assert REGION_BRIDGE_ID not in all_members
    # If the bridge glued A and B together, there would be one big region
    # instead of two, and it would contain members from both clusters.
    assert len(rs) == 2
    for rg in rs:
        assert not (set(REGION_A_IDS) & set(rg.member_ids) and
                    set(REGION_B_IDS) & set(rg.member_ids))


def test_small_pair_filtered_out(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    all_members = {sid for rg in rs for sid in rg.member_ids}
    assert not (set(REGION_C_IDS) & all_members)


def test_decoy_alone_filtered_out(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    all_members = {sid for rg in rs for sid in rg.member_ids}
    assert "decoy" not in all_members


def test_box_members_and_borders_excluded_from_candidates(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    all_members = {sid for rg in rs for sid in rg.member_ids}
    taken = {sid for b in bs for sid in b.border_ids} | {sid for b in bs for sid in b.member_ids}
    assert all_members.isdisjoint(taken)


def test_deterministic_order_and_membership(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs1 = regions.find_regions(r.strokes, bs)
    rs2 = regions.find_regions(r.strokes, bs)
    assert [(rg.bbox, rg.member_ids) for rg in rs1] == [(rg.bbox, rg.member_ids) for rg in rs2]


def test_sorted_by_y_then_x(synthetic_svg):
    r, bs = _pipeline(synthetic_svg)
    rs = regions.find_regions(r.strokes, bs)
    keys = [(rg.bbox[1], rg.bbox[0]) for rg in rs]
    assert keys == sorted(keys)


def test_no_regions_when_no_strokes():
    assert regions.find_regions([], []) == []


@pytest.mark.golden
def test_perf_real_file_unbound_strokes():
    if not CS_STAT.exists():
        pytest.skip("cs-stat.svg not present")
    parsed = parse.parse_svg(CS_STAT)
    bs = boxes.find_boxes(parsed.strokes)
    edges, _ = arrows.find_edges(parsed.strokes, bs)
    bind.bind(parsed.strokes, parsed.images, bs, edges)
    start = time.monotonic()
    rs = regions.find_regions(parsed.strokes, bs)
    elapsed = time.monotonic() - start
    assert elapsed < 30.0
    assert isinstance(rs, list)
