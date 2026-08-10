"""Export pipeline: frame-mapped step application and render settings handling."""

import os
import bpy

from .state import SESSION, _EXPORT
from .viewnav import _restore_view, _blend_view
from .replay import _apply_step_geometry, _interp_geometry

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

