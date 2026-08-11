"""User-facing operators: record toggle, clear, step, play, export."""

import os
import time
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty

from .state import SESSION, _EXPORT, WATCHDOG_DT, BUILD
from .viewnav import (_tag_redraw, _exit_all_edit, _any_nonobject_mode,
                      _find_view3d_context)
from .capture import _capture_step, _watchdog_tick, _restore_collections
from .overlay import keys_for_step
from .replay import _apply_step_geometry, _play_tick
from .exporter import (_export_frame_handler, _resolve_export_path,
                       _resolve_export_dir, _stash_render, _restore_render,
                       setup_stamp, apply_video_settings, composite_text_video,
                       _stamp_text_for)

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
            SESSION.key_log.clear()
            SESSION.keys_captured_total = 0
            try:
                _capture_step()     # baseline: the scene before anything happens
            except Exception:
                pass
            if not bpy.app.timers.is_registered(_watchdog_tick):
                bpy.app.timers.register(_watchdog_tick, first_interval=WATCHDOG_DT)
            # Primary start: this runs from the panel button, so the context
            # has a real window and the modal handler attaches cleanly. The
            # watchdog below is only the re-arm path if it later gets dropped.
            try:
                bpy.ops.scenecast.keylogger('INVOKE_DEFAULT')
            except Exception as e:
                print("[SceneCast] keylogger start failed:", e)
            if not bpy.app.timers.is_registered(_keylogger_watchdog):
                bpy.app.timers.register(_keylogger_watchdog, first_interval=0.5)
            self.report({'INFO'}, "Recording started")
        else:
            n_keyed = sum(1 for i in range(len(SESSION.steps)) if keys_for_step(i))
            print("[SceneCast] session: %d steps, %d keystrokes captured, "
                  "%d steps carry keys, logger attached=%s"
                  % (len(SESSION.steps), SESSION.keys_captured_total,
                     n_keyed, SESSION.keylogger_running))
            self.report({'INFO'}, "Recording stopped (%d steps, %d keys)"
                        % (len(SESSION.steps), SESSION.keys_captured_total))
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
        SESSION.key_log.clear()
        SESSION.key_buffer.clear()
        SESSION.pending_keys.clear()
        SESSION.keys_captured_total = 0
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


class SCENECAST_OT_diagnose(Operator):
    bl_idname = "scenecast.diagnose"
    bl_label = "Diagnostics"
    bl_description = ("Write a report on key capture and step contents to the "
                      "System Console and a 'SceneCast Report' text block")

    def execute(self, context):
        from . import overlay as _ov
        sc = context.scene
        L = []
        L.append("SceneCast diagnostics  (build %s)" % BUILD)
        L.append("-" * 58)
        L.append("show_keys prop      : %s" % getattr(sc, "scenecast_show_keys", "?"))
        L.append("draw handler        : %s" % ("installed" if _ov._draw_handle
                                               else "MISSING"))
        L.append("logger attached     : %s" % SESSION.keylogger_running)
        L.append("recording           : %s" % SESSION.recording)
        L.append("keystrokes captured : %d" % SESSION.keys_captured_total)
        L.append("key_log entries     : %d" % len(SESSION.key_log))
        L.append("live key_buffer     : %d" % len(SESSION.key_buffer))
        L.append("pending (undrained) : %d" % len(SESSION.pending_keys))
        L.append("steps               : %d" % len(SESSION.steps))
        if SESSION.key_log:
            sample = ", ".join(t for t, _ in SESSION.key_log[:12])
            L.append("first logged keys   : %s" % sample)

        n_own = sum(1 for s in SESSION.steps if s.get("keys"))
        n_res = sum(1 for i in range(len(SESSION.steps)) if _ov.keys_for_step(i))
        L.append("steps w/ own keys   : %d" % n_own)
        L.append("steps w/ resolved   : %d" % n_res)
        L.append("")
        L.append("idx  op                        op_id                     keys")
        for i, s in enumerate(SESSION.steps[:40]):
            L.append("%-4d %-25.25s %-25.25s %s"
                     % (i, s.get("op", ""), s.get("op_id", ""),
                        ",".join(_ov.keys_for_step(i)) or "-"))
        if len(SESSION.steps) > 40:
            L.append("... %d more steps" % (len(SESSION.steps) - 40))

        # Does the keymap/menu lookup resolve the operators this session used?
        L.append("")
        L.append("shortcut lookup for operators seen this session:")
        seen = []
        for s in SESSION.steps:
            oid = s.get("op_id", "")
            if oid and oid not in seen:
                seen.append(oid)
        for oid in seen[:25]:
            L.append("  %-40.40s -> %s"
                     % (oid, _ov.shortcut_for_operator(oid) or "(none found)"))
        if not seen:
            L.append("  (no operator ids recorded)")

        report = "\n".join(L)
        print("\n" + report + "\n")
        try:
            name = "SceneCast Report"
            txt = bpy.data.texts.get(name) or bpy.data.texts.new(name)
            txt.clear()
            txt.write(report)
            self.report({'INFO'},
                        "Report written to console and '%s' text block" % name)
        except Exception as e:
            self.report({'WARNING'}, "Console only (text block failed: %s)" % e)
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

        placement = getattr(sc, "scenecast_keys_placement", 'CORNER')
        if not sc.scenecast_show_keys:
            placement = 'NONE'
        # Bottom-centre text can't come from the render itself, so the frames
        # go to a scratch folder and a second pass composites over them.
        two_pass = (fmt == 'MP4' and placement == 'BOTTOM')
        tmp_dir = ""
        if two_pass:
            tmp_dir = os.path.join(bpy.app.tempdir, "scenecast_frames")
            try:
                if os.path.isdir(tmp_dir):
                    for f in os.listdir(tmp_dir):
                        os.remove(os.path.join(tmp_dir, f))
                else:
                    os.makedirs(tmp_dir, exist_ok=True)
            except Exception as e:
                print("[SceneCast] scratch folder unusable, "
                      "falling back to corner stamp:", e)
                two_pass = False
                placement = 'CORNER'

        if fmt == 'MP4':
            out = _resolve_export_path(sc.scenecast_export_path, ".mp4")
        else:
            out = os.path.join(_resolve_export_dir(sc.scenecast_export_path), "frame_")
        render_to = os.path.join(tmp_dir, "f_") if two_pass else out

        stash = _stash_render(sc, rnd)
        try:
            rnd.fps = sc.scenecast_export_fps
            img = rnd.image_settings
            if fmt == 'MP4' and not two_pass:
                apply_video_settings(rnd, sc.scenecast_export_fps)
            else:
                if hasattr(img, "media_type"):
                    img.media_type = 'IMAGE'
                img.file_format = 'PNG'
            rnd.filepath = render_to
            sc.frame_start = 1
            sc.frame_end = n * hold

            stamp = (placement == 'CORNER')
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
            SESSION.export_active = False

            if two_pass:
                texts = [_stamp_text_for(SESSION.steps[i], i) for i in range(n)]
                size = {'SMALL': 32, 'MEDIUM': 48,
                        'LARGE': 64}.get(sc.scenecast_keys_size, 32)
                composite_text_video(sc, tmp_dir, out, hold,
                                     sc.scenecast_export_fps, texts, size)

            self.report({'INFO'}, "Exported to %s" % out)
            res = {'FINISHED'}
        except Exception as e:
            hint = ("set Keys to 'Top Left (fast)'" if two_pass
                    else "try PNG sequence")
            self.report({'ERROR'}, "Export failed: %s (%s)" % (e, hint))
            print("[SceneCast] export failed:", e)
            res = {'CANCELLED'}
        finally:
            SESSION.export_active = False
            if _export_frame_handler in bpy.app.handlers.frame_change_pre:
                bpy.app.handlers.frame_change_pre.remove(_export_frame_handler)
            _restore_render(sc, rnd, stash)
            _exit_all_edit()
            if tmp_dir and os.path.isdir(tmp_dir):
                try:                      # scratch frames, not the deliverable
                    for f in os.listdir(tmp_dir):
                        os.remove(os.path.join(tmp_dir, f))
                    os.rmdir(tmp_dir)
                except Exception:
                    pass
        return res


# ----------------------------------------------------------------------------
