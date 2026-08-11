"""Text strip creation across the Blender versions that renamed the span.

5.0's signature is (name, type, channel, frame_start, length, input1, input2);
4.x took frame_end instead. Neither accepts the other's keyword.
"""
import pytest
from scenecast.exporter import new_text_strip


class _Strip:
    def __init__(self, **kw):
        self.kw = kw


class _ModernStrips:
    """Blender 5.0: accepts length, rejects frame_end."""
    def new_effect(self, name, type, channel, frame_start, length=0,
                   input1=None, input2=None):
        return _Strip(name=name, frame_start=frame_start, length=length)


class _LegacyStrips:
    """Blender 4.x: accepts frame_end, rejects length."""
    def new_effect(self, name, type, channel, frame_start, frame_end=0,
                   seq1=None, seq2=None):
        return _Strip(name=name, frame_start=frame_start, frame_end=frame_end)


def test_modern_signature_receives_length():
    s = new_text_strip(_ModernStrips(), "k", 2, 10, 5)
    assert s.kw["length"] == 5
    assert s.kw["frame_start"] == 10


def test_legacy_signature_receives_a_converted_frame_end():
    s = new_text_strip(_LegacyStrips(), "k", 2, 10, 5)
    assert s.kw["frame_end"] == 15       # frame_start + length
    assert s.kw["frame_start"] == 10


def test_both_versions_cover_the_same_span():
    modern = new_text_strip(_ModernStrips(), "k", 2, 7, 12)
    legacy = new_text_strip(_LegacyStrips(), "k", 2, 7, 12)
    assert modern.kw["frame_start"] == legacy.kw["frame_start"]
    assert (legacy.kw["frame_end"] - legacy.kw["frame_start"]
            == modern.kw["length"])


def test_an_unrelated_type_error_is_not_swallowed_into_a_wrong_call():
    class _Broken:
        def new_effect(self, **kw):
            raise TypeError("something else entirely")

    with pytest.raises(TypeError):
        new_text_strip(_Broken(), "k", 2, 1, 1)
