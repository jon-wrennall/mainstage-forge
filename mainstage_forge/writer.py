"""Write a Concert model to a .concert package on disk."""

from __future__ import annotations
import plistlib
import shutil
import subprocess
from pathlib import Path

from .models import Concert, Set, Patch
from .plist_builder import _INST_IDS
from .plist_builder import concert_data_plist, concert_root_plist, set_plist, patch_plist, instrument_channel_entry

_BASE_PLISTZ = Path(__file__).parent / "base.plistZ"
_WORKSPACE_LAYOUT = Path(__file__).parent / "workspace.layout"
_WORKSPACE_LAYOUT_SMART = Path(__file__).parent / "workspace_smart.layout"
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

    # Choose workspace layout: use the smart-controls variant if any patch has smart knobs
    has_smart_controls = any(
        p.smart_knobs
        for s in concert.sets
        for p in s.patches
    )
    workspace_src = _WORKSPACE_LAYOUT_SMART if has_smart_controls else _WORKSPACE_LAYOUT

    # Root data.plist (UI/window state) + required seed files
    _write_plist(concert_path / "data.plist", concert_data_plist())
    shutil.copy2(_BASE_PLISTZ, concert_path / "base.plistZ")
    shutil.copytree(workspace_src, concert_path / "workspace.layout")

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
            slot_inst_ids: list[int] = []
            for idx, ch in enumerate(p.channels):
                cst_src = ch.resolve_cst()
                cst_filename = ch.name + ".cst"
                cst_dest = patch_dir / cst_filename
                modified = False
                cst_bytes = cst_src.read_bytes()

                # Graft FX chain from fx_source if provided
                if ch.fx_source:
                    from .cst_tools import graft_fx_chain
                    fx_path = Path(ch.fx_source)
                    if not fx_path.exists():
                        raise FileNotFoundError(f"fx_source not found: {ch.fx_source!r}")
                    cst_bytes = graft_fx_chain(cst_bytes, fx_path.read_bytes())
                    modified = True

                # Patch key zone if non-default
                if ch.low_note != 0 or ch.high_note != 127:
                    from .smart_controls import patch_cst_key_zone
                    cst_bytes = patch_cst_key_zone(cst_bytes, ch.low_note, ch.high_note)
                    modified = True

                if modified:
                    cst_dest.write_bytes(cst_bytes)
                else:
                    shutil.copy2(cst_src, cst_dest)
                entry = instrument_channel_entry(
                    name=ch.name,
                    filename=cst_filename,
                    slot_index=idx,
                    uuid=ch.uuid,
                    volume=ch.volume,
                    pan=ch.pan,
                    muted=ch.muted,
                    color_index=ch.color_index,
                )
                channel_entries.append(entry)
                slot_inst_ids.append(entry["Channel_instID"])

            # Build smart knob specs: (knob_num, inst_id, param_index, rl, rh, label, prefix)
            smart_knob_specs = None
            if p.smart_knobs:
                smart_knob_specs = []
                for auto_num, knob in enumerate(p.smart_knobs, start=1):
                    knob_num = knob.knob_number if knob.knob_number is not None else auto_num
                    slot = knob.channel_slot_index
                    inst_id = slot_inst_ids[slot] if slot < len(slot_inst_ids) else _INST_IDS[0]
                    smart_knob_specs.append((
                        knob_num, inst_id, knob.param_index,
                        knob.range_low, knob.range_high, knob.label,
                        knob.identity_prefix, knob.range_is_flipped,
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
                    smart_knob_specs=smart_knob_specs,
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
