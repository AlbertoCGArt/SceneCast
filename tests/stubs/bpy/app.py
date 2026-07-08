class _Timers:
    def is_registered(self, f): return False
    def register(self, *a, **k): pass
    def unregister(self, *a, **k): pass
class _Handlers:
    def __init__(self):
        self.depsgraph_update_post = []
        self.frame_change_pre = []
timers = _Timers()
handlers = _Handlers()
tempdir = "/tmp"
