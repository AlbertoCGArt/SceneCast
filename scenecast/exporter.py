"""Export pipeline: frame-mapped step application and render settings handling."""

import os
import bpy

from .state import SESSION, _EXPORT, KEY_MAX_SHOWN
from .viewnav import _restore_view, _blend_view, apply_view_filters, view_spec
from .replay import _apply_step_geometry, _interp_geometry
from .overlay import _collapse, keys_for_step, op_label_for_step
from .props import EXPORT_RESOLUTIONS
from . import layout as sc_layout
from . import fonts

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


def export_resolution(sc):
    """(width, height) for this export, or None to leave the scene alone.

    Kept separate from the scene's own render settings on purpose: the size a
    session should be published at -- 1080p for a tutorial, 1080x1920 for a
    Reel -- has nothing to do with whatever the file renders stills at, and
    making the user change Output Properties to publish vertically was the
    kind of detour that stops the video getting made.
    """
    mode = getattr(sc, "scenecast_export_res", 'SCENE')
    if mode == 'SCENE':
        return None
    if mode == 'CUSTOM':
        return (int(sc.scenecast_export_res_x), int(sc.scenecast_export_res_y))
    return EXPORT_RESOLUTIONS.get(mode)


def export_aspect(sc):
    """Width / height the export will actually be rendered at."""
    res = export_resolution(sc)
    if res is None:
        rnd = sc.render
        res = (rnd.resolution_x, rnd.resolution_y)
    return float(res[0]) / max(1.0, float(res[1]))


def _stamp_text_for(step, idx=None):
    """One line of burn-in text: the keys for this step, then the operator."""
    if idx is not None:
        raw = keys_for_step(idx)
        op = op_label_for_step(idx)
    else:
        raw = step.get("keys", [])
        op = step.get("op", "")
        if op == "(edit)":
            op = ""
    note = "   ".join(_collapse(raw)[-KEY_MAX_SHOWN:])
    if note and op:
        return "%s     %s" % (note, op)
    return note or op


# The viewport overlay draws each keystroke chunk followed by this gap.
KEY_GAP = "    "


def overlay_lines(idx):
    """(keys, operator) for a step, as the viewport overlay shows them.

    Two lines, not one: the viewport draws the keystrokes and, under them in
    blue, the operator that ran. An export that wants to look like the
    viewport draws the same two -- the render stamp, which only has one line,
    is the exception and uses _stamp_text_for.
    """
    keys = KEY_GAP.join(_collapse(keys_for_step(idx))[-KEY_MAX_SHOWN:])
    return keys, op_label_for_step(idx)


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
                scene.render.stamp_note_text = _stamp_text_for(
                    SESSION.steps[idx], idx)
            except Exception as e:
                print("[SceneCast] export stamp error:", e)
    if _EXPORT["smooth"] and idx < n - 1:
        try:
            _interp_geometry(SESSION.steps[idx], SESSION.steps[idx + 1], frac)
        except Exception as e:
            print("[SceneCast] export interp error:", e)
    # Only Recorded Views drives the camera per frame. A static mode was
    # pointed once before the render started and must be left alone -- and
    # _blend_view flips the projection at its midpoint, so the whole call has
    # to be skipped, not just the rotation write.
    if _EXPORT["follow"]:
        if _EXPORT["smooth"] and idx < n - 1:
            _blend_view(SESSION.steps[idx], SESSION.steps[idx + 1], frac)
        else:
            _restore_view(SESSION.steps[idx])
    apply_view_filters(idx, frac)
    _record_export_view(scene)


def _record_export_view(scene):
    """Keep the camera this frame renders with, at its frame's index.

    Runs last in the frame handler, after the view mode and the view filters
    have had their say, so what is kept is the camera the frame is drawn from.
    """
    frames = SESSION.export_views
    i = scene.frame_current - 1
    if i < 0:
        return
    while len(frames) < i:
        frames.append(None)
    spec = view_spec(scene)
    if i == len(frames):
        frames.append(spec)
    else:
        frames[i] = spec


def _seq_strips(se):
    """Blender 5.0 renamed SequenceEditor.sequences to .strips.

    Test for presence, never truthiness: the editor is created empty, and an
    empty Blender collection is falsy, so `strips or sequences` picks the
    wrong one on exactly the versions that need `strips`.
    """
    strips = getattr(se, "strips", None)
    if strips is not None:
        return strips
    return se.sequences


def new_text_strip(strips, name, channel, frame_start, length):
    """Create a TEXT strip across the Blender versions that renamed the span.

    5.0 takes `length` (name, type, channel, frame_start, length, input1,
    input2); 4.x took `frame_end`. Neither accepts the other's keyword, so
    try each and let TypeError pick.
    """
    try:
        return strips.new_effect(name=name, type='TEXT', channel=channel,
                                 frame_start=frame_start, length=length)
    except TypeError:
        return strips.new_effect(name=name, type='TEXT', channel=channel,
                                 frame_start=frame_start,
                                 frame_end=frame_start + length)


def _set_any(obj, pairs):
    """Set whichever of these attributes this Blender version actually has."""
    for attr, val in pairs:
        try:
            setattr(obj, attr, val)
        except Exception:
            pass


def apply_video_settings(rnd, fps):
    if hasattr(rnd.image_settings, "media_type"):
        rnd.image_settings.media_type = 'VIDEO'      # Blender 5.0+ gate
    rnd.image_settings.file_format = 'FFMPEG'
    rnd.ffmpeg.format = 'MPEG4'
    rnd.ffmpeg.codec = 'H264'
    rnd.ffmpeg.constant_rate_factor = 'MEDIUM'
    rnd.ffmpeg.audio_codec = 'NONE'
    rnd.fps = fps


def composite_text_video(src_scene, png_dir, out_path, hold, fps, lines, scale=1.0):
    """Second pass: rebuild the rendered frames into a video with text burned in.

    render.opengl will not run Python draw handlers, and Blender's render stamp
    is locked to the top-left corner -- neither can put keystrokes where a
    screencast wants them. Feeding the frames back through the sequencer as an
    image strip with text strips over it gives full control of position, size,
    font, colour and shadow.

    `lines` holds one (keys, operator) pair per step, from overlay_lines(): the
    two lines the viewport draws, in its font, its colours and its bands.
    """
    files = sorted(f for f in os.listdir(png_dir) if f.lower().endswith(".png"))
    if not files:
        raise RuntimeError("no frames were rendered")

    scene = bpy.data.scenes.new("SceneCast Composite")
    try:
        r = scene.render
        sr = src_scene.render
        r.resolution_x = sr.resolution_x
        r.resolution_y = sr.resolution_y
        r.resolution_percentage = sr.resolution_percentage
        scene.frame_start = 1
        scene.frame_end = len(files)

        # Text is sized and placed as a fraction of frame height, from the
        # same table the viewport overlay reads. A pixel size picked for
        # 1080p is a rounding error at 4K and covers half the frame on a
        # 1080x1920 vertical export.
        out_h = r.resolution_y * max(1, r.resolution_percentage) / 100.0
        bands = {}
        for name in ("keys", "op"):
            y, size = sc_layout.band_norm(name, scale)
            bands[name] = (y, max(sc_layout.MIN_FONT_PX, size * out_h))
        # Without a font, text strips render in Blender's monospace default.
        font = fonts.vse_font(fonts.ui_font_path())

        se = scene.sequence_editor_create()
        strips = _seq_strips(se)
        img = strips.new_image(name="frames", channel=1, frame_start=1,
                               filepath=os.path.join(png_dir, files[0]))
        for fn in files[1:]:
            img.elements.append(fn)

        for i, pair in enumerate(lines):
            start = 1 + i * hold
            if start > len(files):
                break
            length = min(hold, len(files) + 1 - start)
            if length < 1:
                continue
            for text, band, channel, color in (
                    (pair[0], "keys", 2, sc_layout.KEYS_COLOR),
                    (pair[1], "op", 3, sc_layout.OP_COLOR)):
                if not text:
                    continue
                try:
                    t = new_text_strip(strips, "%s%04d" % (band, i), channel,
                                       start, length)
                except Exception as e:  # one bad strip shouldn't lose the video
                    print("[SceneCast] text strip %d failed: %s" % (i, e))
                    continue
                t.text = text
                y, size = bands[band]
                # anchor_* is 4.x+, align_* is the older spelling; set both.
                _set_any(t, (("font_size", size), ("color", color),
                             ("use_shadow", True),
                             ("shadow_color", (0.0, 0.0, 0.0, 0.9)),
                             ("anchor_x", 'CENTER'), ("anchor_y", 'BOTTOM'),
                             ("align_x", 'CENTER'), ("align_y", 'BOTTOM'),
                             ("location", (0.5, y))))
                if font is not None:
                    _set_any(t, (("font", font),))

        apply_video_settings(r, fps)
        r.filepath = out_path
        with bpy.context.temp_override(scene=scene):
            bpy.ops.render.render(animation=True)
    finally:
        try:
            bpy.data.scenes.remove(scene)
        except Exception:
            pass


def _stash_render(sc, rnd):
    return {
        "fs": sc.frame_start, "fe": sc.frame_end, "fc": sc.frame_current,
        "fp": rnd.filepath, "ff": rnd.image_settings.file_format, "fps": rnd.fps,
        "rx": rnd.resolution_x, "ry": rnd.resolution_y,
        "rp": rnd.resolution_percentage,
        "mt": getattr(rnd.image_settings, "media_type", None),
        "vf": rnd.ffmpeg.format, "vc": rnd.ffmpeg.codec, "va": rnd.ffmpeg.audio_codec,
        "stamp": {a: getattr(rnd, a) for a in _STAMP_ATTRS if hasattr(rnd, a)},
    }


def _restore_render(sc, rnd, s):
    try:
        sc.frame_start = s["fs"]; sc.frame_end = s["fe"]; sc.frame_current = s["fc"]
        rnd.filepath = s["fp"]; rnd.fps = s["fps"]
        rnd.resolution_x = s["rx"]; rnd.resolution_y = s["ry"]
        rnd.resolution_percentage = s["rp"]
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

