# mainstage-forge

Generate Apple MainStage `.concert` packages programmatically — from a setlist, a script, or an LLM via MCP.

There is no public API for MainStage. This library reverse-engineers the `.concert` package format (plist-based directory tree) to create fully loadable concerts without touching the GUI.

## What it creates

A `.concert` package MainStage can open directly:

```
My Gig.concert/
├── data.plist               ← window/UI state
└── Concert.patch/
    ├── data.plist           ← concert-level channels
    ├── Song A.patch/
    │   ├── data.plist       ← set-level channels
    │   └── Main.patch/
    │       └── data.plist   ← patch with full engineNode
    └── Song B.patch/
        └── ...
```

Generated concerts have **empty channel strips** (no instruments). Open in MainStage and add your own. Use `copy_channel_strips` / `clone_channel_strips()` to copy `.cst` presets from an existing concert.

## Install

```bash
pip install -e ".[dev]"
```

## Python API

```python
from mainstage_forge.models import Concert
from mainstage_forge.writer import write_concert

# Simple — one patch per song
concert = Concert.from_setlist(
    "Edinburgh 2025-06-14",
    ["Intro", "Song 1", "Song 2", "Encore"],
    patch_name="Main",
    tempo=120.0,
)
write_concert(concert, "~/Music/MainStage")

# Advanced — multiple patches, per-song tempo
concert = Concert(name="Wembley Night 1")
s = concert.add_set("Song 1", tempo=128.0)
s.add_patch("Keys", has_tempo=True)
s.add_patch("Synth Lead", global_transpose=-2)
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

### Available tools

| Tool | Description |
|------|-------------|
| `build_concert` | Preview concert structure (no files written) |
| `export_concert` | Generate a `.concert` from a flat setlist |
| `export_concert_advanced` | Generate with per-song tempo and multiple patches |
| `copy_channel_strips` | Copy `.cst` presets from an existing concert into a patch |

### Example prompt

> Create a MainStage concert called "London Gig" for songs: Intro, Song 1, Song 2, Song 3, Encore. Save it to ~/Music/MainStage.

## Format notes

- `.concert` is a **directory package**, not a single file
- `data.plist` files are standard Apple XML plists (readable with `plutil`)
- `.cst` channel strip presets are **proprietary binary** — cannot be generated from scratch, only copied from existing concerts
- `base.plistZ` (selection state) and `workspace.layout/` (screen controls) are optional and can be omitted
- Tested against MainStage 3.6+ format (VersionPatches 40014)

## Tests

```bash
pytest
```

## Limitations

- No instrument/plugin generation (`.cst` is proprietary)
- No screen controls or MIDI mappings
- No smart controls
- Concert must be closed in MainStage before loading a generated file

## Roadmap

- [ ] Template concerts — clone full channel strip structure from an existing concert
- [ ] MIDI program change mapping
- [ ] Per-patch key range splits
- [ ] Smart control layouts
