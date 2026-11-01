"""Command line entry point: build the runtime from config + flags, run the GUI."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from announcer import config
from announcer.audio.player import MockPlayer, Player, SoundPlayer
from announcer.audio.tts import Tts
from announcer.clock import Clock, RealClock, SimClock
from announcer.config import Config, ConfigError
from announcer.config import Tts as TtsConfig
from announcer.controller.base import Controller
from announcer.controller.mock import MockController
from announcer.engine import Synth
from announcer.schedule.cupkit import CupkitSource
from announcer.schedule.filesource import FileSource
from announcer.schedule.source import ScheduleSource

log = logging.getLogger(__name__)

DEFAULT_SIM_SPEED = 60.0
SIM_STATE_DIR = "sim"  # next to the real store: state/sim/schedule.json


@dataclass
class Runtime:
    cfg: Config
    cfg_path: Path
    clock: Clock
    ctrl: Controller
    player: Player
    source: ScheduleSource
    store_path: Path
    tts_factory: Callable[[TtsConfig], Synth]
    sim: bool
    fresh_sim_state: bool  # sim run on the default sim state dir: forget handled.json


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="announcer", description="ISSTT IMPRO announcer")
    p.add_argument("--config", type=Path, default=Path("config.toml"), help="config TOML")
    p.add_argument("--mock", action="store_true", help="mock servo controller (no hardware)")
    p.add_argument(
        "--sim-start",
        type=datetime.fromisoformat,
        help="simulated clock start, e.g. 2026-12-18T08:55 (local time)",
    )
    p.add_argument(
        "--sim-speed",
        type=float,
        help=f"simulated clock speed (default {DEFAULT_SIM_SPEED:g}); not 1 => mock audio",
    )
    p.add_argument("--source", choices=["file", "cupkit"], help="override schedule.kind")
    p.add_argument(
        "--state-dir",
        type=Path,
        help="directory for schedule.json + handled.json (sim default: fresh state/sim/)",
    )
    p.add_argument("--host", default="127.0.0.1", help="GUI host (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8080, help="GUI port")
    return p.parse_args(argv)


def piper_tts(tts_cfg: TtsConfig) -> Synth:
    return Tts(Path(tts_cfg.voice_model), tts_cfg.length_scale, Path(tts_cfg.cache_dir))


def store_path(cfg: Config, args: argparse.Namespace, sim: bool) -> Path:
    """Sim runs never touch the real store: their handled.json would drop real announcements."""
    if args.state_dir is not None:
        return Path(args.state_dir) / "schedule.json"
    real = Path(cfg.schedule.store)
    if sim:
        return real.parent / SIM_STATE_DIR / "schedule.json"
    return real


def reset_sim_state(store: Path) -> None:
    """Forget what earlier rehearsals handled, so the same day can be replayed."""
    (store.parent / "handled.json").unlink(missing_ok=True)


def build_controller(args: argparse.Namespace, cfg: Config, clock: Clock) -> Controller:
    if args.mock:
        return MockController(clock, cfg.actuators)
    try:
        from announcer.controller.serial_ctrl import SerialController  # type: ignore[import-not-found]
    except ImportError:
        raise SystemExit("serial controller not available yet; use --mock") from None
    c = cfg.controller
    return SerialController(
        c.port, cfg.actuators, c.keepalive_ms, c.watchdog_ms, c.max_hold_s, clock
    )


def build_source(args: argparse.Namespace, cfg: Config) -> ScheduleSource:
    kind = args.source or cfg.schedule.kind
    if kind == "file":
        return FileSource(cfg.schedule.file, cfg.schedule.timezone)
    return CupkitSource(cfg.schedule.matches_urls, cfg.schedule.timezone)


def build_runtime(args: argparse.Namespace) -> Runtime:
    try:
        cfg = config.load(args.config)
    except ConfigError as e:
        raise SystemExit(f"config error: {e}") from None
    tz = cfg.schedule.timezone
    sim = args.sim_start is not None or args.sim_speed is not None
    clock: Clock
    if sim:
        start = args.sim_start or datetime.now(ZoneInfo(tz))
        if start.tzinfo is None:
            start = start.replace(tzinfo=ZoneInfo(tz))
        speed = args.sim_speed if args.sim_speed is not None else DEFAULT_SIM_SPEED
        try:
            clock = SimClock(start, speed)
        except ValueError as e:
            raise SystemExit(f"--sim-speed: {e}") from None
    else:
        clock = RealClock(tz)
    player: Player
    if sim and args.sim_speed != 1:
        player = MockPlayer(clock)  # audio cannot play faster than real time
    else:
        player = SoundPlayer(cfg.audio.device, cfg.audio.volume)
    return Runtime(
        cfg=cfg,
        cfg_path=Path(args.config),
        clock=clock,
        ctrl=build_controller(args, cfg, clock),
        player=player,
        source=build_source(args, cfg),
        store_path=store_path(cfg, args, sim),
        tts_factory=piper_tts,
        sim=sim,
        fresh_sim_state=sim and args.state_dir is None,
    )


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    rt = build_runtime(args)
    if rt.sim:
        log.warning("SIMULATION: clock %s, state in %s", rt.clock.now(), rt.store_path.parent)
    if rt.fresh_sim_state:
        reset_sim_state(rt.store_path)

    from announcer import inhibit
    from announcer.gui import app  # imports NiceGUI: only when actually serving

    with inhibit.Inhibitor():
        try:
            app.serve(rt, args.host, args.port)
        except KeyboardInterrupt:
            log.info("interrupted")


if __name__ == "__main__":
    main()
