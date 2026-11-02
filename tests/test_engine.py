import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest
import soundfile as sf

from announcer.audio.player import MockPlayer
from announcer.clock import SimClock
from announcer.config import Actuator, Config
from announcer.controller.base import ControllerError
from announcer.controller.mock import MockController
from announcer.engine import Engine
from announcer.model import Match
from announcer.planner import lead_seconds
from announcer.schedule import store
from announcer.schedule.filesource import FileSource
from announcer.schedule.source import SourceError

TZ = "Europe/Amsterdam"
SPEED = 600.0
START_MSG = "Referees, you may start the matches."
END_MSG = "Referees, you may end the matches."


def at(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 12, 18, h, m, s, tzinfo=ZoneInfo(TZ))


def match(start: datetime, hall: str = "SC1", minutes: int = 20) -> Match:
    return Match(start, hall, "Field 1", "A", "B", "Ref", "Round 1", minutes)


def make_cfg(poll_seconds: int = 60) -> Config:
    cfg = Config()
    cfg.actuators = {
        "SC1": Actuator(channel=0, rest=10, press=40),
        "SC2": Actuator(channel=1, rest=10, press=40),
        "SPREKEN": Actuator(channel=2, rest=10, press=40),
    }
    cfg.announce.halls = ["SC1", "SC2"]
    cfg.announce.chime_seconds = 3.0
    cfg.announce.tail_seconds = 0.5
    cfg.schedule.poll_seconds = poll_seconds
    return cfg


class FakeTts:
    """Writes a short silent wav per text."""

    def __init__(self, cache: Path, clock: SimClock, seconds: float = 1.0) -> None:
        self.cache = cache
        self.clock = clock
        self.seconds = seconds
        self.texts: list[str] = []  # every synth call
        self.synth_at: dict[str, datetime] = {}  # first synth (clock time) per text
        self.by_path: dict[Path, str] = {}
        self.fail = False

    async def synth(self, text: str) -> Path:
        if self.fail:
            raise RuntimeError("tts broke")
        self.texts.append(text)
        self.synth_at.setdefault(text, self.clock.now())
        self.cache.mkdir(parents=True, exist_ok=True)
        path = self.cache / f"{hashlib.sha256(f'{self.seconds}|{text}'.encode()).hexdigest()}.wav"
        self.by_path[path] = text
        if not path.exists():
            sr = 16000
            sf.write(path, np.zeros(int(sr * self.seconds), dtype="int16"), sr)
        return path


class SwitchSource:
    def __init__(self, matches: list[Match]) -> None:
        self.matches = matches
        self.error: str | None = None
        self.calls = 0

    async def fetch(self) -> list[Match]:
        self.calls += 1
        if self.error is not None:
            raise SourceError(self.error)
        return list(self.matches)


class Rig:
    def __init__(self, tmp_path: Path, start: datetime, cfg: Config, speed: float) -> None:
        self.tmp_path = tmp_path
        self.cfg = cfg
        self.clock = SimClock(start, speed)
        self.ctrl = MockController(self.clock, cfg.actuators)
        self.ctrl.connected = True
        self.player = MockPlayer(self.clock)
        self.tts = FakeTts(tmp_path / "tts", self.clock)
        self.schedule_file = tmp_path / "schedule.json"
        self.store_path = tmp_path / "state" / "schedule.json"

    def write(self, matches: list[Match]) -> None:
        store.save(matches, self.schedule_file)

    def engine(self, source=None) -> Engine:
        if source is None:
            source = FileSource(self.schedule_file, TZ)
        return Engine(
            self.cfg, source, self.store_path, self.ctrl, self.player, self.tts, self.clock
        )

    def played(self) -> list[str]:
        """Texts actually played, in order."""
        return [self.tts.by_path[p] for p in self.player.played]

    def kinds(self) -> list[tuple[str, str]]:
        return [(k, b) for _, k, b in self.ctrl.events]

    def times(self, kind: str, button: str = "SPREKEN") -> list[datetime]:
        return [t for t, k, b in self.ctrl.events if k == kind and b == button]


def make_rig(tmp_path, start, cfg=None, speed=SPEED) -> Rig:
    return Rig(tmp_path, start, cfg or make_cfg(), speed)


async def until(cond: Callable[[], bool], timeout: float = 3.0) -> None:
    """Wait (real time) until cond() holds."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not cond():
        if loop.time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.001)


async def until_clock(clock: SimClock, t: datetime) -> None:
    await until(lambda: clock.now() >= t)


def statuses(engine: Engine) -> list[tuple[tuple[str, str], str]]:
    return [(h.key, h.status) for h in engine.history]


def key(kind: str, due: datetime) -> tuple[str, str]:
    return (kind, due.isoformat())


def other_tasks() -> list[asyncio.Task]:
    return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]


async def test_plays_start_and_end_on_time(tmp_path):
    # speed 100: at 600 each asyncio sleep overshoots ~0.4 s of clock time, too coarse for +-1 s
    rig = make_rig(tmp_path, at(8, 59, 50), speed=100.0)
    rig.write([match(at(9, 0), minutes=1)])
    engine = rig.engine()
    await engine.start()
    assert len(engine.upcoming) == 2
    try:
        await until(lambda: len(engine.history) == 2)
    finally:
        await engine.stop()
    assert statuses(engine) == [
        (key("match_start", at(9, 0)), "played"),
        (key("match_end", at(9, 1)), "played"),
    ]
    holds = rig.times("hold")
    assert len(holds) == 2
    for hold, due in zip(holds, (at(9, 0), at(9, 1)), strict=True):
        assert abs((hold - (due - timedelta(seconds=3.0))).total_seconds()) <= 1.0
    assert rig.played() == [START_MSG, END_MSG]
    assert engine.upcoming == []


async def test_pause_skips_when_late(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    engine.pause()
    await engine.start()
    try:
        await until_clock(rig.clock, at(9, 1, 5))
        await until(lambda: engine.history != [])
        assert statuses(engine) == [(key("match_start", at(9, 0)), "skipped")]
        engine.resume()
        t = rig.clock.now()
        await until_clock(rig.clock, t + timedelta(seconds=5))
    finally:
        await engine.stop()
    assert "hold" not in [k for k, _ in rig.kinds()]
    assert rig.player.played == []
    assert len(engine.history) == 1


async def test_play_now_plays_skipped(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    engine.pause()
    await engine.start()
    try:
        k = key("match_start", at(9, 0))
        await until(lambda: statuses(engine) == [(k, "skipped")], timeout=5)
        await engine.play_now(k)  # runs even while paused
        assert statuses(engine) == [(k, "skipped"), (k, "played")]
        assert rig.played() == [START_MSG]
        assert rig.kinds() == [
            ("tap", "SC1"),
            ("tap", "SC2"),
            ("hold", "SPREKEN"),
            ("release", "SPREKEN"),
        ]
        with pytest.raises(KeyError):
            await engine.play_now(k)  # no longer skipped
    finally:
        await engine.stop()


async def test_play_now_failure_is_recorded(tmp_path):
    rig = make_rig(tmp_path, at(10, 0))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        k = key("match_start", at(9, 0))
        rig.ctrl.fail_on = {"hold"}
        await engine.play_now(k)
    finally:
        await engine.stop()
    entry = engine.history[-1]
    assert (entry.key, entry.status) == (k, "failed")
    assert "mock failure on hold" in entry.detail


async def test_play_now_retries_failed(tmp_path):
    rig = make_rig(tmp_path, at(10, 0))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    k = key("match_start", at(9, 0))
    try:
        rig.ctrl.fail_on = {"hold"}
        await engine.play_now(k)
        rig.ctrl.fail_on = set()
        await engine.play_now(k)  # a failed entry can be played again
        with pytest.raises(KeyError):
            await engine.play_now(k)
    finally:
        await engine.stop()
    assert [s for kk, s in statuses(engine) if kk == k] == ["missed", "failed", "played"]


async def test_replan_does_not_replay_played(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50), make_cfg(poll_seconds=10))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        await until(lambda: len(engine.history) == 1)
        rig.write([match(at(9, 0)), match(at(9, 1), hall="SC2")])
        await until(lambda: len(engine.history) == 2, timeout=5)
        t = rig.clock.now()
        await until_clock(rig.clock, t + timedelta(seconds=20))  # a few more polls
    finally:
        await engine.stop()
    assert statuses(engine) == [
        (key("match_start", at(9, 0)), "played"),
        (key("match_start", at(9, 1)), "played"),
    ]
    assert len(rig.times("hold")) == 2
    assert engine.matches_count == 2
    assert rig.store_path.exists()


async def test_partly_handled_session_does_not_replay_handled_part(tmp_path):
    # 09:00 start played; a new match ends at 09:00:20 -> would merge with it
    rig = make_rig(tmp_path, at(8, 59, 50), make_cfg(poll_seconds=10))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    end_key = key("match_end", at(9, 0, 20))
    try:
        await until(lambda: len(engine.history) == 1)
        early = Match(at(8, 40, 20), "SC2", "Field 2", "C", "D", "Ref", "Round 1", 20)
        rig.write([match(at(9, 0)), early])
        await until(lambda: end_key in [h.key for h in engine.history], timeout=5)
    finally:
        await engine.stop()
    assert (end_key, "played") in statuses(engine)
    assert (key("match_start", at(8, 40, 20)), "skipped") in statuses(engine)
    assert rig.played() == [START_MSG, END_MSG]  # the handled start is not replayed
    assert len(rig.times("hold")) == 2


async def test_restart_does_not_replay_handled(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        await until(lambda: len(engine.history) == 1)
    finally:
        await engine.stop()
    handled = json.loads((tmp_path / "state" / "handled.json").read_text())
    assert ["match_start", at(9, 0).isoformat()] in handled
    # restart 20 s after due (inside the late threshold): no replay, not missed
    rig2 = make_rig(tmp_path, at(9, 0, 20))
    engine2 = rig2.engine()
    await engine2.start()
    try:
        t = rig2.clock.now()
        await until_clock(rig2.clock, t + timedelta(seconds=10))
    finally:
        await engine2.stop()
    assert engine2.history == []
    assert rig2.kinds() == [("release_all", "")]
    assert [s.announcements[0].kind for s in engine2.upcoming] == ["match_end"]


async def test_startup_marks_past_as_missed(tmp_path):
    rig = make_rig(tmp_path, at(10, 0))
    rig.write([match(at(9, 0)), match(at(9, 59, 30))])
    engine = rig.engine()
    await engine.start()
    try:
        assert statuses(engine) == [
            (key("match_start", at(9, 0)), "missed"),
            (key("match_end", at(9, 20)), "missed"),
        ]
        await until(lambda: len(engine.history) == 3)  # 09:59:30 is only 30 s late: plays
    finally:
        await engine.stop()
    assert statuses(engine)[2] == (key("match_start", at(9, 59, 30)), "played")
    assert rig.played() == [START_MSG]
    handled = json.loads((tmp_path / "state" / "handled.json").read_text())
    assert ["match_end", at(9, 20).isoformat()] in handled


async def test_startup_uses_store_when_source_fails(tmp_path):
    rig = make_rig(tmp_path, at(8, 0))
    store.save([match(at(9, 0))], rig.store_path)
    source = SwitchSource([])
    source.error = "offline"
    engine = rig.engine(source)
    await engine.start()
    try:
        assert engine.matches_count == 1
        assert len(engine.upcoming) == 2
        assert engine.source_error == "offline"
        assert engine.source_ok_at is None
    finally:
        await engine.stop()


async def test_source_error_keeps_schedule(tmp_path):
    rig = make_rig(tmp_path, at(8, 0), make_cfg(poll_seconds=5))
    source = SwitchSource([match(at(9, 0)), match(at(9, 30))])
    engine = rig.engine(source)
    await engine.start()
    try:
        assert engine.source_error is None
        assert engine.source_ok_at is not None
        ok_at = engine.source_ok_at
        before = list(engine.upcoming)
        source.error = "site down"
        calls = source.calls
        await until(lambda: source.calls > calls and engine.source_error is not None)
        assert engine.source_error == "site down"
        assert engine.upcoming == before
        assert engine.matches_count == 2
        assert engine.source_ok_at == ok_at
        source.error = None
        await until(lambda: engine.source_error is None)
    finally:
        await engine.stop()


async def test_manual_waits_for_running_session(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        await until(lambda: rig.times("hold") != [])
        await engine.manual_text(["SC1"], "Hello there")
        await until(lambda: len(engine.history) == 2)
    finally:
        await engine.stop()
    assert [h.status for h in engine.history] == ["played", "played"]
    assert engine.history[1].key[0] == "manual_text"
    first_release = rig.kinds().index(("release", "SPREKEN"))
    assert rig.kinds()[first_release + 1 :] == [
        ("tap", "SC1"),
        ("hold", "SPREKEN"),
        ("release", "SPREKEN"),
        ("release_all", ""),
    ]
    assert rig.played() == [START_MSG, "Hello there"]


async def test_manual_waits_while_paused(tmp_path):
    rig = make_rig(tmp_path, at(8, 0))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    engine.pause()
    await engine.start()
    try:
        await engine.manual_text(["SC2"], "Lunch is ready")
        t = rig.clock.now()
        await until_clock(rig.clock, t + timedelta(seconds=120))  # longer than late threshold
        assert engine.history == []
        assert rig.ctrl.events == []
        engine.resume()
        await until(lambda: len(engine.history) == 1)
    finally:
        await engine.stop()
    assert engine.history[0].status == "played"
    assert rig.kinds()[:3] == [("tap", "SC2"), ("hold", "SPREKEN"), ("release", "SPREKEN")]


async def test_failure_marks_failed_and_engine_continues(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0), minutes=1)])
    engine = rig.engine()
    rig.tts.fail = True
    await engine.start()
    try:
        await until(lambda: len(engine.history) == 1)
        rig.tts.fail = False
        await until(lambda: len(engine.history) == 2)
    finally:
        await engine.stop()
    first, second = engine.history
    assert (first.status, first.detail) == ("failed", "tts broke")
    assert second.status == "played"


async def test_talk_runs_while_paused_and_holds_the_lock(tmp_path):
    rig = make_rig(tmp_path, at(8, 0))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    engine.pause()
    await engine.start()
    try:
        await engine.talk_start(["SC1"])
        assert engine.talking
        assert rig.kinds() == [("tap", "SC1"), ("hold", "SPREKEN")]
        engine.resume()
        await engine.manual_text(["SC2"], "Waiting")
        t = rig.clock.now()
        await until_clock(rig.clock, t + timedelta(seconds=5))
        assert engine.history == []  # manual waits for the talk
        await engine.talk_stop()
        assert not engine.talking
        await until(lambda: len(engine.history) == 1)
    finally:
        await engine.stop()
    assert rig.kinds()[:5] == [
        ("tap", "SC1"),
        ("hold", "SPREKEN"),
        ("release", "SPREKEN"),
        ("tap", "SC2"),
        ("hold", "SPREKEN"),
    ]


async def test_reload_config_reconfigures_and_replans(tmp_path):
    rig = make_rig(tmp_path, at(8, 0))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        new = make_cfg()
        new.announce.lead_seconds = 10.0
        new.actuators["SC1"] = Actuator(channel=0, rest=20, press=50)
        await engine.reload_config(new)
        assert engine.cfg is new
        assert rig.ctrl.actuators["SC1"].rest == 20
        assert engine.upcoming[0].start_at == at(9, 0) - timedelta(seconds=10)
    finally:
        await engine.stop()


async def test_stop_releases_all(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    await until(lambda: rig.times("hold") != [])
    await engine.stop()
    assert rig.kinds()[-2:] == [("release", "SPREKEN"), ("release_all", "")]
    assert other_tasks() == []


async def test_stop_releases_all_during_talk(tmp_path):
    rig = make_rig(tmp_path, at(8, 0))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    await engine.talk_start(["SC1"])
    await engine.stop()
    assert rig.kinds()[-2:] == [("release", "SPREKEN"), ("release_all", "")]
    assert other_tasks() == []


async def test_stop_when_session_ends_with_error_after_cancel(tmp_path, caplog):
    # player fails, and stop() cancels while the error-path release is still running:
    # the session task then ends with the RuntimeError, not CancelledError
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    rig.player.fail = True
    rig.ctrl.release_delay_s = 30.0
    await engine.start()
    await until(lambda: rig.times("hold") != [])
    await until_clock(rig.clock, rig.times("hold")[0] + timedelta(seconds=4))
    assert rig.times("release") == []  # release in progress
    with caplog.at_level(logging.WARNING, logger="announcer.engine"):
        await engine.stop()
    assert any("mock playback failure" in r.getMessage() for r in caplog.records)
    assert rig.kinds()[-2:] == [("release", "SPREKEN"), ("release_all", "")]
    assert other_tasks() == []


async def test_manual_does_not_bypass_pause_after_talk(tmp_path):
    # regression: run loop queued on the lock behind a talk, then ran without re-checking pause
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        await until(lambda: rig.times("hold") != [])  # scheduled session running
        talk = asyncio.create_task(engine.talk_start(["SC1"]))  # waits for the lock
        await engine.manual_text(["SC2"], "queued")
        await until(lambda: len(engine.history) == 1)
        await talk
        engine.pause()
        await engine.talk_stop()
        t = rig.clock.now()
        await until_clock(rig.clock, t + timedelta(seconds=30))
        assert len(engine.history) == 1, "manual played while paused"
        engine.resume()
        await until(lambda: len(engine.history) == 2)
    finally:
        await engine.stop()
    assert engine.history[1].key[0] == "manual_text"


async def test_scheduled_is_skipped_when_late_after_talk(tmp_path):
    # regression: captured scheduled session played after waiting > late threshold for the lock
    rig = make_rig(tmp_path, at(8, 59, 40))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        rig.tts.seconds = 25.0
        await engine.manual_text(["SC2"], "long manual")  # runs first
        await until(lambda: rig.times("hold") != [])
        talk = asyncio.create_task(engine.talk_start(["SC1"]))
        await until_clock(rig.clock, at(8, 59, 58))  # scheduled start_at passes meanwhile
        await until(lambda: len(engine.history) == 1, timeout=5)
        await talk
        await until_clock(rig.clock, at(9, 2, 30))  # talk lasts past the late threshold
        await engine.talk_stop()
        await until(lambda: len(engine.history) == 2, timeout=5)
    finally:
        await engine.stop()
    assert statuses(engine)[1] == (key("match_start", at(9, 0)), "skipped")
    assert rig.played() == ["long manual"]


async def test_talk_without_stop_ends_at_max_hold(tmp_path):
    cfg = make_cfg()
    cfg.controller.max_hold_s = 10
    rig = make_rig(tmp_path, at(8, 59, 30), cfg)
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        await engine.talk_start(["SC1"])  # never stopped
        await until(lambda: len(engine.history) == 1)
        assert not engine.talking
    finally:
        await engine.stop()
    assert statuses(engine) == [(key("match_start", at(9, 0)), "played")]
    assert rig.kinds()[:3] == [("tap", "SC1"), ("hold", "SPREKEN"), ("release", "SPREKEN")]


async def test_talk_start_raises_runtime_error_when_stopped_while_waiting(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    await until(lambda: rig.times("hold") != [])
    talk = asyncio.create_task(engine.talk_start(["SC1"]))  # waits for the lock
    await asyncio.sleep(0.001)
    await engine.stop()
    with pytest.raises(RuntimeError, match="engine stopped"):
        await talk


async def test_poll_during_session_does_not_replay_or_show_it_upcoming(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50), make_cfg(poll_seconds=1))
    rig.write([match(at(9, 0))])
    rig.tts.seconds = 10.0  # session lasts ~15 s of clock: many polls/replans meanwhile
    engine = rig.engine()
    await engine.start()
    try:
        await until(lambda: rig.times("hold") != [])
        running = engine.current
        assert running is not None
        assert running.announcements[0].key == key("match_start", at(9, 0))
        t = rig.clock.now()
        while rig.clock.now() < t + timedelta(seconds=8):
            assert engine.current == running
            assert all(running.announcements[0] not in s.announcements for s in engine.upcoming)
            await asyncio.sleep(0.001)
        await until(lambda: engine.history != [])
        assert engine.current is None
        await until_clock(rig.clock, rig.clock.now() + timedelta(seconds=5))
    finally:
        await engine.stop()
    assert statuses(engine) == [(key("match_start", at(9, 0)), "played")]
    assert len(rig.times("hold")) == 1


async def test_presynth_before_start_at(tmp_path):
    cfg = make_cfg()
    cfg.messages["match_start"] = "Start of {time}."  # not plain: cannot be pre-warmed
    rig = make_rig(tmp_path, at(8, 59, 0), cfg)
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    start_at = engine.upcoming[0].start_at
    try:
        await until(lambda: engine.history != [])
        # plain template pre-warmed on start, far before its 09:19:55 session
        assert rig.tts.synth_at[END_MSG] < start_at - timedelta(seconds=30)
        # the next session's text synthesised as soon as it became next
        assert rig.tts.synth_at["Start of 09:00."] < start_at - timedelta(seconds=30)
    finally:
        await engine.stop()
    assert rig.played() == ["Start of 09:00."]
    assert rig.tts.texts.count("Start of 09:00.") == 1  # reused at start_at


async def test_poll_loop_survives_replan_error(tmp_path, monkeypatch):
    rig = make_rig(tmp_path, at(8, 0), make_cfg(poll_seconds=5))
    source = SwitchSource([match(at(9, 0))])
    engine = rig.engine(source)
    await engine.start()
    try:
        orig = engine._replan
        calls = {"n": 0}

        def broken() -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("replan broke")
            orig()

        monkeypatch.setattr(engine, "_replan", broken)
        await until(lambda: calls["n"] >= 3)
    finally:
        await engine.stop()


async def test_reload_config_keeps_old_cfg_when_configure_fails(tmp_path):
    rig = make_rig(tmp_path, at(8, 0))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    old = engine.cfg
    try:
        rig.ctrl.fail_on = {"configure"}
        new = make_cfg()
        new.announce.lead_seconds = 10.0
        with pytest.raises(ControllerError):
            await engine.reload_config(new)
        assert engine.cfg is old
        assert engine.upcoming[0].start_at == at(9, 0) - timedelta(seconds=lead_seconds(old))
    finally:
        rig.ctrl.fail_on = set()
        await engine.stop()


async def test_bad_render_does_not_stall_engine(tmp_path, caplog):
    # regression: a render error in pre-synth aborted every run-loop step
    cfg = make_cfg()
    cfg.messages["match_start"] = "Fields {fields:d}"  # bypasses validation; fails at render
    rig = make_rig(tmp_path, at(8, 59, 30), cfg)
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        with caplog.at_level(logging.ERROR, logger="announcer.engine"):
            await engine.manual_text(["SC1"], "manual still plays")
            await until(lambda: len(engine.history) == 2)
    finally:
        await engine.stop()
    (manual_key, manual_status), (sched_key, sched_status) = statuses(engine)
    assert (manual_key[0], manual_status) == ("manual_text", "played")
    assert (sched_key, sched_status) == (key("match_start", at(9, 0)), "failed")
    assert "Unknown format code" in engine.history[1].detail
    assert rig.played() == ["manual still plays"]
    # logged once by pre-synth and once by the failed session, not every tick
    assert len([r for r in caplog.records if "render" in r.getMessage()]) == 1


async def test_reload_config_rebuilds_tts_when_tts_settings_change(tmp_path):
    rig = make_rig(tmp_path, at(8, 0))
    rig.write([match(at(9, 0))])
    built: list = []

    def factory(tts_cfg):
        built.append(tts_cfg)
        return FakeTts(tmp_path / "tts2", rig.clock)

    engine = Engine(
        rig.cfg,
        FileSource(rig.schedule_file, TZ),
        rig.store_path,
        rig.ctrl,
        rig.player,
        rig.tts,
        rig.clock,
        tts_factory=factory,
    )
    await engine.start()
    try:
        same = make_cfg()
        await engine.reload_config(same)  # tts settings unchanged: keep the instance
        assert built == []
        new = make_cfg()
        new.tts.length_scale = 1.3
        await engine.reload_config(new)
        assert built == [new.tts]
        await engine.manual_text(["SC1"], "new voice")
        await until(lambda: engine.history != [])
    finally:
        await engine.stop()
    assert engine.history[0].status == "played"
    assert rig.player.played[-1].parent == tmp_path / "tts2"


# disconnected controller, bounded audio, interrupted holds (final review I4, I5, I6)


async def test_disconnected_session_waits_then_is_skipped_late(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.ctrl.connected = False
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        await until_clock(rig.clock, at(9, 0, 30))
        assert engine.history == []  # not failed at start_at: it may still reconnect in time
        await until(lambda: engine.history != [])
        assert statuses(engine) == [(key("match_start", at(9, 0)), "skipped")]
        assert rig.ctrl.events == []
        assert engine.history[0].detail == "late"
    finally:
        await engine.stop()


async def test_reconnect_within_late_threshold_still_plays(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.ctrl.connected = False
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        await until_clock(rig.clock, at(9, 0, 20))
        assert engine.history == []
        rig.ctrl.connected = True
        await until(lambda: engine.history != [])
        assert statuses(engine) == [(key("match_start", at(9, 0)), "played")]
    finally:
        await engine.stop()


async def test_play_now_without_connection_fails_clearly(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.ctrl.connected = False
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        await until(lambda: engine.history != [])
        rig.ctrl.fail_on = {"tap"}  # what a disconnected SerialController does
        await engine.play_now(key("match_start", at(9, 0)))
        assert engine.history[-1].status == "failed"
        assert "mock failure on tap" in engine.history[-1].detail
    finally:
        await engine.stop()


class HangingPlayer(MockPlayer):
    """Never returns from its first play (a stuck audio device), later plays work."""

    def __init__(self, clock: SimClock) -> None:
        super().__init__(clock)
        self.hung = 0

    async def play(self, path: Path) -> None:
        if not self.hung:
            self.hung += 1
            await asyncio.Event().wait()
        await super().play(path)


async def test_hung_audio_fails_session_frees_lock_and_later_sessions_run(tmp_path, monkeypatch):
    monkeypatch.setattr("announcer.sequencer.PLAY_MARGIN_S", 0.02)
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.player = HangingPlayer(rig.clock)
    rig.tts.seconds = 0.01  # the bound runs in real time: keep it short against the sim clock
    rig.write([match(at(9, 0), minutes=1)])
    engine = rig.engine()
    await engine.start()
    try:
        await until(lambda: len(engine.history) == 2, timeout=5.0)
        assert statuses(engine) == [
            (key("match_start", at(9, 0)), "failed"),
            (key("match_end", at(9, 1)), "played"),
        ]
        assert "did not finish" in engine.history[0].detail
        assert rig.times("release") and len(rig.times("release")) == 2
        assert not engine._lock.locked()
    finally:
        await engine.stop()


async def test_interrupted_hold_is_failed_and_can_be_played_again(tmp_path):
    rig = make_rig(tmp_path, at(8, 59, 50))
    rig.write([match(at(9, 0))])
    engine = rig.engine()
    await engine.start()
    try:
        await until(lambda: rig.times("hold") != [])
        rig.ctrl.simulate_interruption("EVT MAXHOLD 2")
        await until(lambda: engine.history != [])
        assert statuses(engine) == [(key("match_start", at(9, 0)), "failed")]
        assert "EVT MAXHOLD 2" in engine.history[0].detail
        assert rig.ctrl.last_event == "EVT MAXHOLD 2"
        assert rig.times("release")
        await engine.play_now(key("match_start", at(9, 0)))
        assert engine.history[-1].status == "played"
    finally:
        await engine.stop()


async def test_skipped_blocks_of_the_source_are_exposed(tmp_path):
    rig = make_rig(tmp_path, at(8, 0))
    source = SwitchSource([match(at(9, 0))])
    source.skipped_blocks = 2
    engine = rig.engine(source)
    await engine.start()
    try:
        assert engine.source_skipped == 2
        assert engine.matches_count == 1
    finally:
        await engine.stop()
