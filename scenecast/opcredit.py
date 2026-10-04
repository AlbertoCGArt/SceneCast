"""Which operator made a step's change.

Blender reports an operator in wm.operators only once it *finishes*, and a
step is captured as soon as the geometry settles. So while a modal tool is
running, its geometry is captured under whatever finished before it: in a
real session the Inset was captioned "Edit Mode", each Extrude "Inset Faces",
and three steps of Bevel cuts "Loop Select", with the Bevel only named once
the user clicked to confirm. The label trailed the action by one operator.

The rule here: a step that changed geometry belongs to the next operator to
finish -- unless that is a selection, view or mode operator (nothing that
edits was coming to claim it), or a move that could not have made new faces.
With nothing later claiming it, the step keeps its own operator if that
could have done it (the same tool run twice reports the same id, so a repeat
never shows up as a new finish), and otherwise shows no operator rather than
a wrong one.

Shared with Pro's auto notes, so the caption and the note agree.
"""

# Operators that select, look, or switch mode. They finish constantly between
# the edits that matter and change nothing a caption should be about.
PASSIVE_PREFIXES = (
    "view3d.", "view2d.", "wm.", "screen.", "ed.", "scenecast.", "outliner.",
    "buttons.", "file.", "image.", "info.", "ui.", "anim.", "marker.",
    "object.mode_set", "object.editmode_toggle", "object.posemode_toggle",
    "sculpt.sculptmode_toggle", "paint.", "object.hide", "object.reveal",
    "mesh.hide", "mesh.reveal", "object.modifier_",
    "transform.select_orientation", "transform.create_orientation",
)

# Moving things never adds or removes geometry, so a move cannot be what made
# a topology change -- it only reshapes.
SHAPE_ONLY_PREFIXES = ("transform.",)

# How far ahead a modal tool's confirmation is looked for. A step is captured
# every settle or watchdog tick (0.7s), so this is a long drag, not a session.
LOOKAHEAD = 60


def op_key(op_id):
    """'MESH_OT_inset' and 'mesh.inset' are the same operator; compare as the latter.

    wm.operators reports the C-style name, the Python API takes the dotted
    one, and both turn up in sessions.
    """
    op_id = op_id or ""
    if "_OT_" in op_id:
        head, _sep, tail = op_id.partition("_OT_")
        return "%s.%s" % (head.lower(), tail)
    return op_id


def is_passive(op_id, op_name=""):
    """True for an operator that selects, looks or switches mode."""
    key = op_key(op_id)
    if not key:
        return True
    if key.startswith(PASSIVE_PREFIXES):
        return True
    if "select" in key.split(".", 1)[-1]:
        return True                     # select_all, loop_select, select_more...
    return "Select" in (op_name or "")


def is_shape_only(op_id):
    return op_key(op_id).startswith(SHAPE_ONLY_PREFIXES)


def _op(step):
    return step.get("op", "") or "", step.get("op_id", "") or ""


def _finished_at(steps, j):
    """True if an operator finished between step j-1 and step j."""
    op_id = steps[j].get("op_id", "")
    prev = steps[j - 1].get("op_id", "") if j > 0 else ""
    return bool(op_id) and op_id != prev


def _objs(step):
    objs = step.get("objs")
    return objs if isinstance(objs, dict) else {}


def topology_changed(prev, step):
    """Did any object gain or lose vertices or faces between these steps."""
    a, b = _objs(prev), _objs(step)
    if a is b:
        return False
    for name, sb in b.items():
        sa = a.get(name)
        if sa is None or sa is sb:
            continue
        if sa.get("vcount") != sb.get("vcount") or \
                sa.get("fcount") != sb.get("fcount"):
            return True
    return False


def added_object(prev, step):
    a, b = _objs(prev), _objs(step)
    return a is not b and any(name not in a for name in b) and bool(a)


def _can_have_made(op_id, op_name, topo):
    if is_passive(op_id, op_name):
        return False
    return not (topo and is_shape_only(op_id))


def credited_op(steps, idx, shortcut=None):
    """(name, op_id) of the operator a step's caption should name.

    Steps that changed no geometry keep their own operator; the overlay's
    staleness rule decides whether to show it. `shortcut(op_id)` -> key
    combo, when given, breaks one tie: a stale operator that could have made
    the change and a later one that also could. The keys logged on the step
    say which tool the user actually reached for.
    """
    if not (0 <= idx < len(steps)):
        return "", ""
    step = steps[idx]
    own = _op(step)
    if not step.get("geo_new") or idx == 0:
        return own
    prev = steps[idx - 1]
    # An object appearing is never what a later tool was in the middle of.
    if added_object(prev, step):
        return own
    topo = topology_changed(prev, step)
    own_can = _can_have_made(own[1], own[0], topo)
    if _finished_at(steps, idx) and own_can:
        return own                      # finished with this very capture

    for j in range(idx, min(len(steps), idx + 1 + LOOKAHEAD)):
        if not _finished_at(steps, j):
            continue
        name, op_id = _op(steps[j])
        if is_passive(op_id, name):
            if j == idx:
                continue                # selected, then reached for a tool
            break                       # nothing that edits was coming
        if topo and is_shape_only(op_id):
            break
        if own_can and own[1] != op_id and shortcut is not None:
            keys = step.get("keys") or ()
            mine, theirs = shortcut(own[1]), shortcut(op_id)
            if mine and mine in keys and not (theirs and theirs in keys):
                return own              # a repeat of the tool it says
        return name, op_id
    return own if own_can else ("", "")
