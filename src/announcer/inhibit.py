"""Keep the laptop awake, also with the lid closed, while the announcer runs (systemd-inhibit)."""

from __future__ import annotations

import ctypes
import logging
import os
import signal
import subprocess
from functools import partial
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
PR_SET_PDEATHSIG = 1

_LIBC = ctypes.CDLL(None)  # loaded here: the forked child must not load libraries


def _die_with_parent(parent: int) -> None:
    """Runs in the helper before exec. A killed app runs no cleanup, and a helper left
    behind would block sleep and the lid until reboot."""
    _LIBC.prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
    if os.getppid() != parent:  # the app died before the line above took effect
        os._exit(1)


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
                preexec_fn=partial(_die_with_parent, os.getpid()),
            )
        except (OSError, subprocess.SubprocessError) as e:
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
