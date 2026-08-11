class Vector:
    def __init__(self, t=(0,0,0)): self.t = tuple(t)
    def __iter__(self): return iter(self.t)
    def __getitem__(self, i): return self.t[i]
    def __len__(self): return len(self.t)
    @property
    def x(self): return self.t[0]
    @property
    def y(self): return self.t[1]
    @property
    def z(self): return self.t[2]
    @property
    def w(self): return self.t[3]        # 4D: Matrix @ Vector gives clip space
class Quaternion:
    def __init__(self, t=(1,0,0,0)): self.t = tuple(t)
    def __iter__(self): return iter(self.t)
class Euler:
    def __init__(self, t=(0,0,0), order="XYZ"): self.t = tuple(t); self.order = order
    def __iter__(self): return iter(self.t)
class Matrix:
    def __init__(self, rows=()): self.rows = tuple(rows)
    def __iter__(self): return iter(self.rows)
