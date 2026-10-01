"""Unchanged objects share one snapshot instead of being copied per step."""

import numpy as np
import pytest
import bpy

from scenecast import capture
from scenecast.state import SESSION
from scenecast.meshdata import snapshot_digest, session_bytes, _STEP_OVERHEAD

_IDENTITY = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
             [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


class _FakeObject:
    """An object whose 'mesh' is just the coordinate buffer we hand it."""

    def __init__(self, name, coords):
        self.name = name
        self.coords = np.asarray(coords, dtype=np.float32)
        self.data = self

    @property
    def vertices(self):
        return [None] * (len(self.coords) // 3)


def _fake_snapshot(obj, want_mods=False):
    n = len(obj.coords) // 3
    data = {
        "vcount": n, "ecount": 0, "fcount": 0,
        "coords": obj.coords.copy(),
        "edges": np.empty(0, np.int32), "faces": np.empty(0, np.int32),
        "floops": np.empty(0, np.int32),
        "vsel": np.zeros(n, bool), "esel": np.empty(0, bool),
        "fsel": np.empty(0, bool),
        "mat": _IDENTITY, "mods": None,
    }
    data["h"] = snapshot_digest(data)
    return data


@pytest.fixture
def scene(monkeypatch):
    SESSION.reset()
    objects = [_FakeObject(n, [0.0] * 300) for n in "ABCDE"]
    monkeypatch.setattr(capture, "_visible_mesh_objects", lambda: objects)
    monkeypatch.setattr(capture, "_isolate_objects", lambda objs: None)
    monkeypatch.setattr(capture, "_snapshot_object", _fake_snapshot)
    bpy.context.scene.scenecast_memory_limit = 0
    yield objects
    SESSION.reset()


def _distinct_snapshots():
    return len({id(d) for s in SESSION.steps for d in s["objs"].values()})


def _distinct_tables():
    return len({id(s["objs"]) for s in SESSION.steps})


def test_only_the_edited_object_costs_a_new_snapshot(scene):
    edited = scene[0]
    for i in range(1, 11):
        edited.coords[0] = float(i)
        capture._capture_step()
    assert len(SESSION.steps) == 10
    # 10 versions of A, plus one shared snapshot each for B, C, D and E.
    assert _distinct_snapshots() == 14


def test_untouched_objects_alias_the_previous_step(scene):
    edited = scene[0]
    for i in range(1, 4):
        edited.coords[0] = float(i)
        capture._capture_step()
    first, last = SESSION.steps[0], SESSION.steps[-1]
    assert last["objs"]["B"] is first["objs"]["B"]
    assert last["objs"]["A"] is not first["objs"]["A"]


def test_running_estimate_matches_a_full_measurement(scene):
    edited = scene[0]
    for i in range(1, 8):
        edited.coords[0] = float(i)
        capture._capture_step()
    assert SESSION.bytes_est == session_bytes(SESSION.steps)


def test_a_step_that_changes_nothing_is_not_recorded(scene):
    capture._capture_step()
    capture._capture_step()
    assert len(SESSION.steps) == 1


def test_a_selection_only_step_still_gets_its_own_snapshot(scene):
    """Selection lives in the snapshot, so a step that only changes what is
    selected must not share the previous step's dict."""
    capture._capture_step()

    def selected(obj, want_mods=False):
        data = _fake_snapshot(obj, want_mods)
        if obj.name == "A":
            data["vsel"] = np.ones(data["vcount"], bool)
            data["h"] = snapshot_digest(data)
        return data

    capture._snapshot_object = selected
    try:
        capture._capture_step()
    finally:
        capture._snapshot_object = _fake_snapshot
    assert len(SESSION.steps) == 2
    assert SESSION.steps[1]["objs"]["A"] is not SESSION.steps[0]["objs"]["A"]
    assert SESSION.steps[1]["objs"]["B"] is SESSION.steps[0]["objs"]["B"]


def test_a_camera_step_shares_the_whole_object_table(scene):
    capture._capture_step()
    before = SESSION.bytes_est
    capture._capture_view_step()
    assert len(SESSION.steps) == 2
    assert SESSION.steps[1]["objs"] is SESSION.steps[0]["objs"]
    assert SESSION.bytes_est - before == _STEP_OVERHEAD
    assert _distinct_tables() == 1


def test_recording_stops_at_the_memory_limit(scene):
    SESSION.recording = True
    bpy.context.scene.scenecast_memory_limit = 1     # 1 MB
    edited = scene[0]
    for i in range(1, 400):
        edited.coords[0] = float(i)
        capture._capture_step()
        if SESSION.memory_stopped:
            break
    assert SESSION.memory_stopped is True
    assert SESSION.recording is False
    assert SESSION.steps                             # what was captured is kept


def test_no_limit_never_stops(scene):
    SESSION.recording = True
    bpy.context.scene.scenecast_memory_limit = 0
    edited = scene[0]
    for i in range(1, 60):
        edited.coords[0] = float(i)
        capture._capture_step()
    assert SESSION.memory_stopped is False
    assert SESSION.recording is True
