"""The N-panel UI."""

import bpy
from bpy.types import Panel

from .state import SESSION
from .viewnav import _any_nonobject_mode
from .overlay import _collapse

# ----------------------------------------------------------------------------
class SCENECAST_PT_panel(Panel):
    bl_label = "SceneCast"
    bl_idname = "SCENECAST_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SceneCast"

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
        layout.label(text="Captured steps: %d" % n)
        if SESSION.recording:
            layout.label(text="Live -- edit your meshes...", icon='RADIOBUT_ON')

        icol = layout.column(align=True)
        icol.prop(sc, "scenecast_isolate")
        sub = icol.row()
        sub.enabled = sc.scenecast_isolate
        sub.prop(sc, "scenecast_collection_name", text="", icon='OUTLINER_COLLECTION')

        layout.prop(sc, "scenecast_capture_context")
        krow = layout.row(align=True)
        krow.prop(sc, "scenecast_show_keys")
        krow.prop(sc, "scenecast_keys_mouse")
        krow.prop(sc, "scenecast_keys_size", text="")

        if n == 0:
            layout.separator()
            layout.label(text="Nothing recorded yet.")
            return

        layout.separator()
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
        layout.prop(sc, "scenecast_smooth_view")
        layout.prop(sc, "scenecast_show_edit")
        layout.prop(sc, "scenecast_restore_context")

        idx = max(0, min(sc.scenecast_playhead, n - 1))
        step = SESSION.steps[idx]
        t0 = SESSION.steps[0]["t"]

        box = layout.box()
        box.label(text="Step %d / %d" % (idx + 1, n))
        box.label(text="Op:  %s" % step["op"])
        mode_lbl = "Edit" if step.get("mode") == 'EDIT' else "Object"
        box.label(text="Mode: %s   View: %s" % (mode_lbl, step["view"]),
                  icon='EDITMODE_HLT' if mode_lbl == "Edit" else 'OBJECT_DATAMODE')
        total_v = sum(d["vcount"] for d in step["objs"].values())
        total_f = sum(d["fcount"] for d in step["objs"].values())
        box.label(text="Objects: %d   Verts: %d   Faces: %d"
                       % (len(step["objs"]), total_v, total_f))
        act = step.get("active", "")
        seldata = step["objs"].get(act)
        if seldata is not None:
            sv = int(seldata["vsel"].sum()) if seldata.get("vsel") is not None else 0
            sf = int(seldata["fsel"].sum()) if seldata.get("fsel") is not None else 0
            box.label(text="Active: %s  (%dv %df sel)" % (act, sv, sf),
                      icon='RESTRICT_SELECT_OFF')
        elif act:
            box.label(text="Active: %s" % act, icon='RESTRICT_SELECT_OFF')
        keys = step.get("keys", [])
        if keys:
            box.label(text="Keys: " + "  ".join(_collapse(keys)[-6:]), icon='EVENT_A')
        box.label(text="t + %.1fs" % (step["t"] - t0))

        if _any_nonobject_mode() and not sc.scenecast_show_edit and not SESSION.recording:
            layout.label(text="Object Mode needed to scrub (or enable Show Edit Mode).",
                         icon='ERROR')

        layout.separator()
        layout.prop(sc, "scenecast_restore_view")
        layout.prop(sc, "scenecast_follow_tip")

        ebox = layout.box()
        ebox.label(text="Export", icon='RENDER_ANIMATION')
        ebox.prop(sc, "scenecast_export_format", text="")
        ebox.prop(sc, "scenecast_export_path", text="")
        er = ebox.row(align=True)
        er.prop(sc, "scenecast_export_fps")
        er.prop(sc, "scenecast_export_hold")
        ebox.prop(sc, "scenecast_export_follow_view")
        sub = ebox.row()
        sub.enabled = sc.scenecast_show_edit
        sub.prop(sc, "scenecast_export_edit")
        ebox.operator("scenecast.export", icon='RENDER_ANIMATION')

        layout.separator()
        layout.operator("scenecast.clear", icon='TRASH')

