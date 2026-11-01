"""GUI logic without NiceGUI: formatting, history rows, config edits, the talk button."""

from __future__ import annotations

import asyncio
import copy
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from announcer import config
from announcer.audio.player import SoundPlayer
from announcer.config import Config, ConfigError
from announcer.engine import HistoryEntry, Key
from announcer.model import Session
from announcer.sequencer import SPREKEN

log = logging.getLogger(__name__)

REPLAYABLE = ("skipped", "missed", "failed")
TEST_PHRASE = "This is a test announcement."
KIND_LABELS = {"match_start": "start", "match_end": "end", "manual_text": "manual"}


def hall_choices(cfg: Config) -> list[str]:
    """Zone buttons the operator may select: every actuator except SPREKEN."""
    return [name for name in cfg.actuators if name != SPREKEN]


def fmt_countdown(seconds: float) -> str:
    if seconds <= 0:
        return "now"
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def fmt_age(now: datetime, at: datetime | None) -> str:
    if at is None:
        return "never"
    seconds = max(0, int((now - at).total_seconds()))
    return f"{seconds} s ago" if seconds < 120 else f"{seconds // 60} min ago"


def session_kinds(session: Session) -> str:
    return " + ".join(KIND_LABELS.get(a.kind, a.kind) for a in session.announcements)


def session_matches(session: Session) -> int:
    return sum(len(a.matches) for a in session.announcements)


def fmt_key(key: Key) -> str:
    kind, due = key
    try:
        when = datetime.fromisoformat(due).strftime("%a %H:%M")
    except ValueError:
        when = due
    return f"{KIND_LABELS.get(kind, kind)} {when}"


@dataclass(frozen=True)
class HistoryRow:
    at: datetime
    key: Key
    status: str
    detail: str
    replayable: bool  # show "play now"


def history_rows(history: Sequence[HistoryEntry]) -> list[HistoryRow]:
    """Newest first; only the latest entry of a skipped/missed/failed key can be replayed."""
    seen: set[Key] = set()
    rows = []
    for entry in reversed(history):
        latest = entry.key not in seen
        seen.add(entry.key)
        rows.append(
            HistoryRow(
                entry.at,
                entry.key,
                entry.status,
                entry.detail,
                latest and entry.status in REPLAYABLE,
            )
        )
    return rows


def list_signature(engine: Any, upcoming_limit: int) -> tuple[Any, ...]:
    """Changes whenever the dashboard lists need rebuilding."""
    return (len(engine.history), tuple(engine.upcoming[:upcoming_limit]), engine.current)


def desk_busy(engine: Any) -> bool:
    """A session or talk is using the desk: calibration actions must wait."""
    return engine.current is not None or engine.talking


class _Reloadable(Protocol):
    cfg: Config

    async def reload_config(self, cfg: Config) -> None: ...


async def apply_config(
    engine: _Reloadable,
    path: Path,
    edit: Callable[[Config], None],
    player: object | None = None,
) -> str | None:
    """Edit a copy of the live config, save it, reload the engine. Returns an error or None."""
    cfg = copy.deepcopy(engine.cfg)
    try:
        edit(cfg)
        config.save(cfg, path)
    except (ConfigError, ValueError, TypeError) as e:
        return str(e)
    except OSError as e:
        return f"cannot save {path}: {e}"
    try:
        await engine.reload_config(cfg)
    except Exception as e:
        log.exception("reload_config failed")
        return f"saved, but applying it failed: {e!r}"
    if isinstance(player, SoundPlayer):  # the engine does not own the player volume
        player.volume = cfg.audio.volume
    return None


class _Talker(Protocol):
    async def talk_start(self, halls: Sequence[str]) -> None: ...

    async def talk_stop(self) -> None: ...


class TalkHold:
    """Hold-to-talk button: press starts a talk in the background, release always stops it.

    talk_start waits for the desk lock, so a release can come before the talk holds
    SPREKEN; the talk is then stopped as soon as talk_start returns.
    """

    def __init__(self, engine: _Talker) -> None:
        self._engine = engine
        self._task: asyncio.Task[None] | None = None
        self._released = True
        self.error: str | None = None

    @property
    def pressed(self) -> bool:
        return self._task is not None and not self._task.done()

    def press(self, halls: Sequence[str]) -> None:
        if self.pressed:  # e.g. touchstart followed by an emulated mousedown
            return
        self._released = False
        self.error = None
        self._task = asyncio.create_task(self._run(tuple(halls)), name="gui-talk")

    async def _run(self, halls: tuple[str, ...]) -> None:
        if self._released:
            return
        try:
            await self._engine.talk_start(halls)
        except Exception as e:
            self.error = str(e) or repr(e)
            log.warning("talk did not start: %s", self.error)
            return
        if self._released:
            await self._engine.talk_stop()

    async def release(self) -> None:
        """Stop this button's talk; a no-op if not pressed (another tab's talk keeps going)."""
        if self._released:
            return
        self._released = True
        await self._engine.talk_stop()

    async def wait(self) -> None:
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)
