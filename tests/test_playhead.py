"""Moving the playhead: when it replays a step, and when it must not."""

import pytest
import bpy

from scenecast import replay
from scenecast.state import SESSION


class _Scene(dict):
    """A scene whose playhead behaves like the registered RNA property.

    Writing it runs the update callback, exactly as Blender does. The dict
    half stands in for custom properties, which on Blender 5.0 are a separate
    container from the property -- the separation that caused the bug.
    """

    def __init__(self, playhead=0):
        super().__init__()
        self._playhead = playhead

    @property
    def scenecast_playhead(self):
        return self._playhead

    @scenecast_playhead.setter
    def scenecast_playhead(self, value):
        self._playhead = value
        replay._playhead_update(self, None)


@pytest.fixture
def replayed(monkeypatch):
    """Record which steps get replayed instead of touching any meshes."""
    calls = []
    monkeypatch.setattr(replay, "_apply_step", lambda idx, *a, **k: calls.append(idx))
    SESSION.reset()
    SESSION.steps = [{"objs": {}} for _ in range(14)]
    yield calls
    SESSION.reset()


@pytest.fixture
def blender_version(monkeypatch):
    def set_version(version):
        monkeypatch.setattr(bpy.app, "version", version)
    return set_version


# ----------------------------------------------------------------------------
# The reported bug
# ----------------------------------------------------------------------------
def test_set_playhead_moves_the_number_the_slider_shows(replayed):
    """The Scrub slider reads the property, not a custom property of the same
    name -- on Blender 5.0 those are different things."""
    scene = _Scene()
    replay.set_playhead(scene, 9)
    assert scene.scenecast_playhead == 9
    assert "scenecast_playhead" not in scene


def test_set_playhead_does_not_replay(replayed):
    """Following the newest step, or tracking playback, must not re-apply the
    step: during capture that would fight the edit being recorded."""
    replay.set_playhead(_Scene(), 5)
    assert replayed == []


def test_set_playhead_never_goes_negative(replayed):
    scene = _Scene()
    replay.set_playhead(scene, -3)
    assert scene.scenecast_playhead == 0


# ----------------------------------------------------------------------------
# Scrubbing by hand still replays
# ----------------------------------------------------------------------------
def test_dragging_the_slider_replays_that_step(replayed):
    scene = _Scene()
    scene.scenecast_playhead = 6
    assert replayed == [6]


def test_dragging_past_the_end_lands_on_the_last_step(replayed):
    """The property's range is fixed at registration; the session's is not.
    A playhead of 14 in a 14-step session points at nothing."""
    scene = _Scene()
    scene.scenecast_playhead = 14
    assert scene.scenecast_playhead == 13
    assert replayed == [13]


def test_dragging_far_past_the_end_also_clamps(replayed):
    scene = _Scene()
    scene.scenecast_playhead = 100000
    assert scene.scenecast_playhead == 13
    assert replayed == [13]


@pytest.mark.parametrize("state", ["recording", "playing"])
def test_scrubbing_is_inert_while_recording_or_playing(replayed, state):
    setattr(SESSION, state, True)
    _Scene().scenecast_playhead = 4
    assert replayed == []


def test_scrubbing_an_empty_session_does_nothing(replayed):
    SESSION.steps = []
    _Scene().scenecast_playhead = 3
    assert replayed == []


# ----------------------------------------------------------------------------
# Cleaning up after the old write
# ----------------------------------------------------------------------------
def test_the_stray_custom_property_is_removed_on_blender_5(replayed, blender_version):
    blender_version((5, 0, 0))
    scene = _Scene()
    scene["scenecast_playhead"] = 13          # what the old code left behind
    replay.set_playhead(scene, 2)
    assert "scenecast_playhead" not in scene
    assert scene.scenecast_playhead == 2


def test_the_key_is_left_alone_before_blender_5(replayed, blender_version):
    """Before 5.0 the same key *is* the property's storage; deleting it would
    reset the playhead."""
    blender_version((4, 2, 0))
    scene = _Scene()
    scene["scenecast_playhead"] = 13
    replay.set_playhead(scene, 2)
    assert scene["scenecast_playhead"] == 13
