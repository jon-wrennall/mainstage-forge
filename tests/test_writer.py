"""Tests for concert package generation."""

import plistlib
from pathlib import Path
import pytest
import tempfile

from mainstage_forge.models import Concert, Set, Patch, ChannelStrip, TEMPLATES
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


def test_base_plistz_present(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"])
    path = write_concert(concert, tmp)
    assert (path / "base.plistZ").exists()


def test_concert_patch_has_required_channels(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"])
    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "data.plist", "rb"))
    names = [c["Channel_name"] for c in data["channels"]]
    assert "Master" in names
    assert "Metronome" in names
    assert "Output 1-2" in names


def test_templates_available():
    assert "Grand Piano" in TEMPLATES
    assert "Classic Electric Piano" in TEMPLATES
    assert "Bass" in TEMPLATES
    for name, path in TEMPLATES.items():
        assert path.exists(), f"Template file missing: {path}"


def test_channel_strip_resolves_template():
    ch = ChannelStrip(name="Piano", cst_source="Grand Piano")
    resolved = ch.resolve_cst()
    assert resolved.exists()
    assert resolved.stem == "Grand Piano"


def test_channel_strip_resolves_absolute_path(tmp_path):
    # Copy a real .cst to tmp to simulate an absolute path
    src = TEMPLATES["Grand Piano"]
    dst = tmp_path / "MyPiano.cst"
    import shutil
    shutil.copy2(src, dst)
    ch = ChannelStrip(name="Piano", cst_source=str(dst))
    assert ch.resolve_cst() == dst


def test_channel_strip_unknown_raises():
    ch = ChannelStrip(name="Piano", cst_source="NonExistentInstrument")
    with pytest.raises(FileNotFoundError):
        ch.resolve_cst()


def test_patch_with_channels_writes_cst(tmp):
    concert = Concert(name="Test Gig")
    s = concert.add_set("Song A")
    p = s.add_patch("Keys")
    p.add_channel("Piano", "Grand Piano")
    p.add_channel("Bass", "Bass")

    path = write_concert(concert, tmp)
    patch_dir = path / "Concert.patch" / "Song A.patch" / "Keys.patch"
    assert (patch_dir / "Piano.cst").exists()
    assert (patch_dir / "Bass.cst").exists()


def test_patch_channels_in_plist(tmp):
    concert = Concert(name="Test Gig")
    s = concert.add_set("Song A")
    p = s.add_patch("Keys")
    p.add_channel("Piano", "Grand Piano", volume=0.8, pan=-0.5)
    p.add_channel("Bass", "Bass")

    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "Song A.patch" / "Keys.patch" / "data.plist", "rb"))
    ch_names = [c["Channel_name"] for c in data["channels"]]
    assert ch_names == ["Piano", "Bass"]
    piano = data["channels"][0]
    assert piano["Filename"] == "Piano.cst"
    assert piano["Channel_instID"] == 104
    assert piano["Channel_pan"] == pytest.approx(-0.5)
    bass = data["channels"][1]
    assert bass["Channel_instID"] == 108


def test_empty_patch_has_no_channels(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"])
    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "Song A.patch" / "Main.patch" / "data.plist", "rb"))
    assert data["channels"] == []


# ── Smart Controls ────────────────────────────────────────────────────────────

def test_smart_knob_label_in_plist(tmp):
    concert = Concert(name="Test Gig")
    s = concert.add_set("Song A")
    p = s.add_patch("Keys")
    p.add_channel("Piano V", "Grand Piano")
    p.add_smart_knob("Cutoff", channel_slot_index=0, param_index=35)
    p.add_smart_knob("Resonance", channel_slot_index=0, param_index=36)

    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "Song A.patch" / "Keys.patch" / "data.plist", "rb"))
    uid = data["patch"]["engineNode"]["uiPluginDataDict"]
    assert "\x01IDENTITY:Smart Knob 1" in uid
    assert uid["\x01IDENTITY:Smart Knob 1"]["storeDict"]["customLabel"] == "Cutoff"
    assert uid["\x01IDENTITY:Smart Knob 2"]["storeDict"]["customLabel"] == "Resonance"


def test_smart_knob_mapping_in_plist(tmp):
    concert = Concert(name="Test Gig")
    s = concert.add_set("Song A")
    p = s.add_patch("Keys")
    p.add_channel("Piano V", "Grand Piano")
    p.add_smart_knob("Attack", channel_slot_index=0, param_index=107, range_low=-1, range_high=85)

    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "Song A.patch" / "Keys.patch" / "data.plist", "rb"))
    pmm = data["patch"]["engineNode"]["parameterMappingMap"]
    assert "\x01IDENTITY:Smart Knob 1" in pmm["containsDictionary"]
    # storeDict value is a bytes blob — verify it parses as a valid plist
    blob = bytes(pmm["storeDict"]["\x01IDENTITY:Smart Knob 1"])
    decoded = plistlib.loads(blob)
    assert decoded["$archiver"] == "NSKeyedArchiver"


def test_smart_knob_references_correct_instid(tmp):
    import plistlib as _pl
    concert = Concert(name="Test Gig")
    s = concert.add_set("Song A")
    p = s.add_patch("Keys")
    p.add_channel("Piano V", "Grand Piano")   # slot 0 → instID 104
    p.add_channel("Bass", "Bass")             # slot 1 → instID 108
    p.add_smart_knob("Bass Cutoff", channel_slot_index=1, param_index=35)

    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "Song A.patch" / "Keys.patch" / "data.plist", "rb"))
    pmm = data["patch"]["engineNode"]["parameterMappingMap"]
    blob = bytes(pmm["storeDict"]["\x01IDENTITY:Smart Knob 1"])
    raw = _pl.loads(blob)
    objects = raw["$objects"]
    mapping = next(o for o in objects if isinstance(o, dict) and "kGInstIDKey" in o)
    assert mapping["kGInstIDKey"] == 108  # instID for slot 1


def test_no_smart_knobs_uses_empty_map(tmp):
    concert = Concert.from_setlist("Test Gig", ["Song A"])
    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "Song A.patch" / "Main.patch" / "data.plist", "rb"))
    pmm = data["patch"]["engineNode"]["parameterMappingMap"]
    assert pmm["storeDict"] == {}
    assert pmm["containsDictionary"] == {}


def test_knob_identity_prefix(tmp):
    """Custom 'Knob N' identity prefix is stored correctly (vs default 'Smart Knob N')."""
    concert = Concert(name="Test Gig")
    s = concert.add_set("Song A")
    p = s.add_patch("Keys")
    p.add_channel("Piano V", "Grand Piano")
    p.add_smart_knob("Filter Freq", channel_slot_index=0, param_index=20, identity_prefix="Knob")

    path = write_concert(concert, tmp)
    data = plistlib.load(open(path / "Concert.patch" / "Song A.patch" / "Keys.patch" / "data.plist", "rb"))
    pmm = data["patch"]["engineNode"]["parameterMappingMap"]
    assert "\x01IDENTITY:Knob 1" in pmm["containsDictionary"]
    assert "\x01IDENTITY:Smart Knob 1" not in pmm["containsDictionary"]


def test_key_zone_patch_applied_to_cst(tmp):
    """lowNote/highNote are patched into the .cst WsKeyboardLayer bplist."""
    import re
    template = list(TEMPLATES.values())[0]

    concert = Concert(name="Test Gig")
    s = concert.add_set("Song A")
    p = s.add_patch("Keys")
    ch = p.add_channel("Piano V", str(template))
    ch.low_note = 60
    ch.high_note = 127

    path = write_concert(concert, tmp)
    cst_path = path / "Concert.patch" / "Song A.patch" / "Keys.patch" / "Piano V.cst"
    assert cst_path.exists()
    raw = cst_path.read_bytes()

    # Find WsKeyboardLayer bplist and verify patched values
    for m in re.finditer(b'bplist00', raw):
        off = m.start()
        for end in range(200, min(len(raw) - off + 1, 4000)):
            try:
                p2 = plistlib.loads(raw[off:off+end])
                objs = p2.get('$objects', [])
                for o in objs:
                    if isinstance(o, dict) and 'highNote' in o:
                        assert o['lowNote'] == 60
                        assert o['highNote'] == 127
                        return
            except Exception:
                continue
    pytest.fail("WsKeyboardLayer bplist not found in patched .cst")
