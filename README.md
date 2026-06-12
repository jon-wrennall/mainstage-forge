# mainstage-forge

Generate Apple MainStage `.concert` packages programmatically — from a setlist, a script, or an LLM via MCP.

There is no public API for MainStage. This library reverse-engineers the `.concert` package format (a plist-based directory tree) and the `.cst` channel-strip binary format to create fully loadable concerts — with pre-loaded Arturia (and other AU) instruments, Smart Control mappings, key zone splits, and FX chains — without touching the GUI.

## What it creates

A `.concert` package MainStage can open directly:

```
My Gig.concert/
├── data.plist               ← window/UI state
└── Concert.patch/
    ├── data.plist           ← concert-level channels (Master, Metronome, Output)
    ├── Master.cst
    ├── Metronome.cst
    ├── Output 1-2.cst
    └── Song A.patch/
        ├── data.plist       ← set-level node
        └── Keys.patch/
            ├── data.plist   ← patch with engineNode + channel entries
            ├── Piano V.cst  ← copied/patched from template library
            └── D50 Pad.cst
```

## What works

### Concert structure
- Sets (songs) and patches with correct `VersionPatches 40014` plist format
- Per-patch tempo (`hasTempo`), program change (`hasProgramChange` + `patchChangeNum`), and global transpose
- All required concert-level channel strips (Master, Metronome, Output 1-2) copied automatically
- `base.plistZ` and `workspace.layout/` seeded from real MainStage examples
- Finder `com.apple.FinderInfo` xattr set so macOS recognises the package

### Channel strips / instruments
- **Third-party AU plugins load correctly** — the `.cst` binary format has been reverse-engineered. Each channel strip embeds the AU component description (`manufacturer + type + subtype`) so MainStage loads the correct plugin (not just a name label).
- A **template library** of bundled `.cst` files ships with the package. Use a template name as `cst_source` and the library handles the rest:

| Template name | Plugin |
|---------------|--------|
| `OP-Xa V` | Arturia OP-Xa V |
| `OB-Xa V` | Arturia OB-Xa V |
| `Piano V3` | Arturia Piano V3 |
| `Jun-6 V` | Arturia Jun-6 V |
| `DX7 V` | Arturia DX7 V |
| `Jup-8 V4` | Arturia Jup-8 V4 |
| `Stage-73 V2` | Arturia Stage-73 V2 |
| `Alone` | Arturia (atmospheric preset) |
| `Grand Piano` | Logic Piano |
| `Classic Electric Piano` | Logic E-Piano |
| `Bass` | Logic Bass |
| `Bebop Organ` / `Oakland Organ` / `B-3 V2` | Logic B-3 |
| `Analog Spheres` | Logic ES2 |
| `D50 Pad` / `80s Sync Lead` / `80s FM Bass Attack` | Logic Alchemy |

- Any `.cst` file from an existing concert can be passed as an absolute path instead of a template name — lets you reuse presets with specific patch state (saved Arturia preset, knob positions, etc.)
- Multiple channels per patch with independent volume, pan, mute, and colour-index

### Key zone splits
Per-channel MIDI note range — `low_note` and `high_note` are patched directly into the `WsKeyboardLayer` bplist inside the `.cst` binary at build time:

```python
ch = p.add_channel("OB-Xa", "OB-Xa V")
ch.low_note = 48   # C3 and above only
ch.high_note = 127
```

### Smart Controls
Full Smart Control parameter mapping — knobs on the hardware Smart Controls panel (`Smart Knob N`) and custom on-screen controls (`Knob N`). Reverse-engineered from the `MAPlugInParameterMapping` NSKeyedArchiver format.

```python
# Standard Smart Knob (hardware panel knob 1–12)
p.add_smart_knob("Cutoff",    param_index=35, range_high=305)
p.add_smart_knob("Resonance", param_index=36, range_high=65)
p.add_smart_knob("Osc Mix",   param_index=26, range_is_flipped=True)

# On-screen Knob N — specify knob_number to target a specific slot
p.add_smart_knob("",  param_index=7,  identity_prefix="Knob", knob_number=3)
p.add_smart_knob("",  param_index=14, identity_prefix="Knob", knob_number=4)
```

Each knob maps to a channel by `channel_slot_index` (0 = first channel in the patch). Known parameter index tables for ES2 and Prophet-5 are in `smart_controls.py`.

### FX chain grafting
FX insert chains can be copied from a reference `.cst` file (saved from MainStage with the desired chain configured) and grafted into a template at build time:

```python
ch = p.add_channel("Lead", "80s Sync Lead")
ch.fx_source = "/path/to/reference/with-fx.cst"
```

`graft_fx_chain` identifies FX blocks by finding GAME block pairs present in the source but absent in the instrument template — making it robust to different instrument slot IDs.

### MCP tools
All tools are available to any MCP-compatible LLM client (Claude Desktop, etc.):

| Tool | Description |
|------|-------------|
| `build_concert` | Preview concert structure without writing files |
| `export_concert` | Generate a `.concert` from a flat setlist (empty patches) |
| `export_concert_advanced` | Generate with per-song tempo, multiple patches, program changes |
| `export_concert_with_instruments` | Generate with named instrument channels per patch |
| `copy_channel_strips` | Copy `.cst` files verbatim from an existing concert into a patch directory |
| `list_templates` | List all bundled template names |

## Install

```bash
pip install -e ".[dev]"
```

## Python API

```python
from mainstage_forge.models import Concert
from mainstage_forge.writer import write_concert

# Simple setlist — one empty patch per song
concert = Concert.from_setlist(
    "My Gig",
    ["Song 1", "Song 2", "Song 3"],
    patch_name="Main",
    tempo=120.0,
)
write_concert(concert, "~/Music/MainStage")

# With instruments, key zones, Smart Controls, and FX
concert = Concert(name="My Gig")

s = concert.add_set("Song 1", tempo=120.0)
p = s.add_patch("Synth Lead", has_tempo=True)

# Channel strip from a bundled template
ch = p.add_channel("Lead Synth", "Jun-6 V", volume=0.9)
ch.low_note = 60    # C4 and above (right-hand split)

# Second channel covering the bass range
ch2 = p.add_channel("Bass", "Bass")
ch2.high_note = 59  # below C4

# Smart Controls — standard hardware panel knobs
p.add_smart_knob("Cutoff",    channel_slot_index=0, param_index=35, range_high=305)
p.add_smart_knob("Resonance", channel_slot_index=0, param_index=36, range_high=65)
p.add_smart_knob("Osc Mix",   channel_slot_index=0, param_index=26, range_is_flipped=True)

# On-screen Knob N controls with explicit slot numbers
p.add_smart_knob("", channel_slot_index=0, param_index=7,  identity_prefix="Knob", knob_number=3)
p.add_smart_knob("", channel_slot_index=0, param_index=14, identity_prefix="Knob", knob_number=4)

s2 = concert.add_set("Song 2", tempo=130.0)
p2 = s2.add_patch("Keys + Pad", has_program_change=True, program_change_num=4)
p2.add_channel("Keys", "Piano V3")
p2.add_channel("Pad",  "Analog Spheres", volume=0.7)

# FX chain grafted from a reference .cst saved by MainStage
ch3 = p2.add_channel("FX Lead", "80s Sync Lead")
ch3.fx_source = "/path/to/reference-with-fx.cst"

write_concert(concert, "~/Music/MainStage", overwrite=True)
```

## MCP server

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mainstage-forge": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/mainstage-forge",
        "run", "mainstage_forge/server.py"
      ]
    }
  }
}
```

### Example prompt

> Create a MainStage concert called "My Gig" with three songs at 120, 130, and 110 BPM. Song 1: a lead patch with Jun-6 V split above C4 and Cutoff/Resonance Smart Controls. Song 2: a layered patch with Piano V3 and Analog Spheres (PC:4). Song 3: a bass patch with Bass channel only. Save to ~/Music/MainStage.

## Adding instruments to the template library

Templates are `.cst` files in `mainstage_forge/templates/`. To add a new plugin:

1. Open MainStage, add a channel strip with the desired plugin (any default patch)
2. Save the concert — MainStage writes the `.cst` with the correct AU component descriptor embedded
3. Copy the `.cst` to `mainstage_forge/templates/<Plugin Name>.cst`
4. The template name is the file stem — use it as `cst_source` in `add_channel()`

## Inspecting .cst files

`cst_tools.inspect_cst()` decodes the structure of any `.cst` file:

```python
from mainstage_forge.cst_tools import inspect_cst

info = inspect_cst("path/to/file.cst")
# info["game_pairs"]      — list of GAME block slot IDs and sizes
# info["fx_slot_count"]   — number of FX insert slots
# info["key_zone"]        — {'lowNote': 0, 'highNote': 127, ...}
# info["layout_name"]     — Smart Controls layout name
# info["smart_knob_labels"] — decoded custom knob labels
```

## Finding parameter indices

To find the `param_index` for any plugin parameter:

1. In MainStage, assign a Smart Knob to the parameter you want
2. Save the concert
3. Run:
```python
import plistlib
d = plistlib.load(open("path/to/patch/data.plist", "rb"))
pmm = d["patch"]["engineNode"]["parameterMappingMap"]["storeDict"]
raw = plistlib.loads(bytes(pmm["\x01IDENTITY:Smart Knob 1"]))
objs = raw["$objects"]
m = next(o for o in objs if isinstance(o, dict) and "parameterIndex_1" in o)
print("param_index:", objs[m["parameterIndex_1"].data])
```

Known tables in `smart_controls.py`: `ES2_PARAMS`, `JUN6V_PARAMS`, `PROPHET5_PARAMS`.

## Format notes

- `.concert` is a **directory package** — macOS shows it as a single file, it's a directory on disk
- `data.plist` files are Apple binary plists (inspect with `plutil -p`)
- `.cst` channel-strip presets are **proprietary binary**: OCuA header + GAME block pairs + NSKeyedArchiver bplists. Not a plist file — `plutil` cannot parse them.
- GAME block pairs encode plugin parameter arrays as raw IEEE 754 floats; the slot ID at byte offset 8 identifies the block type
- Tested against MainStage 3.6+ (VersionPatches 40014, OCuA format version 0x07)

## Tests

```bash
uv run pytest tests/ -v
```

33 tests across 4 files covering concert structure, plist correctness, template resolution, channel strip writing, Smart Controls, key zone patching, and FX chain grafting.

## Limitations

- **Preset state**: bundled templates load plugins at their default/init state. To load a specific saved preset, pass an absolute path to a `.cst` captured from MainStage after selecting that preset.
- **FX chain format**: FX plugin state is opaque binary. The graft approach copies FX blocks verbatim from a reference `.cst` — there is no way to configure individual FX parameters programmatically. Arturia and Logic GAMEMELC-format instruments are not compatible with GAME-block grafting.
- **No MIDI routing per channel**: channel MIDI input filtering (channel filter, transpose per strip) is not exposed.
- **No velocity layers**: `lowVelocity`/`highVelocity` in the key zone are preserved from the template but not yet configurable via the API.
- **MainStage must be closed** before loading a generated or modified concert (it does not hot-reload).
- **macOS only**: `.concert` packages are a macOS/MainStage format.

## Roadmap

- [x] Key-zone splits (high/low note) per channel
- [x] Smart Control knob mappings (Smart Knob N and Knob N)
- [x] FX chain grafting from reference `.cst`
- [ ] Velocity layer range per channel
- [ ] Per-channel MIDI transpose and channel filter
- [ ] Preset injection — patch specific Arturia/other preset state into a `.cst` without opening MainStage
