"""The export keeps the camera each frame was rendered from."""

import pytest

from scenecast import exporter
from scenecast.state import SESSION


class _Scene:
    def __init__(self, frame):
        self.frame_current = frame


@pytest.fixture
def recording(monkeypatch):
    SESSION.reset()
    monkeypatch.setattr(exporter, "view_spec",
                        lambda scene: {"frame": scene.frame_current})
    yield SESSION.export_views
    SESSION.reset()


def test_each_frame_is_kept_at_its_index(recording):
    for frame in (1, 2, 3):
        exporter._record_export_view(_Scene(frame))
    assert [v["frame"] for v in SESSION.export_views] == [1, 2, 3]


def test_a_frame_rendered_twice_keeps_its_latest_camera(recording):
    exporter._record_export_view(_Scene(1))
    exporter._record_export_view(_Scene(2))
    exporter._record_export_view(_Scene(1))
    assert len(SESSION.export_views) == 2


def test_a_skipped_frame_leaves_a_gap_not_a_shift(recording):
    """Indices must stay frame numbers, or every later note lands on the
    wrong frame's camera."""
    exporter._record_export_view(_Scene(1))
    exporter._record_export_view(_Scene(4))
    assert SESSION.export_views[1] is None and SESSION.export_views[2] is None
    assert SESSION.export_views[3] == {"frame": 4}


def test_frame_zero_is_ignored(recording):
    exporter._record_export_view(_Scene(0))
    assert SESSION.export_views == []


def test_a_new_session_starts_with_no_cameras():
    SESSION.reset()
    assert SESSION.export_views == []
