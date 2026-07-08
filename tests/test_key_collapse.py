"""Repeat-collapsing for the keystroke overlay (imports the real overlay module)."""
import time
from scenecast.overlay import _collapse, _push_key, _REPEAT_WINDOW
from scenecast.state import SESSION

def test_collapse_runs_of_repeats():
    assert _collapse(['G', 'X', 'X', 'X', '5']) == ['G', 'X \u00d73', '5']

def test_collapse_no_repeats_passthrough():
    assert _collapse(['G', 'X', '5']) == ['G', 'X', '5']

def test_collapse_nonadjacent_not_merged():
    assert _collapse(['X', 'G', 'X']) == ['X', 'G', 'X']

def test_collapse_empty():
    assert _collapse([]) == []

def test_push_key_live_counter():
    SESSION.reset()
    _push_key('X'); _push_key('X'); _push_key('X')
    assert len(SESSION.key_buffer) == 1
    txt, ts, n = SESSION.key_buffer[-1]
    assert txt == 'X' and n == 3

def test_push_key_different_key_appends():
    SESSION.reset()
    _push_key('X'); _push_key('G')
    assert len(SESSION.key_buffer) == 2

def test_push_key_repeat_outside_window_appends():
    SESSION.reset()
    _push_key('X')
    txt, ts, n = SESSION.key_buffer[-1]
    SESSION.key_buffer[-1] = (txt, ts - (_REPEAT_WINDOW + 0.1), n)  # age it out
    _push_key('X')
    assert len(SESSION.key_buffer) == 2
