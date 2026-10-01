"""Stand-in for Blender's mathutils.

Only what the add-on actually asks of these types, but the arithmetic is
real: several behaviours under test are about *how* a camera interpolates,
and a Quaternion that cannot slerp or dot cannot answer that question.
"""

import math


class Vector:
    def __init__(self, t=(0.0, 0.0, 0.0)):
        self.t = tuple(float(x) for x in t)

    # -- container ----------------------------------------------------------
    def __iter__(self):
        return iter(self.t)

    def __getitem__(self, i):
        return self.t[i]

    def __len__(self):
        return len(self.t)

    def __repr__(self):
        return "Vector(%s)" % (self.t,)

    @property
    def x(self):
        return self.t[0]

    @property
    def y(self):
        return self.t[1]

    @property
    def z(self):
        return self.t[2]

    @property
    def w(self):
        return self.t[3]                 # 4D: Matrix @ Vector gives clip space

    # -- arithmetic ---------------------------------------------------------
    def __add__(self, other):
        return Vector(a + b for a, b in zip(self.t, other))

    def __sub__(self, other):
        return Vector(a - b for a, b in zip(self.t, other))

    def __mul__(self, k):
        return Vector(a * float(k) for a in self.t)

    __rmul__ = __mul__

    def __eq__(self, other):
        try:
            return all(abs(a - b) < 1e-9 for a, b in zip(self.t, other))
        except TypeError:
            return NotImplemented

    def __hash__(self):
        return hash(self.t)

    @property
    def length(self):
        return math.sqrt(sum(a * a for a in self.t))

    def dot(self, other):
        return sum(a * b for a, b in zip(self.t, other))

    def normalized(self):
        n = self.length
        return Vector(self.t) if n < 1e-12 else Vector(a / n for a in self.t)

    def lerp(self, other, f):
        f = float(f)
        return Vector(a + (b - a) * f for a, b in zip(self.t, other))

    def copy(self):
        return Vector(self.t)


class Quaternion:
    def __init__(self, *args):
        if not args:
            self.t = (1.0, 0.0, 0.0, 0.0)
        elif len(args) == 2:
            # Quaternion(axis, angle) -- the rotation-about-an-axis form.
            axis, angle = Vector(args[0]).normalized(), float(args[1])
            s = math.sin(angle * 0.5)
            self.t = (math.cos(angle * 0.5), axis.x * s, axis.y * s, axis.z * s)
        else:
            self.t = tuple(float(x) for x in args[0])

    def __iter__(self):
        return iter(self.t)

    def __getitem__(self, i):
        return self.t[i]

    def __len__(self):
        return 4

    def __repr__(self):
        return "Quaternion(%s)" % (self.t,)

    @property
    def w(self):
        return self.t[0]

    @property
    def x(self):
        return self.t[1]

    @property
    def y(self):
        return self.t[2]

    @property
    def z(self):
        return self.t[3]

    def copy(self):
        return Quaternion(self.t)

    def dot(self, other):
        return sum(a * b for a, b in zip(self.t, other))

    def normalized(self):
        n = math.sqrt(self.dot(self))
        return Quaternion(self.t) if n < 1e-12 else Quaternion(
            tuple(a / n for a in self.t))

    def __matmul__(self, other):
        """Rotate a vector, or compose with another rotation."""
        if isinstance(other, Quaternion):
            w1, x1, y1, z1 = self.t
            w2, x2, y2, z2 = other.t
            return Quaternion((
                w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
                w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2))
        v = Vector(other)
        w, x, y, z = self.t
        # v + 2w(q x v) + 2(q x (q x v)), the standard expansion.
        ux, uy, uz = x, y, z
        cx = uy * v.z - uz * v.y
        cy = uz * v.x - ux * v.z
        cz = ux * v.y - uy * v.x
        c2x = uy * cz - uz * cy
        c2y = uz * cx - ux * cz
        c2z = ux * cy - uy * cx
        return Vector((v.x + 2.0 * (w * cx + c2x),
                       v.y + 2.0 * (w * cy + c2y),
                       v.z + 2.0 * (w * cz + c2z)))

    def slerp(self, other, f):
        f = float(f)
        a = self.normalized()
        b = Quaternion(tuple(other)).normalized()
        dot = a.dot(b)
        if dot < 0.0:                    # take the short way round
            b = Quaternion(tuple(-v for v in b.t))
            dot = -dot
        if dot > 0.9995:                 # nearly parallel: lerp and renormalise
            return Quaternion(tuple(p + (q - p) * f
                                    for p, q in zip(a.t, b.t))).normalized()
        theta = math.acos(max(-1.0, min(1.0, dot)))
        sin_theta = math.sin(theta)
        wa = math.sin((1.0 - f) * theta) / sin_theta
        wb = math.sin(f * theta) / sin_theta
        return Quaternion(tuple(p * wa + q * wb for p, q in zip(a.t, b.t)))

    def to_matrix(self):
        w, x, y, z = self.t
        return Matrix((
            (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))))


class Euler:
    def __init__(self, t=(0.0, 0.0, 0.0), order="XYZ"):
        self.t = tuple(float(x) for x in t)
        self.order = order

    def __iter__(self):
        return iter(self.t)

    def __getitem__(self, i):
        return self.t[i]

    def copy(self):
        return Euler(self.t, self.order)


class Matrix:
    def __init__(self, rows=()):
        self.rows = tuple(tuple(float(v) for v in row) for row in rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, i):
        return self.rows[i]

    def __len__(self):
        return len(self.rows)

    def copy(self):
        return Matrix(self.rows)

    def __matmul__(self, other):
        vec = tuple(other)
        return Vector(sum(row[i] * vec[i] for i in range(len(vec)))
                      for row in self.rows)

    def decompose(self):
        """(location, rotation, scale) -- rotation only for pure rotations."""
        loc = Vector((self.rows[0][3], self.rows[1][3], self.rows[2][3]))
        cols = [[self.rows[r][c] for r in range(3)] for c in range(3)]
        scale = Vector(math.sqrt(sum(v * v for v in col)) for col in cols)
        return loc, Quaternion(), scale

    @staticmethod
    def LocRotScale(loc, rot, scale):
        m = Quaternion(tuple(rot)).to_matrix().rows
        sx, sy, sz = tuple(scale)
        s = (sx, sy, sz)
        rows = [[m[r][c] * s[c] for c in range(3)] + [tuple(loc)[r]]
                for r in range(3)]
        rows.append([0.0, 0.0, 0.0, 1.0])
        return Matrix(rows)

    @staticmethod
    def Identity(size=4):
        return Matrix([[1.0 if r == c else 0.0 for c in range(size)]
                       for r in range(size)])
