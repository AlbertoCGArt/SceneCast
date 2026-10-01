"""Stub of bpy.app.handlers.

A module in Blender, so a module here too: add-ons write
`from bpy.app.handlers import persistent`, which an attribute would not
satisfy.
"""


def persistent(fn):
    """Blender's marker for handlers that survive a file load."""
    fn._bpy_persistent = True
    return fn


depsgraph_update_post = []
frame_change_pre = []
save_post = []
load_post = []
