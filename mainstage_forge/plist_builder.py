"""Build the plist structures that MainStage expects for each level of the hierarchy."""

from __future__ import annotations
from typing import Any


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
        "midiClockPort": 0,
        "name": name,
        "patchChangeNum": 0,
        "programChangeChannel": 0,
        "programChangePort": 0,
        "sendThruProgramChanges": False,
        "smartControlsTabIndex": 0,
        "tempo": float(tempo),
        "tuning": 440.0,
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
        "LocalBusses": [],
        "patchMappings": {},
        "selected": False,
        "virtualMappings": {},
    }


def concert_root_plist(name: str, tempo: float = 120.0, child_names: list[str] | None = None) -> dict:
    """data.plist for Concert.patch/ (concert level)."""
    return {
        "VersionPatches": VERSION_PATCHES,
        "Patch_isPasteboardType": False,
        "channels": [],
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
        "channels": [],
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
