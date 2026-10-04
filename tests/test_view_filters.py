"""View filters adjust the view they were given, never their own output."""

import pytest
import bpy
from mathutils import Quaternion, Vector

from scenecast import viewnav, replay
from scenecast.state import SESSION


class _RV3D:
    def __init__(self, dist=10.0, rot=(1.0, 0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
        self.view_perspective = 'PERSP'
        self.view_rotation = Quaternion(rot)
        self.view_distance = dist
        self.view_location = Vector(loc)


@pytest.fixture
def rv3d(monkeypatch):
    view = _RV3D()
    monkeypatch.setattr(viewnav, "_get_view3d_rv3d", lambda: view)
    monkeypatch.setattr(viewnav, "_VIEW_FILTERS", [])
    monkeypatch.setattr(viewnav, "_FILTER_VIEW", {"base": None, "result": None},
                        raising=False)
    return view


def _halve_distance(rv3d, idx, frac):
    rv3d.view_distance = rv3d.view_distance * 0.5


# ----------------------------------------------------------------------------
def test_a_filter_does_not_compound_when_nothing_resets_the_camera(rv3d):
    """Current View and the static views never rewrite the camera between
    frames. Before this, a 50% punch reached 100% within a few frames."""
    viewnav.register_view_filter(_halve_distance)
    for _ in range(6):
        viewnav.apply_view_filters(0, 0.0)
        assert rv3d.view_distance == pytest.approx(5.0)


def test_a_fresh_camera_each_frame_becomes_the_base(rv3d):
    """Recorded Views sets the camera every frame; each one is filtered once."""
    viewnav.register_view_filter(_halve_distance)
    for recorded in (10.0, 12.0, 8.0):
        viewnav._set_view(rv3d, 'PERSP', Quaternion(), recorded, Vector())
        viewnav.apply_view_filters(0, 0.0)
        assert rv3d.view_distance == pytest.approx(recorded / 2.0)


def test_orbiting_by_hand_while_paused_is_respected(rv3d):
    """If the artist moved the camera since the filters ran, that view is what
    the filters should start from -- not the one before it."""
    viewnav.register_view_filter(_halve_distance)
    viewnav.apply_view_filters(0, 0.0)
    rv3d.view_rotation = Quaternion((0.0, 0.0, 1.0), 1.0)     # orbit
    rv3d.view_distance = 30.0
    viewnav.apply_view_filters(0, 0.0)
    assert rv3d.view_distance == pytest.approx(15.0)


def test_switching_a_filter_off_hands_back_the_original_view(rv3d):
    """Punching out has to restore the framing that was there before."""
    state = {"on": True}

    def maybe_halve(view, idx, frac):
        if state["on"]:
            view.view_distance *= 0.5
    viewnav.register_view_filter(maybe_halve)
    viewnav.apply_view_filters(0, 0.0)
    assert rv3d.view_distance == pytest.approx(5.0)
    state["on"] = False
    viewnav.apply_view_filters(0, 0.0)
    assert rv3d.view_distance == pytest.approx(10.0)


def test_no_filters_means_the_camera_is_never_touched(rv3d):
    viewnav.apply_view_filters(0, 0.0)
    assert rv3d.view_distance == 10.0
    assert viewnav._FILTER_VIEW["base"] is None


def test_a_failing_filter_does_not_stop_the_others(rv3d):
    def broken(view, idx, frac):
        raise RuntimeError("boom")
    viewnav.register_view_filter(broken)
    viewnav.register_view_filter(_halve_distance)
    viewnav.apply_view_filters(0, 0.0)
    assert rv3d.view_distance == pytest.approx(5.0)


# ----------------------------------------------------------------------------
# Live refresh while paused
# ----------------------------------------------------------------------------
@pytest.fixture
def paused(rv3d, monkeypatch):
    calls = []
    viewnav.register_view_filter(lambda view, idx, frac: calls.append(idx))
    SESSION.reset()
    SESSION.steps = [{"objs": {}} for _ in range(10)]
    monkeypatch.setattr(bpy.context.scene, "scenecast_playhead", 4, raising=False)
    monkeypatch.setattr(bpy.context.scene, "scenecast_view_mode", 'CURRENT',
                        raising=False)
    yield calls
    SESSION.reset()


def test_refresh_reapplies_the_filters_at_the_playhead(paused):
    replay.refresh_view()
    assert paused == [4]


@pytest.mark.parametrize("state", ["playing", "recording", "export_active"])
def test_refresh_leaves_the_camera_alone_when_something_else_owns_it(paused, state):
    setattr(SESSION, state, True)
    replay.refresh_view()
    assert paused == []


def test_refresh_with_nothing_recorded_does_nothing(paused):
    SESSION.steps = []
    replay.refresh_view()
    assert paused == []
