"""Keep the laptop awake, also with the lid closed, while the announcer runs (systemd-inhibit)."""

from __future__ import annotations

import logging
import subprocess
from types import TracebackType
from typing import Self

log = logging.getLogger(__name__)

COMMAND = [
    "systemd-inhibit",
    "--what=sleep:idle:handle-lid-switch",
    "--who=announcer",
    "--why=tournament announcements",
    "sleep",
    "infinity",
]
STOP_TIMEOUT_S = 5.0


class Inhibitor:
    """Context manager: blocks sleep, idle and lid close inside. A missing tool only warns."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> Self:
        try:
            self._proc = subprocess.Popen(
                COMMAND,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            log.warning("cannot run systemd-inhibit (%s): the laptop may go to sleep", e)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
