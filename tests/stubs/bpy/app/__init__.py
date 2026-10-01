"""Stub of bpy.app."""
from . import handlers


class _Timers:
    def is_registered(self, f): return False
    def register(self, *a, **k): pass
    def unregister(self, *a, **k): pass


timers = _Timers()
tempdir = "/tmp"
binary_path = "/usr/bin/blender"
version = (4, 2, 0)
