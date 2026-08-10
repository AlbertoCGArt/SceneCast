"""Burn-in stamp text built for each exported step (real exporter module)."""
from scenecast.exporter import _stamp_text_for


def test_keys_and_operator_both_shown():
    out = _stamp_text_for({"keys": ["Shift+A"], "op": "Add Plane"})
    assert "Shift+A" in out and "Add Plane" in out


def test_repeats_collapse_in_stamp():
    out = _stamp_text_for({"keys": ["X", "X", "X"], "op": "Move"})
    assert "×3" in out


def test_placeholder_operator_is_not_shown():
    # "(edit)" is the no-operator placeholder, not something to burn in
    assert _stamp_text_for({"keys": [], "op": "(edit)"}) == ""
    assert _stamp_text_for({"keys": ["G"], "op": "(edit)"}) == "G"


def test_operator_only_when_no_keys():
    assert _stamp_text_for({"keys": [], "op": "Extrude Region"}) == "Extrude Region"


def test_empty_step_is_empty_string():
    assert _stamp_text_for({}) == ""
