"""View-change detection: camera moves must become steps of their own.

Viewport navigation never fires a depsgraph update, so without this a session
records nothing until the first mesh edit.
"""
import math
from scenecast.capture import _view_differs


class Q:
    """Minimal quaternion stand-in: only the dot product is exercised."""
    def __init__(self, d=1.0):
        self._d = d

    def dot(self, other):
        return self._d


class V:
    def __init__(self, length=0.0):
        self._len = length

    def __sub__(self, other):
        return self

    @property
    def length(self):
        return self._len


def _step(dot=1.0, dist=10.0, loc_delta=0.0, persp='PERSP'):
    return {"persp": persp, "rot": Q(dot), "dist": dist, "loc": V(loc_delta)}


def test_identical_view_is_not_a_change():
    assert _view_differs(_step(), _step()) is False


def test_missing_view_data_is_not_a_change():
    assert _view_differs({}, _step()) is False
    assert _view_differs(_step(), {}) is False


def test_perspective_switch_is_a_change():
    assert _view_differs(_step(persp='PERSP'), _step(persp='ORTHO')) is True


def test_rotation_beyond_threshold_is_a_change():
    assert _view_differs(_step(dot=0.99), _step(dot=0.99)) is True


def test_tiny_rotation_is_ignored():
    assert _view_differs(_step(dot=0.99999), _step(dot=0.99999)) is False


def test_quaternion_double_cover_uses_absolute_dot():
    # q and -q are the same orientation; a negative dot must not read as motion
    assert _view_differs(_step(dot=-1.0), _step(dot=-1.0)) is False


def test_zoom_beyond_threshold_is_a_change():
    assert _view_differs(_step(dist=10.0), _step(dist=12.0)) is True


def test_zoom_is_relative_to_distance():
    # the same absolute delta is motion when zoomed in, noise when zoomed out
    assert _view_differs(_step(dist=1.0), _step(dist=1.5)) is True
    assert _view_differs(_step(dist=1000.0), _step(dist=1000.5)) is False


def test_pan_beyond_threshold_is_a_change():
    assert _view_differs(_step(dist=10.0, loc_delta=5.0),
                         _step(dist=10.0, loc_delta=5.0)) is True
