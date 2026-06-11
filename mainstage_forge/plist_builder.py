"""Build the plist structures that MainStage expects for each level of the hierarchy."""

from __future__ import annotations
from typing import Any

# instID values for software instrument slots 1-N (multiples of 4 starting at 104)
_INST_IDS = [104, 108, 112, 116, 120, 124, 128, 132]


VERSION_PATCHES = 40014


def _base_engine_node(name: str, tempo: float = 120.0, **overrides) -> dict:
    """Minimal engineNode dict that MainStage accepts for any patch/set/concert level."""
    node: dict[str, Any] = {
        "TimeSignatureDenominator": 2,
        "TimeSignatureNumerator": 4,
        "Metronome_BarEnabled": True,
        "Metronome_BarNote": 91,
        "Metronome_BarVelocity": 127,
        "Metronome_BeatEnabled": True,
        "Metronome_BeatNote": 84,
        "Metronome_BeatVelocity": 112,
        "Metronome_DivEnabled": False,
        "Metronome_DivNote": 46,
        "Metronome_DivVelocity": 60,
        "Metronome_Division": 4,
        "Metronome_GroupEnabled": False,
        "Metronome_GroupNote": 63,
        "Metronome_GroupVelocity": 119,
        "Metronome_PolyphonicClicksEnabled": False,
        "bankOffset": 0,
        "bankSelectNumber": 0,
        "defersPatchChange": False,
        "disabled": False,
        "faderStatForVolAndPan": False,
        "abletonLinkEnabled": False,
        "abletonLinkStartStopEnabled": False,
        "followMIDITempo": False,
        "globalTranspose": 0,
        "hasBankSelect": False,
        "hasCustomLayout": False,
        "hasFolderColor": False,
        "hasProgramChange": False,
        "hasTempo": False,
        "hasTimeSignature": False,
        "imageNameForSetFolder": "icon_patchlist_set",
        "instantlyKillsPatches": False,
        "midiCCsHardwired": False,
        "midiClockPort": {"uniqueIDType": 0, "uniqueID": 0},
        "name": name,
        "patchChangeNum": 0,
        "programChangeChannel": 0,
        "programChangePort": {"uniqueIDType": 0, "uniqueID": 0},
        "sendThruProgramChanges": False,
        "smartControlsTabIndex": 0,
        "tempo": float(tempo),
        "tuning": {
            "tuningMode": 0, "hermodeType": 18, "hermodeDepth": 100,
            "userRootKey": 0, "presetRootKey": 0,
            "userStretchUpper": 0.0, "userStretchLower": 0.0,
            "user0": 0.0, "user1": 0.0, "user2": 0.0, "user3": 0.0,
            "user4": 0.0, "user5": 0.0, "user6": 0.0, "user7": 0.0,
            "user8": 0.0, "user9": 0.0, "user10": 0.0, "user11": 0.0,
        },
        "parameterMappingMap": {
            "containsDictionary": {},
            "overrideDict": {},
            "storeDict": {},
        },
        "uiPluginDataDict": {},
    }
    node.update(overrides)
    return node


def _patch_wrapper(engine_node: dict) -> dict:
    """Wrap an engineNode in the 'patch' dict that data.plist expects."""
    return {
        "engineNode": engine_node,
        "expanded": False,
        "iconID": 4098,
        "LocalBusses": [],
        "patchMappings": {},
        "selected": False,
        "virtualMappings": {},
    }


_REQUIRED_CHANNELS = [
    {
        "Channel_chaStrCategory": "",
        "Channel_chaStrName": "",
        "Channel_expressionValue": 127,
        "Channel_inputIndex_1": -1,
        "Channel_inputIsBus": False,
        "Channel_instID": 92,
        "Channel_isMuted": False,
        "Channel_isSolo": False,
        "Channel_name": "Master",
        "Channel_outputIndex": -1,
        "Channel_outputIsBus": False,
        "Channel_pan": 0.0,
        "Channel_seqColorIndex": 20,
        "Channel_userDidModifySmartControls": False,
        "Custom_icon": 4098,
        "Custom_name": False,
        "Filename": "Master.cst",
        "Root": False,
        "Track_icon": 4400,
        "UUID": "FDF68CCF-20BD-4EC2-B38D-4DFC0D059678",
        "volume": 1509949440,
    },
    {
        "Channel_chaStrCategory": "",
        "Channel_chaStrName": "",
        "Channel_expressionValue": 127,
        "Channel_inputIndex_1": -1,
        "Channel_inputIsBus": False,
        "Channel_instID": 96,
        "Channel_isMetronome": True,
        "Channel_isMuted": False,
        "Channel_isSolo": False,
        "Channel_name": "Metronome",
        "Channel_outputIndex": 0,
        "Channel_outputIsBus": False,
        "Channel_outputIsStereo": True,
        "Channel_pan": 0.0,
        "Channel_seqColorIndex": 9,
        "Channel_userDidModifySmartControls": False,
        "Custom_icon": 4098,
        "Custom_name": False,
        "Filename": "Metronome.cst",
        "Root": False,
        "Track_icon": 4505,
        "UUID": "59835CF4-C0EE-47B5-9984-8AA9C562C6DA",
        "volume": 1509949440,
    },
    {
        "Channel_chaStrCategory": "",
        "Channel_chaStrName": "",
        "Channel_expressionValue": 0,
        "Channel_inputIndex_1": -1,
        "Channel_inputIsBus": False,
        "Channel_instID": 88,
        "Channel_isMuted": False,
        "Channel_isSolo": False,
        "Channel_name": "Output 1-2",
        "Channel_outputIndex": -1,
        "Channel_outputIsBus": False,
        "Channel_outputIsStereo": True,
        "Channel_pan": 0.0,
        "Channel_seqColorIndex": 24,
        "Channel_userDidModifySmartControls": False,
        "Custom_icon": 4098,
        "Custom_name": False,
        "Filename": "Output 1-2.cst",
        "Root": False,
        "Track_icon": 4400,
        "UUID": "417DB2D4-FA48-4838-B791-96A2A06165D1",
        "volume": 1509949440,
    },
]


def _volume_to_raw(v: float) -> int:
    """Convert 0.0–1.0 linear volume to MainStage's packed-float int (1.0 = 1509949440)."""
    import struct
    clamped = max(0.0, min(1.0, v))
    return struct.unpack(">I", struct.pack(">f", clamped))[0]


def instrument_channel_entry(
    name: str,
    filename: str,
    slot_index: int,
    uuid: str,
    volume: float = 1.0,
    pan: float = 0.0,
    muted: bool = False,
    color_index: int = 33,
) -> dict:
    """
    Build a channel entry dict for a software instrument slot.

    *slot_index* is 0-based (0 → instID 104, 1 → 108, etc.).
    *filename* is the basename of the .cst file (e.g. "Grand Piano.cst").
    """
    inst_id = _INST_IDS[slot_index] if slot_index < len(_INST_IDS) else 104 + slot_index * 4
    return {
        "Channel_chaStrCategory": "",
        "Channel_chaStrName": "",
        "Channel_expressionValue": 127,
        "Channel_filterAftertouch": False,
        "Channel_filterExpression": False,
        "Channel_filterHermodeTuning": False,
        "Channel_filterModulation": False,
        "Channel_filterPitchBend": False,
        "Channel_filterSustainPedal": False,
        "Channel_inputIndex_1": -1,
        "Channel_inputIsBus": False,
        "Channel_instID": inst_id,
        "Channel_isMuted": muted,
        "Channel_isSolo": False,
        "Channel_name": name,
        "Channel_outputIndex": 0,
        "Channel_outputIsBus": False,
        "Channel_outputIsStereo": True,
        "Channel_pan": float(pan),
        "Channel_sends": [{}, {}],
        "Channel_seqColorIndex": color_index,
        "Channel_userDidModifySmartControls": False,
        "Custom_icon": 4098,
        "Custom_name": True,
        "Filename": filename,
        "MIDITransform": {"hermode": False, "transforms": [{"filter": True, "in": -7}]},
        "Root": False,
        "Track_icon": 4505,
        "UUID": uuid,
        "volume": _volume_to_raw(volume),
    }


def concert_root_plist(name: str, tempo: float = 120.0, child_names: list[str] | None = None) -> dict:
    """data.plist for Concert.patch/ (concert level)."""
    return {
        "VersionPatches": VERSION_PATCHES,
        "Patch_isPasteboardType": False,
        "channels": list(_REQUIRED_CHANNELS),
        "nodes": [f"{n}.patch" for n in (child_names or [])],
        "patch": _patch_wrapper(_base_engine_node(name, tempo=tempo)),
    }


def set_plist(name: str, tempo: float = 120.0, child_names: list[str] | None = None) -> dict:
    """data.plist for a {Set}.patch/ directory."""
    return {
        "VersionPatches": VERSION_PATCHES,
        "channels": [],
        "nodes": [f"{n}.patch" for n in (child_names or [])],
        "patch": _patch_wrapper(
            _base_engine_node(name, tempo=tempo, imageNameForSetFolder="icon_patchlist_set")
        ),
    }


def patch_plist(
    name: str,
    tempo: float = 120.0,
    has_tempo: bool = False,
    has_program_change: bool = False,
    program_change_num: int = 0,
    global_transpose: int = 0,
    icon_id: int | None = None,
    channel_entries: list[dict] | None = None,
) -> dict:
    """data.plist for a leaf {Patch}.patch/ directory."""
    overrides: dict[str, Any] = {
        "globalTranspose": global_transpose,
        "hasProgramChange": has_program_change,
        "hasTempo": has_tempo,
        "patchChangeNum": program_change_num,
        "selected": False,
    }
    if icon_id is not None:
        overrides["iconID"] = icon_id

    engine_node = _base_engine_node(name, tempo=tempo, **overrides)
    wrapper = _patch_wrapper(engine_node)
    wrapper["selected"] = False
    wrapper["patchPath"] = f"@BASE@/MainStage/{name}.patch"

    return {
        "VersionPatches": VERSION_PATCHES,
        "channels": list(channel_entries or []),
        "patch": wrapper,
    }


def concert_data_plist() -> dict:
    """data.plist at the concert root (stores UI/window state)."""
    return {
        "Document Subview Sizes": {
            "Assignment Column Width": 1.0,
            "Mapping Column Width": 1.0,
            "Screen Control Column Width": 1.0,
            "bottom center view size": 296.0,
            "bottom center view size layout": 164.0,
            "bottom left view size for QuickHelp": 277.0,
            "bottom left view size for QuickHelp layout": 310.0,
            "left view size": 277.0,
            "left view size layout": 310.0,
            "right view size": 428.0,
            "right view size layout": 428.0,
        },
        "Document Window Frame": "0 129 1512 815 0 0 1512 944 ",
        "Document_TypeCount": {
            "Input Mono": 18,
            "Input Stereo": 9,
            "Output Mono": 18,
            "Output Stereo": 9,
        },
        "Document_faderStatForVolAndPan": False,
        "Document_panLaw": 0,
        "Document_passThroughUnmappedControlEvents": True,
        "Document_sendThruProgramChanges": True,
        "LogicPropertyAssetFlags": 1,
        "Version": 55057,
    }
