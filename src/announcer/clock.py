"""Real and simulated clocks (the simulated one lets tests and dry runs go fast)."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    def now(self) -> datetime: ...

    async def sleep(self, seconds: float) -> None: ...


class RealClock:
    def __init__(self, tz: str) -> None:
        self._tz = ZoneInfo(tz)

    def now(self) -> datetime:
        return datetime.now(self._tz)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class SimClock:
    """Simulated time: now() = start + elapsed real time * speed."""

    def __init__(self, start: datetime, speed: float) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        self._start = start
        self._speed = speed
        self._t0 = time.monotonic()

    @property
    def start(self) -> datetime:
        return self._start

    @property
    def speed(self) -> float:
        return self._speed

    def now(self) -> datetime:
        return self._start + timedelta(seconds=(time.monotonic() - self._t0) * self._speed)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds / self._speed)
