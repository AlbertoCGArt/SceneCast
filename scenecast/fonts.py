"""The interface font, for text the export draws itself.

Text strips in the sequencer render in Blender's built-in monospace unless
given a font, while the viewport overlay draws in the interface font -- so
keystrokes burnt into an exported video looked typed on a terminal next to
the same keystrokes in the viewport. Strips are given the interface font
file explicitly instead.
"""

import os

import bpy

# Blender's interface font, by the names it has shipped under, newest first.
_UI_FONT_NAMES = ("Inter.woff2", "Inter.ttf", "DejaVuSans.woff2",
                  "DejaVuSans.ttf", "droidsans.ttf")


def ui_font_path():
    """The interface font's file: the user's own UI font if they set one.

    Empty when neither can be found, which vse_font() answers with Blender's
    built-in sans.
    """
    try:
        custom = bpy.context.preferences.view.font_path_ui
    except Exception:
        custom = ""
    if custom:
        path = bpy.path.abspath(custom)
        if os.path.isfile(path):
            return path
    try:
        folder = bpy.utils.system_resource('DATAFILES', path="fonts")
    except Exception:
        folder = ""
    if folder:
        for name in _UI_FONT_NAMES:
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                return path
    return ""


def vse_font(path):
    """A font datablock for text strips, or None for Blender's default.

    Falls back to Blender's built-in sans rather than the monospace default
    if the file will not load -- a font is decoration, never a reason for an
    export to fail.
    """
    for candidate in ((path,) if path else ()) + ("<builtin>",):
        try:
            return bpy.data.fonts.load(candidate, check_existing=True)
        except Exception as e:
            print("[SceneCast] font %s would not load: %s" % (candidate, e))
    return None
