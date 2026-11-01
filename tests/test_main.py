import asyncio
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from announcer import config, inhibit
from announcer.audio.player import MockPlayer, SoundPlayer
from announcer.clock import RealClock, SimClock
from announcer.config import Actuator, Config
from announcer.controller.mock import MockController
from announcer.engine import HistoryEntry
from announcer.gui import view
from announcer.main import build_runtime, parse_args, reset_sim_state
from announcer.schedule.cupkit import CupkitSource
from announcer.schedule.filesource import FileSource

REPO = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Europe/Amsterdam")


@pytest.fixture
def cfg_path(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    shutil.copy(REPO / "config.example.toml", path)
    return path


def runtime(cfg_path: Path, *argv: str):
    return build_runtime(parse_args(["--config", str(cfg_path), *argv]))


# CLI


def test_cli_parses_sim_args(cfg_path: Path) -> None:
    rt = runtime(cfg_path, "--mock", "--sim-start", "2026-12-18T08:55", "--sim-speed", "60")
    assert isinstance(rt.clock, SimClock)
    assert rt.clock.start == datetime(2026, 12, 18, 8, 55, tzinfo=TZ)
    assert rt.clock.speed == 60
    assert isinstance(rt.ctrl, MockController)
    assert isinstance(rt.player, MockPlayer)
    assert rt.sim


def test_cli_defaults(cfg_path: Path) -> None:
    args = parse_args(["--config", str(cfg_path), "--mock"])
    assert args.port == 8080
    rt = build_runtime(args)
    assert isinstance(rt.clock, RealClock)
    assert isinstance(rt.player, SoundPlayer)
    assert not rt.sim
    assert rt.store_path == Path("state/schedule.json")


def test_sim_speed_1_plays_real_audio(cfg_path: Path) -> None:
    rt = runtime(cfg_path, "--mock", "--sim-start", "2026-12-18T08:55", "--sim-speed", "1")
    assert isinstance(rt.player, SoundPlayer)


def test_sim_start_alone_defaults_speed(cfg_path: Path) -> None:
    rt = runtime(cfg_path, "--mock", "--sim-start", "2026-12-18T08:55")
    assert isinstance(rt.clock, SimClock)
    assert rt.clock.speed == 60


def test_sim_store_path_differs_from_real(cfg_path: Path) -> None:
    real = runtime(cfg_path, "--mock")
    sim = runtime(cfg_path, "--mock", "--sim-start", "2026-12-18T08:55", "--sim-speed", "60")
    assert sim.store_path != real.store_path
    assert sim.store_path.parent != real.store_path.parent  # handled.json lives next to it
    assert sim.store_path == Path("state/sim/schedule.json")


def test_state_dir_overrides_store(cfg_path: Path, tmp_path: Path) -> None:
    rt = runtime(cfg_path, "--mock", "--sim-speed", "60", "--state-dir", str(tmp_path / "s"))
    assert rt.store_path == tmp_path / "s" / "schedule.json"
    assert rt.fresh_sim_state is False


def test_reset_sim_state_removes_only_handled(tmp_path: Path) -> None:
    store = tmp_path / "sim" / "schedule.json"
    store.parent.mkdir()
    store.write_text("{}")
    (store.parent / "handled.json").write_text("[]")
    reset_sim_state(store)
    assert store.exists()
    assert not (store.parent / "handled.json").exists()
    reset_sim_state(store)  # nothing to remove: no error


def test_source_override(cfg_path: Path) -> None:
    assert isinstance(runtime(cfg_path, "--mock", "--source", "file").source, FileSource)
    assert isinstance(runtime(cfg_path, "--mock", "--source", "cupkit").source, CupkitSource)
    assert isinstance(runtime(cfg_path, "--mock").source, CupkitSource)  # config kind


def test_source_override_does_not_change_config(cfg_path: Path) -> None:
    rt = runtime(cfg_path, "--mock", "--source", "file", "--sim-speed", "60")
    assert rt.cfg.schedule.kind == "cupkit"  # a GUI save must not persist CLI overrides
    assert rt.cfg.schedule.store == "state/schedule.json"


def test_without_mock_fails_fast_if_serial_missing(
    cfg_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "announcer.controller.serial_ctrl", None)
    with pytest.raises(SystemExit, match="serial controller not available yet; use --mock"):
        runtime(cfg_path)


def test_bad_config_exits_with_message(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="cannot read"):
        build_runtime(parse_args(["--config", str(tmp_path / "missing.toml"), "--mock"]))


# sleep inhibitor


class FakeProc:
    def __init__(self, argv: list[str], **kwargs: object) -> None:
        self.argv = argv
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_inhibitor_spawns_and_kills(monkeypatch: pytest.MonkeyPatch) -> None:
    procs: list[FakeProc] = []

    def popen(argv: list[str], **kwargs: object) -> FakeProc:
        procs.append(FakeProc(argv, **kwargs))
        return procs[-1]

    monkeypatch.setattr(inhibit.subprocess, "Popen", popen)
    with inhibit.Inhibitor():
        assert procs[0].argv == [
            "systemd-inhibit",
            "--what=sleep:idle",
            "--who=announcer",
            "--why=tournament announcements",
            "sleep",
            "infinity",
        ]
        assert not procs[0].terminated
    assert procs[0].terminated


def test_inhibitor_kills_if_terminate_hangs(monkeypatch: pytest.MonkeyPatch) -> None:
    class Stuck(FakeProc):
        def wait(self, timeout: float | None = None) -> int:
            if not self.killed:
                raise subprocess.TimeoutExpired("systemd-inhibit", timeout or 0)
            return 0

    procs: list[Stuck] = []
    monkeypatch.setattr(
        inhibit.subprocess, "Popen", lambda a, **k: procs.append(Stuck(a)) or procs[-1]
    )
    with inhibit.Inhibitor():
        pass
    assert procs[0].killed


def test_inhibitor_missing_warns_and_continues(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def popen(argv: list[str], **kwargs: object) -> None:
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(inhibit.subprocess, "Popen", popen)
    with inhibit.Inhibitor():
        pass
    assert "systemd-inhibit" in caplog.text


# GUI helpers


def make_cfg() -> Config:
    cfg = Config()
    cfg.actuators = {
        "SC1": Actuator(channel=0, rest=10, press=40),
        "SC2": Actuator(channel=1, rest=10, press=40),
        "SPREKEN": Actuator(channel=2, rest=10, press=40),
    }
    cfg.announce.halls = ["SC1"]
    return cfg


def test_hall_choices_exclude_spreken() -> None:
    assert view.hall_choices(make_cfg()) == ["SC1", "SC2"]


def test_fmt_countdown() -> None:
    assert view.fmt_countdown(-3) == "now"
    assert view.fmt_countdown(65.4) == "01:05"
    assert view.fmt_countdown(3 * 3600 + 61) == "3:01:01"


def test_fmt_age() -> None:
    now = datetime(2026, 12, 18, 9, 0, tzinfo=TZ)
    assert view.fmt_age(now, None) == "never"
    assert view.fmt_age(now, datetime(2026, 12, 18, 8, 59, 48, tzinfo=TZ)) == "12 s ago"
    assert view.fmt_age(now, datetime(2026, 12, 18, 8, 55, tzinfo=TZ)) == "5 min ago"


def test_history_rows_newest_first_and_replayable() -> None:
    t = [datetime(2026, 12, 18, 9, m, tzinfo=TZ) for m in range(5)]
    a, b, c = ("match_start", "A"), ("match_end", "B"), ("match_start", "C")
    rows = view.history_rows(
        [
            HistoryEntry(t[0], a, "skipped", "late"),
            HistoryEntry(t[1], b, "failed", "boom"),
            HistoryEntry(t[2], c, "played"),
            HistoryEntry(t[3], a, "played"),  # a was played now later
        ]
    )
    assert [r.key for r in rows] == [a, c, b, a]
    assert [r.replayable for r in rows] == [False, False, True, False]


async def test_apply_config_saves_and_reloads(tmp_path: Path) -> None:
    class FakeEngine:
        def __init__(self) -> None:
            self.cfg = make_cfg()
            self.reloaded: list[Config] = []

        async def reload_config(self, cfg: Config) -> None:
            self.reloaded.append(cfg)

    engine = FakeEngine()
    player = SoundPlayer(None, 1.0)
    path = tmp_path / "config.toml"

    def edit(cfg: Config) -> None:
        cfg.announce.chime_seconds = 4.5
        cfg.audio.volume = 0.5

    assert await view.apply_config(engine, path, edit, player) is None
    assert config.load(path).announce.chime_seconds == 4.5
    assert engine.reloaded[0].announce.chime_seconds == 4.5
    assert engine.cfg.announce.chime_seconds == 3.0  # the engine swaps it in itself
    assert player.volume == 0.5

    def bad(cfg: Config) -> None:
        cfg.announce.halls = ["NOPE"]

    error = await view.apply_config(engine, path, bad, player)
    assert error is not None and "NOPE" in error
    assert len(engine.reloaded) == 1
    assert engine.cfg.announce.halls == ["SC1"]  # live config untouched


async def test_apply_config_reports_reload_failure(tmp_path: Path) -> None:
    class FailingEngine:
        cfg = make_cfg()

        async def reload_config(self, cfg: Config) -> None:
            raise RuntimeError("controller gone")

    error = await view.apply_config(FailingEngine(), tmp_path / "c.toml", lambda c: None)
    assert error is not None and "controller gone" in error


class FakeTalkEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.gate = asyncio.Event()

    async def talk_start(self, halls: tuple[str, ...]) -> None:
        self.calls.append("start")
        await self.gate.wait()  # waiting for the desk lock

    async def talk_stop(self) -> None:
        self.calls.append("stop")


async def test_talk_hold_release_before_start_returns_still_stops() -> None:
    engine = FakeTalkEngine()
    talk = view.TalkHold(engine)
    talk.press(["SC1"])
    await asyncio.sleep(0)
    talk.press(["SC1"])  # touchstart + mousedown: one talk
    await talk.release()
    engine.gate.set()
    await talk.wait()
    assert engine.calls == ["start", "stop", "stop"]


async def test_talk_hold_release_before_task_runs_never_starts() -> None:
    engine = FakeTalkEngine()
    talk = view.TalkHold(engine)
    talk.press(["SC1"])
    await talk.release()
    await talk.wait()
    assert engine.calls == ["stop"]


async def test_talk_hold_release_without_press_does_nothing() -> None:
    engine = FakeTalkEngine()
    talk = view.TalkHold(engine)
    await talk.release()  # mouseleave / tab closed without a press
    talk.press(["SC1"])
    await asyncio.sleep(0)
    await talk.release()
    await talk.release()  # mouseup then mouseleave
    engine.gate.set()
    await talk.wait()
    assert engine.calls == ["start", "stop", "stop"]


async def test_talk_hold_records_error() -> None:
    class Stopped(FakeTalkEngine):
        async def talk_start(self, halls: tuple[str, ...]) -> None:
            raise RuntimeError("engine stopped")

    talk = view.TalkHold(Stopped())
    talk.press(["SC1"])
    await talk.wait()
    assert talk.error == "engine stopped"
