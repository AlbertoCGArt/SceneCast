"""A step's caption names the operator that made its change.

Blender reports an operator only when it finishes, so a modal tool's geometry
was captured under the operator before it. In a real 5.2 session the label
trailed every action by one: the Inset captioned "Edit Mode", each Extrude
"Inset Faces", three steps of Bevel cuts "Loop Select".
"""
from scenecast.opcredit import credited_op, op_key, is_passive
from scenecast.overlay import op_label_for_step
from scenecast.state import SESSION


def _snap(v, f):
    return {"vcount": v, "fcount": f}


def _step(op_id, op, geo=True, topo=None, keys=()):
    objs = {"Plane": _snap(*topo)} if topo else {"Plane": _snap(4, 1)}
    return {"op_id": op_id, "op": op, "geo_new": geo, "objs": objs,
            "keys": list(keys)}


def _labels(steps):
    SESSION.reset()
    SESSION.steps.extend(steps)
    return [op_label_for_step(i) for i in range(len(steps))]


SELECT = ("MESH_OT_loop_select", "Loop Select")
BEVEL = ("MESH_OT_bevel", "Bevel")
INSET = ("MESH_OT_inset", "Inset Faces")
EXTRUDE = ("MESH_OT_extrude_region_move", "Extrude Region and Move")
RESIZE = ("TRANSFORM_OT_resize", "Resize")
DUP = ("MESH_OT_duplicate_move", "Add Duplicate")
EDIT = ("OBJECT_OT_editmode_toggle", "Edit Mode")


def test_a_modal_bevel_is_named_on_its_cuts_not_on_the_selection_before_it():
    steps = [_step(*EDIT, geo=False, topo=(36, 29)),
             _step(*SELECT, topo=(48, 41), keys=["Ctrl+B"]),
             _step(*SELECT, topo=(64, 57)),
             _step(*SELECT, topo=(72, 65)),
             _step(*BEVEL, topo=(72, 65))]
    assert _labels(steps)[1:] == ["Bevel"] * 4


def test_an_inset_after_entering_edit_mode_is_called_an_inset():
    steps = [_step(*EDIT, topo=(4, 1)),
             _step(*EDIT, topo=(8, 5), keys=["I"]),
             _step(*INSET, topo=(8, 5))]
    assert _labels(steps)[1:] == ["Inset Faces", "Inset Faces"]


def test_the_next_tool_is_named_while_the_last_one_is_still_reported():
    """Extrude's faces arrive while wm.operators still says Inset."""
    steps = [_step(*INSET, topo=(8, 5)),
             _step(*INSET, topo=(12, 9), keys=["E"]),
             _step(*EXTRUDE, topo=(12, 9))]
    assert _labels(steps)[1] == "Extrude Region and Move"


def test_a_move_is_never_credited_with_new_faces():
    """Shift+D's copies appear under "Resize"; the duplicate names them."""
    steps = [_step(*RESIZE, topo=(28, 23)),
             _step(*RESIZE, topo=(36, 29)),
             _step(*DUP, geo=False, topo=(36, 29))]
    assert _labels(steps)[1] == "Add Duplicate"


def test_a_selection_finishing_next_means_no_tool_is_named():
    """A wrong label is worse than none: the change was made without an
    operator -- typed into a field, say -- and a select followed."""
    steps = [_step(*EDIT, geo=False),
             _step(*EDIT, topo=(8, 5)),
             _step(*SELECT, geo=False, topo=(8, 5))]
    assert _labels(steps)[1] == ""


def test_the_same_tool_twice_keeps_its_name():
    """A repeat reports the same id, so it never shows up as a new finish."""
    steps = [_step(*EXTRUDE, topo=(8, 5)),
             _step(*EXTRUDE, topo=(12, 9)),
             _step(*SELECT, geo=False, topo=(12, 9))]
    assert _labels(steps)[1] == "Extrude Region and Move"


def test_the_keys_on_a_step_settle_a_repeat_against_the_next_tool():
    steps = [_step(*EXTRUDE, topo=(8, 5)),
             _step(*EXTRUDE, topo=(12, 9), keys=["E"]),
             _step(*INSET, topo=(16, 13))]
    SESSION.reset()
    SESSION.steps.extend(steps)
    shortcut = {"MESH_OT_extrude_region_move": "E", "MESH_OT_inset": "I"}.get
    assert credited_op(steps, 1, shortcut)[0] == "Extrude Region and Move"
    steps[1]["keys"] = ["I"]
    assert credited_op(steps, 1, shortcut)[0] == "Inset Faces"


def test_adding_an_object_is_not_credited_to_a_later_tool():
    steps = [{"op_id": "", "op": "(edit)", "geo_new": True,
              "objs": {"Human": _snap(9, 9)}},
             {"op_id": EDIT[0], "op": EDIT[1], "geo_new": True,
              "objs": {"Human": _snap(9, 9), "Plane": _snap(4, 1)}},
             _step(*INSET, topo=(8, 5))]
    assert _labels(steps)[1] == "Edit Mode"


def test_a_step_without_new_geometry_keeps_the_old_rules():
    steps = [_step(*EXTRUDE, topo=(8, 5)),
             _step(*EXTRUDE, geo=False, topo=(8, 5)),
             _step(*SELECT, geo=False, topo=(8, 5))]
    assert _labels(steps) == ["Extrude Region and Move", "", "Loop Select"]


def test_the_operator_search_is_bounded():
    steps = [_step(*EDIT, geo=False)] + [_step(*EDIT, topo=(8 + i, 5))
                                        for i in range(200)] + [_step(*BEVEL)]
    assert credited_op(steps, 1) == ("", "")


def test_operator_ids_compare_in_either_spelling():
    assert op_key("MESH_OT_inset") == op_key("mesh.inset") == "mesh.inset"
    assert is_passive("MESH_OT_select_all", "(De)select All")
    assert is_passive("ED_OT_undo", "Undo")
    assert not is_passive("MESH_OT_bevel", "Bevel")
