"""Viewport discovery, view classification, mode management, view interpolation."""

import math

import numpy as np
import bpy
from mathutils import Vector, Quaternion

# ----------------------------------------------------------------------------
# Fixed views
#
# Blender's numpad orientations as view_rotation quaternions, and which two
# bounding-box extents end up across and up the screen for each.
# ----------------------------------------------------------------------------
_R2 = math.sqrt(0.5)
FIXED_VIEW_ROT = {
    'FRONT': (_R2, _R2, 0.0, 0.0),      # numpad 1: looking along +Y, Z up
    'RIGHT': (0.5, 0.5, 0.5, 0.5),      # numpad 3: looking along -X, Z up
    'TOP':   (1.0, 0.0, 0.0, 0.0),      # numpad 7: looking down -Z, Y up
}
FIXED_VIEW_AXES = {
    'FRONT': (0, 2),                    # X across, Z up
    'RIGHT': (1, 2),                    # Y across, Z up
    'TOP':   (0, 1),                    # X across, Y up
}

# Modes that pin the camera once and then leave it alone.
STATIC_VIEW_MODES = frozenset(FIXED_VIEW_ROT) | {'CAMERA'}

VIEW_LENS = 50.0        # Blender's default viewport lens
VIEW_SENSOR = 72.0      # and the sensor width it pairs with
FRAME_MARGIN = 0.10


def fit_distance(width, height, aspect, lens=VIEW_LENS, sensor=VIEW_SENSOR,
                 margin=FRAME_MARGIN):
    """Smallest view_distance that keeps a width x height box on screen.

    Half the sensor over the lens gives the half-angle. The viewport derives
    its orthographic scale from view_distance through the same relation, which
    is why one formula frames both projections.

    `aspect` is region width / height; the sensor maps to whichever of the two
    is larger, matching Blender's automatic sensor fit.
    """
    half = math.atan((sensor * 0.5) / max(1e-6, lens))
    t2 = 2.0 * max(1e-6, math.tan(half))
    aspect = max(1e-6, aspect)
    w = max(0.0, width) * (1.0 + margin)
    h = max(0.0, height) * (1.0 + margin)
    if aspect >= 1.0:                   # sensor spans the width
        need = max(w, h * aspect)
    else:                               # portrait: sensor spans the height
        need = max(h, w / aspect)
    return max(1e-4, need / t2)


def snapshot_bbox(objs):
    """World-space (min, max) corners across every object snapshot given.

    Returns (None, None) when there is nothing with coordinates to measure.
    """
    lo = hi = None
    for data in (objs or {}).values():
        co = data.get("coords") if isinstance(data, dict) else None
        if co is None or len(co) < 3:
            continue
        pts = np.asarray(co, dtype=np.float64).reshape(-1, 3)
        m = data.get("mat")
        if m is not None:
            try:
                M = np.array([[float(m[r][c]) for c in range(4)]
                              for r in range(4)], dtype=np.float64)
                pts = pts @ M[:3, :3].T + M[:3, 3]
            except Exception:
                pass
        p_lo, p_hi = pts.min(axis=0), pts.max(axis=0)
        lo = p_lo if lo is None else np.minimum(lo, p_lo)
        hi = p_hi if hi is None else np.maximum(hi, p_hi)
    return lo, hi

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


# ----------------------------------------------------------------------------
# View filters
#
# Extension point for anything that wants the last word on where the camera
# sits -- a punch-in that tightens on the active object, or a set of custom
# camera keys that overrides the recorded angles entirely. Filters run after
# the view has been set, in every view mode, on the three paths that move it:
# scrubbing, playback and export. Each is handed the step index and how far
# between that step and the next the current frame is.
# ----------------------------------------------------------------------------
_VIEW_FILTERS = []


def register_view_filter(fn):
    if fn not in _VIEW_FILTERS:
        _VIEW_FILTERS.append(fn)


def unregister_view_filter(fn):
    if fn in _VIEW_FILTERS:
        _VIEW_FILTERS.remove(fn)


# What the view was before the filters touched it, and what they left behind.
# A filter adjusts a view; it must never be handed its own previous output.
# Recorded Views writes a fresh camera every frame so that never came up, but
# Current View and the static views leave the camera alone between frames --
# so each frame Punch In was tightening the frame before it, and reached full
# zoom whatever its Strength said.
_FILTER_VIEW = {"base": None, "result": None}


def _read_view(rv3d):
    try:
        return (rv3d.view_perspective, rv3d.view_rotation.copy(),
                float(rv3d.view_distance), rv3d.view_location.copy())
    except Exception:
        return None


def _same_view(a, b):
    """True if two views are the same camera, to float32 storage precision."""
    if a is None or b is None or a[0] != b[0]:
        return False
    try:
        scale = max(1.0, abs(a[2]))
        return (abs(a[1].dot(b[1])) > 1.0 - 1e-6
                and abs(a[2] - b[2]) <= 1e-5 * scale
                and (a[3] - b[3]).length <= 1e-5 * scale)
    except Exception:
        return False


def apply_view_filters(idx, frac=0.0):
    """Run every registered filter over the live viewport. Never raises.

    Filters always start from the view they were *given*. If the camera is
    still exactly where the filters left it, nothing else has set it since,
    so it is put back to what they started from; if it has moved, whatever
    moved it -- the view mode, or the artist orbiting -- is the new base.

    A filter that throws must not take playback or a half-finished render
    down with it, so each one is isolated -- but it is reported, because a
    silently dead filter looks exactly like a feature that does nothing.
    """
    if not _VIEW_FILTERS:
        return
    rv3d = _get_view3d_rv3d()
    if rv3d is None:
        return
    live = _read_view(rv3d)
    base = _FILTER_VIEW["base"]
    if base is not None and _same_view(live, _FILTER_VIEW["result"]):
        _set_view(rv3d, *base)
    else:
        _FILTER_VIEW["base"] = live
    for fn in list(_VIEW_FILTERS):
        try:
            fn(rv3d, idx, frac)
        except Exception as e:
            print("[SceneCast] view filter %s failed: %s"
                  % (getattr(fn, "__name__", fn), e))
    _FILTER_VIEW["result"] = _read_view(rv3d)


# ----------------------------------------------------------------------------
# Static view modes: set the camera once, then never touch it again
# ----------------------------------------------------------------------------
_VIEW_STASH = {}


def view_mode(scene):
    return getattr(scene, "scenecast_view_mode", 'RECORDED')


def stash_view():
    """Remember where the user was looking, so a run can hand it back."""
    rv3d = _get_view3d_rv3d()
    _VIEW_STASH.clear()
    if rv3d is None:
        return
    try:
        _VIEW_STASH.update(persp=rv3d.view_perspective,
                           rot=rv3d.view_rotation.copy(),
                           dist=rv3d.view_distance,
                           loc=rv3d.view_location.copy())
    except Exception:
        _VIEW_STASH.clear()


def restore_stashed_view():
    if not _VIEW_STASH:
        return
    rv3d = _get_view3d_rv3d()
    if rv3d is not None:
        _set_view(rv3d, _VIEW_STASH["persp"], _VIEW_STASH["rot"],
                  _VIEW_STASH["dist"], _VIEW_STASH["loc"])
    _VIEW_STASH.clear()


def _region_aspect():
    _win, _area, region = _find_view3d_context()
    if region is None or not region.height:
        return 16.0 / 9.0
    return float(region.width) / float(region.height)


def apply_static_view(scene, mode, frame_step=None, aspect=None):
    """Point the camera once for a fixed-view run. True if it was applied.

    Fixed axes are framed on the session's LAST step, where the model is at
    its largest, so it grows into frame rather than overflowing it.

    `aspect` is the shape the result will be seen at. Playback leaves it None
    and gets the viewport's, but an export renders at its own resolution --
    frame a 1080x1920 vertical export to a wide viewport and the model walks
    out of the sides.
    """
    rv3d = _get_view3d_rv3d()
    if rv3d is None:
        return False

    if mode == 'CAMERA':
        if getattr(scene, "camera", None) is None:
            return False                # caller falls back and warns
        try:
            rv3d.view_perspective = 'CAMERA'
            return True
        except Exception:
            return False

    rot = FIXED_VIEW_ROT.get(mode)
    if rot is None:
        return False
    try:
        rv3d.view_rotation = Quaternion(rot)
        rv3d.view_perspective = 'ORTHO'
    except Exception:
        return False

    if frame_step is not None:
        lo, hi = snapshot_bbox(frame_step.get("objs"))
        if lo is not None:
            ax_w, ax_h = FIXED_VIEW_AXES[mode]
            size = hi - lo
            try:
                rv3d.view_location = Vector(
                    ((lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5,
                     (lo[2] + hi[2]) * 0.5))
                rv3d.view_distance = fit_distance(
                    float(size[ax_w]), float(size[ax_h]),
                    _region_aspect() if aspect is None else aspect)
            except Exception:
                pass
    return True


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

