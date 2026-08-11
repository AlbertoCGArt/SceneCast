"""Stand-in for gpu_extras.batch."""


class _Batch:
    def __init__(self, shader, kind, content):
        self.kind = kind
        self.content = content
        self.drawn = 0

    def draw(self, shader=None):
        self.drawn += 1


def batch_for_shader(shader, kind, content):
    return _Batch(shader, kind, content)
