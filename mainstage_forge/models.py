"""Data models for MainStage concert structure."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import uuid


def _uuid() -> str:
    return str(uuid.uuid4()).upper()


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
