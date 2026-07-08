"""Capture pipeline: collection isolation, snapshots, change detection, handlers."""

import time
import numpy as np
import bpy

from .state import SESSION, DEBOUNCE, MAX_VERTS_FULL, WATCHDOG_DT
from .viewnav import (_get_view3d_rv3d, classify_view, _tag_redraw,
                      _edit_mode_object)

# ----------------------------------------------------------------------------
# Collection isolation (gather all recorded objects into one tidy collection)
# ----------------------------------------------------------------------------
def _get_or_create_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        try:
            bpy.context.scene.collection.children.link(coll)
        except Exception:
            pass
    return coll


def _move_object_to_collection(obj, coll):
    """Unlink obj from its current collections and link it into `coll`.
    Returns the list of original collection names (for later restore)."""
    originals = [c.name for c in obj.users_collection]
    if originals == [coll.name]:
        return originals                     # already isolated
    for c in list(obj.users_collection):
        try:
            c.objects.unlink(obj)
        except Exception:
            pass
    try:
        coll.objects.link(obj)
    except Exception:
        pass
    return originals


def _isolate_objects(objects):
    sc = bpy.context.scene
    if not sc.scenecast_isolate:
        return
    coll = _get_or_create_collection(sc.scenecast_collection_name)
    if coll is None:
        return
    for obj in objects:
        if obj.name in SESSION.original_collections:
            continue                         # already gathered earlier this session
        SESSION.original_collections[obj.name] = _move_object_to_collection(obj, coll)


def _restore_collections():
    """Undo isolation: put objects back where they came from; drop empty coll."""
    sc = bpy.context.scene
    coll = bpy.data.collections.get(sc.scenecast_collection_name)
    for name, originals in list(SESSION.original_collections.items()):
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        current = [c.name for c in obj.users_collection]
        if coll is None or current != [coll.name]:
            continue                         # user manually re-organized: leave it
        try:
            coll.objects.unlink(obj)
        except Exception:
            pass
        linked = False
        for cn in originals:
            oc = bpy.data.collections.get(cn)   # master collection isn't here -> None
            if oc is not None:
                try:
                    oc.objects.link(obj)
                    linked = True
                except Exception:
                    pass
        if not linked:
            try:
                sc.collection.objects.link(obj)   # fall back to scene root
            except Exception:
                pass
    SESSION.original_collections.clear()
    if coll is not None and len(coll.objects) == 0 and len(coll.children) == 0:
        try:
            bpy.data.collections.remove(coll)
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Capture (multi-object, mode-aware)
# ----------------------------------------------------------------------------
def _visible_mesh_objects():
    out = []
    try:
        for obj in bpy.context.view_layer.objects:
            if obj.type == 'MESH' and obj.visible_get():
                out.append(obj)
    except Exception:
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                out.append(obj)
    return out


def _snapshot_object(obj):
    if obj.mode == 'EDIT':
        try:
            obj.update_from_editmode()
        except Exception:
            pass
    mesh = obj.data
    vcount = len(mesh.vertices)
    ecount = len(mesh.edges)
    fcount = len(mesh.polygons)
    coords = np.empty(vcount * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    vsel = np.empty(vcount, dtype=bool)
    esel = np.empty(ecount, dtype=bool)
    fsel = np.empty(fcount, dtype=bool)
    mesh.vertices.foreach_get("select", vsel)
    mesh.edges.foreach_get("select", esel)
    mesh.polygons.foreach_get("select", fsel)
    return {
        "vcount": vcount,
        "fcount": fcount,
        "coords": coords,
        "edges": [tuple(e.vertices) for e in mesh.edges],
        "faces": [tuple(p.vertices) for p in mesh.polygons],
        "mat": obj.matrix_world.copy(),
        "vsel": vsel,
        "esel": esel,
        "fsel": fsel,
    }


def _objects_equal(a, b):
    """Geometry + transform only (selection is compared separately as context)."""
    if a["vcount"] != b["vcount"] or a["fcount"] != b["fcount"]:
        return False
    if not np.array_equal(a["coords"], b["coords"]):
        return False
    for i in range(4):
        for j in range(4):
            if abs(a["mat"][i][j] - b["mat"][i][j]) > 1e-7:
                return False
    return True


def _selection_equal(a, b):
    for m in ("vsel", "esel", "fsel"):
        va, vb = a.get(m), b.get(m)
        if (va is None) != (vb is None):
            return False
        if va is not None and not np.array_equal(va, vb):
            return False
    return True


def _capture_context(step):
    """Record the interaction state: object selection, 3D cursor, pivot, mode."""
    sc = bpy.context.scene
    ts = sc.tool_settings
    try:
        step["sel_objects"] = sorted(
            o.name for o in bpy.context.view_layer.objects if o.select_get())
    except Exception:
        step["sel_objects"] = []
    step["cursor_loc"] = sc.cursor.location.copy()
    try:
        step["cursor_rot"] = sc.cursor.rotation_euler.copy()
    except Exception:
        pass
    try:
        step["pivot"] = ts.transform_pivot_point
    except Exception:
        pass
    try:
        step["orientation"] = sc.transform_orientation_slots[0].type
    except Exception:
        pass
    try:
        step["select_mode"] = tuple(ts.mesh_select_mode)
    except Exception:
        pass


def _context_equal(a, b):
    """True if interaction state (not geometry) is identical between two steps."""
    for key in ("active", "sel_objects", "pivot", "orientation", "select_mode"):
        if a.get(key) != b.get(key):
            return False
    ca, cb = a.get("cursor_loc"), b.get("cursor_loc")
    if (ca is None) != (cb is None):
        return False
    if ca is not None and (ca - cb).length > 1e-6:
        return False
    for k in a["objs"]:
        db = b["objs"].get(k)
        if db is None or not _selection_equal(a["objs"][k], db):
            return False
    return True


def _capture_step():
    objects = _visible_mesh_objects()
    if not objects:
        return

    _isolate_objects(objects)

    rv3d = _get_view3d_rv3d()
    op_name = ""
    try:
        ops = bpy.context.window_manager.operators
        if len(ops):
            op_name = ops[-1].name or ops[-1].bl_idname
    except Exception:
        pass

    active = bpy.context.active_object
    step = {
        "t": time.monotonic(),
        "op": op_name or "(edit)",
        "view": classify_view(rv3d),
        "active": active.name if active else "",
        "mode": active.mode if active else "OBJECT",
        "objs": {},
    }
    if rv3d is not None:
        step["persp"] = rv3d.view_perspective
        step["rot"] = rv3d.view_rotation.copy()
        step["dist"] = rv3d.view_distance
        step["loc"] = rv3d.view_location.copy()

    _capture_context(step)

    budget = MAX_VERTS_FULL
    for obj in objects:
        vcount = len(obj.data.vertices)
        if vcount > budget:
            continue
        try:
            step["objs"][obj.name] = _snapshot_object(obj)
            budget -= vcount
        except Exception as e:
            print("[SceneCast] snapshot error on %s: %s" % (obj.name, e))

    if not step["objs"]:
        return

    if SESSION.steps:
        prev = SESSION.steps[-1]
        geo_same = (set(prev["objs"].keys()) == set(step["objs"].keys())
                    and all(_objects_equal(prev["objs"][k], step["objs"][k])
                            for k in step["objs"]))
        if geo_same:
            sc = bpy.context.scene
            if not sc.scenecast_capture_context:
                return                          # geometry-only mode: nothing new
            if _context_equal(prev, step):
                return                          # truly nothing changed
            # else: selection / cursor / pivot / mode changed -> record it

    SESSION.steps.append(step)
    SESSION.all_names.update(step["objs"].keys())
    step["keys"] = list(SESSION.pending_keys)
    SESSION.pending_keys.clear()

    try:
        sc = bpy.context.scene
        if sc.scenecast_follow_tip:
            sc["scenecast_playhead"] = len(SESSION.steps) - 1
    except Exception:
        pass
    _tag_redraw()


def _settle_tick():
    if not SESSION.recording:
        return None
    quiet = time.monotonic() - SESSION.last_stamp
    if SESSION.pending and quiet >= DEBOUNCE:
        SESSION.pending = False
        try:
            _capture_step()
        except Exception as e:
            print("[SceneCast] capture error:", e)
        return None
    return max(0.02, DEBOUNCE - quiet)


def _watchdog_tick():
    """Safety net: while recording in Edit Mode, diff the active mesh on a clock
    so steps register even when depsgraph events don't fire per edit."""
    if not SESSION.recording:
        return None
    obj = _edit_mode_object()
    if obj is not None and obj.type == 'MESH':
        try:
            obj.update_from_editmode()
            mesh = obj.data
            changed = True
            if SESSION.steps:
                prev = SESSION.steps[-1]["objs"].get(obj.name)
                if prev is not None and prev["vcount"] == len(mesh.vertices) \
                        and prev["fcount"] == len(mesh.polygons):
                    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
                    mesh.vertices.foreach_get("co", coords)
                    changed = not np.array_equal(prev["coords"], coords)
            if changed:
                _capture_step()
        except Exception as e:
            print("[SceneCast] watchdog error:", e)
    return WATCHDOG_DT


def _on_depsgraph(scene, depsgraph):
    if not SESSION.recording:
        return
    if time.monotonic() < SESSION.applying_until:
        return
    SESSION.pending = True
    SESSION.last_stamp = time.monotonic()
    if not bpy.app.timers.is_registered(_settle_tick):
        bpy.app.timers.register(_settle_tick, first_interval=DEBOUNCE)

