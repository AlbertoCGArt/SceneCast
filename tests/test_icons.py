"""Every icon name the panels ask for is shaped like a real one.

Blender only checks an icon when the panel draws, and a bad one raises in the
middle of the draw -- everything below it in the panel simply never appears.
That is how a lowercase `IMAGE_data` hid half of the Branding panel without
anyone being told. Icon identifiers are always upper case; this cannot prove
a name exists, but it catches the typo that actually happened.
"""

import os
import re

import pytest

PACKAGE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenecast")
_ICON = re.compile(r"""icon\s*=\s*'([^']*)'""")
_CONDITIONAL = re.compile(r"""else\s+'([^']*)'""")
_VALID = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _icon_names(folder):
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                found = _ICON.findall(line)
                if "icon" in line:
                    found += _CONDITIONAL.findall(line)
                for icon in found:
                    yield "%s:%d" % (name, lineno), icon


ICONS = list(_icon_names(PACKAGE))


def test_there_are_icons_to_check():
    assert len(ICONS) > 20


@pytest.mark.parametrize("where,icon", ICONS)
def test_icon_names_are_upper_case_identifiers(where, icon):
    assert _VALID.match(icon), "%s uses icon %r" % (where, icon)
