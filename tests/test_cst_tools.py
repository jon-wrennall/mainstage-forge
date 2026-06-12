"""Tests for cst_tools — FX chain inspection, extraction, and injection."""

import struct
import pytest
from pathlib import Path

from mainstage_forge.cst_tools import (
    inspect_cst,
    extract_fx_blocks,
    inject_fx_blocks,
    graft_fx_chain,
    _STANDARD_SLOT_IDS,
)

TEMPLATES_DIR = Path(__file__).parent.parent / "mainstage_forge" / "templates"
# Analog Spheres uses the ES2 plugin — GAME\x00\x00\x00\x00 format, slot 0xd6, no FX inserts.
# Arturia/Roland plugins (OP-Xa V, Jun-6 V, D50 Pad) have 0 GAME blocks so can't test injection.
# Logic-native instruments (Grand Piano, B-3) use GAMEMELC format which is incompatible.
_au_template = TEMPLATES_DIR / "Analog Spheres.cst"
_any_template = _au_template if _au_template.exists() else next(iter(TEMPLATES_DIR.glob("*.cst")), None)


# ── inspect_cst ───────────────────────────────────────────────────────────────

def test_inspect_returns_expected_keys():
    info = inspect_cst(_any_template)
    assert "game_pairs" in info
    assert "fx_slot_count" in info
    assert "key_zone" in info
    assert "layout_name" in info
    assert "bplist_offsets" in info


def test_inspect_template_has_no_fx():
    info = inspect_cst(_any_template)
    assert info["fx_slot_count"] == 0
    for pair in info["game_pairs"]:
        assert not pair["is_fx"], f"Unexpected FX slot {pair['slot_id_hex']} in template"


def test_inspect_template_has_key_zone():
    info = inspect_cst(_any_template)
    kz = info["key_zone"]
    assert kz is not None
    assert kz["lowNote"] == 0
    assert kz["highNote"] == 127


def test_inspect_game_pairs_have_required_fields():
    info = inspect_cst(_any_template)
    assert len(info["game_pairs"]) > 0
    for pair in info["game_pairs"]:
        assert "slot_id" in pair
        assert "slot_id_hex" in pair
        assert "data_size" in pair
        assert "is_fx" in pair
        assert pair["data_size"] > 0


# ── extract / inject round-trip ───────────────────────────────────────────────

def test_extract_from_no_fx_template_returns_empty():
    fx_blocks = extract_fx_blocks(_any_template)
    assert fx_blocks == []


def test_inject_empty_fx_blocks_is_noop():
    original = _any_template.read_bytes()
    result = inject_fx_blocks(original, [])
    assert result == original


def test_inject_synthetic_fx_block_appears_in_output():
    """Inject a hand-crafted GAME pair and verify it survives round-trip."""
    original = _any_template.read_bytes()

    # Build a minimal GAME---- header + GAMETSPP for a fake slot ID 0x1234
    fake_slot_id = 0x1234
    header = b"GAME\x00\x00\x00\x00" + struct.pack("<H", fake_slot_id) + b"\x00" * 42
    tspp_data = b"GAMETSPP" + struct.pack("<H", fake_slot_id) + b"\x00" * 10 + b"\x01\x02\x03\x04" * 8
    fx_blocks = [(header, tspp_data)]

    result = inject_fx_blocks(original, fx_blocks)
    assert len(result) > len(original)
    assert b"GAMETSPP" + struct.pack("<H", fake_slot_id) in result


def test_graft_fx_chain_preserves_bplists():
    """After grafting, the WsKeyboardLayer bplist must still be intact."""
    import plistlib
    import re

    original = _any_template.read_bytes()
    grafted = graft_fx_chain(original, original)  # graft from self = no change

    # Find WsKeyboardLayer bplist in grafted output
    found = False
    for m in re.finditer(b"bplist00", grafted):
        off = m.start()
        for end in range(200, min(len(grafted) - off + 1, 4000)):
            try:
                p = plistlib.loads(grafted[off:off+end])
                objs = p.get("$objects", [])
                for o in objs:
                    if isinstance(o, dict) and "highNote" in o:
                        found = True
                        break
            except Exception:
                continue
            if found:
                break
        if found:
            break
    assert found, "WsKeyboardLayer bplist not found after graft"
