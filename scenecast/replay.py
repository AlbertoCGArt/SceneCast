"""Replay pipeline: mesh rebuilds, context restore, step application, playback."""

import time
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix

from .state import SESSION, APPLY_LOCKOUT, PLAY_DT
from .viewnav import (_tag_redraw, _mode_set, _exit_all_edit,
                      _any_nonobject_mode, _restore_view, _blend_view)

# ----------------------------------------------------------------------------
# Motion smoothing (glide between steps instead of snapping frame-to-frame)
# ----------------------------------------------------------------------------
def _smoothstep(t):
    """Ease-in-out clamp of t into [0, 1]."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def _lerp_coords(ca, cb, f):
    """Linear blend of two equal-length flat coordinate buffers."""
    return ca + (cb - ca) * f


def _lerp_matrix(m0, m1, f):
    """Blend two world matrices: lerp location & scale, slerp rotation."""
    l0, r0, s0 = m0.decompose()
    l1, r1, s1 = m1.decompose()
    return Matrix.LocRotScale(l0.lerp(l1, f), r0.slerp(r1, f), s0.lerp(s1, f))


def _interp_edit_cage(obj, blended):
    """Blend an object that is currently in Edit Mode.

    Writing to mesh.vertices does nothing visible while Edit Mode is active --
    the cage is drawn from the bmesh -- so modelling work snapped from step to
    step while the camera glided. The bmesh has to be moved instead.
    """
    try:
        bm = bmesh.from_edit_mesh(obj.data)
        if len(bm.verts) * 3 != len(blended):
            return
        bm.verts.ensure_lookup_table()
        for i, v in enumerate(bm.verts):
            j = i * 3
            v.co = Vector((blended[j], blended[j + 1], blended[j + 2]))
        # coordinates only: no topology change, so skip the destructive path
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    except Exception:
        pass


def _interp_geometry(step_a, step_b, frac):
    """Glide same-topology meshes and transforms from step_a toward step_b.

    Called every playback/export frame between two integer steps so a moved
    face or grabbed object slides instead of snapping. Only objects present in
    BOTH steps with a matching vertex count are blended: a step that adds or
    removes geometry genuinely is a jump, and no lerp turns 8 vertices into 12.

    Uses a LINEAR (constant-velocity) blend on purpose: it reads like the real
    drag the artist did, not an eased keyframe animation.
    """
    f = 0.0 if frac < 0.0 else 1.0 if frac > 1.0 else frac
    for name, a in step_a["objs"].items():
        b = step_b["objs"].get(name)
        if b is None:
            continue
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != 'MESH':
            continue
        editing = obj.mode == 'EDIT'
        mesh = obj.data
        ca, cb = a.get("coords"), b.get("coords")
        if (a["vcount"] == b["vcount"] and ca is not None and cb is not None
                and len(ca) == len(cb)
                and (editing or len(mesh.vertices) == a["vcount"])):
            try:
                blended = _lerp_coords(ca, cb, f)
                if editing:
                    _interp_edit_cage(obj, blended)
                else:
                    mesh.vertices.foreach_set("co", blended)
                    mesh.update()
            except Exception:
                pass
        try:
            obj.matrix_world = _lerp_matrix(a["mat"], b["mat"], f)
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Replay core
# ----------------------------------------------------------------------------
def _apply_mesh_selection(mesh, data):
    try:
        vsel = data.get("vsel")
        if vsel is not None and len(mesh.vertices) == len(vsel):
            mesh.vertices.foreach_set("select", vsel)
        esel = data.get("esel")
        if esel is not None and len(mesh.edges) == len(esel):
            mesh.edges.foreach_set("select", esel)
        fsel = data.get("fsel")
        if fsel is not None and len(mesh.polygons) == len(fsel):
            mesh.polygons.foreach_set("select", fsel)
    except Exception:
        pass


def _rebuild_object(obj, data):
    """Object-mode rebuild (mesh datablock)."""
    mesh = obj.data
    same_topo = (len(mesh.vertices) == data["vcount"]
                 and len(mesh.polygons) == data["fcount"])
    try:
        if same_topo:
            mesh.vertices.foreach_set("co", data["coords"])
        else:
            verts = data["coords"].reshape(-1, 3).tolist()
            mesh.clear_geometry()
            mesh.from_pydata(verts, data["edges"], data["faces"])
            mesh.validate(verbose=False)
        _apply_mesh_selection(mesh, data)
        mesh.update()
        obj.matrix_world = data["mat"]
        return True
    except Exception as e:
        print("[SceneCast] rebuild error on %s: %s" % (obj.name, e))
        return False


def _rebuild_object_editmode(obj, data):
    """Rebuild while the object is IN Edit Mode, via bmesh (safe path).
    Restores per-element selection so the cage shows what was selected."""
    try:
        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        bm.clear()
        coords = data["coords"].reshape(-1, 3)
        vs = [bm.verts.new(Vector(c)) for c in coords]
        bm.verts.ensure_lookup_table()
        vsel = data.get("vsel")
        if vsel is not None:
            for i, v in enumerate(vs):
                v.select = bool(vsel[i])
        esel = data.get("esel")
        for ei, e in enumerate(data["edges"]):
            try:
                edge = bm.edges.new((vs[e[0]], vs[e[1]]))
                if esel is not None:
                    edge.select = bool(esel[ei])
            except ValueError:
                pass                    # edge already exists
        fsel = data.get("fsel")
        for fi, f in enumerate(data["faces"]):
            try:
                face = bm.faces.new([vs[i] for i in f])
                if fsel is not None:
                    face.select = bool(fsel[fi])
            except (ValueError, IndexError):
                pass
        bm.select_flush_mode()
        bm.normal_update()
        bmesh.update_edit_mesh(mesh, loop_triangles=True, destructive=True)
        obj.matrix_world = data["mat"]
        return True
    except Exception as e:
        print("[SceneCast] edit rebuild error on %s: %s" % (obj.name, e))
        return False


def _restore_context(step, allow_object_select=True):
    """Put back the interaction state: cursor, pivot, select-mode, object selection.
    Called in Object Mode so object selection/active can be set safely."""
    sc = bpy.context.scene
    ts = sc.tool_settings
    if "cursor_loc" in step:
        try:
            sc.cursor.location = step["cursor_loc"]
        except Exception:
            pass
    if "cursor_rot" in step:
        try:
            sc.cursor.rotation_euler = step["cursor_rot"]
        except Exception:
            pass
    if "pivot" in step:
        try:
            ts.transform_pivot_point = step["pivot"]
        except Exception:
            pass
    if "orientation" in step:
        try:
            sc.transform_orientation_slots[0].type = step["orientation"]
        except Exception:
            pass
    if "select_mode" in step:
        try:
            ts.mesh_select_mode = step["select_mode"]
        except Exception:
            pass
    if allow_object_select and "sel_objects" in step:
        sel = set(step["sel_objects"])
        for o in bpy.context.view_layer.objects:
            try:
                o.select_set(o.name in sel)
            except Exception:
                pass
    act = bpy.data.objects.get(step.get("active", ""))
    if act is not None:
        try:
            bpy.context.view_layer.objects.active = act
        except Exception:
            pass


def _apply_step_geometry(step, show_edit=False):
    """Rebuild all objects for a step; hide session objects that don't exist yet.

    Order: exit to Object Mode -> restore object-level context -> rebuild meshes
    -> (optionally) re-enter Edit Mode on the recorded active object and rebuild
    its cage with selection. This keeps context restore in a mode where it's legal.
    """
    SESSION.applying_until = time.monotonic() + APPLY_LOCKOUT
    sc = bpy.context.scene

    want_edit_name = ""
    if show_edit and step.get("mode") == 'EDIT' and step.get("active"):
        if step["active"] in step["objs"] and \
                bpy.data.objects.get(step["active"]) is not None:
            want_edit_name = step["active"]

    if not show_edit and _any_nonobject_mode():
        return False                    # legacy guard: user is hand-editing, don't fight

    _exit_all_edit()                    # clean Object-Mode slate

    if sc.scenecast_restore_context:
        _restore_context(step, allow_object_select=True)

    names_in_step = set(step["objs"].keys())
    for name in SESSION.all_names:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != 'MESH':
            continue                    # deleted from scene: can't resurrect (limitation)
        if name in names_in_step:
            try:
                obj.hide_set(False)
            except Exception:
                obj.hide_viewport = False
            if name != want_edit_name:  # the edit target is rebuilt in Edit Mode below
                _rebuild_object(obj, step["objs"][name])
        else:
            try:
                obj.hide_set(True)
            except Exception:
                obj.hide_viewport = True

    if want_edit_name:
        obj = bpy.data.objects.get(want_edit_name)
        if obj is not None:
            _mode_set(obj, 'EDIT')
            if obj.mode == 'EDIT':
                _rebuild_object_editmode(obj, step["objs"][want_edit_name])
            else:
                _rebuild_object(obj, step["objs"][want_edit_name])
    return True


def _apply_step(index, with_view=True):
    if not (0 <= index < len(SESSION.steps)):
        return
    step = SESSION.steps[index]
    sc = bpy.context.scene
    _apply_step_geometry(step, show_edit=sc.scenecast_show_edit)
    if with_view and sc.scenecast_restore_view:
        _restore_view(step)
    _tag_redraw()


def _playhead_update(self, context):
    n = len(SESSION.steps)
    if n == 0 or SESSION.playing or SESSION.recording:
        return
    _apply_step(max(0, min(self.scenecast_playhead, n - 1)))


# ----------------------------------------------------------------------------
# Playback
# ----------------------------------------------------------------------------
def _play_tick():
    if not SESSION.playing:
        return None
    sc = bpy.context.scene
    n = len(SESSION.steps)
    if n == 0:
        SESSION.playing = False
        return None

    now = time.monotonic()
    dt = min(0.25, now - SESSION.play_last_t)
    SESSION.play_last_t = now
    hold = max(0.02, sc.scenecast_step_hold)
    SESSION.play_pos += dt / hold

    end = float(n - 1)
    if SESSION.play_pos >= end:
        if sc.scenecast_loop and n > 1:
            SESSION.play_pos = SESSION.play_pos % end
        else:
            SESSION.play_pos = end

    idx = int(SESSION.play_pos)
    frac = SESSION.play_pos - idx

    if idx != SESSION.play_last_idx:
        SESSION.play_last_idx = idx
        _apply_step_geometry(SESSION.steps[idx], show_edit=sc.scenecast_show_edit)
        sc["scenecast_playhead"] = idx

    if sc.scenecast_smooth_view and idx < n - 1:
        _interp_geometry(SESSION.steps[idx], SESSION.steps[idx + 1], frac)

    if sc.scenecast_restore_view:
        if sc.scenecast_smooth_view and idx < n - 1:
            _blend_view(SESSION.steps[idx], SESSION.steps[idx + 1], frac)
        else:
            _restore_view(SESSION.steps[idx])

    _tag_redraw()

    if SESSION.play_pos >= end and not sc.scenecast_loop:
        SESSION.playing = False
        _restore_view(SESSION.steps[n - 1])
        return None
    return PLAY_DT

