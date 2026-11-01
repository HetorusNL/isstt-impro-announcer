from dataclasses import replace
from pathlib import Path

import pytest

from announcer.config import Actuator, ConfigError, load, save

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
