"""Keystroke capture (modal operator) and on-screen overlay drawing."""

import time
import bpy
import blf
from bpy.types import Operator

from .state import SESSION, KEY_FADE, KEY_MAX_SHOWN, KEY_LOOKBACK
from .viewnav import _tag_redraw

_REPEAT_WINDOW = 1.2       # seconds within which a repeated key collapses to xN


def _push_key(txt):
    """Append to the live buffer, collapsing rapid repeats into a counter."""
    now = time.monotonic()
    buf = SESSION.key_buffer
    if buf:
        last_txt, last_ts, last_n = buf[-1]
        if last_txt == txt and (now - last_ts) <= _REPEAT_WINDOW:
            buf[-1] = (txt, now, last_n + 1)
            return
    buf.append((txt, now, 1))
    if len(buf) > 64:
        del buf[:-64]


def keys_for_step(idx):
    """Keys belonging to step `idx`, newest attribution method first.

    A step's own list is used when it has one, but that list is filled from a
    pending buffer that whichever step lands next drains -- and camera steps
    fire on a 0.7s clock, so they routinely drain keys that belong to the edit
    the artist was actually making. The timestamped session log doesn't race:
    a step claims the keys pressed between the previous step and itself.
    """
    steps = SESSION.steps
    if not (0 <= idx < len(steps)):
        return []
    step = steps[idx]

    # An operator that ran on this step is the most reliable signal there is.
    # Its shortcut is deterministic, while logged keys get mis-credited: the
    # camera watchdog fires on a clock, so a step captured mid-extrude lands
    # between the E press and the geometry it produced, and claims the E.
    op_id = step.get("op_id", "")
    if op_id:
        prev_op = steps[idx - 1].get("op_id", "") if idx > 0 else ""
        if step.get("geo_new") or op_id != prev_op:
            combo = shortcut_for_operator(op_id)
            if combo:
                return [combo]

    own = step.get("keys")
    if own:
        return own
    log = SESSION.key_log
    if not log:
        return []
    t_end = step.get("t")
    if t_end is None:
        return []
    t_start = steps[idx - 1].get("t", t_end) if idx > 0 else t_end - KEY_LOOKBACK
    return [txt for txt, ts in log if t_start < ts <= t_end]


def _collapse(keys):
    """['G','X','X','X','5'] -> ['G', 'X x3', '5'] for compact display."""
    out = []
    for k in keys:
        if out and out[-1][0] == k:
            out[-1][1] += 1
        else:
            out.append([k, 1])
    return [k if n == 1 else "%s \u00d7%d" % (k, n) for k, n in out]

# ----------------------------------------------------------------------------
# Keystroke capture + on-screen overlay (screencast-style, for tutorials)
# ----------------------------------------------------------------------------
_MOD_TYPES = {'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_SHIFT', 'RIGHT_SHIFT',
              'LEFT_ALT', 'RIGHT_ALT', 'OSKEY', 'APP'}
_SKIP_TYPES = {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE', 'TRACKPADPAN', 'TRACKPADZOOM',
               'MOUSEROTATE', 'MOUSESMARTZOOM', 'TIMER', 'TIMER_REPORT', 'TIMER0',
               'TIMER1', 'TIMER2', 'TIMER_JOBS', 'TIMER_AUTOSAVE', 'NONE',
               'WINDOW_DEACTIVATE'} | _MOD_TYPES
_MOUSE_TYPES = {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'WHEELUPMOUSE',
                'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE', 'BUTTON4MOUSE',
                'BUTTON5MOUSE', 'BUTTON6MOUSE', 'BUTTON7MOUSE'}
_KEY_LABELS = {
    'LEFTMOUSE': 'LMB', 'RIGHTMOUSE': 'RMB', 'MIDDLEMOUSE': 'MMB',
    'WHEELUPMOUSE': 'Wheel Up', 'WHEELDOWNMOUSE': 'Wheel Dn',
    'RET': 'Enter', 'ESC': 'Esc', 'TAB': 'Tab', 'SPACE': 'Space', 'DEL': 'Del',
    'BACK_SPACE': 'Backspace', 'LEFT_ARROW': 'Left', 'RIGHT_ARROW': 'Right',
    'UP_ARROW': 'Up', 'DOWN_ARROW': 'Down', 'PERIOD': '.', 'COMMA': ',',
    'MINUS': '-', 'EQUAL': '=', 'SLASH': '/', 'SEMI_COLON': ';',
    'ZERO': '0', 'ONE': '1', 'TWO': '2', 'THREE': '3', 'FOUR': '4', 'FIVE': '5',
    'SIX': '6', 'SEVEN': '7', 'EIGHT': '8', 'NINE': '9',
    'NUMPAD_0': 'Num 0', 'NUMPAD_1': 'Num 1', 'NUMPAD_2': 'Num 2',
    'NUMPAD_3': 'Num 3', 'NUMPAD_4': 'Num 4', 'NUMPAD_5': 'Num 5',
    'NUMPAD_6': 'Num 6', 'NUMPAD_7': 'Num 7', 'NUMPAD_8': 'Num 8',
    'NUMPAD_9': 'Num 9', 'NUMPAD_PLUS': 'Num +', 'NUMPAD_MINUS': 'Num -',
    'NUMPAD_PERIOD': 'Num .', 'NUMPAD_SLASH': 'Num /', 'NUMPAD_ASTERIX': 'Num *',
    'NUMPAD_ENTER': 'Num Enter',
}


_SHORTCUT_CACHE = {}

# Operators reached through a menu have no shortcut bound to them: Shift+A
# opens the Add menu and X opens the delete menu -- neither is bound to
# mesh.primitive_cube_add or mesh.delete, so the keymap lookup correctly finds
# nothing. These are the menu entry points, which is what a viewer needs to
# see. Prefix matches, longest first.
_ADD_PREFIXES = (
    "mesh.primitive_", "curve.primitive_", "surface.primitive_",
    "object.add", "object.empty_add", "object.light_add", "object.camera_add",
    "object.text_add", "object.metaball_add", "object.armature_add",
    "object.speaker_add", "object.collection_instance_add",
    "object.gpencil_add", "object.grease_pencil_add",
)
_MENU_SHORTCUTS = (
    ("mesh.dissolve", "Ctrl+X"),
    ("object.delete", "X"),
    ("mesh.delete", "X"),
    ("object.duplicate", "Shift+D"),
    ("mesh.duplicate", "Shift+D"),
    ("object.join", "Ctrl+J"),
    ("object.parent_set", "Ctrl+P"),
    ("mesh.separate", "P"),
    ("mesh.merge", "M"),
    ("mesh.knife", "K"),
)


def _menu_shortcut(idname):
    """Entry-point shortcut for operators that are only reachable via a menu."""
    if any(idname.startswith(p) for p in _ADD_PREFIXES):
        return "Shift+A"
    for prefix, combo in _MENU_SHORTCUTS:
        if idname.startswith(prefix):
            return combo
    return ""


def _kmi_label(kmi):
    mods = []
    if kmi.ctrl:
        mods.append("Ctrl")
    if kmi.shift:
        mods.append("Shift")
    if kmi.alt:
        mods.append("Alt")
    if kmi.oskey:
        mods.append("Cmd")
    t = kmi.type
    if t in _KEY_LABELS:
        label = _KEY_LABELS[t]
    elif len(t) == 1:
        label = t
    else:
        label = t.replace("_", " ").title()
    return "+".join(mods + [label]) if mods else label


def shortcut_for_operator(idname):
    """Keyboard shortcut bound to an operator id ('mesh.extrude_region' -> 'E').

    Blender consumes keys pressed *inside* a running modal operator, so the
    logger physically cannot see the Z and 5 of a G Z 5 move. Reading the
    shortcut back out of the user keymap gives a correct label for what
    triggered the step regardless. Cached: the keymap walk is not cheap.
    """
    if not idname:
        return ""
    if idname in _SHORTCUT_CACHE:
        return _SHORTCUT_CACHE[idname]
    out = ""
    # bpy.context is None in restricted contexts (load handlers, background
    # runs), so reach for the keyconfigs defensively rather than assuming.
    kcs = getattr(getattr(bpy.context, "window_manager", None),
                  "keyconfigs", None)

    def _usable(kmi):
        return (kmi is not None and getattr(kmi, "active", True)
                and kmi.type not in _SKIP_TYPES and kmi.type not in _MOUSE_TYPES)

    try:                                   # official lookup, honours user remaps
        km, kmi = kcs.find_item_from_operator(idname=idname)
        if _usable(kmi):
            out = _kmi_label(kmi)
    except Exception:
        pass
    if not out:                            # manual sweep as a backstop
        try:
            for km in kcs.user.keymaps:
                for kmi in km.keymap_items:
                    if kmi.idname == idname and _usable(kmi):
                        out = _kmi_label(kmi)
                        break
                if out:
                    break
        except Exception:
            out = ""
    if not out:                            # menu-driven: nothing to look up
        out = _menu_shortcut(idname)
    if out:
        _SHORTCUT_CACHE[idname] = out      # only cache hits: keymaps load late
    return out


def _format_key(event, include_mouse):
    t = event.type
    if t in _SKIP_TYPES:
        return ""
    if t in _MOUSE_TYPES and not include_mouse:
        return ""
    mods = []
    if event.ctrl:
        mods.append("Ctrl")
    if event.shift:
        mods.append("Shift")
    if event.alt:
        mods.append("Alt")
    if event.oskey:
        mods.append("Cmd")
    if t in _KEY_LABELS:
        label = _KEY_LABELS[t]
    elif len(t) == 1:
        label = t
    elif t.startswith('F') and t[1:].isdigit():
        label = t                       # F1..F12
    else:
        label = t.replace("_", " ").title()
    return "+".join(mods + [label]) if mods else label


class SCENECAST_OT_keylogger(Operator):
    bl_idname = "scenecast.keylogger"
    bl_label = "Session Key Logger"
    bl_description = "Internal: captures keystrokes while recording"

    def modal(self, context, event):
        # A newer logger was re-armed (e.g. after a menu dropped us) -> retire
        # quietly without clearing the running flag the new one now owns.
        if self._seq != SESSION.keylogger_seq:
            self._remove_timer(context)
            return {'FINISHED'}
        if not SESSION.recording:
            SESSION.keylogger_running = False
            self._remove_timer(context)
            return {'FINISHED'}
        SESSION.keylogger_heartbeat = time.monotonic()   # proof-of-life for watchdog
        try:
            if event.value == 'PRESS':
                try:
                    inc = context.scene.scenecast_keys_mouse
                except Exception:
                    inc = False
                txt = _format_key(event, inc)
                if txt:
                    _push_key(txt)
                    SESSION.pending_keys.append(txt)
                    SESSION.key_log.append((txt, time.monotonic()))
                    SESSION.keys_captured_total += 1
                    if len(SESSION.pending_keys) > 64:
                        del SESSION.pending_keys[:-64]
                    _tag_redraw()
        except Exception as e:
            print("[SceneCast] keylogger error:", e)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if context.window is None:
            # Without a window the handler cannot attach and the operator would
            # sit there capturing nothing. Fail loudly so the watchdog retries.
            print("[SceneCast] keylogger: no window in context, not started")
            return {'CANCELLED'}
        self._timer = None
        try:
            # A timer keeps the modal ticking so the watchdog can tell it is
            # alive even when the artist isn't pressing keys.
            self._timer = context.window_manager.event_timer_add(
                0.25, window=context.window)
        except Exception:
            self._timer = None
        if not context.window_manager.modal_handler_add(self):
            print("[SceneCast] keylogger: modal_handler_add refused")
            self._remove_timer(context)
            return {'CANCELLED'}
        SESSION.keylogger_seq += 1
        self._seq = SESSION.keylogger_seq
        SESSION.keylogger_running = True
        SESSION.keylogger_heartbeat = time.monotonic()
        return {'RUNNING_MODAL'}

    def _remove_timer(self, context):
        if getattr(self, "_timer", None) is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None


_draw_handle = None


def _blf_size(fid, size):
    try:
        blf.size(fid, size)             # Blender 4.0+ (dpi dropped)
    except TypeError:
        blf.size(fid, size, 72)         # older Blender


def _overlay_chunks():
    """Return (list_of(text, alpha), op_label) for whatever should be shown now."""
    now = time.monotonic()
    chunks = []
    op_label = ""
    if SESSION.recording:
        for txt, ts, n in SESSION.key_buffer[-KEY_MAX_SHOWN:]:
            age = now - ts
            if age <= KEY_FADE:
                label = txt if n == 1 else "%s \u00d7%d" % (txt, n)
                chunks.append((label, max(0.05, 1.0 - age / KEY_FADE)))
    else:
        idx = None
        if SESSION.export_active:
            idx = SESSION.export_step_idx
        else:
            try:
                idx = int(bpy.context.scene.scenecast_playhead)
            except Exception:
                idx = None
        if idx is not None and 0 <= idx < len(SESSION.steps):
            step = SESSION.steps[idx]
            for txt in _collapse(keys_for_step(idx))[-KEY_MAX_SHOWN:]:
                chunks.append((txt, 1.0))
            op_label = step.get("op", "")
    return chunks, op_label


def _draw_keys_overlay():
    try:
        sc = bpy.context.scene
        if not getattr(sc, "scenecast_show_keys", False):
            return
        region = bpy.context.region
        if region is None:
            return
        chunks, op_label = _overlay_chunks()
        if not chunks and not op_label:
            return

        fid = 0
        sep = "    "
        try:
            size = {'SMALL': 14, 'MEDIUM': 18, 'LARGE': 24}[
                bpy.context.scene.scenecast_keys_size]
        except Exception:
            size = 14
        _blf_size(fid, size)
        blf.enable(fid, blf.SHADOW)
        blf.shadow(fid, 5, 0.0, 0.0, 0.0, 0.9)
        blf.shadow_offset(fid, 1, -1)

        widths = [blf.dimensions(fid, t + sep)[0] for t, _ in chunks]
        total = sum(widths)
        x = max(20.0, (region.width - total) / 2.0)
        y = 48.0
        for (t, alpha), w in zip(chunks, widths):
            blf.position(fid, x, y, 0)
            blf.color(fid, 0.92, 0.92, 0.92, alpha * 0.9)
            blf.draw(fid, t)
            x += w

        if op_label:
            _blf_size(fid, max(11, size - 4))
            w = blf.dimensions(fid, op_label)[0]
            blf.position(fid, max(20.0, (region.width - w) / 2.0), y - 22.0, 0)
            blf.color(fid, 0.65, 0.82, 1.0, 0.85)
            blf.draw(fid, op_label)

        blf.disable(fid, blf.SHADOW)
    except Exception as e:
        print("[SceneCast] overlay draw error:", e)


def _add_draw_handler():
    global _draw_handle
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_keys_overlay, (), 'WINDOW', 'POST_PIXEL')


def _remove_draw_handler():
    global _draw_handle
    if _draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        except Exception:
            pass
        _draw_handle = None


# ----------------------------------------------------------------------------
