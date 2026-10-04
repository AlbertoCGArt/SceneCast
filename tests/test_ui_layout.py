"""The N-panel reads top to bottom in the order a session is made.

Record, Capture Settings, Playback (with Step Details inside it), Export --
with Pro's sections slotting in between by bl_order. A sub-panel whose parent
is not registered yet fails to register, so registration order is part of
the layout.
"""

import inspect

import pytest

import scenecast
from scenecast import ui
from scenecast.state import SESSION


@pytest.fixture
def session():
    SESSION.reset()
    yield SESSION
    SESSION.reset()


EXPECTED = {
    "SCENECAST_PT_panel": (None, 0),
    "SCENECAST_PT_capture": ("SCENECAST_PT_panel", 1),
    "SCENECAST_PT_playback": ("SCENECAST_PT_panel", 2),
    "SCENECAST_PT_step_info": ("SCENECAST_PT_playback", 0),
    "SCENECAST_PT_export": ("SCENECAST_PT_panel", 6),
}


def _panels():
    return [cls for _n, cls in inspect.getmembers(ui, inspect.isclass)
            if cls.__module__ == ui.__name__ and hasattr(cls, "bl_idname")
            and cls.__name__.startswith("SCENECAST_PT_")]


def test_every_panel_is_where_the_layout_puts_it():
    found = {cls.bl_idname: (getattr(cls, "bl_parent_id", None), cls.bl_order)
             for cls in _panels()}
    assert found == EXPECTED


def test_every_panel_is_registered():
    assert set(c.bl_idname for c in _panels()) <= \
        set(getattr(c, "bl_idname", "") for c in scenecast._classes)


def test_parents_register_before_their_children():
    seen = set()
    for cls in scenecast._classes:
        parent = getattr(cls, "bl_parent_id", None)
        if parent:
            assert parent in seen, "%s registers before %s" % (cls.__name__, parent)
        if hasattr(cls, "bl_idname"):
            seen.add(cls.bl_idname)


def test_sub_panels_live_in_the_sidebar_tab():
    for cls in _panels():
        assert (cls.bl_space_type, cls.bl_region_type, cls.bl_category) == \
            ('VIEW_3D', 'UI', "SceneCast")


def test_no_label_says_pro():
    for cls in scenecast._classes:
        assert "(Pro)" not in getattr(cls, "bl_label", "")


@pytest.mark.parametrize("idname,closed", [
    ("SCENECAST_PT_capture", True), ("SCENECAST_PT_step_info", True),
    ("SCENECAST_PT_playback", False), ("SCENECAST_PT_export", False),
])
def test_what_starts_closed(idname, closed):
    cls = next(c for c in _panels() if c.bl_idname == idname)
    assert ('DEFAULT_CLOSED' in getattr(cls, "bl_options", set())) == closed


def test_playback_and_export_wait_for_a_session(session):
    for idname in ("SCENECAST_PT_playback", "SCENECAST_PT_step_info",
                   "SCENECAST_PT_export"):
        cls = next(c for c in _panels() if c.bl_idname == idname)
        assert not cls.poll(None)
        session.steps.append({"t": 0.0})
        assert cls.poll(None)
        session.steps.clear()


def test_clear_session_asks_first():
    from scenecast.ops import SCENECAST_OT_clear
    assert hasattr(SCENECAST_OT_clear, "invoke")
    assert "invoke_confirm" in inspect.getsource(SCENECAST_OT_clear.invoke)


# ----------------------------------------------------------------------------
# The one-line summaries
# ----------------------------------------------------------------------------
def test_elapsed_reads_like_a_player():
    assert ui.elapsed_text(0) == "0:00"
    assert ui.elapsed_text(75.9) == "1:15"
    assert ui.elapsed_text(-3) == "0:00"


def test_step_summary():
    step = {"op": "Bevel", "t": 112.0}
    assert ui.step_summary(2, 40, step, 100.0) == \
        "Step 3 / 40  ·  Bevel  ·  0:12"


def test_a_step_without_an_operator_shows_a_dash():
    for op in ("", "(edit)"):
        assert "—" in ui.step_summary(0, 1, {"op": op, "t": 0.0}, 0.0)


class _Scene:
    scenecast_step_hold = 0.8
    scenecast_view_mode = 'RECORDED'
    scenecast_export_res = 'CUSTOM'
    scenecast_export_res_x = 1080
    scenecast_export_res_y = 1350


def test_export_summary_names_a_custom_size_by_its_pixels():
    assert ui.export_summary(_Scene()) == \
        "0.80s / step  ·  RECORDED  ·  1080x1350"


def test_memory_readout_warns_at_three_quarters(session, monkeypatch):
    class Sc:
        scenecast_memory_limit = 100
    session.bytes_est = 74 * (1 << 20)
    assert ui.memory_readout(Sc())[1] == 'NONE'
    session.bytes_est = 75 * (1 << 20)
    text, icon = ui.memory_readout(Sc())
    assert icon == 'ERROR' and text.endswith("of 100 MB")


def test_memory_readout_without_a_limit():
    class Sc:
        scenecast_memory_limit = 0
    assert ui.memory_readout(Sc())[1] == 'NONE'


def test_step_summary_names_the_tool_the_caption_names():
    """The raw op is whatever wm.operators had finished; the caption is the
    tool that made the change. The panel shows the caption's."""
    step = {"op": "Edit Mode", "t": 3.0}
    assert "Inset Faces" in ui.step_summary(1, 44, step, 0.0, "Inset Faces")
    assert "\u2014" in ui.step_summary(1, 44, step, 0.0, "")
