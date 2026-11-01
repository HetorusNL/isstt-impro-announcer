from __future__ import annotations

from pathlib import Path

from announcer.model import Match
from announcer.schedule import store


class FileSource:
    def __init__(self, path: Path | str, tz: str) -> None:
        self._path = Path(path)
        self._tz = tz

    async def fetch(self) -> list[Match]:
        return store.load(self._path, self._tz)
