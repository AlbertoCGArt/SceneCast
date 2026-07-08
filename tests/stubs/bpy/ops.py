class _OpsCat:
    def __getattr__(self, n):
        def _f(*a, **k): pass
        return _f
def __getattr__(n): return _OpsCat()
