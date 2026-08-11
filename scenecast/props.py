"""Scene property registration."""

import bpy
from bpy.props import (IntProperty, BoolProperty, EnumProperty,
                       FloatProperty, StringProperty)

from .replay import _playhead_update

_PROP_NAMES = (
    "scenecast_playhead", "scenecast_restore_view", "scenecast_follow_tip",
    "scenecast_step_hold", "scenecast_loop", "scenecast_smooth_view",
    "scenecast_show_edit", "scenecast_capture_context", "scenecast_restore_context",
    "scenecast_capture_view",
    "scenecast_show_keys", "scenecast_keys_mouse", "scenecast_keys_size",
    "scenecast_isolate", "scenecast_collection_name",
    "scenecast_export_format", "scenecast_export_path",
    "scenecast_export_fps", "scenecast_keys_placement",
    "scenecast_export_follow_view", "scenecast_export_edit",
)


def register_props():
    S = bpy.types.Scene
    S.scenecast_playhead = IntProperty(
        name="Step", default=0, min=0, soft_max=100000, update=_playhead_update)
    S.scenecast_restore_view = BoolProperty(
        name="Restore View on Scrub", default=True,
        description="Snap the viewport back to the view recorded at each step")
    S.scenecast_follow_tip = BoolProperty(
        name="Follow Newest", default=True,
        description="Keep the playhead on the newest step while recording")
    S.scenecast_isolate = BoolProperty(
        name="Isolate to Collection", default=True,
        description="On Record, gather all recorded objects into a dedicated "
                    "collection for tidy organization (restored on Clear)")
    S.scenecast_collection_name = StringProperty(
        name="Collection", default="SceneCast Session",
        description="Name of the collection recorded objects are gathered into")
    S.scenecast_step_hold = FloatProperty(
        name="Hold (s)", default=0.8, min=0.02, max=5.0,
        description="Seconds each step lasts during playback")
    S.scenecast_loop = BoolProperty(name="Loop", default=False)
    S.scenecast_smooth_view = BoolProperty(
        name="Smooth Motion", default=True,
        description="Glide geometry and camera between steps instead of snapping, "
                    "so moves and edits slide smoothly (playback and export)")
    S.scenecast_show_edit = BoolProperty(
        name="Show Edit Mode", default=False,
        description="Replay steps recorded in Edit Mode with the edit cage visible "
                    "(enters/exits Edit Mode during playback -- pollutes undo history)")
    S.scenecast_capture_context = BoolProperty(
        name="Capture Selection & Cursor", default=True,
        description="Record selection, 3D cursor, pivot and select-mode changes as "
                    "their own steps even when no geometry moves (key for tutorials)")
    S.scenecast_capture_view = BoolProperty(
        name="Capture Camera Moves", default=True,
        description="Record orbiting, panning and zooming as their own steps. "
                    "Viewport navigation never fires a depsgraph update, so "
                    "without this nothing is recorded until the first mesh edit")
    S.scenecast_restore_context = BoolProperty(
        name="Restore Selection & Cursor", default=True,
        description="On playback/scrub, re-apply each step's selection, 3D cursor and "
                    "pivot -- this changes your live selection while reviewing")
    S.scenecast_show_keys = BoolProperty(
        name="Show Keystrokes", default=True,
        description="Draw pressed keys at the bottom of the viewport (live while "
                    "recording; per-step during playback and export)")
    S.scenecast_keys_mouse = BoolProperty(
        name="+ Mouse", default=False,
        description="Also log mouse-button clicks (noisier)")
    S.scenecast_keys_size = EnumProperty(
        name="Overlay Size", default='SMALL',
        items=[('SMALL', "Small", "Subtle 14px overlay"),
               ('MEDIUM', "Medium", "18px overlay"),
               ('LARGE', "Large", "24px overlay for high-res recording")],
        description="Size of the on-screen keystroke text")
    S.scenecast_export_format = EnumProperty(
        name="Format", default='MP4',
        items=[('MP4', "MP4 Video", "Single H.264 video file"),
               ('PNG', "PNG Sequence", "Numbered PNG frames")])
    S.scenecast_export_path = StringProperty(
        name="Output", subtype='FILE_PATH', default="//scenecast_session.mp4",
        description="MP4: file path.  PNG: folder for the frames")
    S.scenecast_export_fps = IntProperty(name="FPS", default=24, min=1, max=120)
    S.scenecast_keys_placement = EnumProperty(
        name="Keys in Video", default='BOTTOM',
        items=[('BOTTOM', "Bottom Centre",
                "Screencast placement. Renders frames first, then composites "
                "the text over them through the sequencer (slower, two passes)"),
               ('CORNER', "Top Left (fast)",
                "Blender's render stamp burns the text in during the render. "
                "One pass, but the corner position is fixed by Blender"),
               ('NONE', "Off", "Don't put keystrokes in the exported video")],
        description="Where keystrokes appear in exported video")
    S.scenecast_export_follow_view = BoolProperty(
        name="Use Recorded Views", default=False,
        description="Restore each step's viewport angle in the export")
    S.scenecast_export_edit = BoolProperty(
        name="Edit Mode in Export", default=False,
        description="EXPERIMENTAL: show the edit cage in exported video for steps "
                    "recorded in Edit Mode (mode switching during render can be fragile)")


def unregister_props():
    S = bpy.types.Scene
    for prop in _PROP_NAMES:
        if hasattr(S, prop):
            delattr(S, prop)
