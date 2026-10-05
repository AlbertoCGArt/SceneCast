"""Keys follow the caption: a step credited to an operator shows its shortcut.

In a real 5.2 session the caption on three steps of Bevel cuts said "Bevel"
and the keys under them were blank. Sessions record operator ids the way
wm.operators reports them, 'MESH_OT_bevel', and the shortcut lookup only
knew the Python form, 'mesh.bevel' -- so no recorded step ever resolved its
shortcut, and the keys came only from what the logger caught.
"""
import pytest

from scenecast import overlay
from scenecast.overlay import keys_for_step, op_label_for_step, shortcut_for_operator
from scenecast.state import SESSION


@pytest.fixture
def keymap(monkeypatch):
    """A keymap that knows Bevel and Loop Select by their Python ids."""
    monkeypatch.setattr(overlay, "_SHORTCUT_CACHE",
                        {"mesh.bevel": "Ctrl+B", "mesh.loop_select": "Alt+LMB",
                         "mesh.select_all": "A"})


def _step(op_id, op, geo, verts, keys=()):
    return {"op_id": op_id, "op": op, "geo_new": geo, "keys": list(keys),
            "objs": {"Plane": {"vcount": verts, "fcount": verts}}, "t": 0.0}


SELECT = ("MESH_OT_loop_select", "Loop Select")
BEVEL = ("MESH_OT_bevel", "Bevel")
EDIT = ("OBJECT_OT_editmode_toggle", "Edit Mode")
ALL = ("MESH_OT_select_all", "(De)select All")


def _session(steps):
    SESSION.reset()
    SESSION.steps.extend(steps)


def test_a_modal_bevel_run_twice_keeps_its_keys_on_every_cut(keymap):
    _session([
        _step(*EDIT, geo=False, verts=36),
        _step(*SELECT, geo=True, verts=48, keys=["Ctrl+B"]),   # first bevel's cuts
        _step(*SELECT, geo=True, verts=64),
        _step(*BEVEL, geo=True, verts=64),                      # first one confirmed
        _step(*BEVEL, geo=True, verts=80),                      # second bevel, same id
        _step(*BEVEL, geo=True, verts=96),
        _step(*ALL, geo=False, verts=96),
    ])
    for i in range(1, 6):
        assert op_label_for_step(i) == "Bevel", i
        assert keys_for_step(i) == ["Ctrl+B"], i


def test_the_recorded_id_and_the_python_id_find_the_same_shortcut(keymap):
    assert shortcut_for_operator("MESH_OT_bevel") == "Ctrl+B"
    assert shortcut_for_operator("mesh.bevel") == "Ctrl+B"


def test_a_menu_operator_recorded_c_style_still_gets_its_menu_key(monkeypatch):
    monkeypatch.setattr(overlay, "_SHORTCUT_CACHE", {})
    assert shortcut_for_operator("MESH_OT_primitive_cube_add") == "Shift+A"
    assert shortcut_for_operator("OBJECT_OT_duplicate_move") == "Shift+D"
