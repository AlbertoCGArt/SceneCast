"""The Scrub slider counts steps from 1, like everything else in the panel.

It showed the playhead's 0-based index, so "Scrub 26" sat above
"Step 27 / 44". The stored playhead stays 0-based: saved files and every
module read it as an index.
"""
import inspect

from scenecast import props, ui


class _Scene:
    def __init__(self, playhead=0):
        self.scenecast_playhead = playhead


def test_the_slider_shows_the_step_the_summary_shows():
    sc = _Scene(26)
    assert props._scrub_get(sc) == 27
    assert ui.step_summary(26, 44, {"op": "Bevel", "t": 0.0}, 0.0).startswith(
        "Step 27 / 44")


def test_dragging_it_moves_the_0_based_playhead():
    sc = _Scene(0)
    props._scrub_set(sc, 27)
    assert sc.scenecast_playhead == 26


def test_it_cannot_reach_before_the_first_step():
    sc = _Scene(5)
    props._scrub_set(sc, 0)
    assert sc.scenecast_playhead == 0


def test_the_panel_draws_the_1_based_slider():
    src = inspect.getsource(ui.SCENECAST_PT_playback.draw)
    assert '"scenecast_scrub_step"' in src
    assert 'prop(sc, "scenecast_playhead"' not in src


def test_it_is_registered_and_removed_with_the_rest():
    assert "scenecast_scrub_step" in props._PROP_NAMES
