"""Operator labels must not outlive the operator that produced them.

wm.operators keeps reporting the last operator, so a camera step captured
after an extrude would caption itself "Extrude Region and Move".
"""
from scenecast.overlay import op_label_for_step
from scenecast.state import SESSION


def _session(steps):
    SESSION.reset()
    SESSION.steps.extend(steps)


def test_the_step_that_ran_the_operator_is_labelled():
    _session([{"op": "Extrude Region and Move",
               "op_id": "mesh.extrude_region_and_move", "geo_new": True}])
    assert op_label_for_step(0) == "Extrude Region and Move"


def test_a_following_camera_step_is_not_labelled():
    _session([
        {"op": "Extrude Region and Move",
         "op_id": "mesh.extrude_region_and_move", "geo_new": True},
        {"op": "Extrude Region and Move",          # stale wm.operators entry
         "op_id": "mesh.extrude_region_and_move", "geo_new": False},
    ])
    assert op_label_for_step(1) == ""


def test_a_genuine_second_extrude_is_still_labelled():
    _session([
        {"op": "Extrude Region and Move",
         "op_id": "mesh.extrude_region_and_move", "geo_new": True},
        {"op": "Extrude Region and Move",
         "op_id": "mesh.extrude_region_and_move", "geo_new": True},
    ])
    assert op_label_for_step(1) == "Extrude Region and Move"


def test_a_different_operator_is_labelled_even_without_new_geometry():
    _session([
        {"op": "Extrude Region and Move",
         "op_id": "mesh.extrude_region_and_move", "geo_new": True},
        {"op": "Select All", "op_id": "mesh.select_all", "geo_new": False},
    ])
    assert op_label_for_step(1) == "Select All"


def test_the_no_operator_placeholder_is_not_a_label():
    _session([{"op": "(edit)", "op_id": "", "geo_new": True}])
    assert op_label_for_step(0) == ""


def test_out_of_range_index_is_safe():
    _session([{"op": "Move", "op_id": "transform.translate", "geo_new": True}])
    assert op_label_for_step(-1) == ""
    assert op_label_for_step(99) == ""
