"""One layout table drives the viewport overlay and the video export.

They used to carry independent hardcoded numbers, so elements crowded each
other and scrubbing did not match the exported video.
"""
import pytest
from scenecast import layout


def test_every_band_resolves_in_both_spaces():
    for name in layout.BANDS:
        y_px, size_px = layout.band_px(name, 1000.0)
        y_n, size_n = layout.band_norm(name)
        assert 0.0 <= y_n <= 1.0
        assert size_px > 0 and size_n > 0
        assert y_px == pytest.approx(y_n * 1000.0)


def test_viewport_and_video_agree_proportionally():
    # the whole point: a 900px viewport and a 1080p render lay out the same
    for name in layout.BANDS:
        y_small, size_small = layout.band_px(name, 900.0)
        y_big, size_big = layout.band_px(name, 1080.0)
        assert y_small / 900.0 == pytest.approx(y_big / 1080.0)
        assert size_small / 900.0 == pytest.approx(size_big / 1080.0)


def test_bottom_bands_stack_without_overlapping():
    h = 1000.0
    op_y, op_size = layout.band_px("op", h)
    keys_y, keys_size = layout.band_px("keys", h)
    note_y, note_size = layout.band_px("note", h)
    assert op_y + op_size < keys_y, "op label runs into the keystrokes"
    assert keys_y + keys_size < note_y, "keystrokes run into the note"


def test_chapter_sits_clear_of_the_bottom_stack():
    h = 1000.0
    note_y, note_size = layout.band_px("note", h)
    ch_y, _ = layout.band_px("chapter", h)
    assert ch_y > note_y + note_size


def test_chapter_stays_inside_the_frame():
    h = 1000.0
    ch_y, ch_size = layout.band_px("chapter", h)
    assert ch_y + ch_size < h


def test_scale_grows_text_without_moving_the_bands():
    h = 1000.0
    y_small, size_small = layout.band_px("keys", h, layout.scale_for('SMALL'))
    y_large, size_large = layout.band_px("keys", h, layout.scale_for('LARGE'))
    assert y_small == y_large          # position is independent of size
    assert size_large > size_small


def test_font_never_collapses_to_nothing_in_a_tiny_region():
    for name in layout.BANDS:
        _, size = layout.band_px(name, 40.0, 0.85)
        assert size >= layout.MIN_FONT_PX


def test_unknown_band_is_a_loud_error():
    with pytest.raises(KeyError):
        layout.band_px("nope", 1000.0)
