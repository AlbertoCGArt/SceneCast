"""The N-panel UI.

One parent panel and its sub-panels, top to bottom in the order a session is
made: record, the settings recording uses, playback, export. Pro adds its own
sub-panels under the same parent, ordered among these by bl_order -- notes,
camera and branding between Playback and Export, sessions after it.

Each sub-panel is registered after its parent: a child whose parent is not
registered yet fails to register.
"""

import bpy
from bpy.types import Panel

from .state import SESSION, BUILD
from .viewnav import _any_nonobject_mode
from .overlay import _collapse, keys_for_step, op_label_for_step
from .meshdata import format_bytes
from .modifiers import describe_modifiers
from . import paths


# ----------------------------------------------------------------------------
# Export box extension point
#
# Each hook draws into the Export box just above its button, and may return
# the id of the operator that button should run. That is how a paid build
# routes the one Export button through its own pipeline: a second, separate
# export panel is how branding came to exist and never be found.
# ----------------------------------------------------------------------------
_EXPORT_HOOKS = []


def register_export_hook(fn):
    if fn not in _EXPORT_HOOKS:
        _EXPORT_HOOKS.append(fn)


def unregister_export_hook(fn):
    if fn in _EXPORT_HOOKS:
        _EXPORT_HOOKS.remove(fn)


def export_operator(layout, context):
    """Draw the hooks and return the operator the Export button runs.

    A hook that raises is reported inside the box rather than taking the
    whole panel down with it -- one bad draw used to blank everything below
    it, which is how a single typo hid the branding settings.
    """
    op_id = "scenecast.export"
    for fn in list(_EXPORT_HOOKS):
        try:
            chosen = fn(layout, context)
        except Exception as e:
            layout.label(text="Extension failed: %s" % e, icon='ERROR')
            continue
        if chosen:
            op_id = chosen
    return op_id


# What goes *under* the button -- the state of a job the button started, a
# second deliverable made from the same take. Footers only draw; the hooks
# above decide what the button runs.
_EXPORT_FOOTERS = []


def register_export_footer(fn):
    if fn not in _EXPORT_FOOTERS:
        _EXPORT_FOOTERS.append(fn)


def unregister_export_footer(fn):
    if fn in _EXPORT_FOOTERS:
        _EXPORT_FOOTERS.remove(fn)


def export_footer(layout, context):
    """Draw the footers below the Export button, one failure at a time."""
    for fn in list(_EXPORT_FOOTERS):
        try:
            fn(layout, context)
        except Exception as e:
            layout.label(text="Extension failed: %s" % e, icon='ERROR')


def _edition_line():
    """Which build this is, so a paid install is identifiable in place.

    Imported lazily: HAS_PRO lives on the package that imports this module,
    so it cannot be read at import time.
    """
    try:
        from . import HAS_PRO
        edition = "Pro" if HAS_PRO else "Free"
    except Exception:
        edition = "Free"
    return "SceneCast %s  -  build %s" % (edition, BUILD)


def memory_readout(sc):
    """(text, icon) for the session footprint against its budget.

    Shown always rather than on a warning threshold: the number is the whole
    reason a long session is or is not possible, and finding that out at the
    moment recording stops is finding out too late.
    """
    limit_mb = getattr(sc, "scenecast_memory_limit", 0)
    used = SESSION.bytes_est
    if limit_mb > 0:
        frac = used / float(limit_mb * (1 << 20))
        return ("%s of %d MB" % (format_bytes(used), limit_mb),
                'ERROR' if frac >= 0.75 else 'NONE')
    return format_bytes(used), 'NONE'


def _enum_name(sc, prop):
    try:
        return sc.bl_rna.properties[prop].enum_items[getattr(sc, prop)].name
    except Exception:
        return str(getattr(sc, prop, ""))


def elapsed_text(seconds):
    """m:ss, the way a video player shows a position."""
    seconds = max(0, int(seconds))
    return "%d:%02d" % (seconds // 60, seconds % 60)


def step_summary(idx, n, step, t0, op=None):
    """'Step 3 / 40  ·  Bevel  ·  0:12' for the step under the playhead.

    `op` is the caption the viewport shows for the step -- the operator that
    made its change, not the one wm.operators had finished when it was
    captured -- so the panel and the overlay name the same tool.
    """
    if op is None:
        op = step.get("op", "")
    if not op or op == "(edit)":
        op = "—"
    return "Step %d / %d  ·  %s  ·  %s" % (
        idx + 1, n, op, elapsed_text(step.get("t", t0) - t0))


def resolution_name(sc):
    if getattr(sc, "scenecast_export_res", 'SCENE') == 'CUSTOM':
        return "%dx%d" % (sc.scenecast_export_res_x, sc.scenecast_export_res_y)
    return _enum_name(sc, "scenecast_export_res")


def export_summary(sc):
    """'0.80s / step  ·  Recorded Views  ·  1080p  (1920x1080)'.

    Hold and View are set in Playback, and the export follows them; one line
    here says so instead of two labels pointing back up the panel.
    """
    return "%.2fs / step  ·  %s  ·  %s" % (
        sc.scenecast_step_hold, _enum_name(sc, "scenecast_view_mode"),
        resolution_name(sc))


def _has_steps(context):
    return len(SESSION.steps) > 0


class _SubPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SceneCast"
    bl_parent_id = "SCENECAST_PT_panel"


# ----------------------------------------------------------------------------
class SCENECAST_PT_panel(Panel):
    """Record: the one thing to do first, and how the take is going."""
    bl_label = "SceneCast"
    bl_idname = "SCENECAST_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SceneCast"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        sc = context.scene
        n = len(SESSION.steps)

        row = layout.row()
        row.scale_y = 1.4
        row.operator(
            "scenecast.toggle",
            text="Stop Recording" if SESSION.recording else "Start Recording",
            icon='SNAP_FACE' if SESSION.recording else 'REC',
            depress=SESSION.recording,
        )
        mem, icon = memory_readout(sc)
        layout.label(text="%d steps  ·  %d keys  ·  %s"
                          % (n, SESSION.keys_captured_total, mem), icon=icon)
        if SESSION.memory_stopped:
            box = layout.box()
            box.alert = True
            box.label(text="Recording stopped: memory limit reached.", icon='ERROR')
            box.label(text="%d steps kept. Raise the limit to record longer." % n)
        if SESSION.recording:
            layout.label(text="Live -- edit your meshes...", icon='RADIOBUT_ON')
        elif n == 0:
            layout.label(text="Press Start Recording, then model.")


class SCENECAST_PT_capture(_SubPanel, Panel):
    bl_label = "Capture Settings"
    bl_idname = "SCENECAST_PT_capture"
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        sc = context.scene
        # What a take records is decided before it starts; changing it halfway
        # would leave the session half one way and half the other.
        layout.enabled = not SESSION.recording

        icol = layout.column(align=True)
        icol.prop(sc, "scenecast_isolate")
        sub = icol.row()
        sub.enabled = sc.scenecast_isolate
        sub.prop(sc, "scenecast_collection_name", text="", icon='OUTLINER_COLLECTION')

        layout.prop(sc, "scenecast_capture_context")
        layout.prop(sc, "scenecast_capture_view")
        layout.prop(sc, "scenecast_capture_modifiers")
        krow = layout.row(align=True)
        krow.prop(sc, "scenecast_show_keys")
        krow.prop(sc, "scenecast_keys_mouse")
        krow.prop(sc, "scenecast_keys_size", text="")
        layout.prop(sc, "scenecast_memory_limit", text="Memory Limit (MB)")
        layout.prop(sc, "scenecast_follow_tip")

        layout.separator()
        row = layout.row(align=True)
        row.label(text=_edition_line())
        row.operator("scenecast.diagnose", text="", icon='CONSOLE')


class SCENECAST_PT_playback(_SubPanel, Panel):
    bl_label = "Playback"
    bl_idname = "SCENECAST_PT_playback"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        return _has_steps(context)

    def draw(self, context):
        layout = self.layout
        sc = context.scene
        n = len(SESSION.steps)

        layout.prop(sc, "scenecast_playhead", text="Scrub", slider=True)
        rr = layout.row(align=True)
        rr.operator("scenecast.step", text="", icon='REW').mode = 'FIRST'
        rr.operator("scenecast.step", text="", icon='TRIA_LEFT').mode = 'PREV'
        rr.operator("scenecast.play", text="", icon='PAUSE' if SESSION.playing else 'PLAY')
        rr.operator("scenecast.step", text="", icon='TRIA_RIGHT').mode = 'NEXT'
        rr.operator("scenecast.step", text="", icon='FF').mode = 'LAST'

        pr = layout.row(align=True)
        pr.prop(sc, "scenecast_step_hold")
        pr.prop(sc, "scenecast_loop", text="", icon='FILE_REFRESH')
        layout.prop(sc, "scenecast_view_mode", text="View")
        smooth = layout.row()
        # Smoothing only has anything to move between in Recorded Views.
        smooth.enabled = sc.scenecast_view_mode == 'RECORDED'
        smooth.prop(sc, "scenecast_smooth_view")
        layout.prop(sc, "scenecast_show_edit")
        layout.prop(sc, "scenecast_restore_context")
        layout.prop(sc, "scenecast_replay_modifiers")

        idx = max(0, min(sc.scenecast_playhead, n - 1))
        layout.label(text=step_summary(idx, n, SESSION.steps[idx],
                                       SESSION.steps[0].get("t", 0.0),
                                       op_label_for_step(idx)))

        if _any_nonobject_mode() and not sc.scenecast_show_edit and not SESSION.recording:
            layout.label(text="Object Mode needed to scrub (or enable Show Edit Mode).",
                         icon='ERROR')

        layout.separator()
        layout.operator("scenecast.clear", icon='TRASH')


class SCENECAST_PT_step_info(_SubPanel, Panel):
    bl_label = "Step Details"
    bl_idname = "SCENECAST_PT_step_info"
    bl_parent_id = "SCENECAST_PT_playback"
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _has_steps(context)

    def draw(self, context):
        layout = self.layout
        sc = context.scene
        n = len(SESSION.steps)
        idx = max(0, min(sc.scenecast_playhead, n - 1))
        step = SESSION.steps[idx]
        t0 = SESSION.steps[0]["t"]

        mode_lbl = "Edit" if step.get("mode") == 'EDIT' else "Object"
        layout.label(text="Mode: %s   View: %s" % (mode_lbl, step["view"]),
                     icon='EDITMODE_HLT' if mode_lbl == "Edit" else 'OBJECT_DATAMODE')
        total_v = sum(d["vcount"] for d in step["objs"].values())
        total_f = sum(d["fcount"] for d in step["objs"].values())
        layout.label(text="Objects: %d   Verts: %d   Faces: %d"
                          % (len(step["objs"]), total_v, total_f))
        act = step.get("active", "")
        seldata = step["objs"].get(act)
        if seldata is not None:
            sv = int(seldata["vsel"].sum()) if seldata.get("vsel") is not None else 0
            sf = int(seldata["fsel"].sum()) if seldata.get("fsel") is not None else 0
            layout.label(text="Active: %s  (%dv %df sel)" % (act, sv, sf),
                         icon='RESTRICT_SELECT_OFF')
        elif act:
            layout.label(text="Active: %s" % act, icon='RESTRICT_SELECT_OFF')
        mods = describe_modifiers(seldata.get("mods")) if seldata else ""
        if mods:
            layout.label(text="Modifiers: %s" % mods, icon='MODIFIER')
        keys = keys_for_step(idx)
        if keys:
            layout.label(text="Keys: " + "  ".join(_collapse(keys)[-6:]),
                         icon='EVENT_A')
        layout.label(text="t + %.1fs" % (step["t"] - t0))


class SCENECAST_PT_export(_SubPanel, Panel):
    bl_label = "Export"
    bl_idname = "SCENECAST_PT_export"
    bl_order = 6

    @classmethod
    def poll(cls, context):
        return _has_steps(context)

    def draw(self, context):
        layout = self.layout
        sc = context.scene
        layout.prop(sc, "scenecast_export_format", text="")
        layout.prop(sc, "scenecast_export_path", text="")
        if paths.resolve(sc.scenecast_export_path)[1]:
            # Blender paints a // path red on an unsaved file and stops there;
            # this says what will actually happen instead.
            layout.label(text="Unsaved file: exports go to %s"
                              % paths.fallback_label(), icon='INFO')
        layout.prop(sc, "scenecast_export_res", text="")
        if sc.scenecast_export_res == 'CUSTOM':
            crow = layout.row(align=True)
            crow.prop(sc, "scenecast_export_res_x", text="W")
            crow.prop(sc, "scenecast_export_res_y", text="H")
        layout.prop(sc, "scenecast_export_fps")
        krow = layout.row()
        krow.enabled = sc.scenecast_show_keys
        krow.prop(sc, "scenecast_keys_placement", text="Keys")
        sub = layout.row()
        sub.enabled = sc.scenecast_show_edit
        sub.prop(sc, "scenecast_export_edit")
        layout.label(text=export_summary(sc), icon='INFO')
        layout.operator(export_operator(layout, context), text="Export Session",
                        icon='RENDER_ANIMATION')
        export_footer(layout, context)


# Parents before children: Blender refuses a sub-panel whose parent is not
# registered yet.
PANELS = (
    SCENECAST_PT_panel,
    SCENECAST_PT_capture,
    SCENECAST_PT_playback,
    SCENECAST_PT_step_info,
    SCENECAST_PT_export,
)
