"""A camera move must not re-read the meshes.

Orbiting fires no depsgraph update, so camera steps come off a 0.7s clock.
Taking a full snapshot on that clock made navigation stutter: a snapshot
rebuilds every object's edge and face lists in Python. Nothing about the
geometry changed, so the previous step's snapshots are shared by reference.
"""
import numpy as np
from scenecast.capture import _capture_view_step
from scenecast.state import SESSION


def _snapshot():
    return {"vcount": 8, "fcount": 6,
            "coords": np.zeros(24, dtype=np.float32),
            "edges": [(0, 1)] * 12, "faces": [(0, 1, 2, 3)] * 6}


def _seed_one_step():
    SESSION.reset()
    SESSION.steps.append({"t": 1.0, "objs": {"Cube": _snapshot()}})
    return SESSION.steps[0]


def test_camera_step_shares_the_previous_snapshots():
    first = _seed_one_step()
    _capture_view_step()
    assert len(SESSION.steps) == 2
    # the same dict, not a copy: this is what makes the step nearly free
    assert SESSION.steps[1]["objs"] is first["objs"]
    assert SESSION.steps[1]["objs"]["Cube"] is first["objs"]["Cube"]


def test_camera_step_is_marked_as_changing_no_geometry():
    _seed_one_step()
    _capture_view_step()
    assert SESSION.steps[1]["geo_new"] is False


def test_camera_step_claims_pending_keystrokes():
    _seed_one_step()
    SESSION.pending_keys.extend(["MMB", "Wheel Dn"])
    _capture_view_step()
    assert SESSION.steps[1]["keys"] == ["MMB", "Wheel Dn"]
    assert SESSION.pending_keys == []


def test_a_settling_edit_wins_over_a_camera_step():
    # a real change is mid-debounce; recording its geometry as unchanged
    # would freeze the edit out of the session
    _seed_one_step()
    SESSION.pending = True
    _capture_view_step()
    assert len(SESSION.steps) == 1


def test_nothing_recorded_yet_is_a_no_op():
    SESSION.reset()
    _capture_view_step()
    assert SESSION.steps == []
