"""User-facing operators: record toggle, clear, step, play, export."""

import os
import time
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty

from .state import SESSION, _EXPORT, WATCHDOG_DT
from .viewnav import (_tag_redraw, _exit_all_edit, _any_nonobject_mode,
                      _find_view3d_context)
from .capture import _capture_step, _watchdog_tick, _restore_collections
from .replay import _apply_step_geometry, _play_tick
from .exporter import (_export_frame_handler, _resolve_export_path,
                       _resolve_export_dir, _stash_render, _restore_render,
                       setup_stamp)

# ----------------------------------------------------------------------------
def _keylogger_watchdog():
    """Keep the key-logger alive for the whole recording.

    Two problems this solves: (1) a modal started from inside the Record
    button's execute() often fails to attach -- launching it from this timer
    runs it in a clean context; (2) Blender silently drops a passive modal
    after a menu or modal tool (Shift+A, Grab, Extrude...), so only the first
    keystroke ever gets captured. The logger stamps a heartbeat every ~0.25s;
    if it goes quiet (dropped), we re-arm it. The logger's sequence check
    retires any stale duplicate, so re-arming is always safe.
    """
    if not SESSION.recording:
        return None                      # recording stopped -> let the timer die
    now = time.monotonic()
    alive = (SESSION.keylogger_running
             and (now - SESSION.keylogger_heartbeat) < 1.5)
    if not alive:
        # A timer callback runs in a restricted context where context.window is
        # None, and modal_handler_add() needs a window to attach to -- without
        # the override the modal is created but never receives a single event.
        win, area, region = _find_view3d_context()
        if win is None:
            return 0.5                   # no viewport yet; try again next tick
        try:
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.scenecast.keylogger('INVOKE_DEFAULT')
        except Exception as e:
            print("[SceneCast] keylogger (re)start failed:", e)
    return 0.5


# ----------------------------------------------------------------------------
class SCENECAST_OT_toggle(Operator):
    bl_idname = "scenecast.toggle"
    bl_label = "Toggle Recording"
    bl_description = "Start or stop recording mesh edits"

    def execute(self, context):
        SESSION.recording = not SESSION.recording
        if SESSION.recording:
            SESSION.playing = False
            SESSION.pending = False
            SESSION.last_stamp = time.monotonic()
            SESSION.applying_until = 0.0
            SESSION.key_buffer.clear()
            SESSION.pending_keys.clear()
            try:
                _capture_step()     # baseline: the scene before anything happens
            except Exception:
                pass
            if not bpy.app.timers.is_registered(_watchdog_tick):
                bpy.app.timers.register(_watchdog_tick, first_interval=WATCHDOG_DT)
            if not bpy.app.timers.is_registered(_keylogger_watchdog):
                bpy.app.timers.register(_keylogger_watchdog, first_interval=0.01)
            self.report({'INFO'}, "Recording started")
        else:
            self.report({'INFO'}, "Recording stopped (%d steps)" % len(SESSION.steps))
        _tag_redraw()
        return {'FINISHED'}


class SCENECAST_OT_clear(Operator):
    bl_idname = "scenecast.clear"
    bl_label = "Clear Session"
    bl_description = "Discard all recorded steps (unhides session objects, exits Edit Mode)"

    def execute(self, context):
        _exit_all_edit()
        for name in SESSION.all_names:
            obj = bpy.data.objects.get(name)
            if obj is not None:
                try:
                    obj.hide_set(False)
                except Exception:
                    obj.hide_viewport = False
        _restore_collections()
        SESSION.steps.clear()
        SESSION.all_names.clear()
        SESSION.playing = False
        context.scene["scenecast_playhead"] = 0
        self.report({'INFO'}, "Session cleared")
        _tag_redraw()
        return {'FINISHED'}


class SCENECAST_OT_step(Operator):
    bl_idname = "scenecast.step"
    bl_label = "Step"
    bl_description = "Move the playhead"

    mode: EnumProperty(
        items=[('FIRST', "First", ""), ('PREV', "Prev", ""),
               ('NEXT', "Next", ""), ('LAST', "Last", "")],
        default='NEXT',
    )

    def execute(self, context):
        n = len(SESSION.steps)
        if n == 0:
            return {'CANCELLED'}
        SESSION.playing = False
        cur = max(0, min(context.scene.scenecast_playhead, n - 1))
        if self.mode == 'FIRST':
            new = 0
        elif self.mode == 'LAST':
            new = n - 1
        elif self.mode == 'PREV':
            new = max(0, cur - 1)
        else:
            new = min(n - 1, cur + 1)
        context.scene.scenecast_playhead = new
        return {'FINISHED'}


class SCENECAST_OT_play(Operator):
    bl_idname = "scenecast.play"
    bl_label = "Play / Pause"
    bl_description = "Auto-advance through the recorded steps with smooth camera"

    def execute(self, context):
        if SESSION.playing:
            SESSION.playing = False
            _tag_redraw()
            return {'FINISHED'}
        n = len(SESSION.steps)
        if n == 0:
            return {'CANCELLED'}
        if _any_nonobject_mode() and not context.scene.scenecast_show_edit:
            self.report({'WARNING'},
                        "Switch to Object Mode (or enable Show Edit Mode) to play back")
            return {'CANCELLED'}
        SESSION.recording = False
        start = context.scene.scenecast_playhead
        if start >= n - 1:
            start = 0
        SESSION.play_pos = float(start)
        SESSION.play_last_idx = -1
        SESSION.play_last_t = time.monotonic()
        SESSION.playing = True
        if not bpy.app.timers.is_registered(_play_tick):
            bpy.app.timers.register(_play_tick, first_interval=0.0)
        _tag_redraw()
        return {'FINISHED'}


class SCENECAST_OT_export(Operator):
    bl_idname = "scenecast.export"
    bl_label = "Export Session"
    bl_description = "Render the recorded session to a video or image sequence"

    def execute(self, context):
        n = len(SESSION.steps)
        if n == 0:
            self.report({'WARNING'}, "Nothing to export")
            return {'CANCELLED'}
        if SESSION.recording:
            self.report({'WARNING'}, "Stop recording first")
            return {'CANCELLED'}
        SESSION.playing = False
        _exit_all_edit()               # export always starts from a clean slate

        sc = context.scene
        rnd = sc.render
        # Export speed tracks playback exactly: each step lasts the same
        # "Hold (s)" used when scrubbing, converted to whole frames.
        hold = max(1, round(sc.scenecast_step_hold * sc.scenecast_export_fps))
        fmt = sc.scenecast_export_format

        win, area, region = _find_view3d_context()
        if area is None:
            self.report({'WARNING'}, "No 3D viewport found")
            return {'CANCELLED'}

        if fmt == 'MP4':
            out = _resolve_export_path(sc.scenecast_export_path, ".mp4")
        else:
            out = os.path.join(_resolve_export_dir(sc.scenecast_export_path), "frame_")

        stash = _stash_render(sc, rnd)
        try:
            rnd.fps = sc.scenecast_export_fps
            img = rnd.image_settings
            if fmt == 'MP4':
                if hasattr(img, "media_type"):
                    img.media_type = 'VIDEO'       # Blender 5.0+ gate
                img.file_format = 'FFMPEG'
                rnd.ffmpeg.format = 'MPEG4'
                rnd.ffmpeg.codec = 'H264'
                rnd.ffmpeg.constant_rate_factor = 'MEDIUM'
                rnd.ffmpeg.audio_codec = 'NONE'
            else:
                if hasattr(img, "media_type"):
                    img.media_type = 'IMAGE'
                img.file_format = 'PNG'
            rnd.filepath = out
            sc.frame_start = 1
            sc.frame_end = n * hold

            stamp = bool(sc.scenecast_show_keys)
            if stamp:
                setup_stamp(rnd, {'SMALL': 14, 'MEDIUM': 18,
                                  'LARGE': 24}.get(sc.scenecast_keys_size, 14))

            use_edit = sc.scenecast_show_edit and sc.scenecast_export_edit
            _apply_step_geometry(SESSION.steps[0], show_edit=use_edit)
            _EXPORT.update(hold=hold, n=n, last=-1,
                           follow=sc.scenecast_export_follow_view,
                           smooth=sc.scenecast_smooth_view,
                           editmode=use_edit, stamp=stamp)

            if _export_frame_handler not in bpy.app.handlers.frame_change_pre:
                bpy.app.handlers.frame_change_pre.append(_export_frame_handler)

            SESSION.export_active = True
            with context.temp_override(window=win, area=area, region=region):
                bpy.ops.render.opengl(animation=True, view_context=True)

            self.report({'INFO'}, "Exported to %s" % out)
            res = {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, "Export failed: %s (try PNG sequence)" % e)
            res = {'CANCELLED'}
        finally:
            SESSION.export_active = False
            if _export_frame_handler in bpy.app.handlers.frame_change_pre:
                bpy.app.handlers.frame_change_pre.remove(_export_frame_handler)
            _restore_render(sc, rnd, stash)
            _exit_all_edit()
        return res


# ----------------------------------------------------------------------------
