"""Framing a static view: bounding box -> view_distance.

A fixed axis view is pointed once and framed once, on the session's last step
where the model is largest, so it grows into frame rather than overflowing.
"""
import math

import numpy as np
import pytest

from scenecast.viewnav import (fit_distance, snapshot_bbox, FIXED_VIEW_ROT,
                               FIXED_VIEW_AXES, STATIC_VIEW_MODES)


def _visible_width(distance, lens=50.0, sensor=72.0):
    """Inverse of the framing maths: what a distance actually shows."""
    return 2.0 * distance * math.tan(math.atan((sensor * 0.5) / lens))


# -- fit_distance -------------------------------------------------------------
def test_the_box_fits_with_the_margin_to_spare():
    d = fit_distance(4.0, 2.0, aspect=16 / 9)
    assert _visible_width(d) >= 4.0 * 1.10 - 1e-9


def test_a_bigger_box_needs_more_distance():
    assert fit_distance(8.0, 2.0, 1.0) > fit_distance(4.0, 2.0, 1.0)


def test_distance_scales_linearly_with_size():
    assert fit_distance(8.0, 4.0, 1.5) == pytest.approx(
        2.0 * fit_distance(4.0, 2.0, 1.5))


def test_a_tall_box_is_framed_by_its_height():
    # in a wide viewport, height is the binding constraint
    wide = fit_distance(1.0, 10.0, aspect=2.0)
    assert _visible_width(wide) / 2.0 >= 10.0 * 1.10 - 1e-9


def test_a_wide_box_is_framed_by_its_width():
    d = fit_distance(10.0, 1.0, aspect=2.0)
    assert _visible_width(d) >= 10.0 * 1.10 - 1e-9


def test_portrait_viewports_frame_correctly_too():
    # sensor maps to the taller dimension; the box must still fit
    d = fit_distance(2.0, 10.0, aspect=0.5)
    visible_h = _visible_width(d)
    assert visible_h >= 10.0 * 1.10 - 1e-9
    assert visible_h * 0.5 >= 2.0 * 1.10 - 1e-9


def test_a_zero_sized_box_still_yields_a_usable_distance():
    assert fit_distance(0.0, 0.0, 1.0) > 0.0


def test_degenerate_aspect_does_not_divide_by_zero():
    assert fit_distance(1.0, 1.0, 0.0) > 0.0


# -- snapshot_bbox ------------------------------------------------------------
def _snap(points, mat=None):
    return {"coords": np.asarray(points, dtype=np.float32).ravel(), "mat": mat}


def test_bbox_spans_every_object():
    lo, hi = snapshot_bbox({
        "A": _snap([[0, 0, 0], [1, 1, 1]]),
        "B": _snap([[-2, 0, 0], [0, 3, 0]]),
    })
    assert list(lo) == [-2.0, 0.0, 0.0]
    assert list(hi) == [1.0, 3.0, 1.0]


def test_bbox_is_in_world_space():
    shift = [[1, 0, 0, 10], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    lo, hi = snapshot_bbox({"A": _snap([[0, 0, 0], [1, 0, 0]], mat=shift)})
    assert lo[0] == pytest.approx(10.0)
    assert hi[0] == pytest.approx(11.0)


def test_bbox_of_nothing_is_reported_as_nothing():
    assert snapshot_bbox({}) == (None, None)
    assert snapshot_bbox(None) == (None, None)
    assert snapshot_bbox({"A": {"coords": None}}) == (None, None)


# -- orientation table --------------------------------------------------------
def test_every_fixed_view_is_a_unit_quaternion():
    for name, q in FIXED_VIEW_ROT.items():
        assert math.isclose(sum(c * c for c in q), 1.0, rel_tol=1e-9), name


def test_every_fixed_view_maps_two_distinct_screen_axes():
    for name in FIXED_VIEW_ROT:
        w, h = FIXED_VIEW_AXES[name]
        assert w != h and {w, h} <= {0, 1, 2}, name


def test_static_modes_cover_the_fixed_axes_and_the_camera():
    assert STATIC_VIEW_MODES == set(FIXED_VIEW_ROT) | {'CAMERA'}
    assert 'RECORDED' not in STATIC_VIEW_MODES
    assert 'CURRENT' not in STATIC_VIEW_MODES
