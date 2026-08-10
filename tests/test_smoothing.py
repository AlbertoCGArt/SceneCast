"""Motion-smoothing helpers from the real replay module (imports through stubs)."""
import numpy as np
from scenecast.replay import _smoothstep, _lerp_coords


def test_smoothstep_endpoints_clamped():
    assert _smoothstep(-1.0) == 0.0
    assert _smoothstep(0.0) == 0.0
    assert _smoothstep(1.0) == 1.0
    assert _smoothstep(2.0) == 1.0


def test_smoothstep_midpoint_and_easing():
    assert abs(_smoothstep(0.5) - 0.5) < 1e-9
    # ease-in below the midpoint, ease-out above it
    assert _smoothstep(0.25) < 0.25
    assert _smoothstep(0.75) > 0.75


def test_smoothstep_monotonic():
    prev = -1.0
    for i in range(101):
        v = _smoothstep(i / 100.0)
        assert v >= prev
        prev = v


def test_lerp_coords_endpoints():
    a = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([2.0, 4.0, 6.0], dtype=np.float32)
    assert np.allclose(_lerp_coords(a, b, 0.0), a)
    assert np.allclose(_lerp_coords(a, b, 1.0), b)


def test_lerp_coords_midpoint():
    a = np.array([0.0, 10.0, -4.0], dtype=np.float32)
    b = np.array([4.0, 0.0, 4.0], dtype=np.float32)
    assert np.allclose(_lerp_coords(a, b, 0.5), [2.0, 5.0, 0.0])
