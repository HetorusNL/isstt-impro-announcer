import asyncio
import logging
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
from announcer.planner import lead_seconds
from announcer.sequencer import _uninterruptible, run_session, talk_session

START = datetime(2026, 12, 18, 9, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
SPEED = 200.0
HALLS = ("SC1", "SC2")


def make_cfg(**announce) -> Config:
    cfg = Config()
    cfg.actuators = {
        "SC1": Actuator(channel=0, rest=10, press=40),
        "SC2": Actuator(channel=1, rest=10, press=40),
        "SPREKEN": Actuator(channel=2, rest=10, press=40),
    }
    cfg.announce.halls = list(HALLS)
    cfg.announce.chime_seconds = 3.0
    cfg.announce.tail_seconds = 0.5
    for k, v in announce.items():
        setattr(cfg.announce, k, v)
    return cfg


def silent_wav(tmp_path: Path, seconds: float, name: str = "clip.wav") -> Path:
    path = tmp_path / name
    sr = 8000
    sf.write(path, np.zeros(int(sr * seconds), dtype="int16"), sr)
    return path


def setup(cfg: Config, fail: bool = False, speed: float = SPEED):
    clock = SimClock(START, speed)
    ctrl = MockController(clock, cfg.actuators)
    player = MockPlayer(clock, fail=fail)
    return clock, ctrl, player


def event_time(ctrl: MockController, kind: str, button: str = "SPREKEN") -> datetime:
    return next(t for t, k, b in ctrl.events if k == kind and b == button)


async def test_session_order(tmp_path):
    cfg = make_cfg()
    clock, ctrl, player = setup(cfg)
    clip = silent_wav(tmp_path, 2.0)
    await run_session(ctrl, player, clock, cfg, HALLS, [clip])
    kinds = [(k, b) for _, k, b in ctrl.events]
    assert kinds == [("tap", "SC1"), ("tap", "SC2"), ("hold", "SPREKEN"), ("release", "SPREKEN")]
    hold_t, rel_t = event_time(ctrl, "hold"), event_time(ctrl, "release")
    assert rel_t - hold_t >= timedelta(seconds=3.0 + 2.0 + 0.5)
    assert player.played == [clip]
    assert player.played_at[0] - hold_t >= timedelta(seconds=3.0)  # speech after chime


async def test_mock_timing_matches_lead_seconds(tmp_path):
    # Task 6 relies on: session start + lead_seconds - chime ~= SPREKEN hold time
    cfg = make_cfg()
    clock, ctrl, player = setup(cfg)
    t0 = clock.now()
    await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.1)])
    expected = t0 + timedelta(seconds=lead_seconds(cfg) - cfg.announce.chime_seconds)
    assert abs((event_time(ctrl, "hold") - expected).total_seconds()) <= 1.0


async def test_multiple_clips_back_to_back(tmp_path):
    cfg = make_cfg()
    clock, ctrl, player = setup(cfg)
    a, b = silent_wav(tmp_path, 1.0, "a.wav"), silent_wav(tmp_path, 1.0, "b.wav")
    await run_session(ctrl, player, clock, cfg, HALLS, [a, b])
    assert player.played == [a, b]
    assert player.played_at[1] - player.played_at[0] >= timedelta(seconds=1.0)
    assert event_time(ctrl, "release") - player.played_at[1] >= timedelta(seconds=1.5)


async def test_deselect_after_when_enabled(tmp_path):
    cfg = make_cfg(deselect_zones_after=True)
    clock, ctrl, player = setup(cfg)
    await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.5)])
    kinds = [(k, b) for _, k, b in ctrl.events]
    assert kinds == [
        ("tap", "SC1"),
        ("tap", "SC2"),
        ("hold", "SPREKEN"),
        ("release", "SPREKEN"),
        ("tap", "SC1"),
        ("tap", "SC2"),
    ]


async def test_session_releases_on_player_error(tmp_path):
    cfg = make_cfg()
    clock, ctrl, player = setup(cfg, fail=True)
    with pytest.raises(RuntimeError):
        await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.5)])
    assert ctrl.events[-1][1:] == ("release", "SPREKEN")


async def test_session_releases_on_tap_error(tmp_path):
    cfg = make_cfg()
    clock, ctrl, player = setup(cfg)
    ctrl.fail_on = {"tap"}
    with pytest.raises(ControllerError):
        await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.5)])
    assert [(k, b) for _, k, b in ctrl.events] == [("release", "SPREKEN")]


async def test_release_failure_falls_back_to_release_all(tmp_path):
    cfg = make_cfg(deselect_zones_after=True)
    clock, ctrl, player = setup(cfg)
    ctrl.fail_on = {"release"}
    await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.5)])
    kinds = [(k, b) for _, k, b in ctrl.events]
    # release_all recorded, then the zones are still deselected (they are toggles)
    assert kinds == [
        ("tap", "SC1"),
        ("tap", "SC2"),
        ("hold", "SPREKEN"),
        ("release_all", ""),
        ("tap", "SC1"),
        ("tap", "SC2"),
    ]


async def test_deselect_after_player_error_still_raises(tmp_path):
    cfg = make_cfg(deselect_zones_after=True)
    clock, ctrl, player = setup(cfg, fail=True)
    with pytest.raises(RuntimeError):
        await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.5)])
    kinds = [(k, b) for _, k, b in ctrl.events]
    assert kinds[2:] == [("hold", "SPREKEN"), ("release", "SPREKEN"), ("tap", "SC1"), ("tap", "SC2")]


async def test_deselect_tap_failure_on_error_path_keeps_original_error(tmp_path):
    cfg = make_cfg(deselect_zones_after=True)
    clock, ctrl, player = setup(cfg, fail=True)

    async def flaky_tap(button, _orig=ctrl.tap):
        if any(k == "release" for _, k, _ in ctrl.events):
            raise ControllerError("tap broke")
        await _orig(button)

    ctrl.tap = flaky_tap
    with pytest.raises(RuntimeError):
        await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.5)])
    assert ctrl.events[-1][1:] == ("release", "SPREKEN")


async def test_deselect_only_halls_that_were_selected(tmp_path, caplog):
    cfg = make_cfg(deselect_zones_after=True)
    clock, ctrl, player = setup(cfg)
    ctrl.fail_on = {"tap:SC2"}
    with caplog.at_level(logging.WARNING, logger="announcer.sequencer"):
        with pytest.raises(ControllerError):
            await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.5)])
    kinds = [(k, b) for _, k, b in ctrl.events]
    # SPREKEN never held; release is harmless; SC2's state is unknown so it is not re-tapped
    assert kinds == [("tap", "SC1"), ("release", "SPREKEN"), ("tap", "SC1")]
    assert any(r.levelno == logging.WARNING and "SC2" in r.getMessage() for r in caplog.records)


async def test_no_deselect_on_cancel(tmp_path):
    cfg = make_cfg(deselect_zones_after=True)
    clock, ctrl, player = setup(cfg)
    task = asyncio.create_task(
        run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 2.0)])
    )
    while not any(k == "hold" for _, k, _ in ctrl.events):
        await asyncio.sleep(0.001)
    await asyncio.sleep(1.0 / SPEED)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert ctrl.events[-1][1:] == ("release", "SPREKEN")
    assert sum(1 for _, k, _ in ctrl.events if k == "tap") == 2


async def test_uninterruptible_keeps_cancel_that_lands_with_completion():
    outer: asyncio.Task | None = None

    async def inner() -> str:
        await asyncio.sleep(0)
        outer.cancel()  # cancel arrives in the same loop step the inner finishes
        return "done"

    async def body() -> str:
        return await _uninterruptible(inner())

    outer = asyncio.create_task(body())
    with pytest.raises(asyncio.CancelledError):
        await outer
    assert outer.cancelled()


async def test_release_and_release_all_failure_raises(tmp_path):
    cfg = make_cfg()
    clock, ctrl, player = setup(cfg)
    ctrl.fail_on = {"release", "release_all"}
    with pytest.raises(ControllerError):
        await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.5)])


async def test_original_error_wins_when_release_also_fails(tmp_path):
    cfg = make_cfg()
    clock, ctrl, player = setup(cfg, fail=True)
    ctrl.fail_on = {"release", "release_all"}
    with pytest.raises(RuntimeError):
        await run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 0.5)])


async def test_session_releases_on_cancel(tmp_path):
    cfg = make_cfg()
    clock, ctrl, player = setup(cfg)
    task = asyncio.create_task(
        run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 2.0)])
    )
    # wait until SPREKEN is held, then cancel during the chime
    while not any(k == "hold" for _, k, _ in ctrl.events):
        await asyncio.sleep(0.001)
    await asyncio.sleep(0.25 / SPEED + 1.0 / SPEED)  # past hold press_ms, inside the 3 s chime
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert player.played == []
    assert ctrl.events[-1][1:] == ("release", "SPREKEN")


async def test_session_release_survives_second_cancel(tmp_path):
    cfg = make_cfg()
    clock, ctrl, player = setup(cfg)
    ctrl.release_delay_s = 1.0  # make the release itself take time
    task = asyncio.create_task(
        run_session(ctrl, player, clock, cfg, HALLS, [silent_wav(tmp_path, 2.0)])
    )
    while not any(k == "hold" for _, k, _ in ctrl.events):
        await asyncio.sleep(0.001)
    await asyncio.sleep(1.0 / SPEED)
    task.cancel()
    await asyncio.sleep(0.2 / SPEED)  # first cancel delivered, release in progress
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert ctrl.events[-1][1:] == ("release", "SPREKEN")


async def test_talk_session_holds_and_releases():
    cfg = make_cfg()
    clock, ctrl, _ = setup(cfg)
    async with talk_session(ctrl, clock, cfg, HALLS):
        assert [(k, b) for _, k, b in ctrl.events] == [
            ("tap", "SC1"),
            ("tap", "SC2"),
            ("hold", "SPREKEN"),
        ]
    assert [(k, b) for _, k, b in ctrl.events][-1] == ("release", "SPREKEN")
    assert sum(1 for _, k, _ in ctrl.events if k == "release") == 1
    # watchdog task is gone after a normal exit
    assert not [t for t in asyncio.all_tasks() if "talk-watchdog" in t.get_name()]


async def test_talk_session_releases_on_body_error():
    cfg = make_cfg()
    clock, ctrl, _ = setup(cfg)
    with pytest.raises(ValueError):
        async with talk_session(ctrl, clock, cfg, HALLS):
            raise ValueError("boom")
    assert ctrl.events[-1][1:] == ("release", "SPREKEN")


async def test_talk_session_auto_releases_after_max_hold(caplog):
    cfg = make_cfg()
    cfg.controller.max_hold_s = 60
    clock, ctrl, _ = setup(cfg, speed=1000.0)
    with caplog.at_level(logging.WARNING, logger="announcer.sequencer"):
        async with talk_session(ctrl, clock, cfg, HALLS):
            hold_t = event_time(ctrl, "hold")
            while not any(k == "release" for _, k, _ in ctrl.events):
                await clock.sleep(1.0)
            rel_t = event_time(ctrl, "release")
            assert abs((rel_t - hold_t).total_seconds() - 60) <= 2.0
            await clock.sleep(5.0)
    # the exit does not repeat the watchdog's release
    assert sum(1 for _, k, _ in ctrl.events if k == "release") == 1
    assert any(r.levelno == logging.WARNING for r in caplog.records)
