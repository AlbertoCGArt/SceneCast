"""Modifier-stack capture and replay.

A snapshot used to hold only the evaluated-free base mesh, so a hard-surface
session -- where the shape is a Mirror over a Bevel over a Subdivision --
replayed as the naked control cage and none of the work was visible. What is
recorded here is the stack itself: which modifiers, in what order, with what
settings, so a step can put it back.

Settings are read generically off `bl_rna`, not from a per-type table: there
are ~60 modifier types and Blender adds more, and a table would silently drop
whatever it had not been taught. Anything that is not a plain value or an
ID pointer (a curve mapping, a hook's vertex list) is skipped rather than
guessed at -- those are the rare ones, and a wrong value is worse than a
missing one.
"""

import bpy

# Read-only bookkeeping, or state that would fight the user's own UI.
_SKIP_PROPS = frozenset((
    "rna_type", "name", "type", "is_active", "is_override_data",
    "show_expanded", "execution_time", "persistent_uid",
))

_VALUE_TYPES = frozenset(("BOOLEAN", "INT", "FLOAT", "STRING", "ENUM"))


def snapshot_modifiers(obj):
    """The object's stack as a tuple of plain dicts, top of stack first.

    A tuple of dicts (rather than the live modifier objects) is what makes
    this storable, comparable and hashable-by-repr -- and it keeps no
    reference to anything Blender might free.
    """
    out = []
    try:
        mods = obj.modifiers
    except Exception:
        return ()
    for mod in mods:
        entry = {"name": mod.name, "type": mod.type, "props": {}}
        props = entry["props"]
        try:
            rna_props = mod.bl_rna.properties
        except Exception:
            rna_props = ()
        for p in rna_props:
            ident = p.identifier
            if ident in _SKIP_PROPS or p.is_readonly:
                continue
            try:
                val = getattr(mod, ident)
            except Exception:
                continue
            if p.type in _VALUE_TYPES:
                if getattr(p, "is_array", False):
                    try:
                        val = tuple(val)
                    except TypeError:
                        pass
                props[ident] = val
            elif p.type == 'POINTER':
                # Datablocks are stored by name and looked up again on
                # replay: holding the pointer would keep freed data alive.
                props[ident] = ("=id=", getattr(val, "name", "")) if val else None
            # COLLECTION and anything else: deliberately not guessed at.
        out.append(entry)
    return tuple(out)


def stack_signature(mods):
    """Comparable form of a stack, for "is this already what's applied?"."""
    return repr(mods) if mods else ""


def describe_modifiers(mods, limit=3):
    """Short human line for the panel: 'Mirror, Bevel, Subsurf +2'."""
    if not mods:
        return ""
    names = [m.get("type", "?").title() for m in mods]
    shown = ", ".join(names[:limit])
    if len(names) > limit:
        shown += "  +%d" % (len(names) - limit)
    return shown


def apply_modifiers(obj, mods):
    """Make obj's stack match `mods`. True if anything was changed.

    Rebuilds from scratch rather than diffing: modifier order is part of the
    result, and there is no reorder API that is cheaper than re-adding. The
    no-op case is caught by the signature check first, so a session where the
    stack never changes never touches the object at all.
    """
    if mods is None:
        return False
    try:
        current = obj.modifiers
    except Exception:
        return False

    if stack_signature(snapshot_modifiers(obj)) == stack_signature(mods):
        return False                     # already correct: leave it alone

    try:
        current.clear()
    except Exception:
        for mod in list(current):
            try:
                current.remove(mod)
            except Exception:
                pass

    for entry in mods:
        try:
            mod = current.new(name=entry.get("name", "Modifier"),
                              type=entry["type"])
        except Exception as e:
            print("[SceneCast] could not add %s modifier: %s"
                  % (entry.get("type"), e))
            continue
        for ident, val in entry.get("props", {}).items():
            if isinstance(val, tuple) and len(val) == 2 and val[0] == "=id=":
                val = _resolve_id(val[1])
                if val is None:
                    continue
            try:
                setattr(mod, ident, val)
            except Exception:
                # Settings constrain each other (a Boolean's operand type
                # gates its object slot), so some assignments are simply not
                # valid in isolation. One rejected setting must not cost the
                # rest of the stack.
                pass
    return True


def _resolve_id(name):
    """Find a datablock by name across the collections modifiers point into."""
    if not name:
        return None
    for coll in ("objects", "meshes", "textures", "collections", "images",
                 "materials", "armatures", "node_groups"):
        try:
            found = getattr(bpy.data, coll).get(name)
        except Exception:
            continue
        if found is not None:
            return found
    return None
