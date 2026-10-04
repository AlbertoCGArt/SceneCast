"""Where output goes, especially when the .blend has never been saved."""

import os

import pytest
import bpy

from scenecast import paths


class _Data:
    def __init__(self, filepath=""):
        self.filepath = filepath


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake home folder with a Documents folder in it."""
    monkeypatch.setattr(os.path, "expanduser",
                        lambda p: p.replace("~", str(tmp_path), 1)
                        if p.startswith("~") else p)
    (tmp_path / "Documents").mkdir()
    return tmp_path


@pytest.fixture
def unsaved(monkeypatch, home):
    monkeypatch.setattr(bpy, "data", _Data(""))
    return home


@pytest.fixture
def saved(monkeypatch, home, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(bpy, "data", _Data(str(project / "scene.blend")))
    return project


# ----------------------------------------------------------------------------
# Resolving
# ----------------------------------------------------------------------------
def test_double_slash_is_next_to_a_saved_blend(saved):
    path, fell_back = paths.resolve("//out/clip.mp4")
    assert path == os.path.normpath(str(saved / "out" / "clip.mp4"))
    assert fell_back is False


def test_double_slash_on_an_unsaved_file_goes_to_documents(unsaved):
    """This is the bug: it used to resolve against Blender's start-up folder,
    which on Windows can be the root of C:."""
    path, fell_back = paths.resolve("//clip.mp4")
    assert path == os.path.normpath(str(unsaved / "Documents" / "SceneCast" / "clip.mp4"))
    assert fell_back is True


def test_no_documents_folder_falls_back_to_home(unsaved):
    (unsaved / "Documents").rmdir()
    path, _ = paths.resolve("//clip.mp4")
    assert path == os.path.normpath(str(unsaved / "SceneCast" / "clip.mp4"))


def test_a_bare_relative_path_is_not_left_to_the_working_folder(unsaved):
    path, fell_back = paths.resolve("renders/clip.mp4")
    assert path.startswith(str(unsaved / "Documents" / "SceneCast"))
    assert fell_back is True


def test_a_bare_relative_path_on_a_saved_file_is_next_to_it(saved):
    path, fell_back = paths.resolve("renders/clip.mp4")
    assert path == os.path.normpath(str(saved / "renders" / "clip.mp4"))
    assert fell_back is False


def test_an_absolute_path_is_left_alone(unsaved, tmp_path):
    target = str(tmp_path / "elsewhere" / "clip.mp4")
    assert paths.resolve(target) == (os.path.normpath(target), False)


def test_an_empty_field_means_next_to_the_blend(saved):
    assert paths.resolve("")[0] == os.path.normpath(str(saved))


def test_the_fallback_is_labelled_as_a_person_would_say_it(unsaved):
    assert paths.fallback_label() == os.path.join("Documents", "SceneCast")


# ----------------------------------------------------------------------------
# Output files and folders
# ----------------------------------------------------------------------------
def test_output_file_creates_the_folder_and_says_where(unsaved):
    path, note = paths.output_file("//scenecast_session.mp4",
                                   "scenecast_session.mp4", ".mp4")
    assert os.path.isdir(os.path.dirname(path))
    assert path.endswith("scenecast_session.mp4")
    assert "isn't saved" in note and "SceneCast" in note


def test_output_file_says_nothing_extra_for_a_saved_file(saved):
    _path, note = paths.output_file("//clip.mp4", "x.mp4", ".mp4")
    assert note == ""


def test_output_file_forces_the_extension(saved):
    path, _ = paths.output_file("//session", "x.scast", ".scast")
    assert path.endswith("session.scast")


def test_output_file_given_a_folder_uses_the_default_name(saved):
    path, _ = paths.output_file("//renders/", "scenecast_session.mp4", ".mp4")
    assert path == os.path.normpath(str(saved / "renders" / "scenecast_session.mp4"))


def test_output_dir_given_a_file_path_means_its_folder(saved):
    """The shared Export path names an MP4; a PNG export wants its folder."""
    folder, _ = paths.output_dir("//renders/scenecast_session.mp4")
    assert folder == os.path.normpath(str(saved / "renders"))
    assert os.path.isdir(folder)


def test_an_unwritable_folder_gives_a_message_a_person_can_act_on(unsaved, monkeypatch):
    def refuse(*a, **k):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(os, "makedirs", refuse)
    with pytest.raises(paths.OutputPathError) as err:
        paths.output_file("C:\\as.scast", "x.scast", ".scast")
    message = str(err.value)
    assert "Can't write to" in message
    assert "choose a folder you own" in message
    assert "save the .blend first" in message       # unsaved: say the other fix


def test_a_saved_file_is_not_told_to_save_first(saved, monkeypatch):
    def refuse(*a, **k):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(os, "makedirs", refuse)
    with pytest.raises(paths.OutputPathError) as err:
        paths.output_dir("//renders/")
    assert "save the .blend" not in str(err.value)


def test_writability_is_proven_by_writing_not_by_os_access(saved, monkeypatch):
    """os.access says yes to C:\\ on Windows; only the write tells the truth."""
    real_open = open

    def refusing_open(path, *a, **k):
        if str(path).endswith(".scenecast-write-test"):
            raise PermissionError(13, "Permission denied")
        return real_open(path, *a, **k)
    monkeypatch.setattr("builtins.open", refusing_open)
    with pytest.raises(paths.OutputPathError):
        paths.output_dir("//renders/")


def test_the_write_probe_leaves_nothing_behind(saved):
    folder, _ = paths.output_dir("//renders/")
    assert os.listdir(folder) == []
