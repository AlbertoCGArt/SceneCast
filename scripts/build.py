#!/usr/bin/env python3
"""Build a distributable zip (works as both a Blender 4.2+ extension and a
legacy add-on install)."""
import os
import re
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "scenecast")
DIST = os.path.join(ROOT, "dist")


def get_version():
    with open(os.path.join(PKG, "blender_manifest.toml")) as f:
        m = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.M)
    return m.group(1) if m else "0.0.0"


def main():
    import sys
    pro = "--pro" in sys.argv
    os.makedirs(DIST, exist_ok=True)
    version = get_version()
    suffix = "-pro" if pro else ""
    out = os.path.join(DIST, f"scenecast{suffix}-{version}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(PKG)):
            if fn.endswith((".py", ".toml")):
                # extension layout: files at zip root, manifest beside __init__.py
                z.write(os.path.join(PKG, fn), fn)
        if pro:
            # pro modules live in a sibling private checkout: ../scenecast-pro/pro/
            pro_dir = os.path.join(os.path.dirname(ROOT), "scenecast-pro", "pro")
            if not os.path.isdir(pro_dir):
                raise SystemExit("--pro requested but %s not found" % pro_dir)
            for fn in sorted(os.listdir(pro_dir)):
                if fn.endswith(".py"):
                    z.write(os.path.join(pro_dir, fn), os.path.join("pro", fn))
    print("built", out)


if __name__ == "__main__":
    main()
