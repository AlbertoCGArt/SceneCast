"""Compact mesh snapshots: packed topology, content digests, size accounting.

Snapshots used to hold topology as Python lists of tuples -- one tuple object
per edge and per face, each with its own refcount and header. That is roughly
ten times the size of the equivalent int32 buffer, and building it walked the
mesh one attribute lookup at a time, which is what made capture hitch on a
dense mesh. Everything here is `foreach_get` into numpy instead.

Faces are stored CSR-style, because a mesh mixes triangles with quads and
n-gons and no rectangular array can hold that:

    faces   flat int32 vertex indices for every face, back to back
    floops  int32 loop count per face, so `faces` can be cut back up

The list-of-tuples form is rebuilt on demand by `face_lists()` / `edge_pairs()`,
which only the topology-changing rebuild path needs. Both readers also accept
the old list form, so sessions saved by an earlier build still replay.
"""

import hashlib

import numpy as np

# Fields whose bytes decide whether two snapshots of one object are the same
# thing. Order is fixed: the digest is a stream, so it has to be fed the same
# way every time or two identical snapshots hash differently.
_DIGEST_ARRAYS = ("coords", "edges", "faces", "floops", "vsel", "esel", "fsel")

_DIGEST_SIZE = 16          # 128-bit blake2b: collisions are not a real risk


# ----------------------------------------------------------------------------
# Packing (capture side)
# ----------------------------------------------------------------------------
def pack_edges(mesh):
    """Flat int32 vertex-index pairs, two per edge."""
    n = len(mesh.edges)
    out = np.empty(n * 2, dtype=np.int32)
    if n:
        mesh.edges.foreach_get("vertices", out)
    return out


def pack_faces(mesh):
    """(flat vertex indices, loop count per face) for every polygon.

    Loops are usually laid out contiguously in polygon order, but that is not
    guaranteed by the API, so the flat buffer is gathered through each
    polygon's own loop_start rather than assuming it.
    """
    n = len(mesh.polygons)
    floops = np.empty(n, dtype=np.int32)
    if not n:
        return np.empty(0, dtype=np.int32), floops
    mesh.polygons.foreach_get("loop_total", floops)
    starts = np.empty(n, dtype=np.int32)
    mesh.polygons.foreach_get("loop_start", starts)

    loop_verts = np.empty(len(mesh.loops), dtype=np.int32)
    if len(mesh.loops):
        mesh.loops.foreach_get("vertex_index", loop_verts)

    total = int(floops.sum())
    if total == 0:
        return np.empty(0, dtype=np.int32), floops
    counts = floops.astype(np.int64)
    # Per-slot source index = this face's loop_start + how far into the face
    # the slot is. Both halves are built with repeat/arange so the gather stays
    # vectorised instead of looping in Python once per face.
    base = np.repeat(starts.astype(np.int64), counts)
    ends = np.cumsum(counts)
    within = np.arange(total, dtype=np.int64) - np.repeat(ends - counts, counts)
    return loop_verts[base + within].astype(np.int32), floops


# ----------------------------------------------------------------------------
# Unpacking (replay side)
# ----------------------------------------------------------------------------
def edge_pairs(data):
    """Edges as a list of (a, b) tuples, for `from_pydata` and bmesh."""
    edges = data.get("edges")
    if edges is None:
        return []
    if isinstance(edges, (list, tuple)):
        return list(edges)              # session recorded by an older build
    arr = np.asarray(edges).reshape(-1, 2)
    return [(int(a), int(b)) for a, b in arr]


def face_lists(data):
    """Faces as a list of vertex-index tuples, cut out of the CSR buffers."""
    faces = data.get("faces")
    if faces is None:
        return []
    if isinstance(faces, (list, tuple)):
        return list(faces)              # session recorded by an older build
    flat = np.asarray(faces)
    floops = data.get("floops")
    if floops is None:
        if flat.ndim == 2:              # uniform-width array: rows are faces
            return [tuple(int(i) for i in row) for row in flat]
        return []
    out = []
    pos = 0
    for n in np.asarray(floops):
        n = int(n)
        out.append(tuple(int(i) for i in flat[pos:pos + n]))
        pos += n
    return out


# ----------------------------------------------------------------------------
# Content digest
# ----------------------------------------------------------------------------
def _feed(h, arr):
    if arr is None:
        h.update(b"\x00")
        return
    a = np.ascontiguousarray(arr)
    h.update(("%s%s;" % (a.dtype.str, a.shape)).encode("ascii"))
    try:
        h.update(a.data.cast("B"))      # no copy
    except (TypeError, ValueError):
        h.update(a.tobytes())


def snapshot_digest(data):
    """A stable fingerprint of everything a replay would read back out.

    Covers geometry, transform AND selection, because the digest decides
    whether two steps can share one snapshot dict by reference -- so anything
    a later step could show differently has to be in here.

    Returned as hex rather than raw bytes: this value is stored in the
    snapshot, and a session serialiser that walks whatever it finds there
    handles str everywhere and bytes almost nowhere.
    """
    h = hashlib.blake2b(digest_size=_DIGEST_SIZE)
    h.update(b"%d,%d,%d;" % (data.get("vcount", 0), data.get("ecount", 0),
                             data.get("fcount", 0)))
    for key in _DIGEST_ARRAYS:
        _feed(h, data.get(key))
    mat = data.get("mat")
    if mat is not None:
        h.update(b"m")
        for row in mat:
            for v in row:
                h.update(b"%a," % float(v))
    mods = data.get("mods")
    if mods:
        h.update(repr(mods).encode("utf-8", "replace"))
    return h.hexdigest()


# ----------------------------------------------------------------------------
# Size accounting
# ----------------------------------------------------------------------------
_DICT_OVERHEAD = 360       # snapshot dict + its keys, measured with sys.getsizeof
_STEP_OVERHEAD = 900       # a step's non-geometry fields (view, cursor, keys...)


def snapshot_nbytes(data):
    """Bytes a single object snapshot costs, counting its arrays only once."""
    total = _DICT_OVERHEAD
    seen = set()
    for v in data.values():
        if isinstance(v, np.ndarray) and id(v) not in seen:
            seen.add(id(v))
            total += v.nbytes
        elif isinstance(v, (list, tuple)) and v:
            # An old-format topology list: ~72 bytes per tuple plus its ints.
            total += len(v) * 72
    return total


def session_bytes(steps):
    """Exact-ish session footprint, charging shared data to one owner.

    Camera steps share the previous step's whole `objs` dict, and an object
    that nothing touched shares its snapshot with the step before -- so a
    naive sum reports many times what is actually resident. Identity is what
    distinguishes the two cases, so that is what is deduplicated on.
    """
    seen_objs = set()
    seen_snap = set()
    total = 0
    for step in steps:
        total += _STEP_OVERHEAD
        objs = step.get("objs")
        if not isinstance(objs, dict) or id(objs) in seen_objs:
            continue
        seen_objs.add(id(objs))
        for data in objs.values():
            if id(data) in seen_snap:
                continue
            seen_snap.add(id(data))
            total += snapshot_nbytes(data)
    return total


def format_bytes(n):
    for unit, size in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= size:
            return "%.1f %s" % (n / float(size), unit)
    return "%d B" % n
