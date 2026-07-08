"""Whole-package import + registration smoke test against bpy stubs."""
import scenecast as pkg

def test_registration_surface():
    assert hasattr(pkg, "register") and hasattr(pkg, "unregister")
    assert len(pkg._classes) == 7

def test_register_unregister_smoke():
    pkg.register()
    pkg.unregister()
