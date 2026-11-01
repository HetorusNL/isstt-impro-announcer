"""Core data model shared by the scheduler, planner and UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Kind = Literal["match_start", "match_end", "manual_text"]


@dataclass(frozen=True)
class Match:
    start: datetime  # timezone-aware
    hall: str  # e.g. "SC1" (no space)
    field: str  # e.g. "Field 1"
    home: str
    away: str
    referee: str
    round_name: str
    match_minutes: int | None


@dataclass(frozen=True)
class Announcement:
    due: datetime
    kind: Kind
    matches: tuple[Match, ...] = ()
    text: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.kind, self.due.isoformat())


@dataclass(frozen=True)
class Session:
    start_at: datetime
    announcements: tuple[Announcement, ...]
    halls: tuple[str, ...]
