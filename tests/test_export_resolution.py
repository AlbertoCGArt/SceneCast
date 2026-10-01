"""Export size is chosen by SceneCast, not inherited from render settings."""

import pytest

from scenecast.exporter import export_resolution, export_aspect


class _Render:
    resolution_x = 800
    resolution_y = 600


class _Scene:
    def __init__(self, mode, x=1920, y=1080):
        self.scenecast_export_res = mode
        self.scenecast_export_res_x = x
        self.scenecast_export_res_y = y
        self.render = _Render()


@pytest.mark.parametrize("mode,expected", [
    ('HD720', (1280, 720)),
    ('HD1080', (1920, 1080)),
    ('QHD', (2560, 1440)),
    ('UHD4K', (3840, 2160)),
    ('VERT', (1080, 1920)),
    ('SQUARE', (1080, 1080)),
])
def test_presets(mode, expected):
    assert export_resolution(_Scene(mode)) == expected


def test_scene_settings_are_left_alone():
    assert export_resolution(_Scene('SCENE')) is None


def test_custom_reads_the_pixel_fields():
    assert export_resolution(_Scene('CUSTOM', 720, 1280)) == (720, 1280)


def test_unknown_mode_falls_back_to_the_scene():
    assert export_resolution(_Scene('SOMETHING_NEW')) is None


def test_vertical_aspect_is_portrait():
    assert export_aspect(_Scene('VERT')) == pytest.approx(1080 / 1920)


def test_square_aspect():
    assert export_aspect(_Scene('SQUARE')) == pytest.approx(1.0)


def test_scene_mode_aspect_comes_from_render_settings():
    assert export_aspect(_Scene('SCENE')) == pytest.approx(800 / 600)
