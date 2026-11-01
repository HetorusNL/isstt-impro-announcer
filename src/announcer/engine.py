"""The engine: schedule polling, planning, the session queue, pause, late/skip, talk."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from announcer.audio.player import Player
from announcer.clock import Clock
from announcer.config import Config
from announcer.controller.base import Controller
from announcer.model import Announcement, Match, Session
from announcer.planner import (
    group_sessions,
    lead_seconds,
    plan_announcements,
    render_message,
)
from announcer.schedule import store
from announcer.schedule.source import ScheduleSource, SourceError
from announcer.sequencer import run_session, talk_session

log = logging.getLogger(__name__)

Status = Literal["played", "skipped", "missed", "failed"]
Key = tuple[str, str]
TICK_S = 1.0  # longest clock-time sleep of the run loop


class Synth(Protocol):
    async def synth(self, text: str) -> Path: ...


@dataclass(frozen=True)
class HistoryEntry:
    at: datetime
    key: Key
    status: Status
    detail: str = ""


async def _settle(task: asyncio.Task[None]) -> None:
    """Wait for task. If cancelled meanwhile: cancel task too, still wait for it, re-raise."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.wait({task})
        except asyncio.CancelledError:
            cancelled = True
            task.cancel()
    if cancelled:
        raise asyncio.CancelledError


class Engine:
    def __init__(
        self,
        cfg: Config,
        source: ScheduleSource,
        store_path: Path,
        ctrl: Controller,
        player: Player,
        tts: Synth,
        clock: Clock,
    ) -> None:
        self.cfg = cfg
        self._source = source
        self._store_path = Path(store_path)
        self._handled_path = self._store_path.parent / "handled.json"
        self._ctrl = ctrl
        self._player = player
        self._tts = tts
        self._clock = clock

        # state for the GUI
        self.paused = False
        self.upcoming: list[Session] = []
        self.history: list[HistoryEntry] = []
        self.source_ok_at: datetime | None = None
        self.source_error: str | None = None
        self.matches_count = 0

        self._matches: list[Match] = []
        self._handled: set[Key] = set()
        self._replayable: dict[Key, tuple[Announcement, tuple[str, ...]]] = {}
        self._manual: list[Session] = []
        self._lock = asyncio.Lock()  # one desk session at a time (scheduled, manual, talk)
        self._sessions: set[asyncio.Task[None]] = set()  # in-flight desk session tasks
        self._poll_task: asyncio.Task[None] | None = None
        self._run_task: asyncio.Task[None] | None = None
        self._talk_task: asyncio.Task[None] | None = None
        self._talk_stop: asyncio.Event | None = None
        self._stopped = False

    @property
    def talking(self) -> bool:
        return self._talk_task is not None and not self._talk_task.done()

    # lifecycle

    async def start(self) -> None:
        self._handled = self._load_handled()
        try:
            self._set_matches(store.load(self._store_path, self.cfg.schedule.timezone))
        except SourceError:
            log.info("no stored schedule at %s", self._store_path)
        await self._fetch()
        self._mark_missed()
        self._replan()
        self._poll_task = asyncio.create_task(self._poll_loop(), name="engine-poll")
        self._run_task = asyncio.create_task(self._run_loop(), name="engine-run")

    async def stop(self) -> None:
        self._stopped = True
        try:
            while True:
                tasks = [
                    t
                    for t in (self._poll_task, self._run_task, self._talk_task, *self._sessions)
                    if t is not None and not t.done()
                ]
                if not tasks:
                    break
                for t in tasks:
                    t.cancel()
                # a session may end with its own error even after being cancelled
                for result in await asyncio.gather(*tasks, return_exceptions=True):
                    if isinstance(result, Exception):
                        log.warning("task ended with %r during stop", result)
        finally:
            await self._ctrl.release_all()

    # operator actions

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    async def play_now(self, key: Key) -> None:
        """Play a skipped or missed announcement now, as its own session (even if paused)."""
        self._check_running()
        if key not in self._replayable:
            raise KeyError(f"{key} is not a skipped or missed announcement")
        ann, halls = self._replayable[key]
        session = Session(self._clock.now(), (ann,), halls)
        async with self._lock:
            if key not in self._replayable:  # played by a concurrent play_now meanwhile
                return
            if await self._run_desk(session):
                del self._replayable[key]

    async def manual_text(self, halls: Sequence[str], text: str) -> None:
        """Queue a spoken text; it waits for running sessions and for resume."""
        self._check_running()
        now = self._clock.now()
        ann = Announcement(due=now, kind="manual_text", text=text)
        self._manual.append(Session(now, (ann,), tuple(halls)))

    async def talk_start(self, halls: Sequence[str]) -> None:
        """Select halls and hold SPREKEN until talk_stop (or the max hold). Runs even if paused."""
        self._check_running()
        if self.talking:
            raise RuntimeError("a talk is already active")
        started: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        stop = asyncio.Event()
        self._talk_stop = stop
        self._talk_task = asyncio.create_task(self._talk(tuple(halls), started, stop), name="talk")
        await asyncio.wait({started, self._talk_task}, return_when=asyncio.FIRST_COMPLETED)
        if not started.done():  # the talk ended before SPREKEN was held
            started.cancel()
            await self._talk_task  # re-raises its error

    async def talk_stop(self) -> None:
        task, stop = self._talk_task, self._talk_stop
        if task is None or stop is None:
            return
        stop.set()
        try:
            await _settle(task)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("talk ended with an error")

    async def reload_config(self, cfg: Config) -> None:
        async with self._lock:  # configure moves servos: never during a session
            self.cfg = cfg
            await self._ctrl.configure(cfg.actuators)
        self._replan()

    # schedule

    def _set_matches(self, matches: list[Match]) -> None:
        self._matches = list(matches)
        self.matches_count = len(self._matches)

    async def _fetch(self) -> None:
        try:
            matches = await self._source.fetch()
        except SourceError as e:
            self.source_error = str(e)
            log.warning("schedule source failed, keeping last schedule: %s", e)
            return
        except Exception as e:
            self.source_error = str(e) or repr(e)
            log.exception("schedule source failed unexpectedly, keeping last schedule")
            return
        try:
            store.save(matches, self._store_path)
        except OSError:
            log.exception("could not store the schedule at %s", self._store_path)
        self._set_matches(matches)
        self.source_ok_at = self._clock.now()
        self.source_error = None

    async def _poll_loop(self) -> None:
        while True:
            await self._clock.sleep(self.cfg.schedule.poll_seconds)
            await self._fetch()
            self._replan()

    def _planned(self) -> list[Announcement]:
        sched = self.cfg.schedule
        anns = plan_announcements(self._matches, sched.round_minutes, sched.default_match_minutes)
        return [a for a in anns if a.key not in self._handled]  # before grouping

    def _replan(self) -> None:
        ann = self.cfg.announce
        self.upcoming = group_sessions(
            self._planned(), ann.halls, ann.merge_window_seconds, lead_seconds(self.cfg)
        )

    def _mark_missed(self) -> None:
        limit = self._clock.now() - timedelta(seconds=self.cfg.announce.late_threshold_seconds)
        missed = [a for a in self._planned() if a.due < limit]
        if missed:
            self._record(missed, tuple(self.cfg.announce.halls), "missed")

    # history and persistence

    def _record(
        self, anns: Sequence[Announcement], halls: tuple[str, ...], status: Status, detail: str = ""
    ) -> None:
        now = self._clock.now()
        for a in anns:
            self.history.append(HistoryEntry(now, a.key, status, detail))
            self._handled.add(a.key)
            if status in ("skipped", "missed"):
                self._replayable[a.key] = (a, halls)
        self._save_handled()

    def _load_handled(self) -> set[Key]:
        try:
            raw = json.loads(self._handled_path.read_text(encoding="utf-8"))
            return {(str(kind), str(due)) for kind, due in raw}
        except FileNotFoundError:
            return set()
        except (OSError, ValueError, TypeError) as e:
            log.warning("ignoring unreadable %s: %r", self._handled_path, e)
            return set()

    def _save_handled(self) -> None:
        try:
            self._handled_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._handled_path.with_name(self._handled_path.name + ".tmp")
            tmp.write_text(json.dumps(sorted(self._handled)), encoding="utf-8")
            tmp.replace(self._handled_path)
        except OSError:
            log.exception("could not save %s", self._handled_path)

    # sessions

    def _check_running(self) -> None:
        if self._stopped:
            raise RuntimeError("engine is stopped")

    def _is_late(self, session: Session, now: datetime) -> bool:
        late_s = (now - session.announcements[0].due).total_seconds()
        return late_s > self.cfg.announce.late_threshold_seconds

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._step()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("run loop step failed")
                await self._clock.sleep(TICK_S)

    async def _step(self) -> None:
        now = self._clock.now()
        # late scheduled sessions are skipped, also while paused or busy
        while self.upcoming and now >= self.upcoming[0].start_at:
            first = self.upcoming[0]
            if not self._is_late(first, now):
                break
            self.upcoming.pop(0)
            self._record(first.announcements, first.halls, "skipped", "late")
        sched = self.upcoming[0] if self.upcoming else None
        if not self.paused and not self._lock.locked():
            candidates = [s for s in (sched,) if s is not None and now >= s.start_at]
            candidates += self._manual[:1]
            if candidates:
                session = min(candidates, key=lambda s: s.start_at)
                async with self._lock:
                    if session in self._manual:
                        self._manual.remove(session)
                    await self._run_desk(session)
                self._replan()
                return
        delay = TICK_S
        if sched is not None and now < sched.start_at:
            delay = min(delay, (sched.start_at - now).total_seconds())
        await self._clock.sleep(delay)

    async def _run_desk(self, session: Session) -> bool:
        """Run one desk session in its own task and record the result. Caller holds the lock.

        Returns False (nothing recorded) if the session was cancelled, i.e. by stop().
        """
        task = asyncio.create_task(self._desk(session), name="engine-session")
        self._sessions.add(task)
        task.add_done_callback(self._sessions.discard)
        await _settle(task)
        if task.cancelled():
            log.warning("session cancelled")
            return False
        exc = task.exception()
        if exc is None:
            self._record(session.announcements, session.halls, "played")
        else:
            log.error("session failed: %r", exc)
            self._record(session.announcements, session.halls, "failed", str(exc) or repr(exc))
        return True

    async def _desk(self, session: Session) -> None:
        audio = [await self._tts.synth(self._text(a)) for a in session.announcements]
        await run_session(self._ctrl, self._player, self._clock, self.cfg, session.halls, audio)

    def _text(self, ann: Announcement) -> str:
        if ann.kind == "manual_text":
            return ann.text or ""
        return render_message(self.cfg.messages[ann.kind], ann)

    async def _talk(
        self, halls: tuple[str, ...], started: asyncio.Future[None], stop: asyncio.Event
    ) -> None:
        async with self._lock:
            if stop.is_set():  # stopped while waiting for the lock
                return
            async with talk_session(self._ctrl, self._clock, self.cfg, halls):
                if not started.done():
                    started.set_result(None)
                await stop.wait()
