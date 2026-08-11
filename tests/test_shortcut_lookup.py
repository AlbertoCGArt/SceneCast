"""Shortcut lookup: keymap first, menu entry points only as a fallback."""
from scenecast import overlay
from scenecast.overlay import shortcut_for_operator


def setup_function():
    overlay._SHORTCUT_CACHE.clear()


def test_directly_bound_operators_come_from_the_keymap():
    assert shortcut_for_operator("mesh.extrude_region_and_move") == "E"
    assert shortcut_for_operator("transform.translate") == "G"


def test_modifiers_are_rendered():
    assert shortcut_for_operator("mesh.bevel") == "Ctrl+B"
    assert shortcut_for_operator("mesh.loopcut_slide") == "Ctrl+R"


def test_menu_driven_operators_fall_back_to_the_entry_point():
    # absent from the keymap, exactly as in Blender
    assert shortcut_for_operator("mesh.primitive_cube_add") == "Shift+A"
    assert shortcut_for_operator("mesh.delete") == "X"


def test_unknown_operator_resolves_to_nothing():
    assert shortcut_for_operator("mesh.no_such_operator") == ""


def test_empty_idname_is_safe():
    assert shortcut_for_operator("") == ""


def test_hits_are_cached():
    assert shortcut_for_operator("mesh.inset") == "I"
    assert overlay._SHORTCUT_CACHE.get("mesh.inset") == "I"


def test_misses_are_not_cached():
    # keymaps populate late during startup; a miss must stay retryable
    shortcut_for_operator("mesh.no_such_operator")
    assert "mesh.no_such_operator" not in overlay._SHORTCUT_CACHE
