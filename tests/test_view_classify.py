"""View-direction classification math (mirrors viewnav.classify_view's axis table)."""
import numpy as np

AXES = [
    (np.array([ 0.,  0., -1.]), "Top"),
    (np.array([ 0.,  0.,  1.]), "Bottom"),
    (np.array([ 0.,  1.,  0.]), "Front"),
    (np.array([ 0., -1.,  0.]), "Back"),
    (np.array([-1.,  0.,  0.]), "Right"),
    (np.array([ 1.,  0.,  0.]), "Left"),
]

def classify(look):
    look = look / np.linalg.norm(look)
    best_name, best_dot = "", -2.0
    for vec, name in AXES:
        d = float(look @ vec)
        if d > best_dot:
            best_dot, best_name = d, name
    return best_name if best_dot > 0.9995 else "FREE"

def test_axis_aligned_views():
    assert classify(np.array([0, 0, -1.])) == "Top"
    assert classify(np.array([0, 0, 1.])) == "Bottom"
    assert classify(np.array([0, 1., 0])) == "Front"
    assert classify(np.array([0, -1., 0])) == "Back"
    assert classify(np.array([-1., 0, 0])) == "Right"
    assert classify(np.array([1., 0, 0])) == "Left"

def test_free_orbit_is_unclassified():
    assert classify(np.array([0.3, 0.6, -0.74])) == "FREE"
