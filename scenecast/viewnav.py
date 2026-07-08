"""Viewport discovery, view classification, mode management, view interpolation."""

import bpy
from mathutils import Vector

# ----------------------------------------------------------------------------
# Viewport helpers
# ----------------------------------------------------------------------------
def _get_view3d_rv3d():
    wm = bpy.context.window_manager
    for win in wm.windows:
        scr = win.screen
        if not scr:
            continue
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        return space.region_3d
    return None


def _find_view3d_context():
    wm = bpy.context.window_manager
    for win in wm.windows:
        scr = win.screen
        if not scr:
            continue
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if region:
                    return win, area, region
    return None, None, None


def classify_view(rv3d):
    """Axis names follow Blender's numpad conventions -- flip a sign if reversed."""
    if rv3d is None:
        return "Unknown"
    if rv3d.view_perspective == 'CAMERA':
        return "Camera"
    kind = "Persp" if rv3d.view_perspective == 'PERSP' else "Ortho"
    look = (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))).normalized()
    axes = (
        (Vector(( 0.0,  0.0, -1.0)), "Top"),
        (Vector(( 0.0,  0.0,  1.0)), "Bottom"),
        (Vector(( 0.0,  1.0,  0.0)), "Front"),
        (Vector(( 0.0, -1.0,  0.0)), "Back"),
        (Vector((-1.0,  0.0,  0.0)), "Right"),
        (Vector(( 1.0,  0.0,  0.0)), "Left"),
    )
    best_name, best_dot = "", -2.0
    for vec, name in axes:
        d = look.dot(vec)
        if d > best_dot:
            best_dot, best_name = d, name
    if best_dot > 0.9995:
        return "%s %s" % (best_name, kind)
    return kind


def _tag_redraw():
    wm = bpy.context.window_manager
    for win in wm.windows:
        if win.screen:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()


def _edit_mode_object():
    for obj in bpy.data.objects:
        if obj.mode == 'EDIT':
            return obj
    return None


def _any_nonobject_mode():
    for obj in bpy.data.objects:
        if obj.mode != 'OBJECT':
            return True
    return False


# ----------------------------------------------------------------------------
# Mode management (used by playback when "Show Edit Mode" is on)
# ----------------------------------------------------------------------------
def _mode_set(obj, mode):
    """Set an object's mode via the operator, with a valid 3D-view context."""
    try:
        if obj.mode == mode:
            return True
        bpy.context.view_layer.objects.active = obj
        win, area, region = _find_view3d_context()
        if area is not None:
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.object.mode_set(mode=mode)
        else:
            bpy.ops.object.mode_set(mode=mode)
        return obj.mode == mode
    except Exception as e:
        print("[SceneCast] mode_set error:", e)
        return False


def _exit_all_edit():
    ok = True
    for obj in list(bpy.data.objects):
        if obj.mode != 'OBJECT':
            ok = _mode_set(obj, 'OBJECT') and ok
    return ok


# ----------------------------------------------------------------------------
# View interpolation
# ----------------------------------------------------------------------------
def _smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _set_view(rv3d, persp, rot, dist, loc):
    try:
        rv3d.view_perspective = persp
        rv3d.view_rotation = rot
        rv3d.view_distance = dist
        rv3d.view_location = loc
    except Exception:
        pass


def _restore_view(step):
    rv3d = _get_view3d_rv3d()
    if rv3d is None or "rot" not in step:
        return
    _set_view(rv3d, step["persp"], step["rot"], step["dist"], step["loc"])


def _blend_view(step_a, step_b, frac):
    rv3d = _get_view3d_rv3d()
    if rv3d is None:
        return
    if "rot" not in step_a or "rot" not in step_b:
        if "rot" in step_b:
            _restore_view(step_b)
        return
    t = _smoothstep(frac)
    rot = step_a["rot"].slerp(step_b["rot"], t)
    dist = step_a["dist"] * (1.0 - t) + step_b["dist"] * t
    loc = step_a["loc"].lerp(step_b["loc"], t)
    persp = step_a["persp"] if t < 0.5 else step_b["persp"]
    _set_view(rv3d, persp, rot, dist, loc)

