from __future__ import annotations

from typing import Protocol

from announcer.model import Match


class SourceError(Exception):
    """A schedule source could not deliver a usable schedule."""


class ScheduleSource(Protocol):
    async def fetch(self) -> list[Match]:
        """Return all matches. Raises SourceError on any failure."""
        ...
