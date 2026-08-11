"""Recorded steps must stay plain data.

Anything that persists a session walks SESSION.steps. A value that references
another step turns the session into a linked chain, and the walk then drags in
every later step from each step -- measured at 34x bloat over 200 steps and a
RecursionError by 500. Interpolation caches therefore do not belong on the
snapshots.
"""
import numpy as np
from scenecast.replay import _moved_verts

SERIALIZABLE = (type(None), bool, int, float, str, tuple, list, dict, np.ndarray)


def _snapshot(coords):
    return {"vcount": len(coords) // 3, "fcount": 1,
            "coords": np.asarray(coords, dtype=np.float32)}


def test_diffing_two_snapshots_does_not_write_back_to_them():
    a, b = _snapshot([0, 0, 0, 1, 1, 1]), _snapshot([0, 0, 0, 2, 2, 2])
    before_a, before_b = set(a), set(b)
    _moved_verts(a, b)
    assert set(a) == before_a, "diffing added a key to the snapshot"
    assert set(b) == before_b


def test_repeated_diffs_never_accumulate_state():
    a, b = _snapshot([0, 0, 0, 1, 1, 1]), _snapshot([0, 0, 0, 2, 2, 2])
    for _ in range(50):                      # every frame of a step's hold
        _moved_verts(a, b)
    assert set(a) == {"vcount", "fcount", "coords"}


def test_no_snapshot_value_references_another_snapshot():
    steps = [{"objs": {"Cube": _snapshot([0, 0, 0, float(i), 0, 0])}}
             for i in range(6)]
    for i in range(len(steps) - 1):
        _moved_verts(steps[i]["objs"]["Cube"], steps[i + 1]["objs"]["Cube"])
    for s in steps:
        for snap in s["objs"].values():
            for key, val in snap.items():
                assert isinstance(val, SERIALIZABLE), (key, type(val))
                # a tuple/list holding a dict is the chain that breaks storage
                if isinstance(val, (tuple, list)):
                    assert not any(isinstance(x, dict) for x in val), key


def test_moved_indices_are_correct_and_minimal():
    a = _snapshot([0, 0, 0, 1, 1, 1, 5, 5, 5])
    b = _snapshot([0, 0, 0, 9, 1, 1, 5, 5, 5])
    assert list(_moved_verts(a, b)) == [1]   # only vertex 1 changed


def test_identical_snapshots_report_nothing_moved():
    a, b = _snapshot([1, 2, 3, 4, 5, 6]), _snapshot([1, 2, 3, 4, 5, 6])
    assert len(_moved_verts(a, b)) == 0


def test_mismatched_lengths_are_safe():
    assert len(_moved_verts(_snapshot([0, 0, 0]), _snapshot([0, 0, 0, 1, 1, 1]))) == 0
    assert len(_moved_verts({}, {})) == 0
