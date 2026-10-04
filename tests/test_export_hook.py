"""The Export box can be extended, and a broken extension cannot blank it."""

import pytest

from scenecast import ui


class _Layout:
    def __init__(self):
        self.labels = []

    def label(self, text="", icon='NONE'):
        self.labels.append(text)


@pytest.fixture
def hooks(monkeypatch):
    monkeypatch.setattr(ui, "_EXPORT_HOOKS", [])


def test_the_export_button_runs_the_plain_export_by_default(hooks):
    assert ui.export_operator(_Layout(), None) == "scenecast.export"


def test_a_hook_can_route_the_export_button(hooks):
    ui.register_export_hook(lambda layout, ctx: "scenecast.export_annotated")
    assert ui.export_operator(_Layout(), None) == "scenecast.export_annotated"


def test_a_hook_that_only_draws_leaves_the_button_alone(hooks):
    ui.register_export_hook(lambda layout, ctx: None)
    assert ui.export_operator(_Layout(), None) == "scenecast.export"


def test_a_broken_hook_is_reported_in_the_box_not_raised(hooks):
    """One bad draw used to blank everything below it in the panel."""
    def broken(layout, ctx):
        raise RuntimeError("boom")
    ui.register_export_hook(broken)
    layout = _Layout()
    assert ui.export_operator(layout, None) == "scenecast.export"
    assert any("boom" in text for text in layout.labels)
