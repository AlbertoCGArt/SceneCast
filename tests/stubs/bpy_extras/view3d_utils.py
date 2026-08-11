"""Stand-in for bpy_extras.view3d_utils.

Projects with the region_3d's perspective_matrix when the test supplies one,
so callers get a plausible 2D point instead of a constant.
"""


class _V2:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)

    def __getitem__(self, i):
        return (self.x, self.y)[i]

    def __iter__(self):
        return iter((self.x, self.y))


def location_3d_to_region_2d(region, rv3d, coord, default=None):
    m = getattr(rv3d, "perspective_matrix", None)
    if m is None:
        return default
    try:
        v = m @ (coord[0], coord[1], coord[2], 1.0)
        w = v[3]
        if w <= 0.0:
            return default
        return _V2((v[0] / w * 0.5 + 0.5) * region.width,
                   (v[1] / w * 0.5 + 0.5) * region.height)
    except Exception:
        return default
