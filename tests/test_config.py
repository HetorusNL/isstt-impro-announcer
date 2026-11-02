from dataclasses import replace
from pathlib import Path

import pytest

from announcer.config import Actuator, Config, ConfigError, load, save, validate

EXAMPLE = Path(__file__).parent.parent / "config.example.toml"


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(text)
    return p


def _example_text() -> str:
    return EXAMPLE.read_text()


def test_example_config_loads():
    cfg = load(EXAMPLE)
    assert cfg.announce.halls == ["SC1", "SC2", "SC3"]
    assert cfg.messages["match_start"] == "Referees, you may start the matches."
    assert cfg.messages["match_end"] == "Referees, you may end the matches."
    assert cfg.actuators["SPREKEN"].channel == 3


def test_roundtrip(tmp_path):
    cfg = load(EXAMPLE)
    out = tmp_path / "out.toml"
    save(cfg, out)
    assert load(out) == cfg


def test_roundtrip_with_optionals(tmp_path):
    cfg = load(EXAMPLE)
    cfg = replace(
        cfg,
        announce=replace(cfg.announce, lead_seconds=30.0),
        audio=replace(cfg.audio, device="USB Audio"),
    )
    out = tmp_path / "out.toml"
    save(cfg, out)
    assert load(out) == cfg


def test_hall_without_actuator_rejected(tmp_path):
    text = _example_text().replace('halls = ["SC1", "SC2", "SC3"]', 'halls = ["SC4"]')
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text))


def test_spreken_required(tmp_path):
    text = _example_text().replace("[actuators.SPREKEN]", "[actuators.OTHER]")
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text))


@pytest.mark.parametrize("name", ["ONTRUIMINGSALARM", "KOPPEL_RUIMTES", "koppelruimtes"])
def test_forbidden_button_names_rejected(tmp_path, name):
    text = _example_text() + f"\n[actuators.{name}]\nchannel = 7\nrest = 90\npress = 60\n"
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text))


def test_duplicate_channel_rejected(tmp_path):
    text = _example_text().replace("channel = 1", "channel = 0")
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text))


def test_angles_out_of_range_rejected(tmp_path):
    text = _example_text().replace("press = 60", "press = 181", 1)
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("watchdog_ms = 2000", "watchdog_ms = 10001"),  # firmware caps WATCHDOG at 10000
        ("watchdog_ms = 2000", "watchdog_ms = 0"),
        ("max_hold_s = 60", "max_hold_s = 121"),  # firmware caps MAXHOLD at 120000 ms
        ("max_hold_s = 60", "max_hold_s = 0"),
        ("keepalive_ms = 500", "keepalive_ms = 2000"),  # must ping before the watchdog fires
        ("keepalive_ms = 500", "keepalive_ms = 1001"),  # at most half the watchdog
        ("keepalive_ms = 500", "keepalive_ms = 0"),
        ("channel = 0", "channel = 8"),  # firmware has channels 0-7
    ],
)
def test_controller_limits_rejected(tmp_path, old, new):
    text = _example_text()
    assert old in text
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text.replace(old, new, 1)))


def test_controller_limits_accepted(tmp_path):
    text = _example_text().replace("watchdog_ms = 2000", "watchdog_ms = 10000")
    text = text.replace("max_hold_s = 60", "max_hold_s = 120")
    text = text.replace("keepalive_ms = 500", "keepalive_ms = 5000")  # exactly half
    cfg = load(_write(tmp_path, text))
    c = cfg.controller
    assert (c.watchdog_ms, c.max_hold_s, c.keepalive_ms) == (10000, 120, 5000)


def test_round_minutes_loaded():
    cfg = load(EXAMPLE)
    assert cfg.schedule.round_minutes["Round 1"] == 15
    assert cfg.schedule.round_minutes["Round 5"] == 20


def test_round_minutes_must_be_positive(tmp_path):
    text = _example_text().replace('"Round 1" = 15', '"Round 1" = 0')
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text))


def test_unknown_placeholder_rejected_on_load(tmp_path):
    text = _example_text().replace(
        "Referees, you may start the matches.", "Matches on {teams} may start."
    )
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text))


def test_known_placeholders_accepted(tmp_path):
    text = _example_text().replace(
        "Referees, you may start the matches.",
        "At {time}, {count} matches on {fields} in {halls}.",
    )
    cfg = load(_write(tmp_path, text))
    assert "{fields}" in cfg.messages["match_start"]


def test_unknown_placeholder_rejected_on_save(tmp_path):
    cfg = load(EXAMPLE)
    bad = replace(cfg, messages={**cfg.messages, "match_end": "Hello {teams}"})
    with pytest.raises(ConfigError):
        save(bad, tmp_path / "out.toml")


def test_malformed_template_rejected(tmp_path):
    text = _example_text().replace("Referees, you may end the matches.", "Oops {time")
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text))


def test_save_rejects_invalid_config(tmp_path):
    cfg = load(EXAMPLE)
    acts = {**cfg.actuators, "SC1": Actuator(channel=3, rest=90, press=60)}
    with pytest.raises(ConfigError):
        save(replace(cfg, actuators=acts), tmp_path / "out.toml")


@pytest.mark.parametrize("template", ["Fields {fields:d}", "{count:%H}", "{time!z}"])
def test_template_that_fails_to_render_rejected(tmp_path, template):
    text = _example_text().replace("Referees, you may end the matches.", template)
    with pytest.raises(ConfigError):
        load(_write(tmp_path, text))


def test_template_with_format_spec_that_renders_accepted(tmp_path):
    text = _example_text().replace("Referees, you may end the matches.", "{count:d} at {time:>5}")
    assert load(_write(tmp_path, text)).messages["match_end"] == "{count:d} at {time:>5}"


# alarm-like names, halls, SPREKEN travel (final review I10)


def _valid_config() -> Config:
    cfg = Config()
    cfg.actuators = {
        "SC1": Actuator(channel=0, rest=135, press=65),
        "SC2": Actuator(channel=1, rest=135, press=65),
        "SPREKEN": Actuator(channel=3, rest=135, press=65),
    }
    cfg.announce.halls = ["SC1", "SC2"]
    return cfg


@pytest.mark.parametrize(
    "name",
    [
        "KOPPEL",
        "ONTRUIMING",
        "Koppel ruimtes",
        "KOPPEL-RUIMTES",
        "ALARM",
        "Ontruimingsalarm ",
        "ont ruim",
        "al_arm2",
    ],
)
def test_alarm_like_names_rejected(name):
    cfg = _valid_config()
    cfg.actuators[name] = Actuator(channel=4, rest=135, press=65)
    with pytest.raises(ConfigError, match="forbidden"):
        validate(cfg)


def test_valid_config_accepted():
    validate(_valid_config())


@pytest.mark.parametrize(
    ("halls", "message"),
    [
        ([], "at least one"),
        (["SC1", "SC1"], "more than once"),
        (["SC1", "SPREKEN"], "SPREKEN"),
        (["SC1", "SC3"], "SC3"),
    ],
)
def test_bad_halls_rejected(halls, message):
    cfg = _valid_config()
    cfg.announce.halls = halls
    with pytest.raises(ConfigError, match=message):
        validate(cfg)


@pytest.mark.parametrize(("rest", "press"), [(65, 65), (74, 65), (56, 65)])
def test_spreken_rest_too_close_to_press_rejected(rest, press):
    cfg = _valid_config()
    cfg.actuators["SPREKEN"].rest = rest
    cfg.actuators["SPREKEN"].press = press
    with pytest.raises(ConfigError, match="SPREKEN"):
        validate(cfg)


@pytest.mark.parametrize(("rest", "press"), [(75, 65), (55, 65)])
def test_spreken_rest_at_minimum_travel_accepted(rest, press):
    cfg = _valid_config()
    cfg.actuators["SPREKEN"].rest = rest
    cfg.actuators["SPREKEN"].press = press
    validate(cfg)


def test_travel_minimum_is_only_for_spreken():
    cfg = _valid_config()
    cfg.actuators["SC1"].rest = 65
    validate(cfg)
