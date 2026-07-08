"""Step-recording decisions: geometry vs interaction-context changes."""
import numpy as np

class Vec:
    def __init__(self, t): self.a = np.array(t, dtype=float)
    def __sub__(self, o): return Vec(self.a - o.a)
    @property
    def length(self): return float(np.linalg.norm(self.a))

def _selection_equal(a, b):
    for m in ("vsel", "esel", "fsel"):
        va, vb = a.get(m), b.get(m)
        if (va is None) != (vb is None): return False
        if va is not None and not np.array_equal(va, vb): return False
    return True

def _objects_equal(a, b):
    if a["vcount"] != b["vcount"] or a["fcount"] != b["fcount"]: return False
    return bool(np.array_equal(a["coords"], b["coords"]))

def _context_equal(a, b):
    for key in ("active", "sel_objects", "pivot", "orientation", "select_mode"):
        if a.get(key) != b.get(key): return False
    ca, cb = a.get("cursor_loc"), b.get("cursor_loc")
    if (ca is None) != (cb is None): return False
    if ca is not None and (ca - cb).length > 1e-6: return False
    for k in a["objs"]:
        db = b["objs"].get(k)
        if db is None or not _selection_equal(a["objs"][k], db): return False
    return True

def would_record(prev, step, capture_context=True):
    geo_same = (set(prev["objs"]) == set(step["objs"]) and
                all(_objects_equal(prev["objs"][k], step["objs"][k]) for k in step["objs"]))
    if geo_same:
        if not capture_context: return False
        if _context_equal(prev, step): return False
    return True

def mkobj(coords, vsel):
    return {"vcount": len(vsel), "fcount": 1,
            "coords": np.array(coords, dtype=np.float32),
            "vsel": np.array(vsel, bool),
            "esel": np.array([False]), "fsel": np.array([False])}

def mkstep(coords, vsel, cursor=(0, 0, 0), pivot='MEDIAN_POINT',
           sel_objects=('Cube',), active='Cube', select_mode=(True, False, False)):
    return {"objs": {"Cube": mkobj(coords, vsel)}, "cursor_loc": Vec(cursor),
            "pivot": pivot, "orientation": 'GLOBAL',
            "sel_objects": list(sel_objects), "active": active,
            "select_mode": select_mode}

BASE = mkstep([0, 0, 0, 1, 0, 0], [False, False])

def test_identical_state_dedupes():
    assert not would_record(BASE, mkstep([0, 0, 0, 1, 0, 0], [False, False]))

def test_selection_change_records():
    assert would_record(BASE, mkstep([0, 0, 0, 1, 0, 0], [True, False]))

def test_cursor_move_records():
    assert would_record(BASE, mkstep([0, 0, 0, 1, 0, 0], [False, False], cursor=(2, 0, 0)))

def test_pivot_change_records():
    assert would_record(BASE, mkstep([0, 0, 0, 1, 0, 0], [False, False], pivot='CURSOR'))

def test_select_mode_change_records():
    assert would_record(BASE, mkstep([0, 0, 0, 1, 0, 0], [False, False],
                                     select_mode=(False, True, False)))

def test_active_object_change_records():
    assert would_record(BASE, mkstep([0, 0, 0, 1, 0, 0], [False, False],
                                     active='Sphere', sel_objects=('Sphere',)))

def test_geometry_move_records():
    assert would_record(BASE, mkstep([0, 0, 0, 1.5, 0, 0], [False, False]))

def test_capture_context_off_reverts_to_geometry_only():
    assert not would_record(BASE, mkstep([0, 0, 0, 1, 0, 0], [True, False]),
                            capture_context=False)
