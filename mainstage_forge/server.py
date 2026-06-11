"""MCP server exposing mainstage-forge tools."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .models import Concert, Set, Patch
from .writer import write_concert, clone_channel_strips

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


if __name__ == "__main__":
    mcp.run()
