#!/usr/bin/env python3
"""Build distributable zips.

Blender 4.2+ extensions and classic add-ons want different zip layouts, so a
normal run emits two files:

  scenecast-<ver>.zip         files at the zip root (manifest beside
                              __init__.py) -- the 4.2+ *extension* layout for
                              "Get Extensions > Install from Disk".
  scenecast-<ver>-legacy.zip  files nested under scenecast/ -- the classic
                              *add-on* layout for "Add-ons > Install".

With --pro, the paid modules from the sibling private checkout
(../scenecast-pro/pro/) are bundled in and the output is named
scenecast-pro-<ver>*.zip. The free build simply doesn't contain them.
"""
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "scenecast")
DIST = os.path.join(ROOT, "dist")
PRO_DIR = os.path.join(os.path.dirname(ROOT), "scenecast-pro", "pro")


def get_version():
    with open(os.path.join(PKG, "blender_manifest.toml")) as f:
        m = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.M)
    return m.group(1) if m else "0.0.0"


def _source_files():
    for fn in sorted(os.listdir(PKG)):
        if fn.endswith((".py", ".toml")):
            yield fn


# Both builds share one source tree, so a pro build was identified in
# Blender's extension list as plain "SceneCast" at the same version -- a
# customer had no way to confirm they had installed what they paid for, and
# neither did support. The id deliberately stays "scenecast": Blender keys
# extensions on it, and pro is meant to replace free rather than sit
# alongside it.
_PRO_EDITS = {
    "blender_manifest.toml": (
        ('name = "SceneCast"', 'name = "SceneCast Pro"'),
        ('tagline = "Record your modeling session and replay it as a tutorial '
         'or timelapse"',
         'tagline = "Record your modeling session with notes, chapters, '
         'annotated export and saved sessions"'),
    ),
    "__init__.py": (
        ('"name": "SceneCast",', '"name": "SceneCast Pro",'),
    ),
}


def _pro_text(fn, raw):
    """Apply the pro branding edits, insisting every one of them lands."""
    text = raw.decode("utf-8")
    for old, new in _PRO_EDITS.get(fn, ()):
        if old not in text:
            raise SystemExit(
                "build --pro: %s no longer contains %r, so the pro build "
                "would ship branded as the free one. Update _PRO_EDITS."
                % (fn, old[:60]))
        text = text.replace(old, new)
    return text.encode("utf-8")


def build_zip(out, prefix, pro):
    """Write the add-on into `out`, each entry named `prefix + filename`.

    prefix="" -> extension layout; prefix="scenecast/" -> legacy layout.
    Zip entry names always use forward slashes (the zip spec requires it),
    so never build them with os.path.join.
    """
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in _source_files():
            src = os.path.join(PKG, fn)
            if pro and fn in _PRO_EDITS:
                with open(src, "rb") as f:
                    z.writestr(prefix + fn, _pro_text(fn, f.read()))
            else:
                z.write(src, prefix + fn)
        if pro:
            for fn in sorted(os.listdir(PRO_DIR)):
                if fn.endswith(".py"):
                    z.write(os.path.join(PRO_DIR, fn), prefix + "pro/" + fn)
    print("built", out)


def main():
    pro = "--pro" in sys.argv
    if pro and not os.path.isdir(PRO_DIR):
        raise SystemExit("--pro requested but %s not found" % PRO_DIR)
    os.makedirs(DIST, exist_ok=True)
    version = get_version()
    name = "scenecast-pro" if pro else "scenecast"
    build_zip(os.path.join(DIST, f"{name}-{version}.zip"), "", pro)
    build_zip(os.path.join(DIST, f"{name}-{version}-legacy.zip"), "scenecast/", pro)


if __name__ == "__main__":
    main()
