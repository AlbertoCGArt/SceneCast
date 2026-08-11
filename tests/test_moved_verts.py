"""Only vertices that actually changed get written back per frame.

bmesh has no foreach_set, so each vertex costs a Python round trip. A typical
edit moves a handful out of tens of thousands, and every frame of a step's
hold asks about the same pair of snapshots.
"""
import numpy as np
from scenecast.replay import _moved_verts


def _snap(coords):
    return {"coords": np.array(coords, dtype=np.float32)}


def test_identical_geometry_reports_nothing_to_write():
    a = _snap([0, 0, 0, 1, 1, 1])
    b = _snap([0, 0, 0, 1, 1, 1])
    assert len(_moved_verts(a, b)) == 0


def test_only_the_moved_vertex_is_reported():
    a = _snap([0, 0, 0, 1, 1, 1, 2, 2, 2])
    b = _snap([0, 0, 0, 1, 9, 1, 2, 2, 2])
    assert list(_moved_verts(a, b)) == [1]


def test_a_vertex_counts_as_moved_on_any_axis():
    a = _snap([0, 0, 0, 5, 5, 5])
    b = _snap([0, 0, 7, 5, 5, 5])
    assert list(_moved_verts(a, b)) == [0]


def test_every_moved_vertex_is_reported():
    a = _snap([0, 0, 0, 1, 1, 1, 2, 2, 2])
    b = _snap([9, 0, 0, 1, 1, 1, 9, 2, 2])
    assert list(_moved_verts(a, b)) == [0, 2]


def test_mismatched_lengths_are_not_interpolated():
    a = _snap([0, 0, 0])
    b = _snap([0, 0, 0, 1, 1, 1])
    assert len(_moved_verts(a, b)) == 0


def test_missing_coordinates_are_handled():
    assert len(_moved_verts({}, _snap([0, 0, 0]))) == 0
    assert len(_moved_verts(_snap([0, 0, 0]), {})) == 0


def test_the_answer_is_not_memoised_onto_the_snapshot():
    # Caching this cheap numpy result onto the snapshot linked each step to
    # the next, and anything walking the session to save it then pulled in
    # every later step from each step.
    a = _snap([0, 0, 0, 1, 1, 1])
    b = _snap([0, 0, 0, 2, 1, 1])
    _moved_verts(a, b)
    assert set(a) == {"coords"} and set(b) == {"coords"}


def test_each_successor_is_answered_independently():
    a = _snap([0, 0, 0, 1, 1, 1])
    b = _snap([0, 0, 0, 2, 1, 1])
    c = _snap([0, 0, 0, 1, 1, 1])          # identical to a
    assert list(_moved_verts(a, b)) == [1]
    assert len(_moved_verts(a, c)) == 0    # must not reuse b's answer
