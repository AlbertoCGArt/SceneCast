bl_info = {
    "name": "SceneCast",
    "author": "Alberto (AlbertoCGArt)",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > SceneCast",
    "description": "Record your modeling session -- mesh edits, selection, camera "
                   "and keystrokes -- then replay or export it as a tutorial or "
                   "progress timelapse.",
    "doc_url": "https://github.com/AlbertoCGArt/scenecast",
    "category": "3D View",
}

import bpy

from .state import SESSION
from .capture import _on_depsgraph, _settle_tick, _watchdog_tick
from .replay import _play_tick
from .exporter import _export_frame_handler
from .overlay import SCENECAST_OT_keylogger, _add_draw_handler, _remove_draw_handler
from .ops import (SCENECAST_OT_toggle, SCENECAST_OT_clear, SCENECAST_OT_step,
                  SCENECAST_OT_play, SCENECAST_OT_export, _keylogger_watchdog)
from .ui import SCENECAST_PT_panel
from .props import register_props, unregister_props

_classes = (
    SCENECAST_OT_toggle,
    SCENECAST_OT_clear,
    SCENECAST_OT_step,
    SCENECAST_OT_play,
    SCENECAST_OT_export,
    SCENECAST_OT_keylogger,
    SCENECAST_PT_panel,
)


def _ensure_handler():
    handlers = bpy.app.handlers.depsgraph_update_post
    for h in list(handlers):
        if getattr(h, "__name__", "") == "_on_depsgraph":
            handlers.remove(h)
    handlers.append(_on_depsgraph)


def _remove_handler():
    for hlist in (bpy.app.handlers.depsgraph_update_post,
                  bpy.app.handlers.frame_change_pre):
        for h in list(hlist):
            if getattr(h, "__name__", "") in ("_on_depsgraph", "_export_frame_handler"):
                hlist.remove(h)


# Pro extension point: if a `pro` subpackage is bundled (paid build), it is
# loaded here. The free build simply doesn't contain it. Pro modules receive
# the same public surface as any add-on code: state.SESSION, capture, replay.
try:
    from . import pro as _pro
except ImportError:
    _pro = None

HAS_PRO = _pro is not None


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    register_props()
    SESSION.reset()
    _ensure_handler()
    _add_draw_handler()
    if _pro is not None:
        _pro.register()


def unregister():
    SESSION.recording = False          # let the modal key logger self-terminate
    _remove_handler()
    _remove_draw_handler()
    for tmr in (_settle_tick, _play_tick, _watchdog_tick, _keylogger_watchdog):
        if bpy.app.timers.is_registered(tmr):
            try:
                bpy.app.timers.unregister(tmr)
            except Exception:
                pass
    unregister_props()
    if _pro is not None:
        try:
            _pro.unregister()
        except Exception:
            pass
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    SESSION.reset()


if __name__ == "__main__":
    register()
