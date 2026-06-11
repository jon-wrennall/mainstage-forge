"""MCP server exposing mainstage-forge tools."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

try:
    from .models import Concert, Set, Patch, ChannelStrip, TEMPLATES
    from .writer import write_concert, clone_channel_strips
except ImportError:
    from mainstage_forge.models import Concert, Set, Patch, ChannelStrip, TEMPLATES
    from mainstage_forge.writer import write_concert, clone_channel_strips

mcp = FastMCP(
    "mainstage-forge",
    instructions=(
        "Tools for generating Apple MainStage .concert packages. "
        "Use build_concert to preview structure, export_concert to write to disk. "
        "MainStage must be closed when loading a generated concert."
    ),
)


@mcp.tool()
def build_concert(
    concert_name: str,
    setlist: list[str],
    patch_name: str = "Main",
    tempo: float = 120.0,
) -> dict:
    """
    Preview a concert structure from a list of song names.

    Each song becomes a Set with one Patch named *patch_name*.
    Returns a summary — does not write any files.

    Args:
        concert_name: Name of the concert (e.g. "Edinburgh 2025-06-14")
        setlist: Ordered list of song names
        patch_name: Name for the default patch in each song (default "Main")
        tempo: Default BPM for all patches (default 120)
    """
    concert = Concert.from_setlist(concert_name, setlist, patch_name=patch_name, tempo=tempo)
    return {
        "concert_name": concert.name,
        "tempo": concert.tempo,
        "set_count": len(concert.sets),
        "sets": [
            {
                "name": s.name,
                "patches": [p.name for p in s.patches],
            }
            for s in concert.sets
        ],
    }


@mcp.tool()
def export_concert(
    concert_name: str,
    setlist: list[str],
    output_dir: str,
    patch_name: str = "Main",
    tempo: float = 120.0,
    overwrite: bool = False,
) -> dict:
    """
    Generate a MainStage .concert package on disk and return its path.

    The resulting .concert can be opened directly in MainStage. It will contain
    empty patches (no instruments) — add channel strips in MainStage after loading.

    Args:
        concert_name: Name of the concert
        setlist: Ordered list of song names
        output_dir: Directory to write the .concert package into
        patch_name: Name for the default patch in each song (default "Main")
        tempo: Default BPM (default 120)
        overwrite: Replace existing .concert if present (default False)
    """
    concert = Concert.from_setlist(concert_name, setlist, patch_name=patch_name, tempo=tempo)
    path = write_concert(concert, output_dir, overwrite=overwrite)
    files = [str(p.relative_to(path.parent)) for p in path.rglob("*")]
    return {
        "concert_path": str(path),
        "set_count": len(concert.sets),
        "patch_count": sum(len(s.patches) for s in concert.sets),
        "files_created": sorted(files),
    }


@mcp.tool()
def export_concert_advanced(
    concert_name: str,
    sets: list[dict],
    output_dir: str,
    default_tempo: float = 120.0,
    overwrite: bool = False,
) -> dict:
    """
    Generate a concert with per-song patch customisation.

    Each item in *sets* is a dict with:
      - name (str): song name
      - tempo (float, optional): song BPM
      - patches (list of dicts, optional): each with:
          - name (str)
          - tempo (float, optional)
          - has_tempo (bool, optional)
          - program_change_num (int, optional)
          - has_program_change (bool, optional)
          - global_transpose (int, optional, semitones)

    Example sets value:
        [
          {"name": "Song A", "tempo": 130, "patches": [{"name": "Keys"}, {"name": "Bass"}]},
          {"name": "Song B", "patches": [{"name": "Main"}]}
        ]
    """
    concert = Concert(name=concert_name, tempo=default_tempo)
    for s_data in sets:
        s = concert.add_set(s_data["name"], tempo=s_data.get("tempo", default_tempo))
        for p_data in s_data.get("patches", [{"name": "Main"}]):
            s.patches.append(
                Patch(
                    name=p_data.get("name", "Main"),
                    tempo=p_data.get("tempo", s.tempo),
                    has_tempo=p_data.get("has_tempo", False),
                    has_program_change=p_data.get("has_program_change", False),
                    program_change_num=p_data.get("program_change_num", 0),
                    global_transpose=p_data.get("global_transpose", 0),
                )
            )
    path = write_concert(concert, output_dir, overwrite=overwrite)
    files = [str(p.relative_to(path.parent)) for p in path.rglob("*")]
    return {
        "concert_path": str(path),
        "set_count": len(concert.sets),
        "patch_count": sum(len(s.patches) for s in concert.sets),
        "files_created": sorted(files),
    }


@mcp.tool()
def copy_channel_strips(
    source_concert_path: str,
    target_patch_path: str,
    strip_names: Optional[list[str]] = None,
) -> dict:
    """
    Copy .cst channel-strip presets from an existing concert into a patch directory.

    MainStage .cst files are proprietary binary — this copies them verbatim,
    allowing you to reuse instruments from an existing concert in a new one.

    Args:
        source_concert_path: Path to the source .concert package
        target_patch_path: Path to the destination patch directory inside a .concert
        strip_names: If given, only copy strips whose filename stem matches (e.g. ["Piano", "Bass"])
    """
    copied = clone_channel_strips(source_concert_path, target_patch_path, strip_names)
    return {
        "copied": [str(p) for p in copied],
        "count": len(copied),
    }


@mcp.tool()
def list_templates() -> dict:
    """
    List the bundled .cst channel-strip templates available for use in concerts.

    Template names can be passed as *cst_source* in channel strip definitions.
    Returns a sorted list of available template names.
    """
    return {"templates": sorted(TEMPLATES.keys())}


@mcp.tool()
def export_concert_with_instruments(
    concert_name: str,
    sets: list[dict],
    output_dir: str,
    default_tempo: float = 120.0,
    overwrite: bool = False,
) -> dict:
    """
    Generate a concert with per-patch instrument channels.

    Each item in *sets* is a dict with:
      - name (str): song name
      - tempo (float, optional): song BPM
      - patches (list of dicts, optional): each with:
          - name (str)
          - tempo (float, optional)
          - has_tempo (bool, optional)
          - program_change_num (int, optional)
          - has_program_change (bool, optional)
          - global_transpose (int, optional, semitones)
          - channels (list of dicts, optional): each with:
              - name (str): display name in MainStage
              - cst_source (str): template name (e.g. "Grand Piano") or absolute path to a .cst
              - volume (float 0.0–1.0, optional, default 1.0)
              - pan (float -1.0 to 1.0, optional, default 0.0)
              - muted (bool, optional, default False)

    Example sets value:
        [
          {
            "name": "Jump",
            "tempo": 130,
            "patches": [{
              "name": "Keys",
              "channels": [
                {"name": "OB-Xa Lead", "cst_source": "Analog Spheres"},
                {"name": "Bass", "cst_source": "Bass"}
              ]
            }]
          }
        ]

    Use list_templates to see available template names.
    """
    concert = Concert(name=concert_name, tempo=default_tempo)
    for s_data in sets:
        s = concert.add_set(s_data["name"], tempo=s_data.get("tempo", default_tempo))
        for p_data in s_data.get("patches", [{"name": "Main"}]):
            patch = s.add_patch(
                name=p_data.get("name", "Main"),
                tempo=p_data.get("tempo", s.tempo),
                has_tempo=p_data.get("has_tempo", False),
                has_program_change=p_data.get("has_program_change", False),
                program_change_num=p_data.get("program_change_num", 0),
                global_transpose=p_data.get("global_transpose", 0),
            )
            for ch_data in p_data.get("channels", []):
                patch.add_channel(
                    name=ch_data["name"],
                    cst_source=ch_data["cst_source"],
                    volume=ch_data.get("volume", 1.0),
                    pan=ch_data.get("pan", 0.0),
                    muted=ch_data.get("muted", False),
                    color_index=ch_data.get("color_index", 33),
                )

    path = write_concert(concert, output_dir, overwrite=overwrite)
    files = [str(p.relative_to(path.parent)) for p in path.rglob("*")]
    return {
        "concert_path": str(path),
        "set_count": len(concert.sets),
        "patch_count": sum(len(s.patches) for s in concert.sets),
        "channel_count": sum(len(p.channels) for s in concert.sets for p in s.patches),
        "files_created": sorted(files),
    }


if __name__ == "__main__":
    mcp.run()
