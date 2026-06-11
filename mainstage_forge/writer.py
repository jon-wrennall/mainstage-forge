"""Write a Concert model to a .concert package on disk."""

from __future__ import annotations
import plistlib
import shutil
import subprocess
from pathlib import Path

from .models import Concert, Set, Patch
from .plist_builder import concert_data_plist, concert_root_plist, set_plist, patch_plist, instrument_channel_entry

_BASE_PLISTZ = Path(__file__).parent / "base.plistZ"
_WORKSPACE_LAYOUT = Path(__file__).parent / "workspace.layout"
_REQUIRED_CST = [
    Path(__file__).parent / "Master.cst",
    Path(__file__).parent / "Metronome.cst",
    Path(__file__).parent / "Output 1-2.cst",
]


def _write_plist(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)


def _safe_name(name: str) -> str:
    """Sanitise a name for use as a directory/file component."""
    return name.replace("/", "-").replace(":", "-").replace("\x00", "")


def write_concert(concert: Concert, output_dir: str | Path, overwrite: bool = False) -> Path:
    """
    Write *concert* to *output_dir* as a proper MainStage .concert package.

    Returns the path to the created .concert package.
    """
    out = Path(output_dir)
    concert_path = out / f"{_safe_name(concert.name)}.concert"

    if concert_path.exists():
        if overwrite:
            shutil.rmtree(concert_path)
        else:
            raise FileExistsError(
                f"{concert_path} already exists. Pass overwrite=True to replace it."
            )

    # Root data.plist (UI/window state) + required seed files
    _write_plist(concert_path / "data.plist", concert_data_plist())
    shutil.copy2(_BASE_PLISTZ, concert_path / "base.plistZ")
    shutil.copytree(_WORKSPACE_LAYOUT, concert_path / "workspace.layout")

    # Set FinderInfo xattr — required for MainStage to recognise the package
    _FINDER_INFO = bytes.fromhex("00000000000000000010000000000000" + "00000000000000000000000000000000")
    subprocess.run(
        ["xattr", "-wx", "com.apple.FinderInfo", _FINDER_INFO.hex(), str(concert_path)],
        check=True,
    )

    # Concert.patch/ — required channel strips
    concert_patch = concert_path / "Concert.patch"
    concert_patch.mkdir(parents=True, exist_ok=True)
    for cst in _REQUIRED_CST:
        shutil.copy2(cst, concert_patch / cst.name)
    set_names = [_safe_name(s.name) for s in concert.sets]
    _write_plist(concert_patch / "data.plist", concert_root_plist(concert.name, concert.tempo, child_names=set_names))

    # One sub-directory per set
    for s in concert.sets:
        set_dir = concert_patch / f"{_safe_name(s.name)}.patch"
        patch_names = [_safe_name(p.name) for p in s.patches]
        _write_plist(set_dir / "data.plist", set_plist(s.name, s.tempo, child_names=patch_names))

        # One sub-directory per patch within the set
        for p in s.patches:
            patch_dir = set_dir / f"{_safe_name(p.name)}.patch"
            patch_dir.mkdir(parents=True, exist_ok=True)

            # Copy .cst files and build channel entries
            channel_entries = []
            for idx, ch in enumerate(p.channels):
                cst_src = ch.resolve_cst()
                cst_filename = ch.name + ".cst"
                shutil.copy2(cst_src, patch_dir / cst_filename)
                channel_entries.append(instrument_channel_entry(
                    name=ch.name,
                    filename=cst_filename,
                    slot_index=idx,
                    uuid=ch.uuid,
                    volume=ch.volume,
                    pan=ch.pan,
                    muted=ch.muted,
                    color_index=ch.color_index,
                ))

            _write_plist(
                patch_dir / "data.plist",
                patch_plist(
                    name=p.name,
                    tempo=p.tempo,
                    has_tempo=p.has_tempo,
                    has_program_change=p.has_program_change,
                    program_change_num=p.program_change_num,
                    global_transpose=p.global_transpose,
                    icon_id=p.icon_id,
                    channel_entries=channel_entries,
                ),
            )

    return concert_path


def clone_channel_strips(
    source_concert: str | Path,
    target_patch_dir: str | Path,
    strip_names: list[str] | None = None,
) -> list[Path]:
    """
    Copy .cst channel-strip files from an existing concert into a patch directory.

    MainStage .cst files are proprietary binary — this copies them verbatim.
    *strip_names* filters which strips to copy; None copies all.
    Returns list of copied paths.
    """
    src = Path(source_concert)
    dst = Path(target_patch_dir)
    dst.mkdir(parents=True, exist_ok=True)

    copied = []
    for cst in src.rglob("*.cst"):
        if strip_names is None or cst.stem in strip_names:
            dest = dst / cst.name
            shutil.copy2(cst, dest)
            copied.append(dest)
    return copied
