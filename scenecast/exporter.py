"""Export pipeline: frame-mapped step application and render settings handling."""

import os
import bpy

from .state import SESSION, _EXPORT, KEY_MAX_SHOWN
from .viewnav import _restore_view, _blend_view
from .replay import _apply_step_geometry, _interp_geometry
from .overlay import _collapse

# Render-stamp settings we take over during export and put back afterwards.
# The viewport keystroke overlay is a Python draw handler, and render.opengl
# does not run those -- so the only way to get keys into exported frames is to
# let the render pipeline burn them in itself.
_STAMP_ATTRS = (
    "use_stamp", "use_stamp_note", "stamp_note_text", "use_stamp_labels",
    "stamp_font_size", "use_stamp_date", "use_stamp_time",
    "use_stamp_render_time", "use_stamp_frame", "use_stamp_frame_range",
    "use_stamp_scene", "use_stamp_camera", "use_stamp_lens",
    "use_stamp_filename", "use_stamp_marker", "use_stamp_sequencer_strip",
    "use_stamp_hostname", "use_stamp_memory",
)


def _stamp_text_for(step):
    """One line of burn-in text: the keys for this step, then the operator."""
    keys = _collapse(step.get("keys", []))[-KEY_MAX_SHOWN:]
    note = "   ".join(keys)
    op = step.get("op", "")
    if note and op and op != "(edit)":
        return "%s     %s" % (note, op)
    return note or (op if op != "(edit)" else "")


def setup_stamp(rnd, size):
    """Burn only our note into the frames -- no date/frame/filename clutter."""
    for a in _STAMP_ATTRS:
        if a.startswith("use_stamp_") and hasattr(rnd, a):
            setattr(rnd, a, False)
    rnd.use_stamp = True
    rnd.use_stamp_note = True
    if hasattr(rnd, "use_stamp_labels"):
        rnd.use_stamp_labels = False     # no "Note:" prefix
    if hasattr(rnd, "stamp_font_size"):
        rnd.stamp_font_size = size
    rnd.stamp_note_text = ""

# ----------------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------------
def _export_frame_handler(scene, depsgraph=None):
    hold = _EXPORT["hold"]
    n = _EXPORT["n"]
    pos = (scene.frame_current - 1) / float(hold)
    idx = min(n - 1, max(0, int(pos)))
    frac = pos - idx
    SESSION.export_step_idx = idx
    if idx != _EXPORT["last"]:
        _EXPORT["last"] = idx
        try:
            _apply_step_geometry(SESSION.steps[idx], show_edit=_EXPORT["editmode"])
        except Exception as e:
            print("[SceneCast] export step error:", e)
        if _EXPORT["stamp"]:
            try:
                scene.render.stamp_note_text = _stamp_text_for(SESSION.steps[idx])
            except Exception as e:
                print("[SceneCast] export stamp error:", e)
    if _EXPORT["smooth"] and not _EXPORT["editmode"] and idx < n - 1:
        try:
            _interp_geometry(SESSION.steps[idx], SESSION.steps[idx + 1], frac)
        except Exception as e:
            print("[SceneCast] export interp error:", e)
    if _EXPORT["follow"]:
        if _EXPORT["smooth"] and idx < n - 1:
            _blend_view(SESSION.steps[idx], SESSION.steps[idx + 1], frac)
        else:
            _restore_view(SESSION.steps[idx])


def _resolve_export_path(p, ext):
    ap = bpy.path.abspath(p) if p else ""
    if not ap:
        ap = os.path.join(bpy.app.tempdir, "scenecast_session" + ext)
    root, e = os.path.splitext(ap)
    if e.lower() != ext:
        ap = root + ext
    d = os.path.dirname(ap)
    if d and not os.path.isdir(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
    return ap


def _resolve_export_dir(p):
    ap = bpy.path.abspath(p) if p else ""
    if not ap:
        return bpy.app.tempdir
    d = ap if os.path.isdir(ap) else os.path.dirname(ap)
    if not d:
        d = bpy.app.tempdir
    if not os.path.isdir(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
    return d


def _stash_render(sc, rnd):
    return {
        "fs": sc.frame_start, "fe": sc.frame_end, "fc": sc.frame_current,
        "fp": rnd.filepath, "ff": rnd.image_settings.file_format, "fps": rnd.fps,
        "mt": getattr(rnd.image_settings, "media_type", None),
        "vf": rnd.ffmpeg.format, "vc": rnd.ffmpeg.codec, "va": rnd.ffmpeg.audio_codec,
        "stamp": {a: getattr(rnd, a) for a in _STAMP_ATTRS if hasattr(rnd, a)},
    }


def _restore_render(sc, rnd, s):
    try:
        sc.frame_start = s["fs"]; sc.frame_end = s["fe"]; sc.frame_current = s["fc"]
        rnd.filepath = s["fp"]; rnd.fps = s["fps"]
        if s.get("mt") is not None and hasattr(rnd.image_settings, "media_type"):
            rnd.image_settings.media_type = s["mt"]
        rnd.image_settings.file_format = s["ff"]
        rnd.ffmpeg.format = s["vf"]; rnd.ffmpeg.codec = s["vc"]; rnd.ffmpeg.audio_codec = s["va"]
    except Exception:
        pass
    for a, v in s.get("stamp", {}).items():
        try:
            setattr(rnd, a, v)
        except Exception:
            pass

