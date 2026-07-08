"""Keystroke formatting (imports the real overlay module via stubs)."""
from scenecast.overlay import _format_key

class E:
    def __init__(self, type, ctrl=False, shift=False, alt=False, oskey=False):
        self.type = type; self.ctrl = ctrl; self.shift = shift
        self.alt = alt; self.oskey = oskey

def test_plain_keys():
    assert _format_key(E('G'), False) == "G"
    assert _format_key(E('TAB'), False) == "Tab"
    assert _format_key(E('FIVE'), False) == "5"
    assert _format_key(E('F2'), False) == "F2"
    assert _format_key(E('NUMPAD_5'), False) == "Num 5"

def test_modifier_combos():
    assert _format_key(E('E', ctrl=True), False) == "Ctrl+E"
    assert _format_key(E('A', shift=True), False) == "Shift+A"
    assert _format_key(E('Z', ctrl=True, shift=True), False) == "Ctrl+Shift+Z"

def test_skipped_events():
    assert _format_key(E('LEFT_CTRL'), False) == ""
    assert _format_key(E('MOUSEMOVE'), False) == ""
    assert _format_key(E('TIMER'), False) == ""

def test_mouse_gating():
    assert _format_key(E('LEFTMOUSE'), False) == ""
    assert _format_key(E('LEFTMOUSE'), True) == "LMB"
    assert _format_key(E('LEFTMOUSE', ctrl=True), True) == "Ctrl+LMB"
