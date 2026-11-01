"""Configuration loading, validation and saving (TOML)."""

from __future__ import annotations

import string
import tomllib
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

import tomli_w

FORBIDDEN_BUTTONS = {"ONTRUIMINGSALARM", "KOPPEL_RUIMTES", "KOPPELRUIMTES"}
ALLOWED_PLACEHOLDERS = {"time", "count", "fields", "halls"}
REQUIRED_MESSAGES = ("match_start", "match_end")
# sample values with the same types as planner.render_message, for a trial render
SAMPLE_RENDER = {"time": "09:00", "count": 1, "fields": "Field 1", "halls": "SC1"}
MAX_ANGLE = 180
MAX_CHANNEL = 7
# firmware limits (firmware/PROTOCOL.md): WATCHDOG and MAXHOLD caps
MAX_WATCHDOG_MS = 10_000
MAX_MAXHOLD_MS = 120_000


class ConfigError(Exception):
    pass


@dataclass
class Actuator:
    channel: int
    rest: int
    press: int
    press_ms: int = 250
    release_ms: int = 250


@dataclass
class Controller:
    port: str = "/dev/ttyACM0"
    keepalive_ms: int = 500
    watchdog_ms: int = 2000
    max_hold_s: int = 60


@dataclass
class Announce:
    halls: list[str] = field(default_factory=lambda: ["SC1", "SC2", "SC3"])
    chime_seconds: float = 3.0
    tail_seconds: float = 0.5
    deselect_zones_after: bool = False
    lead_seconds: float | None = None
    late_threshold_seconds: int = 60
    merge_window_seconds: int = 30


@dataclass
class Tts:
    voice_model: str = "voices/en_US-lessac-medium.onnx"
    length_scale: float = 1.0
    cache_dir: str = "cache/tts"


@dataclass
class Audio:
    device: str | None = None
    volume: float = 1.0


def _default_round_minutes() -> dict[str, int]:
    return {"Round 1": 15, "Round 2": 15, "Round 3": 20, "Round 4": 20, "Round 5": 20}


@dataclass
class Schedule:
    kind: Literal["cupkit", "file"] = "cupkit"
    matches_urls: list[str] = field(default_factory=list)
    round_minutes: dict[str, int] = field(default_factory=_default_round_minutes)
    file: str = "schedule.json"
    poll_seconds: int = 60
    store: str = "state/schedule.json"
    default_match_minutes: int = 20
    timezone: str = "Europe/Amsterdam"


def _default_messages() -> dict[str, str]:
    return {
        "match_start": "Referees, you may start the matches.",
        "match_end": "Referees, you may end the matches.",
    }


@dataclass
class Config:
    controller: Controller = field(default_factory=Controller)
    actuators: dict[str, Actuator] = field(default_factory=dict)
    announce: Announce = field(default_factory=Announce)
    messages: dict[str, str] = field(default_factory=_default_messages)
    tts: Tts = field(default_factory=Tts)
    audio: Audio = field(default_factory=Audio)
    schedule: Schedule = field(default_factory=Schedule)


def _check_template(name: str, template: str) -> None:
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as e:
        raise ConfigError(f"message {name!r} is not a valid template: {e}") from e
    for _literal, field_name, _spec, _conv in parsed:
        if field_name is not None and field_name not in ALLOWED_PLACEHOLDERS:
            allowed = ", ".join(sorted(ALLOWED_PLACEHOLDERS))
            raise ConfigError(
                f"message {name!r} uses unknown placeholder {{{field_name}}}; allowed: {allowed}"
            )
    try:
        template.format_map(SAMPLE_RENDER)
    except Exception as e:  # e.g. a format spec that does not fit the value: {fields:d}
        raise ConfigError(f"message {name!r} cannot be rendered: {e}") from e


def validate(cfg: Config) -> None:
    # controller
    c = cfg.controller
    if not 1 <= c.watchdog_ms <= MAX_WATCHDOG_MS:
        raise ConfigError(f"controller.watchdog_ms={c.watchdog_ms} not in 1..{MAX_WATCHDOG_MS}")
    max_hold_s = MAX_MAXHOLD_MS // 1000
    if not 1 <= c.max_hold_s <= max_hold_s:
        raise ConfigError(f"controller.max_hold_s={c.max_hold_s} not in 1..{max_hold_s}")
    if not 1 <= c.keepalive_ms <= c.watchdog_ms // 2:  # a late ping must not trip the watchdog
        raise ConfigError(
            f"controller.keepalive_ms={c.keepalive_ms} must be in 1..watchdog_ms // 2"
        )
    # actuators
    channels: dict[int, str] = {}
    for name, act in cfg.actuators.items():
        if name.upper() in FORBIDDEN_BUTTONS:
            raise ConfigError(f"actuator {name!r} is forbidden (must never be pressed)")
        for attr in ("rest", "press"):
            value = getattr(act, attr)
            if not isinstance(value, int) or not 0 <= value <= MAX_ANGLE:
                raise ConfigError(f"actuator {name!r}: {attr}={value!r} not in 0..{MAX_ANGLE}")
        for attr in ("press_ms", "release_ms"):
            if getattr(act, attr) < 0:
                raise ConfigError(f"actuator {name!r}: {attr} must be >= 0")
        if not isinstance(act.channel, int) or not 0 <= act.channel <= MAX_CHANNEL:
            raise ConfigError(f"actuator {name!r}: channel={act.channel!r} not in 0..{MAX_CHANNEL}")
        if act.channel in channels:
            raise ConfigError(
                f"actuators {channels[act.channel]!r} and {name!r} share channel {act.channel}"
            )
        channels[act.channel] = name
    if "SPREKEN" not in cfg.actuators:
        raise ConfigError("actuator 'SPREKEN' is required")
    for hall in cfg.announce.halls:
        if hall not in cfg.actuators:
            raise ConfigError(f"hall {hall!r} has no actuator")
    # messages
    for key in REQUIRED_MESSAGES:
        if key not in cfg.messages:
            raise ConfigError(f"message {key!r} is required")
    for name, template in cfg.messages.items():
        _check_template(name, template)
    # schedule
    for round_name, minutes in cfg.schedule.round_minutes.items():
        if not isinstance(minutes, int) or minutes <= 0:
            raise ConfigError(f"round_minutes[{round_name!r}] must be a positive integer")
    if cfg.schedule.default_match_minutes <= 0:
        raise ConfigError("default_match_minutes must be positive")
    if cfg.schedule.kind not in ("cupkit", "file"):
        raise ConfigError(f"schedule.kind {cfg.schedule.kind!r} must be 'cupkit' or 'file'")


def _section(cls: type, data: Any, name: str) -> Any:
    if not isinstance(data, dict):
        raise ConfigError(f"[{name}] must be a table")
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"[{name}]: unknown keys {sorted(unknown)}")
    try:
        return cls(**data)
    except TypeError as e:
        raise ConfigError(f"[{name}]: {e}") from e


def _from_dict(raw: dict[str, Any]) -> Config:
    known = {f.name for f in fields(Config)}
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(f"unknown sections {sorted(unknown)}")
    kwargs: dict[str, Any] = {}
    for name, cls in (
        ("controller", Controller),
        ("announce", Announce),
        ("tts", Tts),
        ("audio", Audio),
        ("schedule", Schedule),
    ):
        if name in raw:
            kwargs[name] = _section(cls, raw[name], name)
    if "actuators" in raw:
        acts = raw["actuators"]
        if not isinstance(acts, dict):
            raise ConfigError("[actuators] must be a table")
        kwargs["actuators"] = {n: _section(Actuator, a, f"actuators.{n}") for n, a in acts.items()}
    if "messages" in raw:
        msgs = raw["messages"]
        if not isinstance(msgs, dict) or not all(isinstance(v, str) for v in msgs.values()):
            raise ConfigError("[messages] must be a table of strings")
        kwargs["messages"] = dict(msgs)
    return Config(**kwargs)


def load(path: Path) -> Config:
    try:
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"cannot read {path}: {e}") from e
    cfg = _from_dict(raw)
    validate(cfg)
    return cfg


def _strip_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    return value


def save(cfg: Config, path: Path) -> None:
    validate(cfg)
    data = _strip_none(asdict(cfg))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(tomli_w.dumps(data))
    tmp.replace(path)
