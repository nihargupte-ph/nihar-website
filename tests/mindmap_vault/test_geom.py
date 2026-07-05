import math

from scripts.mindmap_vault import geom


def test_bbox_of_and_center():
    pts = [(0, 0), (4, 2), (2, 6)]
    assert geom.bbox_of(pts) == (0, 0, 4, 6)
    assert geom.bbox_center((0, 0, 4, 6)) == (2, 3)


def test_bbox_union_area_expand():
    assert geom.bbox_union((0, 0, 1, 1), (2, 2, 3, 4)) == (0, 0, 3, 4)
    assert geom.bbox_area((1, 1, 3, 5)) == 8
    assert geom.bbox_expand((1, 1, 3, 5), 1) == (0, 0, 4, 6)


def test_bbox_iou():
    assert geom.bbox_iou((0, 0, 2, 2), (0, 0, 2, 2)) == 1.0
    assert geom.bbox_iou((0, 0, 2, 2), (1, 0, 3, 2)) == 0.5 / 1.5
    assert geom.bbox_iou((0, 0, 1, 1), (5, 5, 6, 6)) == 0.0


def test_bbox_contains():
    assert geom.bbox_contains((0, 0, 4, 4), (2, 2))
    assert not geom.bbox_contains((0, 0, 4, 4), (5, 2))


def test_polyline_and_chord_len():
    pts = [(0, 0), (3, 0), (3, 4)]
    assert geom.polyline_len(pts) == 7
    assert geom.chord_len(pts) == 5
    assert geom.polyline_len([(1, 1)]) == 0


def test_point_bbox_dist():
    b = (0, 0, 4, 4)
    assert geom.point_bbox_dist((2, 2), b) == 0
    assert geom.point_bbox_dist((7, 2), b) == 3
    assert math.isclose(geom.point_bbox_dist((7, 8), b), 5.0)


def test_point_rect_outline_dist():
    b = (0, 0, 10, 10)
    assert geom.point_rect_outline_dist((5, 1), b) == 1      # inside, near bottom edge
    assert geom.point_rect_outline_dist((12, 5), b) == 2     # outside
    assert geom.point_rect_outline_dist((0, 5), b) == 0      # on outline
