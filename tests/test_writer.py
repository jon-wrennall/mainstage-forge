"""Tests for concert package generation."""

import plistlib
from pathlib import Path
import pytest
import tempfile

from mainstage_forge.models import Concert, Set, Patch
from mainstage_forge.writer import write_concert


@pytest.fixture
def tmp(tmp_path):
    return tmp_path


def test_write_creates_package_directory(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A", "Song B"])
    path = write_concert(concert, tmp)
    assert path.is_dir()
    assert path.name == "Test Gig.concert"


def test_root_data_plist_valid(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"])
    path = write_concert(concert, tmp)
    plist_path = path / "data.plist"
    assert plist_path.exists()
    data = plistlib.load(open(plist_path, "rb"))
    assert "Version" in data
    assert data["Version"] == 55057


def test_concert_patch_created(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A", "Song B"])
    path = write_concert(concert, tmp)
    concert_patch = path / "Concert.patch"
    assert concert_patch.is_dir()
    data = plistlib.load(open(concert_patch / "data.plist", "rb"))
    assert data["patch"]["engineNode"]["name"] == "Test Gig"
    assert data["VersionPatches"] == 40014


def test_set_directories_created(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A", "Song B"])
    path = write_concert(concert, tmp)
    concert_patch = path / "Concert.patch"
    assert (concert_patch / "Song A.patch").is_dir()
    assert (concert_patch / "Song B.patch").is_dir()


def test_set_plist_has_correct_name(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"])
    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "Song A.patch" / "data.plist", "rb"))
    assert data["patch"]["engineNode"]["name"] == "Song A"


def test_patch_directories_created(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"], patch_name="Keys")
    path = write_concert(concert, tmp)
    patch_dir = path / "Concert.patch" / "Song A.patch" / "Keys.patch"
    assert patch_dir.is_dir()
    assert (patch_dir / "data.plist").exists()


def test_patch_plist_correct_fields(tmp):
    concert = Concert(name="Test Gig")
    s = concert.add_set("Song A", tempo=130.0)
    s.add_patch("Keys", tempo=130.0, has_tempo=True, global_transpose=2)
    path = write_concert(concert, tmp)
    data = plistlib.load(
        open(path / "Concert.patch" / "Song A.patch" / "Keys.patch" / "data.plist", "rb")
    )
    en = data["patch"]["engineNode"]
    assert en["name"] == "Keys"
    assert en["hasTempo"] is True
    assert en["globalTranspose"] == 2


def test_overwrite_false_raises(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"])
    write_concert(concert, tmp)
    with pytest.raises(FileExistsError):
        write_concert(concert, tmp, overwrite=False)


def test_overwrite_true_replaces(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"])
    path1 = write_concert(concert, tmp)
    path2 = write_concert(concert, tmp, overwrite=True)
    assert path1 == path2


def test_unsafe_name_sanitised(tmp):
    concert = Concert.from_setlist("Test/Gig", ["Song: A"])
    path = write_concert(concert, tmp)
    assert "Test-Gig.concert" in str(path)
    assert (path / "Concert.patch" / "Song- A.patch").is_dir()


def test_channels_array_is_empty(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"])
    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "data.plist", "rb"))
    assert data["channels"] == []
