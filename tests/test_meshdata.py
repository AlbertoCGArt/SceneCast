"""Packed topology, content digests and session size accounting."""

import numpy as np
import pytest

from scenecast.meshdata import (pack_edges, pack_faces, edge_pairs, face_lists,
                                snapshot_digest, session_bytes, snapshot_nbytes,
                                format_bytes, _STEP_OVERHEAD)


class _Collection:
    """Stands in for a Blender mesh collection that supports foreach_get."""

    def __init__(self, count, attrs):
        self._count = count
        self._attrs = attrs

    def __len__(self):
        return self._count

    def foreach_get(self, name, out):
        out[:] = np.asarray(self._attrs[name])


class _Mesh:
    def __init__(self, faces, edges=(), loop_order=None):
        """`faces` is a list of vertex-index tuples, any mix of sizes."""
        totals = [len(f) for f in faces]
        starts = []
        pos = 0
        for t in totals:
            starts.append(pos)
            pos += t
        loop_verts = [i for f in faces for i in f]

        if loop_order == "reversed":
            # Same faces, but their loops live in the opposite order in the
            # loop array -- legal, and fatal to any code that assumes
            # polygons are laid out back to back in index order.
            starts, loop_verts = [], []
            pos = 0
            for f in reversed(faces):
                loop_verts.extend(f)
            offsets = {}
            pos = 0
            for f in reversed(faces):
                offsets[id(f)] = pos
                pos += len(f)
            starts = [offsets[id(f)] for f in faces]

        self.polygons = _Collection(
            len(faces), {"loop_total": totals, "loop_start": starts})
        self.loops = _Collection(len(loop_verts), {"vertex_index": loop_verts})
        flat_edges = [i for e in edges for i in e]
        self.edges = _Collection(len(edges), {"vertices": flat_edges})


def test_faces_round_trip_mixed_sizes():
    faces = [(0, 1, 2), (2, 3, 4, 5), (5, 6, 7, 8, 9, 0)]
    flat, floops = pack_faces(_Mesh(faces))
    assert flat.dtype == np.int32
    assert list(floops) == [3, 4, 6]
    assert face_lists({"faces": flat, "floops": floops}) == faces


def test_faces_gather_follows_loop_start():
    faces = [(0, 1, 2), (3, 4, 5, 6)]
    flat, floops = pack_faces(_Mesh(faces, loop_order="reversed"))
    assert face_lists({"faces": flat, "floops": floops}) == faces


def test_empty_mesh_packs_to_empty_buffers():
    flat, floops = pack_faces(_Mesh([]))
    assert len(flat) == 0 and len(floops) == 0
    assert face_lists({"faces": flat, "floops": floops}) == []


def test_edges_round_trip():
    edges = [(0, 1), (1, 2), (2, 0)]
    packed = pack_edges(_Mesh([], edges))
    assert packed.dtype == np.int32
    assert edge_pairs({"edges": packed}) == edges


def test_readers_accept_the_old_list_format():
    """Sessions saved by an earlier build still hold lists of tuples."""
    old = {"edges": [(0, 1), (1, 2)], "faces": [(0, 1, 2)]}
    assert edge_pairs(old) == [(0, 1), (1, 2)]
    assert face_lists(old) == [(0, 1, 2)]


def test_missing_topology_reads_as_empty():
    assert edge_pairs({}) == [] and face_lists({}) == []


# ----------------------------------------------------------------------------
def _snap(coords, vsel=None, mat=None, mods=None):
    n = len(coords) // 3
    return {
        "vcount": n, "ecount": 0, "fcount": 0,
        "coords": np.asarray(coords, dtype=np.float32),
        "edges": np.empty(0, np.int32), "faces": np.empty(0, np.int32),
        "floops": np.empty(0, np.int32),
        "vsel": np.zeros(n, bool) if vsel is None else np.asarray(vsel, bool),
        "esel": np.empty(0, bool), "fsel": np.empty(0, bool),
        "mat": mat or [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        "mods": mods,
    }


def test_digest_matches_for_identical_content():
    a = _snap([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    b = _snap([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    assert snapshot_digest(a) == snapshot_digest(b)


@pytest.mark.parametrize("changed", [
    _snap([0.0, 0.0, 0.0, 2.0, 0.0, 0.0]),                    # geometry
    _snap([0.0, 0.0, 0.0, 1.0, 0.0, 0.0], vsel=[True, False]),  # selection
    _snap([0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
          mat=[[2, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]),
    _snap([0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
          mods=({"name": "Bevel", "type": "BEVEL", "props": {"width": 0.1}},)),
])
def test_digest_separates_anything_replay_would_show(changed):
    """Two snapshots share one dict when digests match, so every field a
    replay reads back has to move the digest."""
    base = _snap([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    assert snapshot_digest(base) != snapshot_digest(changed)


def test_digest_is_insensitive_to_key_insertion_order():
    a = _snap([1.0, 2.0, 3.0])
    b = {k: a[k] for k in reversed(list(a))}
    assert snapshot_digest(a) == snapshot_digest(b)


# ----------------------------------------------------------------------------
def _payload(steps):
    """Session size with the flat per-step bookkeeping taken back off."""
    return session_bytes(steps) - len(steps) * _STEP_OVERHEAD


def test_session_bytes_charges_a_shared_snapshot_once():
    shared = _snap([0.0] * 3000)
    steps = [{"objs": {"Cube": shared}} for _ in range(50)]
    assert _payload(steps) == snapshot_nbytes(shared)


def test_session_bytes_charges_a_shared_objs_table_once():
    objs = {"A": _snap([0.0] * 3000), "B": _snap([0.0] * 3000)}
    steps = [{"objs": objs} for _ in range(20)]
    assert _payload(steps) == sum(snapshot_nbytes(d) for d in objs.values())


def test_session_bytes_grows_with_genuinely_new_data():
    steps = [{"objs": {"Cube": _snap([float(i)] * 3000)}} for i in range(10)]
    one = snapshot_nbytes(steps[0]["objs"]["Cube"])
    assert _payload(steps) == one * 10


def test_one_edited_object_in_a_crowded_scene_costs_one_snapshot():
    """The case the whole aliasing scheme exists for: five objects, one of
    them edited each step, four of them shared with the step before."""
    idle = {n: _snap([0.0] * 3000) for n in "BCDE"}
    steps = []
    for i in range(40):
        objs = dict(idle)
        objs["A"] = _snap([float(i)] * 3000)
        steps.append({"objs": objs})
    per_obj = snapshot_nbytes(steps[0]["objs"]["A"])
    naive = per_obj * 5 * 40
    assert _payload(steps) == per_obj * 44        # 40 edits + 4 idle objects
    assert _payload(steps) < naive / 4


def test_format_bytes():
    assert format_bytes(512) == "512 B"
    assert format_bytes(2 * 1024) == "2.0 KB"
    assert format_bytes(3 * 1024 ** 2) == "3.0 MB"
    assert format_bytes(int(1.5 * 1024 ** 3)) == "1.5 GB"
