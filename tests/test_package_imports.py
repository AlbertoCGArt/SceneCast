"""Whole-package import + registration smoke test against bpy stubs."""
import scenecast as pkg

def test_registration_surface():
    assert hasattr(pkg, "register") and hasattr(pkg, "unregister")
    # every registered class must be unique and carry a bl_idname/bl_label,
    # which catches a half-added operator without pinning the count
    assert len(set(pkg._classes)) == len(pkg._classes)
    for cls in pkg._classes:
        assert getattr(cls, "bl_label", None), cls
        assert cls.__name__.startswith("SCENECAST_"), cls

def test_register_unregister_smoke():
    pkg.register()
    pkg.unregister()
