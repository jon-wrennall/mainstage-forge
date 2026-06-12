"""
Utilities for reading, modifying, and assembling MainStage .cst channel-strip files.

A .cst file has the layout:
  [preamble]  OCuA header + pre-GAME binary (channel identity, AU component codes)
  [GAME pairs] N × (GAME\x00\x00\x00\x00 header, 52 bytes) + (GAMETSPP data, variable)
  [bplists]   3 NSKeyedArchiver bplists:
                1. Smart Controls parameter mappings
                2. WsPluginIdentity (Smart Knob labels, channel UUID, layout name)
                3. WsKeyboardLayer (key zone: lowNote, highNote, velocity range, colour)

Each GAME pair has a uint16 "slot ID" at byte offset 8.  Slot IDs observed across
the Example 80s concert:

  STANDARD (always present in instrument strips):
    0x00d6 (214)  — instrument plugin parameter block (fixed 1600-byte float array)
    0x00ec (236)  — channel-strip settings (volume/pan/sends, fixed 416 bytes)
    0x0094 (148)  — additional channel state
    0x009a (154)  — additional channel state (some strips)

  FX INSERTS (extra pairs, vary per patch):
    Any slot ID not in the STANDARD set above is an FX insert.
    The actual plugin type is encoded in the binary float data — it is not
    self-describing from the header.  To add FX inserts, extract them from a
    reference .cst that already has the desired FX chain configured in MainStage.
"""

from __future__ import annotations
import re
import struct
from pathlib import Path

# Slot IDs that appear in baseline (no-FX) instrument channel strips.
# These represent the instrument plugin state and channel settings — NOT FX inserts.
# Any slot ID NOT in this set is treated as a candidate FX insert block when
# using inspect_cst().  graft_fx_chain() uses relative comparison instead
# (new IDs in fx_source vs instrument = FX), so this set is only used by inspect_cst.
_STANDARD_SLOT_IDS: frozenset[int] = frozenset({
    0x00d6,  # instrument plugin params (ES2, Alchemy, etc.)
    0x00d8,  # instrument plugin params (EVB3 / Logic B-3 organ)
    0x00dd,  # instrument plugin params (EVP88 / Logic electric piano)
    0x00ec,  # channel strip settings (universal)
    0x0094,  # channel state A
    0x009a,  # channel state B
    0x00b9,  # channel state (aux/bus strips)
    0x0091,  # channel state (reverb/aux bus strips)
    0x00e7,  # reverb/space designer state (bus return channels)
    0x0111,  # Logic B-3 organ extended state
    0x012c,  # arpeggiator / MIDI effect state
    0x0117,  # arpeggiator / MIDI effect state (variant)
})


# ── Low-level block parsing ───────────────────────────────────────────────────

def _find_bplist_start(data: bytes) -> int:
    """
    Return offset of the first standalone bplist00 — i.e. the first bplist
    that comes AFTER all GAME block markers.

    Logic/native instrument .cst files embed a bplist inside the large
    instrument GAMETSPP block.  We skip those embedded bplists by requiring
    the bplist to appear after the last 'GAME' marker in the file.
    """
    game_offsets = [m.start() for m in re.finditer(b'GAME', data)]
    last_game = max(game_offsets) if game_offsets else 0
    for m in re.finditer(b'bplist00', data):
        if m.start() > last_game:
            return m.start()
    raise ValueError("No standalone bplist00 found in .cst data")


def _parse_game_pairs(data: bytes) -> list[dict]:
    """
    Return a list of dicts, one per GAME block pair:
      slot_id   : int   — uint16 identifier
      hdr_start : int   — byte offset of the GAME\x00\x00\x00\x00 header
      data_start: int   — byte offset of the GAMETSPP block
      data_end  : int   — byte offset just past the GAMETSPP block
      hdr_bytes : bytes — 52-byte header block
      data_bytes: bytes — GAMETSPP block (tag + parameter data)
    """
    game_offsets = [m.start() for m in re.finditer(b'GAME', data)]
    bplist_start = _find_bplist_start(data)

    pairs = []
    i = 0
    while i < len(game_offsets):
        off = game_offsets[i]
        tag8 = data[off:off+8]

        if tag8 == b'GAME\x00\x00\x00\x00':
            slot_id = struct.unpack_from('<H', data, off + 8)[0]
            # Next GAME block (any) or bplist = end of this header
            nexts = [x for x in game_offsets if x > off] + [bplist_start]
            hdr_end = min(nexts)

            # The GAMETSPP immediately follows — find it
            tspp_off = hdr_end
            tspp_tag = data[tspp_off:tspp_off+8]
            if tspp_tag == b'GAMETSPP':
                # Find end of TSPP block
                after_tspp = [x for x in game_offsets + [bplist_start] if x > tspp_off]
                tspp_end = after_tspp[0] if after_tspp else len(data)
                pairs.append({
                    'slot_id':    slot_id,
                    'hdr_start':  off,
                    'data_start': tspp_off,
                    'data_end':   tspp_end,
                    'hdr_bytes':  data[off:hdr_end],
                    'data_bytes': data[tspp_off:tspp_end],
                })
                i += 2
                continue
        i += 1

    return pairs


# ── Public API ────────────────────────────────────────────────────────────────

def inspect_cst(cst: bytes | str | Path) -> dict:
    """
    Decode the structure of a .cst file.

    Returns a dict with keys:
      preamble_size   : int
      game_pairs      : list of {'slot_id': int, 'slot_id_hex': str, 'data_size': int, 'is_fx': bool}
      fx_slot_count   : int
      bplist_offsets  : list[int]
      smart_knob_labels: list[str]   (from WsPluginIdentity bplist)
      layout_name     : str | None
      key_zone        : dict | None  (lowNote, highNote, lowVelocity, highVelocity)
    """
    import plistlib

    data = Path(cst).read_bytes() if not isinstance(cst, bytes) else cst
    pairs = _parse_game_pairs(data)
    bplist_offsets = [m.start() for m in re.finditer(b'bplist00', data)]

    fx_slots = [p for p in pairs if p['slot_id'] not in _STANDARD_SLOT_IDS]

    # Decode WsPluginIdentity + WsKeyboardLayer from the bplists
    smart_knob_labels: list[str] = []
    layout_name: str | None = None
    key_zone: dict | None = None

    for bpoff in bplist_offsets:
        blob = data[bpoff:]
        for end in range(100, min(len(blob) + 1, 40000)):
            try:
                p = plistlib.loads(blob[:end])
                objs = p.get('$objects', [])
                cnames = [o.get('$classname', '') for o in objs if isinstance(o, dict)]

                if 'WsPluginIdentity' in cnames:
                    def _resolve(v):
                        return objs[v.data] if isinstance(v, plistlib.UID) else v

                    for o in objs:
                        if not isinstance(o, dict) or 'NS.keys' not in o:
                            continue
                        kv = {_resolve(k): _resolve(v)
                              for k, v in zip(o['NS.keys'], o['NS.objects'])}
                        if 'contentTagLayoutName' in kv:
                            v = kv['contentTagLayoutName']
                            if isinstance(v, str):
                                layout_name = v
                        # Smart knob custom labels: nested dicts with customLabel key
                        for val in kv.values():
                            val = _resolve(val) if isinstance(val, plistlib.UID) else val
                            if not isinstance(val, dict) or 'NS.keys' not in val:
                                continue
                            inner = {_resolve(k): _resolve(v)
                                     for k, v in zip(val['NS.keys'], val['NS.objects'])}
                            lbl = inner.get('customLabel')
                            if isinstance(lbl, str) and lbl not in smart_knob_labels:
                                smart_knob_labels.append(lbl)

                if 'WsKeyboardLayer' in cnames:
                    for o in objs:
                        if isinstance(o, dict) and 'highNote' in o:
                            key_zone = {
                                'lowNote':    o.get('lowNote', 0),
                                'highNote':   o.get('highNote', 127),
                                'lowVelocity':  o.get('lowVelocity', 1),
                                'highVelocity': o.get('highVelocity', 127),
                                'transpose':    o.get('transpose', 0),
                            }
                break
            except Exception:
                continue

    return {
        'preamble_size': pairs[0]['hdr_start'] if pairs else _find_bplist_start(data),
        'game_pairs': [
            {
                'slot_id':    p['slot_id'],
                'slot_id_hex': f"0x{p['slot_id']:04x}",
                'data_size':  len(p['data_bytes']),
                'is_fx':      p['slot_id'] not in _STANDARD_SLOT_IDS,
            }
            for p in pairs
        ],
        'fx_slot_count': len(fx_slots),
        'bplist_offsets': bplist_offsets,
        'smart_knob_labels': smart_knob_labels,
        'layout_name': layout_name,
        'key_zone': key_zone,
    }


def extract_fx_blocks(fx_source: bytes | str | Path) -> list[tuple[bytes, bytes]]:
    """
    Extract the FX insert blocks from a .cst file.

    Returns a list of (header_bytes, data_bytes) tuples for every GAME pair
    whose slot ID is not in the standard baseline set.  Each tuple can be
    injected into another .cst via inject_fx_blocks().
    """
    data = Path(fx_source).read_bytes() if not isinstance(fx_source, bytes) else fx_source
    pairs = _parse_game_pairs(data)
    return [
        (p['hdr_bytes'], p['data_bytes'])
        for p in pairs
        if p['slot_id'] not in _STANDARD_SLOT_IDS
    ]


def inject_fx_blocks(
    target: bytes | str | Path,
    fx_blocks: list[tuple[bytes, bytes]],
) -> bytes:
    """
    Insert FX GAME block pairs into a .cst, just before the bplists.

    *target*    — the instrument .cst to add FX to.
    *fx_blocks* — list of (header_bytes, data_bytes) as returned by extract_fx_blocks().

    Existing FX blocks in *target* (slot IDs not in the standard set) are
    removed before inserting the new ones, so this replaces rather than appends.
    If *fx_blocks* is empty the function returns *target* unchanged.

    Returns the modified .cst bytes.
    """
    if not fx_blocks:
        return target if isinstance(target, bytes) else Path(target).read_bytes()

    data = Path(target).read_bytes() if not isinstance(target, bytes) else target
    bplist_start = _find_bplist_start(data)

    # Strip existing FX pairs from target (keep only standard pairs)
    pairs = _parse_game_pairs(data)
    keep = [p for p in pairs if p['slot_id'] in _STANDARD_SLOT_IDS]

    if not keep:
        # No standard pairs found — fall back to inserting before bplists
        standard_region = data[:bplist_start]
    else:
        # Rebuild standard region: preamble + standard GAME pairs
        preamble_end = pairs[0]['hdr_start']
        standard_region = data[:preamble_end]
        for p in keep:
            standard_region += p['hdr_bytes'] + p['data_bytes']

    fx_region = b''.join(hdr + dat for hdr, dat in fx_blocks)
    bplists = data[bplist_start:]

    return standard_region + fx_region + bplists


def graft_fx_chain(
    instrument_cst: bytes | str | Path,
    fx_source_cst: bytes | str | Path,
) -> bytes:
    """
    Graft the FX insert chain from *fx_source_cst* into *instrument_cst*.

    "FX blocks" are identified relatively: any GAME pair whose slot ID appears
    in *fx_source_cst* but NOT in *instrument_cst*.  This avoids false positives
    when the two files share instrument-level slots.

    Typical use: you have a template for the instrument (e.g. Jun-6 V default
    state) and a reference .cst saved from MainStage with Chorus + Reverb FX
    already configured.  This function combines the instrument preset state
    with the FX chain from the reference.

    Returns the assembled .cst bytes (same as *instrument_cst* if the two
    files share all slot IDs, i.e. *fx_source_cst* has no extra slots).
    """
    inst_bytes = Path(instrument_cst).read_bytes() if not isinstance(instrument_cst, bytes) else instrument_cst
    fx_bytes = Path(fx_source_cst).read_bytes() if not isinstance(fx_source_cst, bytes) else fx_source_cst

    inst_pairs = _parse_game_pairs(inst_bytes)
    fx_pairs = _parse_game_pairs(fx_bytes)

    inst_ids = {p['slot_id'] for p in inst_pairs}
    extra_pairs = [p for p in fx_pairs if p['slot_id'] not in inst_ids]

    if not extra_pairs:
        return inst_bytes

    fx_blocks = [(p['hdr_bytes'], p['data_bytes']) for p in extra_pairs]
    return inject_fx_blocks(inst_bytes, fx_blocks)
