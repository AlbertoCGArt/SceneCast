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


def build_zip(out, prefix, pro):
    """Write the add-on into `out`, each entry named `prefix + filename`.

    prefix="" -> extension layout; prefix="scenecast/" -> legacy layout.
    Zip entry names always use forward slashes (the zip spec requires it),
    so never build them with os.path.join.
    """
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in _source_files():
            z.write(os.path.join(PKG, fn), prefix + fn)
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
