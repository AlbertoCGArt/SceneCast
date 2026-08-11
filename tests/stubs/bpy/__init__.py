from . import types, props, app, utils, path, ops


class _KeyMapItem:
    """Enough of a keymap item for the shortcut lookup to format a label."""
    def __init__(self, idname, key, ctrl=False, shift=False, alt=False):
        self.idname = idname
        self.type = key
        self.ctrl = ctrl
        self.shift = shift
        self.alt = alt
        self.oskey = False
        self.active = True


# A slice of Blender's default keymap: directly-bound operators only. The
# menu-driven ones (add, delete) are deliberately absent, because they are
# absent in Blender too -- Shift+A is bound to the menu, not to the operator.
_DEFAULT_ITEMS = [
    _KeyMapItem("transform.translate", "G"),
    _KeyMapItem("transform.rotate", "R"),
    _KeyMapItem("transform.resize", "S"),
    _KeyMapItem("mesh.extrude_region_and_move", "E"),
    _KeyMapItem("mesh.inset", "I"),
    _KeyMapItem("mesh.bevel", "B", ctrl=True),
    _KeyMapItem("mesh.loopcut_slide", "R", ctrl=True),
]


class _KeyMap:
    def __init__(self, items):
        self.keymap_items = items


class _KeyConfig:
    def __init__(self, items):
        self.keymaps = [_KeyMap(items)]


class _KeyConfigs:
    def __init__(self):
        self.user = _KeyConfig(_DEFAULT_ITEMS)

    def find_item_from_operator(self, idname=""):
        for kmi in _DEFAULT_ITEMS:
            if kmi.idname == idname:
                return None, kmi
        return None, None


class _WindowManager:
    def __init__(self):
        self.keyconfigs = _KeyConfigs()
        self.operators = []
        self.windows = []


class _Context:
    def __init__(self):
        self.window_manager = _WindowManager()
        self.window = None
        self.scene = None
        self.region = None


context = _Context()
data = None
