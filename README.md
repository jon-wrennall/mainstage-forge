# mainstage-forge

Generate Apple MainStage `.concert` packages programmatically — from a setlist, a script, or an LLM via MCP.

There is no public API for MainStage. This library reverse-engineers the `.concert` package format (a plist-based directory tree) and the `.cst` channel-strip binary format to create fully loadable concerts — with pre-loaded Arturia (and other AU) instruments — without touching the GUI.

Concerts can be generated with named instrument channels already assigned to each patch. A bundled template library covers common Arturia V-Collection plugins (OP-Xa V, Piano V3, Jun-6 V, DX7 V, Jup-8 V4) and Logic built-ins. Any `.cst` file saved by MainStage — with a specific preset dialled in — can be passed directly instead of a template.

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
            ├── Piano V.cst  ← copied from template library
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

| Template name | Plugin | AU code |
|---------------|--------|---------|
| `OP-Xa V` | Arturia OP-Xa V | `OBXa Artu` |
| `Piano V3` | Arturia Piano V3 | `Pia3 Artu` |
| `Jun-6 V` | Arturia Jun-6 V | `Jun1 Artu` |
| `DX7 V` | Arturia DX7 V | `Dx71 Artu` |
| `Jup-8 V4` | Arturia Jup-8 V4 | `JUP4 Artu` |
| `D50 Pad` | Logic Alchemy (D50 preset) | — |
| `Grand Piano` | Logic Piano | — |
| `Classic Electric Piano` | Logic E-Piano | — |
| `Bass` | Logic Bass | — |
| `Bebop Organ` / `Oakland Organ` | Logic B-3 | — |
| `Analog Spheres` | Logic ES2 | — |
| `80s Sync Lead` / `80s FM Bass Attack` | Logic Alchemy | — |

- Any `.cst` file from an existing concert can be passed as an absolute path instead of a template name — this lets you reuse presets with specific patch state (saved Arturia preset, knob positions, etc.)
- Multiple channels per patch with independent volume, pan, mute, and colour-index

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

# Simple setlist — empty patches
concert = Concert.from_setlist(
    "Edinburgh 2025-06-14",
    ["Intro", "Song 1", "Song 2", "Encore"],
    patch_name="Main",
    tempo=120.0,
)
write_concert(concert, "~/Music/MainStage")

# With instruments — using bundled templates
concert = Concert(name="Covers Night")
s = concert.add_set("Jump", tempo=138.0)
p = s.add_patch("OB-Xa Brass", has_tempo=True)
p.add_channel("OB-Xa", "OP-Xa V")          # loads Arturia OP-Xa V

s2 = concert.add_set("Here I Go Again", tempo=116.0)
p2 = s2.add_patch("Rock Piano + Pad", has_program_change=True, program_change_num=11)
p2.add_channel("Piano V", "Piano V3")       # loads Arturia Piano V3
p2.add_channel("D50 Pad", "D50 Pad")       # loads Logic Alchemy D50

# Using an absolute path to a .cst with saved preset state
p3 = s2.add_patch("Solo Piano")
p3.add_channel("Piano V", "/path/to/existing/Piano V.cst")

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

> Create a MainStage concert called "Covers Night" with three songs. Jump at 138 BPM with an OB-Xa Brass patch using OP-Xa V. Here I Go Again at 116 BPM with a Rock Piano patch on Piano V3 (PC:11). Don't You at 118 BPM with a Juno Arp patch on Jun-6 V (PC:1). Save to ~/Music/MainStage.

## Adding instruments to the template library

Templates are `.cst` files in `mainstage_forge/templates/`. To add a new plugin:

1. Open MainStage, add a channel strip with the desired plugin (any default patch)
2. Save the concert — MainStage writes the `.cst` with the correct AU component descriptor embedded
3. Copy the `.cst` to `mainstage_forge/templates/<Plugin Name>.cst`
4. The template name is the file stem — use it as `cst_source` in `add_channel()`

> **Important:** `.cst` files generated by older versions of this library (before the binary format was reverse-engineered) will load E-Piano instead of the intended plugin. Replace any such stubs with files generated by MainStage itself.

## Format notes

- `.concert` is a **directory package** — macOS shows it as a single file, it's a directory on disk
- `data.plist` files are Apple binary plists (inspect with `plutil -p`)
- `.cst` channel-strip presets are **proprietary binary** with an OCuA header, GAME chunks, NSKeyedArchiver bplists, and embedded XML plugin state
- The AU component description (`manufacturer/type/subtype`) is stored as 12 bytes (little-endian OSType codes) immediately following the 12-byte plugin name field in the binary header
- Tested against MainStage 3.6+ (VersionPatches 40014, OCuA format version 0x07)

## Tests

```bash
pytest
# or
uv run pytest tests/ -v
```

19 tests covering concert structure, plist correctness, template resolution, channel strip writing, and channel entries in generated plists.

## Limitations

- **Preset state**: bundled templates load plugins at their default/init state. To load a specific saved preset, pass an absolute path to a `.cst` captured from MainStage after selecting that preset.
- **No key-zone splits**: key range and velocity layers are not yet configurable — every channel responds to the full MIDI range.
- **No MIDI routing per channel**: channel MIDI input filtering (channel filter, transpose per strip) is not exposed.
- **No smart controls or screen controls**: Smart Control knob mappings and screen control layouts are not generated.
- **No audio effects chains**: FX plugins on a channel strip are not yet supported — only the instrument slot.
- **MainStage must be closed** before loading a generated or modified concert (it does not hot-reload).
- **macOS only**: `.concert` packages are a macOS/MainStage format.

## Roadmap

- [ ] Key-zone splits (high/low note, velocity range) per channel
- [ ] Per-channel MIDI transpose and channel filter
- [ ] Smart control knob layouts
- [ ] Audio effects chain on channel strips
- [ ] Preset injection — patch specific Arturia/other preset state into a `.cst` without opening MainStage
