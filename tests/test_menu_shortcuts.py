"""Menu-driven operators have no keymap binding to find.

Shift+A opens the Add menu and X opens the delete menu; neither is bound to
the operator that ends up running, so the keymap lookup returns nothing and
the entry-point shortcut has to be supplied.
"""
from scenecast.overlay import _menu_shortcut


def test_add_mesh_primitives_report_the_add_menu():
    for idname in ("mesh.primitive_cube_add", "mesh.primitive_plane_add",
                   "mesh.primitive_uv_sphere_add"):
        assert _menu_shortcut(idname) == "Shift+A"


def test_add_covers_non_mesh_object_types():
    for idname in ("object.empty_add", "object.light_add", "object.camera_add",
                   "curve.primitive_bezier_curve_add", "object.text_add"):
        assert _menu_shortcut(idname) == "Shift+A"


def test_delete_operators():
    assert _menu_shortcut("mesh.delete") == "X"
    assert _menu_shortcut("object.delete") == "X"


def test_dissolve_is_not_swallowed_by_the_delete_prefix():
    # mesh.dissolve_* must not fall through to a "delete" match
    assert _menu_shortcut("mesh.dissolve_edges") == "Ctrl+X"


def test_duplicate_and_join():
    assert _menu_shortcut("object.duplicate_move") == "Shift+D"
    assert _menu_shortcut("object.join") == "Ctrl+J"


def test_unknown_operator_yields_nothing():
    assert _menu_shortcut("mesh.some_future_operator") == ""
    assert _menu_shortcut("") == ""


def test_directly_bound_operators_are_not_in_the_menu_map():
    # these resolve through the real keymap; hardcoding them would override
    # a user's remap
    for idname in ("transform.translate", "mesh.extrude_region_and_move",
                   "mesh.inset", "mesh.bevel"):
        assert _menu_shortcut(idname) == ""
