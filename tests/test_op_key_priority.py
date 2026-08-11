"""An operator's own shortcut outranks time-logged keys.

The camera watchdog fires on a clock, so a step captured mid-extrude lands
between the E press and the geometry it produced and would otherwise claim
the E for itself.
"""
from scenecast.overlay import keys_for_step
from scenecast.state import SESSION


def _session(steps, log=()):
    SESSION.reset()
    SESSION.steps.extend(steps)
    SESSION.key_log.extend(log)


def test_geometry_step_wins_the_key_back_from_a_camera_step():
    _session([
        {"t": 1.0, "op_id": "", "geo_new": False},                  # baseline
        {"t": 2.0, "op_id": "", "geo_new": False},                  # camera move
        {"t": 3.0, "op_id": "mesh.extrude_region_and_move",         # the extrude
         "geo_new": True},
    ], [("E", 1.5)])                       # pressed before the camera step
    assert keys_for_step(2) == ["E"]       # credited to the extrude, not the pan


def test_repeated_operator_still_labelled_when_geometry_changes():
    # extruding twice in a row reports the same op_id both times
    _session([
        {"t": 1.0, "op_id": "mesh.extrude_region_and_move", "geo_new": True},
        {"t": 2.0, "op_id": "mesh.extrude_region_and_move", "geo_new": True},
    ])
    assert keys_for_step(1) == ["E"]


def test_camera_step_does_not_inherit_the_last_operator_label():
    # wm.operators keeps reporting the last operator; a camera step that
    # changed no geometry must not restamp its shortcut
    _session([
        {"t": 1.0, "op_id": "mesh.extrude_region_and_move", "geo_new": True},
        {"t": 2.0, "op_id": "mesh.extrude_region_and_move", "geo_new": False},
    ])
    assert keys_for_step(1) == []


def test_logged_keys_still_used_when_no_operator_ran():
    _session([{"t": 1.0}, {"t": 2.0, "op_id": "", "geo_new": False}],
             [("Tab", 1.5)])
    assert keys_for_step(1) == ["Tab"]


def test_unresolvable_operator_falls_back_to_logged_keys():
    _session([
        {"t": 1.0},
        {"t": 2.0, "op_id": "mesh.no_such_operator", "geo_new": True},
    ], [("Q", 1.5)])
    assert keys_for_step(1) == ["Q"]
