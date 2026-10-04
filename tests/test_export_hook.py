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


# ----------------------------------------------------------------------------
# Footers: drawn under the button, deciding nothing about it
# ----------------------------------------------------------------------------
@pytest.fixture
def footers(monkeypatch):
    monkeypatch.setattr(ui, "_EXPORT_FOOTERS", [])


def test_footers_draw_in_registration_order(footers):
    layout = _Layout()
    ui.register_export_footer(lambda lay, ctx: lay.label(text="status"))
    ui.register_export_footer(lambda lay, ctx: lay.label(text="guide"))
    ui.export_footer(layout, None)
    assert layout.labels == ["status", "guide"]


def test_a_broken_footer_is_reported_and_the_next_still_draws(footers):
    def broken(layout, ctx):
        raise RuntimeError("boom")
    ui.register_export_footer(broken)
    ui.register_export_footer(lambda lay, ctx: lay.label(text="after"))
    layout = _Layout()
    ui.export_footer(layout, None)
    assert any("boom" in t for t in layout.labels) and "after" in layout.labels


def test_a_footer_unregisters(footers):
    fn = lambda lay, ctx: lay.label(text="x")
    ui.register_export_footer(fn)
    ui.register_export_footer(fn)
    ui.unregister_export_footer(fn)
    layout = _Layout()
    ui.export_footer(layout, None)
    assert layout.labels == []


def test_the_footer_draws_after_the_export_button():
    import inspect
    src = inspect.getsource(ui.SCENECAST_PT_export.draw)
    assert src.index("export_operator(") < src.index("export_footer(")
