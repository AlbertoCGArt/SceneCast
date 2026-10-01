"""Modifier stacks are captured generically and put back in order."""

from scenecast.modifiers import (snapshot_modifiers, stack_signature,
                                 describe_modifiers, apply_modifiers)


class _Prop:
    def __init__(self, identifier, type, is_readonly=False, is_array=False):
        self.identifier = identifier
        self.type = type
        self.is_readonly = is_readonly
        self.is_array = is_array


class _RNA:
    def __init__(self, props):
        self.properties = props


class _Named:
    def __init__(self, name):
        self.name = name


class _Mod:
    def __init__(self, name, type, values, props):
        self.name = name
        self.type = type
        self.bl_rna = _RNA(props)
        for k, v in values.items():
            setattr(self, k, v)


class _Stack(list):
    def clear(self):
        del self[:]

    def new(self, name, type):
        mod = _Mod(name, type, {}, [])
        self.append(mod)
        return mod


class _Object:
    def __init__(self, mods=()):
        self.modifiers = _Stack(mods)


def _bevel():
    return _Mod("Bevel", "BEVEL",
                {"width": 0.02, "segments": 3, "use_clamp_overlap": True,
                 "limit_method": 'ANGLE', "execution_time": 0.5,
                 "vertex_group": "", "offset_type": 'OFFSET'},
                [_Prop("width", 'FLOAT'), _Prop("segments", 'INT'),
                 _Prop("use_clamp_overlap", 'BOOLEAN'),
                 _Prop("limit_method", 'ENUM'), _Prop("vertex_group", 'STRING'),
                 _Prop("offset_type", 'ENUM'),
                 _Prop("execution_time", 'FLOAT', is_readonly=True)])


def test_captures_settings_generically():
    entry = snapshot_modifiers(_Object([_bevel()]))[0]
    assert entry["name"] == "Bevel" and entry["type"] == "BEVEL"
    assert entry["props"]["width"] == 0.02
    assert entry["props"]["segments"] == 3
    assert entry["props"]["limit_method"] == 'ANGLE'


def test_read_only_properties_are_skipped():
    """execution_time is a stat, not a setting -- writing it back would fail."""
    entry = snapshot_modifiers(_Object([_bevel()]))[0]
    assert "execution_time" not in entry["props"]
    assert "rna_type" not in entry["props"] and "type" not in entry["props"]


def test_array_properties_become_tuples():
    mod = _Mod("Array", "ARRAY", {"relative_offset_displace": [1.0, 0.0, 0.0]},
               [_Prop("relative_offset_displace", 'FLOAT', is_array=True)])
    props = snapshot_modifiers(_Object([mod]))[0]["props"]
    assert props["relative_offset_displace"] == (1.0, 0.0, 0.0)


def test_pointers_are_stored_by_name_not_by_reference():
    mod = _Mod("Mirror", "MIRROR", {"mirror_object": _Named("Empty")},
               [_Prop("mirror_object", 'POINTER')])
    props = snapshot_modifiers(_Object([mod]))[0]["props"]
    assert props["mirror_object"] == ("=id=", "Empty")


def test_empty_pointer_stays_empty():
    mod = _Mod("Mirror", "MIRROR", {"mirror_object": None},
               [_Prop("mirror_object", 'POINTER')])
    assert snapshot_modifiers(_Object([mod]))[0]["props"]["mirror_object"] is None


def test_collection_properties_are_not_guessed_at():
    mod = _Mod("Hook", "HOOK", {"vertex_indices": [1, 2, 3]},
               [_Prop("vertex_indices", 'COLLECTION')])
    assert snapshot_modifiers(_Object([mod]))[0]["props"] == {}


def test_object_without_modifiers_reports_an_empty_stack():
    assert snapshot_modifiers(_Object()) == ()


# ----------------------------------------------------------------------------
def test_order_is_part_of_the_stack_identity():
    a = ({"name": "Mirror", "type": "MIRROR", "props": {}},
         {"name": "Bevel", "type": "BEVEL", "props": {}})
    assert stack_signature(a) != stack_signature(tuple(reversed(a)))


def test_apply_rebuilds_the_stack_in_order():
    want = ({"name": "Mirror", "type": "MIRROR", "props": {}},
            {"name": "Subsurf", "type": "SUBSURF", "props": {"levels": 2}})
    obj = _Object()
    assert apply_modifiers(obj, want) is True
    assert [m.type for m in obj.modifiers] == ["MIRROR", "SUBSURF"]
    assert obj.modifiers[1].levels == 2


def test_apply_is_a_no_op_when_the_stack_already_matches():
    """Most steps do not touch the stack, and clearing it every frame would
    make scrubbing unusable."""
    obj = _Object([_bevel()])
    assert apply_modifiers(obj, snapshot_modifiers(obj)) is False
    assert len(obj.modifiers) == 1


def test_apply_clears_a_stack_recorded_as_empty():
    obj = _Object([_bevel()])
    assert apply_modifiers(obj, ()) is True
    assert list(obj.modifiers) == []


def test_apply_ignores_an_uncaptured_stack():
    """mods=None means the session never recorded them -- leave the user's
    own modifiers alone rather than deleting them."""
    obj = _Object([_bevel()])
    assert apply_modifiers(obj, None) is False
    assert len(obj.modifiers) == 1


def test_describe_is_short_and_counts_the_rest():
    mods = [{"type": t, "props": {}} for t in
            ("MIRROR", "BEVEL", "SUBSURF", "SOLIDIFY", "ARRAY")]
    assert describe_modifiers(mods) == "Mirror, Bevel, Subsurf  +2"
    assert describe_modifiers([]) == ""
    assert describe_modifiers(None) == ""
