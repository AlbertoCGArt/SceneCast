class Vector:
    def __init__(self, t=(0,0,0)): self.t = tuple(t)
    def __iter__(self): return iter(self.t)
class Quaternion:
    def __init__(self, t=(1,0,0,0)): self.t = tuple(t)
    def __iter__(self): return iter(self.t)
class Euler:
    def __init__(self, t=(0,0,0), order="XYZ"): self.t = tuple(t); self.order = order
    def __iter__(self): return iter(self.t)
class Matrix:
    def __init__(self, rows=()): self.rows = tuple(rows)
    def __iter__(self): return iter(self.rows)
