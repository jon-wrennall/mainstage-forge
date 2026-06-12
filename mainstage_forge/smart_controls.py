"""
Build NSKeyedArchiver bplists for MainStage Smart Control parameter mappings.

Smart Controls appear as the row of knobs/faders at the bottom of the MainStage
workspace. Each Smart Knob can be mapped to a plugin parameter by:
  - label    : display name on screen
  - inst_id  : Channel_instID of the target instrument strip (e.g. 104, 108, ...)
  - param_index : 0-based parameter index within that plugin (plugin-specific)
  - range_low / range_high : clamp range (-1 = plugin default)

The mapping data is stored in the patch data.plist under:
  patch > engineNode > parameterMappingMap > storeDict > "\x01IDENTITY:Smart Knob N"

Labels are stored in:
  patch > engineNode > uiPluginDataDict > "\x01IDENTITY:Smart Knob N" > storeDict > customLabel
"""

from __future__ import annotations
import plistlib
import re
import struct


# Deterministic but unique value per knob — used as WsMutableController.value.
# MainStage requires a non-zero unique int per controller instance.
def _knob_value(knob_number: int, identity_prefix: str = "Smart Knob") -> int:
    import hashlib
    h = hashlib.md5(f"{identity_prefix} {knob_number}".encode()).digest()
    return int.from_bytes(h[:4], "little") & 0x7FFFFFFF or knob_number * 10_000_007


def build_parameter_mapping_bplist(
    inst_id: int,
    param_index: int,
    knob_number: int,
    range_low: int = -1,
    range_high: int = -1,
    range_is_flipped: bool = False,
    identity_prefix: str = "Smart Knob",
) -> bytes:
    """
    Return the NSKeyedArchiver bplist for one Smart Knob → plugin parameter mapping.

    Args:
        inst_id:          Channel_instID of the target instrument strip (e.g. 104).
        param_index:      0-based parameter index inside the plugin.
        knob_number:      1-based knob number.
        range_low:        Lower value clamp (-1 = plugin min).
        range_high:       Upper value clamp (-1 = plugin max).
        range_is_flipped: True to invert the knob direction.
    """
    nsmutabledict_class = {
        "$classname": "NSMutableDictionary",
        "$classes": ["NSMutableDictionary", "NSDictionary", "NSObject"],
    }
    wsmutable_class = {
        "$classname": "WsMutableController",
        "$classes": ["WsMutableController", "NSObject"],
    }
    maChannelID_class = {
        "$classname": "MAChannelID",
        "$classes": ["MAChannelID", "NSObject"],
    }
    mapping_class = {
        "$classname": "MAPlugInParameterMapping",
        "$classes": ["MAPlugInParameterMapping", "MAMappingBase", "NSObject"],
    }
    nsmutablearray_class = {
        "$classname": "NSMutableArray",
        "$classes": ["NSMutableArray", "NSArray", "NSObject"],
    }

    # $objects array — UID indices are hard-coded to match this layout:
    #   [0]  $null
    #   [1]  NSMutableArray wrapper (root)
    #   [2]  MAPlugInParameterMapping (the mapping)
    #   [3]  range_low integer
    #   [4]  range_high integer
    #   [5]  0  (slot / aliasIndex)
    #   [6]  WsMutableController (inputControlEvent = "which Smart Knob")
    #   [7]  MIDIPort dict
    #   [8]  "uniqueIDType" string
    #   [9]  "uniqueID" string
    #   [10] NSMutableDictionary class descriptor
    #   [11] WsMutableController class descriptor
    #   [12] MAChannelID (channelID)
    #   [13] 2  (channel type)
    #   [14] param_index integer
    #   [15] MAChannelID class descriptor
    #   [16] MAPlugInParameterMapping class descriptor
    #   [17] NSMutableArray class descriptor

    U = plistlib.UID

    objects = [
        "$null",
        {"NS.objects": [U(2)], "$class": U(17)},
        {
            "parameterIndex_1": U(14),
            "kGInstIDKey": inst_id,
            "channelID": U(12),
            "slot": U(5),
            "inputControlEvent": U(6),
            "kSavedValueFloatKey": 0.0,
            "kSavedValueDoubleKey": 0.0,
            "kHasSavedValueKey": False,
            "kIsNewSavedValueKey": True,
            "wasAutoset": False,
            "isMIDIPlugIn": False,
            "momentaryType": False,
            "takeVelocity": False,
            "rangeIsFlipped": range_is_flipped,
            "kFilterMappingKey": False,
            "kDiscreteStepsKey": False,
            "kDisplayIndexKey": 0,
            "kDisplayParameterValueAsPercentageKey": False,
            "kMappingCreatedFromSmartMapKey": False,
            "kRangeMappingModeKey": 0,
            "rangeHigh": U(4),
            "rangeLow": U(3),
            "$class": U(16),
        },
        range_low,
        range_high,
        0,
        {
            "timeStamp": 0,
            "mb3": 0,
            "controllerTag": "$null",
            "maxValue": 2130706432,
            "isBaseplate": False,
            "channelID": 0,
            "type": 5,       # 5 = Smart Knob (on-screen controller)
            "minValue": 0,
            "value": _knob_value(knob_number, identity_prefix),
            "MIDIPort": U(7),
            "controllerID": -256,  # -256 = no MIDI CC assigned
            "bits": 7,
            "steps": 128,
            "$class": U(11),
        },
        {
            "NS.keys": [U(8), U(9)],
            "NS.objects": [0, -1],
            "$class": U(10),
        },
        "uniqueIDType",
        "uniqueID",
        nsmutabledict_class,
        wsmutable_class,
        {
            "aliasIndex": U(5),
            "type": U(13),
            "index": U(14),
            "$class": U(15),
        },
        2,           # channel type
        param_index,
        maChannelID_class,
        mapping_class,
        nsmutablearray_class,
    ]

    return plistlib.dumps(
        {
            "$version": 100000,
            "$archiver": "NSKeyedArchiver",
            "$top": {"root": U(1)},
            "$objects": objects,
        },
        fmt=plistlib.FMT_BINARY,
    )


def build_parameter_mapping_map(
    knobs: list[tuple],
) -> dict:
    """
    Build the full parameterMappingMap dict for a patch's engineNode.

    Args:
        knobs: list of (knob_number, inst_id, param_index, range_low, range_high)
               or (knob_number, inst_id, param_index, range_low, range_high, identity_prefix)
               where identity_prefix is "Smart Knob" (default) or "Knob".

    Returns:
        Dict ready to insert as engineNode['parameterMappingMap'].
    """
    contains: dict = {}
    store: dict = {}
    for entry in knobs:
        knob_num, inst_id, param_idx, rl, rh = entry[:5]
        prefix = entry[5] if len(entry) > 5 else "Smart Knob"
        flipped = entry[6] if len(entry) > 6 else False
        key = f"\x01IDENTITY:{prefix} {knob_num}"
        # containsDictionary only tracks Smart Knob (hardware panel) entries,
        # not custom on-screen Knob N controls.
        if prefix == "Smart Knob":
            contains[key] = True
        blob = build_parameter_mapping_bplist(
            inst_id=inst_id,
            param_index=param_idx,
            knob_number=knob_num,
            range_low=rl,
            range_high=rh,
            range_is_flipped=flipped,
            identity_prefix=prefix,
        )
        store[key] = blob

    return {
        "containsDictionary": contains,
        "storeDict": store,
        "overrideDict": {},
    }


def build_ui_plugin_data_dict(knobs: list[tuple]) -> dict:
    """
    Build the uiPluginDataDict entries for Smart Knob labels.

    Args:
        knobs: list of (knob_number, label_string)
               or (knob_number, label_string, identity_prefix)
               where identity_prefix is "Smart Knob" (default) or "Knob".

    Returns:
        Dict to merge into engineNode['uiPluginDataDict'].
    """
    result: dict = {}
    for entry in knobs:
        knob_num, label = entry[:2]
        prefix = entry[2] if len(entry) > 2 else "Smart Knob"
        key = f"\x01IDENTITY:{prefix} {knob_num}"
        # Knob N controls with no custom label use empty storeDict/containsDictionary
        if label:
            store = {"customLabel": label}
            contains = {"customLabel": True}
        else:
            store = {}
            contains = {}
        result[key] = {
            "identity": key,
            "storeDict": store,
            "overrideDict": {},
            "containsDictionary": contains,
            "containsBasedOnMappingExistence": {},
        }
    return result


# ── Known parameter index tables ─────────────────────────────────────────────
#
# These were extracted by decoding the Smart Control mappings in Apple's
# "Example 80s" concert (Ambient Lead patch → ES2 synthesizer).
# Use them as param_index when calling add_smart_knob() with Logic ES2 channels.
#
# To find parameter indices for other plugins:
#   1. In MainStage, assign a Smart Knob to the parameter you want
#   2. Save the concert
#   3. Run: python3 -c "
#      import plistlib
#      d = plistlib.load(open('path/to/patch/data.plist','rb'))
#      pmm = d['patch']['engineNode']['parameterMappingMap']['storeDict']
#      raw = plistlib.loads(bytes(pmm['\x01IDENTITY:Smart Knob 1']))
#      objs = raw['\$objects']
#      m = next(o for o in objs if isinstance(o,dict) and 'parameterIndex_1' in o)
#      print('param_index:', objs[m['parameterIndex_1'].data])
#      "

ES2_PARAMS = {
    # Extracted from Example 80s concert (Ambient Lead patch, instID=140)
    "glide":       6,
    "cutoff":     35,
    "resonance":  36,
    "flanger":   120,
    "ambience":   28,   # baseplate reverb send
    "detune":      2,
    "attack":    107,
    "release":   112,
    "delay":       0,   # baseplate delay send
    "reverb":     29,   # baseplate reverb amount
}

JUN6V_PARAMS = {
    # Extracted from Example 80s concert (Square Bells patch — Jun-6 V, instID=392)
    # Knob 3 → paramIdx 7, Knob 4 → paramIdx 14, Knob 5 → paramIdx 15
    "param_7":    7,
    "param_14":  14,
    "param_15":  15,
}

# Channel_instID values for known plugin types.
# instID is assigned by MainStage based on slot index: slots 1-8 get 104,108,112,...
# A Jun-6 V at an unusually high slot (e.g. slot 73) gets instID 392.
# For programmatic use, instID is derived from channel position, not plugin identity.
# These constants are for reference when hard-coding cross-patch knob mappings.
INST_ID_SLOT1  = 104   # First instrument channel strip
INST_ID_SLOT2  = 108   # Second
INST_ID_SLOT3  = 112   # Third
INST_ID_SLOT4  = 116
INST_ID_SLOT5  = 120
INST_ID_SLOT6  = 124
INST_ID_SLOT7  = 128
INST_ID_SLOT8  = 132

def patch_cst_key_zone(src: bytes, low_note: int, high_note: int) -> bytes:
    """
    Return a copy of a .cst binary with the WsKeyboardLayer lowNote/highNote replaced.

    The key zone is stored in the last NSKeyedArchiver bplist inside the .cst file.
    Only modifies lowNote and highNote; all other fields (velocity range, transpose,
    color, etc.) are preserved from the original.

    Raises ValueError if no WsKeyboardLayer bplist is found in the file.
    """
    # Find the bplist that contains WsKeyboardLayer
    bplist_offset = None
    bplist_len = None
    for m in re.finditer(b'bplist00', src):
        off = m.start()
        blob = src[off:]
        for end in range(200, min(len(blob) + 1, 4000)):
            try:
                p = plistlib.loads(blob[:end])
                objs = p.get('$objects', [])
                has_layer = any(
                    isinstance(o, dict) and o.get('$classname') == 'WsKeyboardLayer'
                    for o in objs
                )
                if has_layer:
                    bplist_offset = off
                    bplist_len = end
                    break
            except Exception:
                continue
        if bplist_offset is not None:
            break

    if bplist_offset is None:
        raise ValueError("No WsKeyboardLayer bplist found in .cst file")

    # Parse and update
    blob = src[bplist_offset : bplist_offset + bplist_len]
    p = plistlib.loads(blob)
    objs = p['$objects']
    for i, o in enumerate(objs):
        if isinstance(o, dict) and 'highNote' in o:
            objs[i] = dict(o, lowNote=low_note, highNote=high_note)
            break

    new_blob = plistlib.dumps(p, fmt=plistlib.FMT_BINARY)
    return src[:bplist_offset] + new_blob + src[bplist_offset + bplist_len:]


PROPHET5_PARAMS = {
    # Extracted from Example 80s concert (Eighties Poly Synth patch, instID=388)
    "filter_frequency": 20,
    "filter_resonance": 21,
}
