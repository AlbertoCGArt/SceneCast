"""Where SceneCast writes things when the obvious answer does not exist.

Every output setting defaults to a `//` path -- Blender's "next to the .blend"
-- which is the right default for a saved file and no default at all for a new
one. A file that has never been saved has no folder, and bpy.path.abspath then
resolves `//` against whatever folder Blender happened to start in: on Windows
often the root of C: or Blender's own install folder, neither of which can be
written to. The first anyone heard of it was "Permission denied" on a file
they never asked to put there, and an autosave that quietly never happened.

So an unsaved file gets a real place instead -- Documents/SceneCast -- and
callers are told when that is where things went, so they can say so.
"""

import os

import bpy

FALLBACK_DIRNAME = "SceneCast"
_PROBE_NAME = ".scenecast-write-test"


class OutputPathError(Exception):
    """A location SceneCast cannot write to, worded for the status bar."""


def blend_saved():
    return bool(getattr(bpy.data, "filepath", ""))


def fallback_dir():
    """Documents/SceneCast, or ~/SceneCast where there is no Documents folder."""
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    return os.path.join(docs if os.path.isdir(docs) else home, FALLBACK_DIRNAME)


def fallback_label():
    """The fallback folder as a person would say it, for a narrow panel."""
    home = os.path.expanduser("~")
    folder = fallback_dir()
    try:
        rel = os.path.relpath(folder, home)
    except ValueError:                   # different drive on Windows
        return folder
    return folder if rel.startswith("..") else rel


def resolve(raw):
    """(absolute path, used_fallback) for a path setting as the user left it.

    `//` means next to the .blend when there is one, and the fallback folder
    when there is not. A bare relative path is read the same way: left to the
    OS it would also land in Blender's start-up folder, which is meaningless
    to anyone using the panel. An empty field means the same as `//`.
    """
    raw = os.path.expanduser((raw or "").strip())
    saved = blend_saved()
    if os.path.isabs(raw) and not raw.startswith("//"):
        return os.path.normpath(raw), False
    rest = raw[2:] if raw.startswith("//") else raw
    if saved:
        base = os.path.dirname(bpy.data.filepath)
        return os.path.normpath(os.path.join(base, rest)), False
    return os.path.normpath(os.path.join(fallback_dir(), rest)), True


def unsaved_note():
    return ("the .blend isn't saved yet, so // points to %s"
            % fallback_label())


def _cannot_write(folder, exc):
    hint = "choose a folder you own"
    if not blend_saved():
        hint += ", or save the .blend first"
    if isinstance(exc, PermissionError):
        return "Can't write to %s -- %s" % (folder, hint)
    reason = getattr(exc, "strerror", None) or str(exc)
    return "Can't write to %s (%s) -- %s" % (folder, reason, hint)


def ensure_writable_dir(folder):
    """Create `folder` if needed and prove it accepts files.

    Proven by writing a file, not by os.access: on Windows os.access only
    consults the read-only attribute, so it answers yes for the root of C:
    and the write itself is what gets refused.
    """
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, _PROBE_NAME)
        with open(probe, "wb"):
            pass
        os.remove(probe)
    except OSError as e:
        raise OutputPathError(_cannot_write(folder, e))
    return folder


def _looks_like_folder(raw, path):
    raw = raw.strip()
    return not raw or raw.endswith(("/", "\\")) or os.path.isdir(path)


def output_file(raw, default_name, ext):
    """(path, note) for a file SceneCast is about to write.

    The extension is forced, the folder is created and proven writable, and
    `note` is non-empty when the fallback folder was used -- callers append
    it to their report so nobody has to hunt for the output.
    """
    path, fell_back = resolve(raw)
    if _looks_like_folder(raw or "", path):
        path = os.path.join(path, default_name)
    root, current = os.path.splitext(path)
    if current.lower() != ext.lower():
        path = root + ext
    ensure_writable_dir(os.path.dirname(path))
    return path, (unsaved_note() if fell_back else "")


def output_dir(raw):
    """(folder, note) for a folder SceneCast is about to write into.

    A field that names a file -- the shared Export path does, for MP4 --
    means the folder that file would be in.
    """
    path, fell_back = resolve(raw)
    if not _looks_like_folder(raw or "", path) and os.path.splitext(path)[1]:
        path = os.path.dirname(path)
    ensure_writable_dir(path)
    return path, (unsaved_note() if fell_back else "")


def input_file(raw):
    """Absolute path of a file SceneCast is about to read. Nothing is created."""
    return resolve(raw)[0]
