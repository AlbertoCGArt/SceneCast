"""The plain export burns keystrokes in the way the viewport draws them.

Before: one white line of monospace -- "G     Move" -- where the viewport drew
the keys in the interface font with the operator in blue on a line under
them.
"""

import contextlib
import os

import pytest
import bpy

from scenecast import exporter, fonts
from scenecast import layout as sc_layout
from scenecast.state import SESSION


# ----------------------------------------------------------------------------
# What the two lines say
# ----------------------------------------------------------------------------
@pytest.fixture
def steps():
    SESSION.reset()
    SESSION.steps = [
        {"t": 1.0, "op": "(edit)", "op_id": "", "keys": []},
        {"t": 2.0, "op": "Move", "op_id": "TRANSFORM_OT_translate",
         "keys": ["G"], "geo_new": True},
        {"t": 3.0, "op": "Duplicate Objects", "op_id": "OBJECT_OT_duplicate_move",
         "keys": ["Shift+D", "Shift+D"], "geo_new": True},
    ]
    yield SESSION.steps
    SESSION.reset()


def test_keys_and_operator_are_separate_lines(steps):
    keys, op = exporter.overlay_lines(1)
    assert keys == "G" and op == "Move"


def test_a_step_with_nothing_to_say_has_empty_lines(steps):
    assert exporter.overlay_lines(0) == ("", "")


def test_the_render_stamp_still_gets_one_line(steps):
    """The stamp has a single line, so only it keeps the combined form."""
    stamp = exporter._stamp_text_for(steps[1], 1)
    assert "G" in stamp and "Move" in stamp


# ----------------------------------------------------------------------------
# What the compositing pass builds
# ----------------------------------------------------------------------------
class _Obj:
    """Takes any attribute; records nothing it is not told."""


class _Strip(_Obj):
    def __init__(self, kind, name, channel):
        self.kind, self.name, self.channel = kind, name, channel
        self.elements = []


class _Strips:
    def __init__(self):
        self.made = []

    def new_image(self, name, channel, frame_start, filepath):
        strip = _Strip("IMAGE", name, channel)
        strip.elements = _Elements()
        self.made.append(strip)
        return strip

    def new_effect(self, name, type, channel, frame_start, length):
        strip = _Strip(type, name, channel)
        strip.frame_start, strip.length = frame_start, length
        self.made.append(strip)
        return strip


class _Elements(list):
    def append(self, filename):
        list.append(self, filename)


class _Editor:
    def __init__(self):
        self.strips = _Strips()


class _Render(_Obj):
    def __init__(self):
        self.resolution_x, self.resolution_y = 1920, 1080
        self.resolution_percentage = 100
        self.image_settings = _Obj()
        self.ffmpeg = _Obj()


class _Scene:
    def __init__(self):
        self.render = _Render()
        self.editor = None

    def sequence_editor_create(self):
        self.editor = _Editor()
        return self.editor


class _Scenes:
    def __init__(self):
        self.made = []

    def new(self, name):
        scene = _Scene()
        self.made.append(scene)
        return scene

    def remove(self, scene):
        pass


@pytest.fixture
def composite(tmp_path, monkeypatch, steps):
    for i in range(36):
        (tmp_path / ("f_%04d.png" % (i + 1))).write_bytes(b"png")
    scenes = _Scenes()
    data = _Obj()
    data.scenes = scenes
    monkeypatch.setattr(bpy, "data", data)
    monkeypatch.setattr(bpy.context, "temp_override",
                        lambda **k: contextlib.nullcontext(), raising=False)
    font = object()
    monkeypatch.setattr(fonts, "vse_font", lambda path: font)
    lines = [exporter.overlay_lines(i) for i in range(3)]
    exporter.composite_text_video(_Scene(), str(tmp_path),
                                  str(tmp_path / "out.mp4"), 12, 24, lines)
    texts = [s for s in scenes.made[0].editor.strips.made if s.kind == 'TEXT']
    return texts, font


def test_keys_and_operator_become_two_strips(composite):
    texts, _font = composite
    # The duplicate step names its operator, so its shortcut outranks the two
    # logged presses. Before the recorded 'OBJECT_OT_duplicate_move' id was
    # normalised, the lookup missed and the logged "Shift+D x2" showed.
    assert sorted(t.text for t in texts) == ["Duplicate Objects", "G", "Move",
                                             "Shift+D"]


def test_every_strip_is_in_the_interface_font(composite):
    """Without a font, text strips render in Blender's monospace default."""
    texts, font = composite
    assert texts and all(t.font is font for t in texts)


def test_keys_and_operator_wear_the_viewport_colours(composite):
    texts, _font = composite
    by_text = {t.text: t for t in texts}
    assert by_text["G"].color == sc_layout.KEYS_COLOR
    assert by_text["Move"].color == sc_layout.OP_COLOR


def test_the_operator_sits_below_the_keys_as_in_the_viewport(composite):
    texts, _font = composite
    by_text = {t.text: t for t in texts}
    assert by_text["Move"].location[1] < by_text["G"].location[1]
    assert by_text["G"].location[1] == pytest.approx(sc_layout.BANDS["keys"][0])


def test_text_has_a_shadow_and_sits_on_its_baseline(composite):
    texts, _font = composite
    for t in texts:
        assert t.use_shadow is True
        assert t.anchor_y == 'BOTTOM' and t.anchor_x == 'CENTER'


def test_a_step_with_nothing_to_say_makes_no_strips(composite):
    texts, _font = composite
    assert not any(t.frame_start == 1 for t in texts)        # step 0 is silent


# ----------------------------------------------------------------------------
# Finding the font
# ----------------------------------------------------------------------------
class _View:
    def __init__(self, path):
        self.font_path_ui = path


class _Prefs:
    def __init__(self, path=""):
        self.view = _View(path)


def test_the_users_own_interface_font_wins(tmp_path, monkeypatch):
    mine = tmp_path / "MyUI.ttf"
    mine.write_bytes(b"font")
    monkeypatch.setattr(bpy.context, "preferences", _Prefs(str(mine)), raising=False)
    assert fonts.ui_font_path() == str(mine)


def test_otherwise_blenders_bundled_interface_font(tmp_path, monkeypatch):
    (tmp_path / "Inter.woff2").write_bytes(b"font")
    (tmp_path / "DejaVuSans.woff2").write_bytes(b"font")
    monkeypatch.setattr(bpy.context, "preferences", _Prefs(""), raising=False)
    monkeypatch.setattr(bpy.utils, "system_resource",
                        lambda kind, path="": str(tmp_path), raising=False)
    assert os.path.basename(fonts.ui_font_path()) == "Inter.woff2"


def test_no_font_file_anywhere_returns_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(bpy.context, "preferences", _Prefs(""), raising=False)
    monkeypatch.setattr(bpy.utils, "system_resource",
                        lambda kind, path="": str(tmp_path), raising=False)
    assert fonts.ui_font_path() == ""


class _Fonts:
    def __init__(self, loadable):
        self.loadable = loadable
        self.asked = []

    def load(self, path, check_existing=False):
        self.asked.append(path)
        if path not in self.loadable:
            raise RuntimeError("cannot read %s" % path)
        return "font:" + path


def test_a_font_that_will_not_load_falls_back_to_the_builtin_sans(monkeypatch):
    """Never back to the monospace default, and never failing the export."""
    data = _Obj()
    data.fonts = _Fonts({"<builtin>"})
    monkeypatch.setattr(bpy, "data", data)
    assert fonts.vse_font("broken.woff2") == "font:<builtin>"


def test_nothing_loadable_leaves_blenders_default(monkeypatch):
    data = _Obj()
    data.fonts = _Fonts(set())
    monkeypatch.setattr(bpy, "data", data)
    assert fonts.vse_font("broken.woff2") is None
