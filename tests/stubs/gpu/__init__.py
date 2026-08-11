"""Minimal stand-in for Blender's `gpu` module.

Enough surface for overlay code that draws leader lines to import and be
exercised outside Blender. Draw calls are no-ops; the logic under test is
which points get computed, not what reaches the GPU.
"""


class _Shader:
    def __init__(self, name="UNIFORM_COLOR"):
        self.name = name
        self.bound = False
        self.uniforms = {}

    def bind(self):
        self.bound = True

    def uniform_float(self, name, value):
        self.uniforms[name] = value


class shader:
    @staticmethod
    def from_builtin(name):
        # Blender 4.0 renamed '2D_UNIFORM_COLOR' to 'UNIFORM_COLOR'; callers
        # try both, so reject the old spelling the way a modern build does.
        if name == '2D_UNIFORM_COLOR':
            raise ValueError("unknown builtin shader: %s" % name)
        return _Shader(name)


class state:
    blend = 'NONE'
    line_width = 1.0

    @staticmethod
    def blend_set(mode):
        state.blend = mode

    @staticmethod
    def line_width_set(width):
        state.line_width = width
