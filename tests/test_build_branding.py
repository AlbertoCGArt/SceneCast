"""A pro build must identify itself.

Both builds come from one source tree, so the pro zip used to install as
plain "SceneCast" at the same version -- a customer could not confirm they
had the build they paid for, and neither could support.
"""
import importlib.util
import os

import pytest

_BUILD_PY = os.path.join(os.path.dirname(__file__), "..", "scripts", "build.py")
_spec = importlib.util.spec_from_file_location("scenecast_build", _BUILD_PY)
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def _read(name):
    with open(os.path.join(os.path.dirname(__file__), "..", "scenecast", name),
              "rb") as f:
        return f.read()


def test_manifest_is_rebranded_for_pro():
    out = build._pro_text("blender_manifest.toml", _read("blender_manifest.toml"))
    text = out.decode("utf-8")
    assert 'name = "SceneCast Pro"' in text
    assert 'name = "SceneCast"' not in text


def test_bl_info_is_rebranded_for_pro():
    text = build._pro_text("__init__.py", _read("__init__.py")).decode("utf-8")
    assert '"name": "SceneCast Pro"' in text


def test_the_extension_id_is_never_rebranded():
    # Blender keys extensions on the id; pro replaces free rather than
    # installing beside it, so both builds must keep the same one.
    text = build._pro_text("blender_manifest.toml",
                           _read("blender_manifest.toml")).decode("utf-8")
    assert 'id = "scenecast"' in text


def test_the_tagline_changes_so_the_listing_differs():
    src = _read("blender_manifest.toml").decode("utf-8")
    out = build._pro_text("blender_manifest.toml",
                          _read("blender_manifest.toml")).decode("utf-8")
    src_tag = [l for l in src.splitlines() if l.startswith("tagline")][0]
    out_tag = [l for l in out.splitlines() if l.startswith("tagline")][0]
    assert src_tag != out_tag


def test_a_stale_edit_fails_the_build_instead_of_shipping_unbranded():
    with pytest.raises(SystemExit):
        build._pro_text("blender_manifest.toml", b'name = "Something Else"\n')


def test_files_with_no_edits_pass_through_untouched():
    raw = b"# nothing to rebrand here\n"
    assert build._pro_text("capture.py", raw) == raw
