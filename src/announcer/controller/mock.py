"""In-memory controller that records what it was asked to do, on a Clock."""

from __future__ import annotations

import logging
from datetime import datetime

from announcer.clock import Clock
from announcer.config import Actuator
from announcer.controller.base import ControllerError

log = logging.getLogger(__name__)

DEFAULT_PRESS_MS = 250
DEFAULT_RELEASE_MS = 250


class MockController:
    def __init__(self, clock: Clock, actuators: dict[str, Actuator] | None = None) -> None:
        self._clock = clock
        self.actuators: dict[str, Actuator] = dict(actuators or {})
        self.connected = False
        self.interruptions = 0
        self.last_event: str | None = None
        self.events: list[tuple[datetime, str, str]] = []
        self.fail_on: set[str] = set()
        self.release_delay_s = 0.0  # test hook: make release take (clock) time

    def simulate_interruption(self, line: str = "EVT WATCHDOG") -> None:
        """Test hook: the board reports line, as if it released on its own."""
        self.last_event = line
        self.interruptions += 1

    def _check(self, kind: str, button: str = "") -> None:
        # fail_on entries: an action kind ("tap") or a kind for one button ("tap:SC2")
        if kind in self.fail_on or f"{kind}:{button}" in self.fail_on:
            raise ControllerError(f"mock failure on {kind} {button}".rstrip())

    def _record(self, kind: str, button: str) -> None:
        now = self._clock.now()
        self.events.append((now, kind, button))
        log.info("%s %s %s", now.isoformat(timespec="milliseconds"), kind, button)

    def _ms(self, button: str) -> tuple[int, int]:
        act = self.actuators.get(button)
        if act is None:
            return DEFAULT_PRESS_MS, DEFAULT_RELEASE_MS
        return act.press_ms, act.release_ms

    async def connect(self) -> None:
        self._check("connect")
        self.connected = True

    async def close(self) -> None:
        self.connected = False

    async def configure(self, actuators: dict[str, Actuator]) -> None:
        self._check("configure")
        self.actuators = dict(actuators)

    async def tap(self, button: str) -> None:
        self._check("tap", button)
        self._record("tap", button)
        press_ms, release_ms = self._ms(button)
        await self._clock.sleep(press_ms / 1000)
        await self._clock.sleep(release_ms / 1000)

    async def hold(self, button: str) -> None:
        self._check("hold", button)
        self._record("hold", button)
        await self._clock.sleep(self._ms(button)[0] / 1000)

    async def release(self, button: str) -> None:
        self._check("release", button)
        if self.release_delay_s:
            await self._clock.sleep(self.release_delay_s)
        self._record("release", button)

    async def release_all(self) -> None:
        self._check("release_all")
        self._record("release_all", "")

    async def set_angle(self, button: str, angle: int) -> None:
        self._check("set_angle", button)
        self._record("set_angle", button)
