"""Sequencer collection lookup across Blender versions.

Blender 5.0 renamed SequenceEditor.sequences to .strips. The editor is created
empty and an empty Blender collection is falsy, so a `strips or sequences`
fallback selects the wrong attribute on exactly the versions that need strips.
"""
import pytest
from scenecast.exporter import _seq_strips


class _Collection(list):
    """Stands in for a Blender collection: falsy while empty."""


class _Modern:
    """Blender 5.0+: only .strips exists."""
    def __init__(self, items=()):
        self.strips = _Collection(items)


class _Legacy:
    """Blender 4.x: only .sequences exists."""
    def __init__(self, items=()):
        self.sequences = _Collection(items)


def test_empty_modern_editor_still_resolves_to_strips():
    # the regression: empty .strips is falsy, and .sequences does not exist
    se = _Modern()
    assert _seq_strips(se) is se.strips


def test_populated_modern_editor_resolves_to_strips():
    se = _Modern(["a"])
    assert _seq_strips(se) is se.strips


def test_empty_legacy_editor_resolves_to_sequences():
    se = _Legacy()
    assert _seq_strips(se) is se.sequences


def test_populated_legacy_editor_resolves_to_sequences():
    se = _Legacy(["a"])
    assert _seq_strips(se) is se.sequences


def test_editor_with_neither_attribute_raises():
    with pytest.raises(AttributeError):
        _seq_strips(object())
