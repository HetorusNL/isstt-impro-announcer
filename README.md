# ISSTT IMPRO announcer

Presses buttons on the PA paging desk with servos and plays Piper TTS into its mic, at the times on the Cupkit schedule. Design: [`docs/superpowers/specs/2026-11-01-impro-announcer-design.md`](docs/superpowers/specs/2026-11-01-impro-announcer-design.md).

## First run

Needs [uv](https://docs.astral.sh/uv/), PortAudio for playback, and for the firmware PlatformIO (`uv tool install platformio`).

```sh
uv sync
cp config.example.toml config.toml
uv run python -m piper.download_voices en_US-lessac-medium --data-dir voices
```

`config.toml`, `voices/`, `cache/` and `state/` are not in git. There are no secrets: the schedule comes from the public Cupkit page.

Try it without hardware, with a mock servo controller:

```sh
uv run announcer --mock
```

Then open <http://127.0.0.1:8080>. Button actions are logged with timestamps. To replay a day quickly, add `--sim-start 2026-12-19T08:55 --sim-speed 60`: a simulator run keeps its state in `state/sim/`, and audio is mocked at any speed other than 1.

### Schedule from a file

`uv run announcer --source file` reads `schedule.file` from `config.toml` (default `schedule.json`) instead of Cupkit:

```json
{
  "matches": [
    {
      "start": "2026-12-19T09:00:00",
      "hall": "SC1",
      "field": "Field 1",
      "home": "A1",
      "away": "A4",
      "referee": "E1",
      "round": "Round 1"
    }
  ]
}
```

`match_minutes` is optional per match and overrides the minutes per round in the config. A `start` without an offset is in the configured timezone.

### Flashing

```sh
pio run -d firmware -e nucleo_f767zi -t upload   # or -e nucleo_f746zg for the spare board
```

Commands and failsafes: [`firmware/PROTOCOL.md`](firmware/PROTOCOL.md).

### Last bench step

Before taking the rig to the desk, set the final `rest` (about 135) in `config.toml` and connect once with `uv run announcer`, with the board on the servo rail. The firmware drives the servos to the rest in its flash at power-on, before the host sends any config. So the rest left over from bench tests decides what the servos do at the next power-on, and at the wrong rest a cam can hold a button down. Keep the plungers out until this connect has happened. The F746 spare board keeps rests in RAM only: after a power cycle it drives nothing until the host connects.

## On site

- [On-site checklist](docs/onsite-checklist.md): Friday setup and evening test, then the Saturday and Sunday mornings.
- [Wiring](hardware/wiring.md)
- [CAD and assembly](hardware/cad/README.md)
- [Bill of materials](hardware/BOM.md)

**Still open until done on site:** the alarm and Koppel cover checks (checklist 0.3) are unproven, and the rig does not run on the desk until they pass. Spreken release is untested on real servos (checklist 0.4).

**Accepted risk:** if the 5 V adapter fails during a hold, no failsafe can act and SPREKEN may stay down. Tim accepted this on 2026-11-02. The bench test and the manual recovery are in checklist 0.5.

## Tests

```sh
uv run pytest
```

No network and no hardware.
