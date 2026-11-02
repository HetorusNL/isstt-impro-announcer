"""Controller interface. Buttons are referred to by name; channels live only in config."""

from __future__ import annotations

from typing import Protocol

from announcer.config import Actuator


class ControllerError(Exception):
    pass


class Controller(Protocol):
    connected: bool
    interruptions: int  # counts what can end a hold unseen: board events, a lost link
    last_event: str | None  # the last event line from the board

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def configure(self, actuators: dict[str, Actuator]) -> None:
        """Store the actuators and send their rest angles to the firmware."""

    async def tap(self, button: str) -> None:
        """Press angle, wait press_ms, rest angle, wait release_ms."""

    async def hold(self, button: str) -> None:
        """Press angle and keep it there (wait press_ms)."""

    async def release(self, button: str) -> None: ...

    async def release_all(self) -> None: ...

    async def set_angle(self, button: str, angle: int) -> None: ...
