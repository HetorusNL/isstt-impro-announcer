# ISSTT IMPRO Announcer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically announce "referees, you may start/end the matches" on the IMPRO paging desk at the times listed on Cupkit, by pressing the desk's buttons with servos and playing Piper speech into its microphone, controlled from a NiceGUI screen on Tim's laptop.

**Architecture:** A Python asyncio app (`announcer`) built from small parts: schedule sources (Cupkit scraper, JSON file), a pure planner that turns matches into announcements and sessions, a sequencer that runs one desk session with guaranteed Spreken release, and an engine that ties clock, queue, pause and history together. A NiceGUI front end sits on top. Hardware is driven through a `Controller` interface with a mock (for everything before the 18th) and a serial implementation talking to channel-based firmware on a NUCLEO-F767ZI. The firmware owns the last-resort failsafes: keep-alive watchdog, maximum hold time, and release on boot.

**Tech Stack:** Python ≥3.12, uv, NiceGUI, httpx, selectolax, pyserial, piper-tts, sounddevice + soundfile, tomli-w, pytest + pytest-asyncio. Firmware: PlatformIO, Arduino framework (STM32duino), `Servo` + `EEPROM` libraries. Mechanics: 3D-printed parts (Bambu Lab H2D), parametric CAD.

**Spec:** `docs/superpowers/specs/2026-11-01-impro-announcer-design.md`

## Global Constraints

- Hard deadline **2026-12-18**, matches from 09:00. Tournament days 18, 19 and 20 December 2026.
- Never open, rewire or modify the IMPRO desk. Attach from the outside only and leave no marks.
- Never mount an actuator over, or configure one for, *Ontruimingsalarm* or *Koppel ruimtes*. The evacuation alarm must stay reachable by hand and its cover openable.
- **Spreken must be released under all circumstances.** Host side: `finally` in every session. Firmware side: keep-alive watchdog, maximum hold time (default 60 s), release on boot.
- Buttons are referred to by name (`SC1`, `SPREKEN`, …) everywhere in host code. Channel numbers appear only in config.
- Default messages, verbatim: `Referees, you may start the matches.` and `Referees, you may end the matches.`
- Default halls `["SC1", "SC2", "SC3"]`. Every announcement goes to the configured halls, never per field.
- Timezone `Europe/Amsterdam`. Match length per round from config: `Round 1` and `Round 2` = 15 min, `Round 3`–`Round 5` = 20 min; unknown rounds use `default_match_minutes = 20`. Late threshold 60 s. Schedule poll 60 s.
- The schedule comes from the **public** Cupkit matches page `https://cupkit.nl/messedup/isstt-36/senior/matches`, so no login or secrets are needed. Never commit organiser/admin pages or credentials; a future API token goes in an env var or the untracked `secrets.toml`, never in `config.toml` or git.
- Platform: Tim's Arch Linux laptop only.
- Commits are GPG-signed. If a commit fails because the key is locked, ask Tim to unlock it (`echo | gpg --clearsign >/dev/null`). Never use `--no-gpg-sign`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The schedule changes while an announcement is due or in progress.** Replanning must not replay an announcement already played or skipped, and must not drop the session currently running. Test: `test_replan_does_not_replay_played` (Task 6).
2. **Restart mid-tournament.** On start-up, announcements already more than 60 s late are marked missed instead of all firing at once. Test: `test_startup_marks_past_as_missed` (Task 6).
3. **Audio device missing or Piper failing mid-session.** Spreken is still released, the failure appears in history, and the engine keeps running. Test: `test_session_releases_on_player_error` (Task 5).
4. **Cupkit returns an error, maintenance or otherwise empty page instead of the timetable.** This counts as a source failure: the last good schedule stays in use and the GUI warns. It must not wipe the schedule to zero matches. Test: `test_page_without_matches_is_source_error` (Task 3).
5. **Placeholder teams and a round missing from `round_minutes`** (e.g. the committee adds a Round 6). Matches still schedule, and the end time falls back to `default_match_minutes`. Test: `test_unknown_round_uses_default_minutes` (Task 4).

---

## File Structure

```
pyproject.toml                 uv project, script `announcer = "announcer.main:main"`
config.example.toml            documented defaults (copied to config.toml, which is gitignored)
.gitignore                     config.toml, secrets.toml, state/, cache/, voices/, .venv/
src/announcer/
  config.py                    Config dataclasses, load/save TOML, validation
  model.py                     Match, Announcement, Session
  clock.py                     Clock protocol, RealClock, SimClock
  planner.py                   matches -> announcements -> sessions, lead time
  schedule/
    source.py                  ScheduleSource protocol, SourceError
    cupkit.py                  parse_matches_html, CupkitSource (public page)
    filesource.py              FileSource (JSON)
    store.py                   save/load last good schedule
  controller/
    base.py                    Controller protocol
    mock.py                    MockController (records events)
    serial_ctrl.py             SerialController (protocol + keep-alive)
  audio/
    tts.py                     Tts (Piper + cache)
    player.py                  Player protocol, SoundPlayer, MockPlayer
  sequencer.py                 run_session, talk_session
  engine.py                    Engine (poll, queue, pause, late/skip, history, manual)
  inhibit.py                   keep laptop awake (systemd-inhibit)
  gui/app.py                   NiceGUI pages: dashboard, manual, calibration, settings
  main.py                      CLI entry
tests/                         one test file per module, fixtures from docs/reference/
firmware/                      PlatformIO project (env nucleo_f767zi + nucleo_f746zg)
hardware/                      BOM.md, CAD sources + params, wiring.md
docs/onsite-checklist.md       morning-of-18-Dec procedure
```

---

### Task 0: Order parts (Tim, today)

Shipping takes 2–4 weeks, so this is on the critical path.

**Files:**
- Create: `hardware/BOM.md`

- [ ] **Step 1: Write `hardware/BOM.md`** with quantities and the reason for each part:
  - 8× MG90S metal-gear micro servos (4 needed, 4 spare or extra buttons)
  - 5 V ≥ 5 A regulated supply with barrel jack, plus a screw-terminal breakout
  - servo extension leads, 30 cm
  - Dupont/JST wiring, a 1000 µF electrolytic capacitor across the servo rail
  - small powered speaker (3.5 mm input), or a PAM8403 amp board plus a 40 mm 4 Ω driver
  - USB sound card (keeps the laptop's own audio free for previews)
  - 20×20 aluminium extrusion, 2× 400 mm, plus T-nuts and M3/M4 bolts (stiff backbone; the printed parts clip onto it)
  - EVA foam or rubber sheet for clamp pads
- [ ] **Step 2: Tim orders.** Done when the order confirmations exist. Note expected delivery dates in `hardware/BOM.md`.
- [ ] **Step 3: Commit**

```bash
git add hardware/BOM.md && git commit -m "docs: bill of materials"
```

### Task 1: Project skeleton, config and model

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `config.example.toml`, `src/announcer/__init__.py`, `src/announcer/config.py`, `src/announcer/model.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `model.Match` (frozen dataclass): `start: datetime` (aware), `hall: str` (e.g. `"SC1"`, no space), `field: str` (e.g. `"Field 1"`), `home: str`, `away: str`, `referee: str`, `round_name: str`, `match_minutes: int | None`
  - `model.Kind = Literal["match_start", "match_end", "manual_text"]`
  - `model.Announcement` (frozen): `due: datetime`, `kind: Kind`, `matches: tuple[Match, ...] = ()`, `text: str | None = None`, property `key -> tuple[str, str]` = `(kind, due.isoformat())`
  - `model.Session` (frozen): `start_at: datetime`, `announcements: tuple[Announcement, ...]`, `halls: tuple[str, ...]`
  - `config.Actuator`: `channel: int`, `rest: int`, `press: int`, `press_ms: int = 250`, `release_ms: int = 250`
  - `config.Config` with sections `controller` (`port: str = "/dev/ttyACM0"`, `keepalive_ms = 500`, `watchdog_ms = 2000`, `max_hold_s = 60`), `actuators: dict[str, Actuator]`, `announce` (`halls = ["SC1","SC2","SC3"]`, `chime_seconds = 3.0`, `tail_seconds = 0.5`, `deselect_zones_after = False`, `lead_seconds: float | None = None`, `late_threshold_seconds = 60`, `merge_window_seconds = 30`), `messages: dict[str, str]` (keys `match_start`, `match_end`), `tts` (`voice_model = "voices/en_US-lessac-medium.onnx"`, `length_scale = 1.0`, `cache_dir = "cache/tts"`), `audio` (`device: str | None = None`, `volume = 1.0`), `schedule` (`kind: Literal["cupkit","file"] = "cupkit"`, `matches_urls: list[str]`, `round_minutes: dict[str, int] = {"Round 1": 15, "Round 2": 15, "Round 3": 20, "Round 4": 20, "Round 5": 20}`, `file = "schedule.json"`, `poll_seconds = 60`, `store = "state/schedule.json"`, `default_match_minutes = 20`, `timezone = "Europe/Amsterdam"`)
  - `config.load(path: Path) -> Config`, `config.save(cfg: Config, path: Path) -> None`, `config.ConfigError(Exception)`

`config.example.toml` defines actuators `SC1` (ch 0), `SC2` (ch 1), `SC3` (ch 2) and `SPREKEN` (ch 3), each with rest 90 and press 60. It sets `matches_urls = ["https://cupkit.nl/messedup/isstt-36/senior/matches"]` and the `round_minutes` above.

- [ ] **Step 1: `uv init --package --name announcer`** and add the dependencies from the Tech Stack. Set `requires-python = ">=3.12"`, `[tool.pytest.ini_options] asyncio_mode = "auto"`. Run `uv sync`. Expected: it exits 0.
- [ ] **Step 2: Write the failing tests**

```python
def test_example_config_loads():
    cfg = load(Path("config.example.toml"))
    assert cfg.announce.halls == ["SC1", "SC2", "SC3"]
    assert cfg.messages["match_start"] == "Referees, you may start the matches."
    assert cfg.messages["match_end"] == "Referees, you may end the matches."
    assert cfg.actuators["SPREKEN"].channel == 3

def test_roundtrip(tmp_path):  # save then load gives an equal Config

def test_hall_without_actuator_rejected(tmp_path):    # halls=["SC4"], no SC4 actuator -> ConfigError
def test_spreken_required(tmp_path):                  # no SPREKEN actuator -> ConfigError
def test_forbidden_button_names_rejected(tmp_path):   # actuator named "ONTRUIMINGSALARM" or "KOPPEL_RUIMTES" -> ConfigError
def test_duplicate_channel_rejected(tmp_path):        # two actuators on channel 0 -> ConfigError
def test_angles_out_of_range_rejected(tmp_path):      # press=181 -> ConfigError
def test_round_minutes_loaded():  # example config -> round_minutes["Round 1"] == 15, round_minutes["Round 5"] == 20
def test_round_minutes_must_be_positive(tmp_path):  # 0 -> ConfigError
```

- [ ] **Step 3: Run** `uv run pytest tests/test_config.py -v`. Expected: FAIL (import error).
- [ ] **Step 4: Implement `config.py` and `model.py`.** Read with `tomllib`, write with `tomli_w`. Do validation in `load` and in `save`. Forbidden names are matched case-insensitively against `{"ONTRUIMINGSALARM", "KOPPEL_RUIMTES", "KOPPELRUIMTES"}`.
- [ ] **Step 5: Run** the tests. Expected: PASS.
- [ ] **Step 6: Commit** `feat: project skeleton, config and model`.

### Task 2: Clock

**Files:**
- Create: `src/announcer/clock.py`
- Test: `tests/test_clock.py`

**Interfaces:**
- Produces: `Clock` protocol with `now() -> datetime` (aware, configured tz) and `async sleep(seconds: float) -> None`. `RealClock(tz: str)`. `SimClock(start: datetime, speed: float)`: `now() = start + elapsed_monotonic * speed`, and `sleep(s)` awaits `s / speed` real seconds.

- [ ] **Step 1: Failing tests:** `test_simclock_advances_fast` (speed 600: `await sleep(60)` takes < 0.5 s real, and `now()` advances ≥ 60 s); `test_realclock_is_aware` (`now().tzinfo` key is `Europe/Amsterdam`).
- [ ] **Step 2: Run, expect FAIL. Implement** with `zoneinfo` and `time.monotonic`. **Run, expect PASS.**
- [ ] **Step 3: Commit** `feat: real and simulated clock`.

### Task 3: Schedule sources and store

**Files:**
- Create: `src/announcer/schedule/{__init__,source,cupkit,filesource,store}.py`
- Test: `tests/test_cupkit.py`, `tests/test_filesource.py`, `tests/test_store.py`
- Fixture: `docs/reference/cupkit-public-matches.html` (public page, saved 2026-11-01)

**Interfaces:**
- Consumes: `Match`, `Config.schedule`
- Produces:
  - `ScheduleSource` protocol: `async fetch() -> list[Match]`. Raises `SourceError` on any failure.
  - `parse_matches_html(html: str, tz: str) -> list[Match]`. Ignore `<script>` content (the Next.js payload repeats the class names). Structure: each `<section>` has the round name in `h2` (class contains `roundName`, e.g. `"Round 1"`). Inside it, each `div` with class containing `__time` has an `h3` (class `moment`) = `"18 December 2026 at 09:00"` and a list of `li` (class `line`). Each `li` has `span.where` = `"SC1, Field 1 · Poule A"`, two `span.side` = teams, `span.referee` = `"Referee: E1"` and `span.score`. Match class names by substring (`roundName`, `moment`, `where`, `side`, `referee`), because the CSS-module hash suffix can change between deploys. `match_minutes` stays `None`; the planner takes it from `round_minutes`. Raise `SourceError` if no matches are found.
  - `CupkitSource(matches_urls, tz)`: httpx `AsyncClient` with a 15 s timeout, no auth. Concatenate matches from all URLs (one per category).
  - `FileSource(path, tz)` reads JSON: `{"matches": [{"start": "2026-12-18T09:00", "hall": "SC1", "field": "Field 1", "home": "A1", "away": "A4", "referee": "E1", "round": "Round 1", "match_minutes": 20}]}`. Naive times get the tz; `match_minutes` is optional.
  - `store.save(matches, path)` / `store.load(path, tz) -> list[Match]` use the same JSON format as `FileSource`, written atomically (tmp file + rename).

- [ ] **Step 2: Failing tests**

```python
def test_parses_all_matches():
    ms = parse_matches_html(PUBLIC, "Europe/Amsterdam")
    assert len(ms) == 198
    first = min(ms, key=lambda m: (m.start, m.field))
    assert first.start == datetime(2026, 12, 18, 9, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    assert (first.hall, first.field, first.home, first.away, first.referee, first.round_name) == \
        ("SC1", "Field 1", "A1", "A4", "E1", "Round 1")
    assert first.match_minutes is None
    assert len({m.start for m in ms}) == 39
    assert {m.hall for m in ms} == {"SC1", "SC2", "SC3"}
    assert {m.round_name for m in ms} == {f"Round {i}" for i in range(1, 6)}

def test_page_without_matches_is_source_error():
    with pytest.raises(SourceError):
        parse_matches_html("<html><main><h2>Senior</h2></main></html>", "Europe/Amsterdam")

async def test_cupkit_http_error_is_source_error(httpx_mock_or_transport)  # 500 / timeout -> SourceError
def test_filesource_roundtrip_with_store(tmp_path)  # store.save -> FileSource.fetch gives equal matches
```

Use `httpx.MockTransport` for the HTTP test; no network in tests.
- [ ] **Step 2: Run, expect FAIL. Implement. Run, expect PASS.**
- [ ] **Step 3: Live check (manual).** Run `uv run python -c "…CupkitSource(...).fetch()…"`. Expected: 198 matches (or the current count).
- [ ] **Step 4: Commit** `feat: cupkit public-page scraper, file source, schedule store`.

### Task 4: Planner

**Files:**
- Create: `src/announcer/planner.py`
- Test: `tests/test_planner.py`

**Interfaces:**
- Consumes: `Match`, `Announcement`, `Session`, `Config`
- Produces:
  - `plan_announcements(matches: list[Match], round_minutes: dict[str, int], default_minutes: int) -> list[Announcement]`: one `match_start` per distinct start time, and one `match_end` per distinct `start + minutes`, where minutes = `match.match_minutes` if set, else `round_minutes[match.round_name]`, else `default_minutes`. Each carries its matches. Sorted by `due`; at equal `due`, end comes before start.
  - `group_sessions(anns: list[Announcement], halls: Sequence[str], merge_window_s: float, lead_s: float) -> list[Session]`: walk in order; an announcement joins the current session if its `due - session_first.due <= merge_window_s`. `start_at = first.due - lead_s`.
  - `render_message(template: str, ann: Announcement) -> str`: `str.format_map` with keys `time` (`HH:MM` of `due`), `count` (number of matches), `fields` (comma-joined distinct fields), `halls` (comma-joined distinct halls). Plain text passes through unchanged. This is the hook for richer messages later (spec §5.5); config load rejects templates with unknown placeholders.
  - `lead_seconds(cfg: Config) -> float`: `cfg.announce.lead_seconds` if set, else `sum((press_ms + release_ms) of each hall)/1000 + SPREKEN.press_ms/1000 + chime_seconds`.

- [ ] **Step 1: Failing tests**

```python
def test_fixture_counts():
    anns = plan_announcements(fixture_matches(), ROUND_MINUTES, 20)   # ROUND_MINUTES = 15,15,20,20,20
    assert sum(a.kind == "match_start" for a in anns) == 39
    assert sum(a.kind == "match_end" for a in anns) == 39
    first_end = min(a.due for a in anns if a.kind == "match_end")
    assert first_end.strftime("%d %H:%M") == "18 09:15"    # Round 1 = 15 min

def test_collisions_merge_end_first():
    sessions = group_sessions(plan_announcements(fixture_matches(), ROUND_MINUTES, 20), ["SC1","SC2","SC3"], 30, 5)
    assert len(sessions) == 76
    merged = [s for s in sessions if len(s.announcements) == 2]
    assert [s.announcements[0].due.strftime("%d %H:%M") for s in merged] == ["19 14:55", "19 16:30"]
    assert all([a.kind for a in s.announcements] == ["match_end", "match_start"] for s in merged)

def test_unknown_round_uses_default_minutes():  # round "Round 6" not in round_minutes, default 20 -> end = start + 20 min
def test_render_plain_and_placeholders():  # plain default text unchanged; "{count} matches at {time}" -> "7 matches at 09:00" for the 18 Dec 09:00 start
def test_lead_seconds_computed():  # 3 halls at 250+250 ms, SPREKEN press 250 ms, chime 3.0 -> 4.75
def test_lead_seconds_override():  # lead_seconds=7 -> 7
def test_session_start_at_is_due_minus_lead()
```

- [ ] **Step 2: Run, expect FAIL. Implement. Run, expect PASS.**
- [ ] **Step 3: Commit** `feat: planner (slots, end times, merged sessions)`.

### Task 5: Controller interface, mock, audio, sequencer

**Files:**
- Create: `src/announcer/controller/{__init__,base,mock}.py`, `src/announcer/audio/{__init__,tts,player}.py`, `src/announcer/sequencer.py`
- Test: `tests/test_sequencer.py`, `tests/test_tts.py`

**Interfaces:**
- Consumes: `Config`, `Clock`
- Produces:
  - `Controller` protocol (async): `connect()`, `close()`, `connected: bool`, `tap(button: str)` (press angle, wait `press_ms`, rest angle, wait `release_ms`), `hold(button)`, `release(button)`, `release_all()`, `set_angle(button: str, angle: int)`, `configure(actuators: dict[str, Actuator])` (sends rest angles to firmware).
  - `MockController(clock)`: `events: list[tuple[datetime, str, str]]`, e.g. `(t, "tap", "SC1")`, `(t, "hold", "SPREKEN")`, `(t, "release", "SPREKEN")`, `(t, "release_all", "")`. `fail_on: set[str]` makes a matching action raise `ControllerError`.
  - `Player` protocol: `async play(path: Path) -> None`, `duration(path: Path) -> float`. `SoundPlayer(device, volume)` uses sounddevice + soundfile and runs playback via `asyncio.to_thread`. `MockPlayer(clock, fail=False)` sleeps `duration` on the clock and records the paths it played.
  - `Tts(voice_model: Path, length_scale: float, cache_dir: Path)`: `async synth(text: str) -> Path` caches `<sha256(model|length_scale|text)>.wav`. It uses `piper.PiperVoice.load(model)` and `voice.synthesize_wav(text, wave_file, syn_config=SynthesisConfig(length_scale=...))`; check the installed piper-tts version's API. Voice download: `uv run python -m piper.download_voices en_US-lessac-medium --data-dir voices`.
  - `async run_session(ctrl, player, clock, cfg, halls: Sequence[str], audio: Sequence[Path]) -> None` runs spec §5.3 steps 1–6. Steps 1–5 sit in `try`; the `finally` releases SPREKEN and, if that fails, calls `release_all()`. The deselect taps run only after a successful release.
  - `talk_session(ctrl, clock, cfg, halls)`: an async context manager. It taps the halls and holds SPREKEN on enter, and releases on exit. It also releases by itself after `cfg.controller.max_hold_s` through a watchdog task.

- [ ] **Step 1: Failing tests**

```python
async def test_session_order():
    # halls SC1,SC2; one 2.0 s clip; chime 3.0; tail 0.5; SimClock
    kinds = [(k, b) for _, k, b in ctrl.events]
    assert kinds == [("tap","SC1"),("tap","SC2"),("hold","SPREKEN"),("release","SPREKEN")]
    hold_t, rel_t = event_time("hold"), event_time("release")
    assert rel_t - hold_t >= timedelta(seconds=3.0 + 2.0 + 0.5)
    assert player.played_at[0] - hold_t >= timedelta(seconds=3.0)   # speech after chime

async def test_deselect_after_when_enabled():  # extra taps SC1,SC2 after release
async def test_session_releases_on_player_error():  # MockPlayer(fail=True): raises, last event is release SPREKEN
async def test_release_failure_falls_back_to_release_all():  # fail_on={"release"} -> release_all recorded
async def test_session_releases_on_cancel():  # task.cancel() mid-chime -> release recorded
async def test_talk_session_auto_releases_after_max_hold():  # max_hold_s=60, SimClock: release at ~60 s even without exit
def test_tts_cache_key_changes_with_text(tmp_path)   # with a fake voice, no model needed
```

- [ ] **Step 2: Run, expect FAIL. Implement. Run, expect PASS.**
- [ ] **Step 3: Manual audio check.** `uv run python -m announcer.audio.tts "Referees, you may start the matches."` writes a wav and plays it through `SoundPlayer`. Expected: speech you can understand from the laptop speaker.
- [ ] **Step 4: Commit** `feat: controller interface, mock, tts, sequencer with guaranteed release`.

### Task 6: Engine

**Files:**
- Create: `src/announcer/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: everything above
- Produces: `Engine(cfg, source, store_path, ctrl, player, tts, clock)` with:
  - `async start()` / `async stop()`. Stop cancels tasks and always ends with `ctrl.release_all()`.
  - state for the GUI: `paused: bool`, `upcoming: list[Session]`, `history: list[HistoryEntry]` (`at`, `key`, `status: Literal["played","skipped","missed","failed"]`, `detail`), `source_ok_at: datetime | None`, `source_error: str | None`, `matches_count: int`
  - `pause()`, `resume()`, `async play_now(key)`, `async manual_text(halls, text)`, `async talk_start(halls)`, `async talk_stop()`, `async reload_config(cfg)`
  - one `asyncio.Lock` around every desk session (scheduled, manual, talk), so sessions never overlap
  - a poll loop every `poll_seconds`: on success, `store.save` and then replan. On `SourceError`, keep the current matches and set `source_error`. On start, load `store` first if present.
  - a run loop: pick the first session not yet handled. When `now >= start_at`: if paused or busy, wait. If `now - first.due > late_threshold_seconds`, mark every announcement in it `skipped`. Otherwise synthesise the texts (`render_message(cfg.messages[kind], ann)` for scheduled, `text` for manual), call `run_session`, and mark them `played` or `failed`.
  - handled keys (`Announcement.key`) are persisted in `state/handled.json`, so a replan or restart never replays them
  - on start, announcements whose `due` is already more than `late_threshold_seconds` in the past are marked `missed` without playing

- [ ] **Step 1: Failing tests** (`SimClock` at speed 600, `MockController`, `MockPlayer`, `FileSource` from a tmp JSON):

```python
async def test_plays_start_and_end_on_time():  # one match 09:00, clock at 08:59 -> 2 sessions; SPREKEN hold at due - chime_seconds (±1 s)
async def test_pause_skips_when_late():  # paused across due + 61 s -> history status "skipped"; resume -> nothing plays
async def test_play_now_plays_skipped()
async def test_replan_does_not_replay_played():  # after play, source returns same matches + one new -> only new plays
async def test_startup_marks_past_as_missed():  # clock starts 10:00, matches at 09:00 -> "missed", no controller events
async def test_source_error_keeps_schedule():  # source raises SourceError after first fetch -> upcoming unchanged, source_error set
async def test_manual_waits_for_running_session():  # manual_text during a session -> its taps start after the first release
async def test_stop_releases_all()
```

- [ ] **Step 2: Run, expect FAIL. Implement. Run, expect PASS.**
- [ ] **Step 3: Commit** `feat: engine (scheduling, pause, late/skip, persistence, manual queue)`.

### Task 7: GUI, CLI, sleep inhibit

**Files:**
- Create: `src/announcer/gui/{__init__,app}.py`, `src/announcer/main.py`, `src/announcer/inhibit.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `Engine`, `Config`, `config.save`
- Produces:
  - CLI: `announcer [--config config.toml] [--mock] [--sim-start 2026-12-18T08:55] [--sim-speed 60] [--source file|cupkit] [--port 8080]`. `--mock` uses `MockController` + `SoundPlayer`. `--sim-*` uses `SimClock` (implies `MockPlayer`, unless `--sim-speed 1`).
  - `inhibit.Inhibitor`: a context manager that spawns `systemd-inhibit --what=sleep:idle --who=announcer --why="tournament announcements" sleep infinity` and kills it on exit.
  - GUI pages (NiceGUI, refreshed every 0.5 s with `ui.timer`):
    - **Dashboard:** big clock, RUNNING/PAUSED with a pause/resume toggle, controller connected, schedule age and source error banner, next session with countdown, upcoming list (time, kinds, number of matches), history with a "play now" button on skipped entries.
    - **Manual:** hall checkboxes from `actuators` minus `SPREKEN` (default = `announce.halls`); a text box with a "Speak" button; a "Talk" button that holds while pressed (`mousedown`/`touchstart` → `talk_start`, `mouseup`/`mouseleave`/`touchend` → `talk_stop`).
    - **Calibration:** per actuator, a slider for the press angle and one for the rest angle (live `set_angle`), and "Test tap". Also a "Test full sequence" with phrase `This is a test announcement.`, inputs for chime/tail/volume/deselect, and "Save" (`config.save` + `engine.reload_config`).
    - **Settings:** message texts with "Preview" (synth + play on the laptop's default device), hall selection, poll interval.
- [ ] **Step 1: Failing test:** `test_cli_parses_sim_args` (argument parsing builds `SimClock` with the given start/speed and `MockController` when `--mock`).
- [ ] **Step 2: Run, expect FAIL. Implement. Run, expect PASS.**
- [ ] **Step 3: Dress rehearsal (manual).** `uv run announcer --mock --source file --sim-start 2026-12-19T14:45 --sim-speed 60`, using `schedule.json` exported from the fixture via `store.save`. Expected: the merged 14:55 session plays end then start audio; pause/resume works; skip appears after pausing past a due time. Repeat a full day 18 Dec at `--sim-speed 600` and check that history shows 24 sessions played (12 start + 12 end).
- [ ] **Step 4: Commit** `feat: NiceGUI interface, CLI, sleep inhibit`.

### Task 8: Firmware (NUCLEO-F767ZI)

**Files:**
- Create: `firmware/platformio.ini` (envs `nucleo_f767zi`, `nucleo_f746zg`, framework `arduino`), `firmware/src/main.cpp`, `firmware/PROTOCOL.md`

**Interfaces:**
- Produces the serial protocol (115200 baud on the ST-Link virtual COM, `Serial`; lines end in `\n`; every command answers `OK …` or `ERR <reason>`):
  - `PING` → `OK PONG`
  - `REST <ch> <deg>` stores the rest angle in EEPROM, attaches the channel and moves it to rest
  - `ANGLE <ch> <deg>` moves the servo (attaches if needed)
  - `RELEASE <ch>` / `RELEASE ALL` move to the stored rest
  - `MAXHOLD <ms>` (default 60000) and `WATCHDOG <ms>` (default 2000)
  - async event lines: `EVT WATCHDOG` (no command for `WATCHDOG` ms: everything released), `EVT MAXHOLD <ch>` (a channel away from rest longer than `MAXHOLD`: it is released), `EVT BOOT` (sent after release-on-boot)
- Channels 0–7 → pins `D3, D5, D6, D9, D10, D11, D12, D13` (Arduino header on the Nucleo-144; change in one table if needed). Degrees 0–180. A channel with no stored rest stays detached and is never driven at boot.
- Power: the board runs from the external 5 V via E5V (jumper JP3 set to E5V), common ground with the servo rail. This makes the watchdog work when the laptop USB is unplugged.

- [ ] **Step 1: Implement** `main.cpp`: a line parser, a servo table, EEPROM rest storage, and `loop()` checking watchdog and max hold every 10 ms.
- [ ] **Step 2: `pio run -e nucleo_f767zi` and `pio run -e nucleo_f746zg`.** Expected: both build.
- [ ] **Step 3: Bench test with one servo (manual, `picocom -b 115200 /dev/ttyACM0`):**
  - `REST 0 90` → `OK`, servo at 90
  - `ANGLE 0 60` → servo moves
  - stop typing for 2 s → `EVT WATCHDOG`, back at 90
  - send `MAXHOLD 5000`, then `ANGLE 0 60` and keep sending `PING`s → `EVT MAXHOLD 0` after about 5 s
  - power-cycle → `EVT BOOT`, servo at 90
  - with the board on E5V: `ANGLE 0 60`, pull USB → back at 90 within 2 s

  Record the results in `firmware/PROTOCOL.md`.
- [ ] **Step 4: Commit** `feat: STM32 servo firmware with watchdog, max hold, release on boot`.

### Task 9: SerialController

**Files:**
- Create: `src/announcer/controller/serial_ctrl.py`
- Test: `tests/test_serial_ctrl.py`

**Interfaces:**
- Consumes: `Controller` protocol, the firmware protocol (Task 8), `Config.controller`, `Config.actuators`
- Produces: `SerialController(port, actuators, keepalive_ms, watchdog_ms, max_hold_s, clock)`.
  - `connect()` opens pyserial, sends `WATCHDOG`, `MAXHOLD` and `REST` for each actuator, then starts a keep-alive task that sends `PING` every `keepalive_ms`.
  - Name→channel lookup comes from `actuators`; an unknown name raises `ControllerError`.
  - Every command waits for `OK`/`ERR` with a 1 s timeout. On timeout, mark `connected=False` and raise `ControllerError`.
  - `EVT` lines are logged and exposed as `last_event: str | None`.
  - A single asyncio lock serialises the port; blocking I/O runs via `asyncio.to_thread`.

- [ ] **Step 1: Failing tests** against a fake port (an in-memory object with `write`/`readline` that answers like the firmware): `test_connect_sends_rest_for_each_actuator`, `test_tap_sends_angle_then_release`, `test_unknown_button_raises`, `test_timeout_marks_disconnected`, `test_keepalive_pings`.
- [ ] **Step 2: Run, expect FAIL. Implement. Run, expect PASS.**
- [ ] **Step 3: Hardware check (manual).** `uv run announcer` with the real board and one servo labelled SC1. Calibration page → "Test tap" moves it; quitting the app (Ctrl+C) leaves every servo at rest.
- [ ] **Step 4: Commit** `feat: serial controller`.

### Task 10: Mechanics, wiring and speaker holder

**Files:**
- Create: `hardware/cad/` (parametric sources, e.g. OpenSCAD or FreeCAD with a spreadsheet; Tim's choice), `hardware/cad/params.*`, `hardware/wiring.md`, `hardware/replica/` (flat panel replica)

Parameters, all in one params file: case outer width/depth/height, edge profile, button pitch X/Y, button size, button travel, press force, position of the evacuation alarm. Start from estimates scaled from `docs/reference/impro-desk.jpg`, using the ~19 mm button pitch as reference (assumption: standard 19 mm illuminated push buttons). Replace the estimates with Tim's measurements when they arrive.

- [ ] **Step 1: Replica.** Print a flat panel with button bosses at the estimated pitch, and a spring-loaded test button whose force is close to the measured force (or a guess of 3 N until measured). Done when printed.
- [ ] **Step 2: Frame.** Aluminium extrusion backbone clamped to the left and right case edges with padded printed clamps (no adhesive). Servo modules slide in the extrusion slot over any button column and adjust in height. The frame must leave the evacuation alarm (top-left, covered red button) and its flip cover free. Check: open the cover by hand with the rig mounted on the replica.
- [ ] **Step 3: Stiffness check.** Hold SPREKEN pressed on the replica for 60 s with the servo at its press angle. Done when the test button stays actuated the whole time, measured deflection is < 0.5 mm (feeler gauge or dial), and the servo force margin is ≥ 2× the measured press force at the arm length used.
- [ ] **Step 4: Speaker holder** that clips to a gooseneck-sized tube at a fixed 3–5 cm from the mic head.
- [ ] **Step 5: `hardware/wiring.md`:** 5 V supply → servo rail (+1000 µF cap) → servos; 5 V → Nucleo E5V with JP3 on E5V; common GND; signal pins per the Task 8 table; USB sound card → speaker/amp.
- [ ] **Step 6: Commit** `feat: parametric frame, replica, wiring`.

### Task 11: Integration rehearsal and on-site checklist

**Files:**
- Create: `docs/onsite-checklist.md`

- [ ] **Step 1: Full bench rehearsal** on the replica with all 4 servos, the speaker at a spare microphone (or phone recording), and the real Cupkit source. Run `--sim-start 2026-12-19T14:45 --sim-speed 1` for 20 minutes. Expected: every session taps the halls, holds SPREKEN through the chime and the speech, and releases; the 14:55 merged session plays end then start. Then pull USB mid-hold → servo back at rest within 2 s.
- [ ] **Step 2: Write `docs/onsite-checklist.md`** (morning of 18 Dec, ≤ 1 h):
  1. Mount the frame; confirm the evacuation alarm cover opens.
  2. Power up; `EVT BOOT`; dashboard shows the controller connected.
  3. Calibrate each servo's rest/press on the Calibration page, then Save.
  4. Press SC1 + Spreken by hand while timing the chime → set `chime_seconds`.
  5. Test full sequence → listen in a hall; adjust volume and the speaker distance.
  6. After the test: are the hall lights still on? If yes, enable `deselect_zones_after` and retest.
  7. Check schedule source OK, matches count, first session time.
  8. Check that `systemd-inhibit --list` shows announcer; laptop on mains power.
  9. Resume (RUNNING) before 08:59.
- [ ] **Step 3: Commit** `docs: on-site checklist`.
