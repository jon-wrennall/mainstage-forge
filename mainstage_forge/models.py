"""Data models for MainStage concert structure."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import uuid


def _uuid() -> str:
    return str(uuid.uuid4()).upper()


_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Catalog of bundled .cst templates (stem → path)
TEMPLATES: dict[str, Path] = {p.stem: p for p in _TEMPLATES_DIR.glob("*.cst")}


@dataclass
class ChannelStrip:
    """A software-instrument channel strip to add to a patch."""
    name: str
    # Path to the .cst file. Use a template name (e.g. "Grand Piano") or an
    # absolute path to any .cst from an existing concert.
    cst_source: str
    volume: float = 1.0        # 0.0–1.0 (1.0 ≈ 0 dB)
    pan: float = 0.0           # -1.0 (L) to 1.0 (R)
    muted: bool = False
    color_index: int = 33      # Channel_seqColorIndex palette entry
    uuid: str = field(default_factory=_uuid)

    def resolve_cst(self) -> Path:
        """Return the absolute path to the .cst file."""
        p = Path(self.cst_source)
        if p.is_absolute() and p.exists():
            return p
        # Try as a template name (with or without .cst extension)
        stem = p.stem if p.suffix.lower() == ".cst" else self.cst_source
        if stem in TEMPLATES:
            return TEMPLATES[stem]
        raise FileNotFoundError(
            f"Channel strip .cst not found: {self.cst_source!r}. "
            f"Available templates: {sorted(TEMPLATES)}"
        )


@dataclass
class SmartKnob:
    """
    One Smart Control knob mapping.

    Maps an on-screen knob to a specific parameter of an instrument channel strip.
    ``channel_slot_index`` is the 0-based position of the target channel in this
    patch's ``channels`` list (0 = first instrument strip).
    ``param_index`` is the 0-based parameter index within that plugin — plugin-specific.
    ``range_low`` / ``range_high`` clamp the knob range (-1 = plugin's own min/max).
    """
    label: str
    channel_slot_index: int = 0
    param_index: int = 0
    range_low: int = -1
    range_high: int = -1


@dataclass
class Patch:
    """A single patch (instrument preset) within a set."""
    name: str
    tempo: float = 120.0
    has_tempo: bool = False
    program_change_num: int = 0
    has_program_change: bool = False
    global_transpose: int = 0
    icon_id: Optional[int] = None
    uuid: str = field(default_factory=_uuid)
    channels: list[ChannelStrip] = field(default_factory=list)
    smart_knobs: list[SmartKnob] = field(default_factory=list)

    def add_channel(self, name: str, cst_source: str, **kwargs) -> ChannelStrip:
        ch = ChannelStrip(name=name, cst_source=cst_source, **kwargs)
        self.channels.append(ch)
        return ch

    def add_smart_knob(
        self,
        label: str,
        channel_slot_index: int = 0,
        param_index: int = 0,
        range_low: int = -1,
        range_high: int = -1,
    ) -> SmartKnob:
        """
        Add a Smart Control knob to this patch.

        Args:
            label:              Display name on the Smart Controls panel.
            channel_slot_index: 0-based index of the target channel in this patch.
            param_index:        0-based plugin parameter index (plugin-specific).
            range_low:          Lower clamp (-1 = plugin min).
            range_high:         Upper clamp (-1 = plugin max).
        """
        knob = SmartKnob(
            label=label,
            channel_slot_index=channel_slot_index,
            param_index=param_index,
            range_low=range_low,
            range_high=range_high,
        )
        self.smart_knobs.append(knob)
        return knob


@dataclass
class Set:
    """A set (song) containing one or more patches."""
    name: str
    patches: list[Patch] = field(default_factory=list)
    tempo: float = 120.0
    icon_id: Optional[int] = None

    def add_patch(self, name: str, **kwargs) -> Patch:
        p = Patch(name=name, **kwargs)
        self.patches.append(p)
        return p


@dataclass
class Concert:
    """Top-level MainStage concert."""
    name: str
    sets: list[Set] = field(default_factory=list)
    tempo: float = 120.0

    def add_set(self, name: str, **kwargs) -> Set:
        s = Set(name=name, **kwargs)
        self.sets.append(s)
        return s

    @classmethod
    def from_setlist(
        cls,
        concert_name: str,
        songs: list[str],
        patch_name: str = "Main",
        tempo: float = 120.0,
    ) -> Concert:
        """Build a concert from a flat list of song names, one patch per song."""
        concert = cls(name=concert_name, tempo=tempo)
        for song in songs:
            s = concert.add_set(song, tempo=tempo)
            s.add_patch(patch_name)
        return concert
