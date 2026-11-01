# ISSTT IMPRO Announcer — Design

Date: 2026-11-01
Hard deadline: **2026-12-18** (tournament day 1, matches from 09:00).

## 1. Intent

At the ISSTT tournament (18–20 December 2026) referees in the sports halls
must be told when to start and when to end their matches. The venue's PA is
driven by an **IMPRO paging desk** (photo: `docs/reference/impro-desk.jpg`):
a panel of illuminated push buttons plus a gooseneck microphone. Today a
person has to stand at the desk at every start and end time, select halls,
hold *Spreken* and speak.

This project makes those announcements happen automatically, on time, from
the tournament timetable published on the Cupkit website, by physically
pressing the desk's buttons from the outside and playing synthesised speech
into its microphone. An operator can pause/resume the whole thing and make
manual announcements from a GUI on a laptop.

Success = on 18–20 December every start and end announcement goes out on
time to the right halls without anybody standing at the desk, and setting it
up on the real desk takes well under the few hours available that morning.

## 2. Goals

1. Read the match timetable from Cupkit's public matches page (API later, see §5.7) and
   keep it up to date during the tournament (later rounds are filled in as
   results come in).
2. At each match start time: announce *"Referees, you may start the
   matches."* At each start + match length: announce *"Referees, you may end
   the matches."*
3. Press the IMPRO buttons mechanically, with actuators attached to the
   outside of the desk.
4. Play the announcement audio through a small speaker held at the gooseneck
   microphone.
5. A NiceGUI screen on the laptop: pause/resume, upcoming announcements,
   status, manual announcements, settings and on-site calibration.
6. Hardware that is easy to move to another desk/location, and where
   actuators can be added, removed or moved to other buttons without code
   changes.

## 3. Non-goals

- Per-field or per-hall targeting of announcements. Every announcement goes to
  the same configured set of halls.
- Sensing the *Bezet/Wachten* (busy) light. A fixed wait is enough (§5.3).
- Richer schedule-derived messages ("teams X and Y on field 1…") — **not
  built now**, but the message design must allow adding them later without
  restructuring (§5.5).
- Anything beyond Cupkit as a schedule source (but the source is swappable).
- Running unattended without the laptop; no Raspberry Pi/standalone box.

## 4. Anti-goals (failure even if it "works")

- **Opening, rewiring or modifying the IMPRO desk in any way.** Only external
  attachments; must leave no marks.
- **Ever touching the covered buttons** (*Ontruimingsalarm* = evacuation
  alarm, *Koppel ruimtes*). No actuator is ever mounted over them; the
  config must reject hall/button definitions that are not explicitly listed.
- **Blocking the evacuation alarm.** It must stay reachable and its flip
  cover openable by hand at all times while the rig is mounted.
- **Leaving Spreken held** (the PA stays open broadcasting the room) after a
  crash, disconnect, or laptop failure.
- Overlapping announcements, or speaking before the desk's chime finishes.
- A frame that flexes so buttons are not reliably pressed.
- A system that only works after code edits on site.

## 5. How it works (decided parts)

### 5.1 The desk (facts)

Buttons relevant now (labels as printed): `SC 1`…`SC 6` (sports halls),
`ALGEMEEN`, `ZWEMBAD`, `KANTINE`, `TERRAS`, `FITNESS`, `DOJO` (other zones),
`SPREKEN` (talk), `MUZIEK VOLUME HARDER/ZACHTER`, pre-recorded message buttons,
red `BEZET/WACHTEN` indicator.

- **Venue staff do not use the desk for announcements** during the
  tournament, so nobody else talks over the system and zones start unlit.
  (No Bezet sensing or manual lockout needed.)
- **Zone buttons are toggles**: press and release, it stays lit until the
  announcement ends. Whether a zone must be explicitly deselected afterwards
  is **unknown** — handled by a setting (§5.4) and verified on site.
- **Spreken is push-to-talk**: held down for the whole announcement; release
  ends it.
- After Spreken is pressed the desk plays a chime of fixed length while
  Bezet/Wachten blinks; speech must start after it.

### 5.2 Halls and timetable mapping

Cupkit locations look like `SC1, Field 1`. Fields 1–3 are in SC1, 4–6 in
SC2, field 7 in SC3. The hall name maps 1:1 to desk buttons `SC 1/2/3`.

Every announcement is sent to **all halls selected in settings** (initially
SC1, SC2, SC3), regardless of which halls have a match in that slot.

### 5.3 Announcement sequence (one "session")

1. Press and release each selected zone button (toggle on).
2. Press and **hold** Spreken.
3. Wait `chime_seconds` (configurable, calibrated on site).
4. Play the message audio (one or more messages back to back, see 5.6).
5. Optional short tail delay, then release Spreken.
6. If `deselect_zones_after` is enabled, press/release each zone again.

**Spreken must be released under all circumstances** (exception in any step,
audio failure, GUI shutdown, Ctrl+C). In addition the **firmware** enforces a
hard maximum hold time (watchdog, e.g. 60 s, configurable) and releases
everything if the laptop stops sending keep-alives (USB unplugged, laptop
crash). Firmware releases all actuators on boot.

### 5.4 Configuration

A single human-editable config file (e.g. TOML), editable from the GUI too:

- Actuators: name → firmware channel, rest angle, press angle, press/release
  durations. Buttons are referred to by name (`SC1`, `SPREKEN`, …), never by
  channel in code. Adding/moving an actuator = edit config, nothing else.
- Selected halls for announcements.
- `chime_seconds`, `tail_seconds`, `deselect_zones_after`, `lead_seconds`
  override (see 5.6), late-announcement threshold.
- Message texts, Piper voice/model, speech rate, output audio device, volume.
- Schedule source settings (matches page URL(s), poll interval) and match
  length per round (§5.6).
- Serial port of the controller.

No secrets are needed now (public page). A future API token is kept out of
the config file and out of git (env var or separate untracked file).

### 5.5 Messages

- Two message templates now: `match_start` and `match_end`, editable text.
- Generated to audio with **Piper** (local TTS). Cache generated audio per
  text+voice so it plays instantly and works offline; regenerate when the
  text changes; the GUI has a "preview" (play on laptop speakers) button.
- Message templates are rendered from the slot's data (the set of matches,
  teams, fields, round), so a later template like *"teams {home} and {away}
  play on {field}…"* is just a new template + render at announcement time.
  Only the two fixed phrases are required now.
- Language/voice: whatever is configured (texts above are the defaults).

### 5.6 Scheduling

- A **slot** = all matches with the same start time. Each slot produces one
  start announcement at `start` and one end announcement at `start + match
  minutes of that round`.
- **Match length per round is set in config** (Tim, 2026-11-01): Round 1 and
  Round 2 (poules) = **15 min**, Round 3–5 (knockout) = **20 min**, 5 min
  break between matches. Unknown rounds use a default of 20 min. Editable in
  the GUI. (The organiser Rounds page says "20 + 5 min" for every round; that
  is not what will be played, and it isn't public anyway.)
- Follow listed times exactly; the schedule is irregular (odd 20-minute gaps,
  one-match slots, long breaks between rounds while the committee prepares
  the next one).
- *Timing (my call):* start the session early by (zone presses + chime) so
  the first word is spoken on the scheduled minute. Computed from config,
  overridable by `lead_seconds`.
- *Collisions (my call):* announcements due within the same session window
  are merged into one session, end message first, then start, Spreken held
  throughout. Scheduled and manual announcements share one queue; never
  overlap.
- *Missed announcements (my call):* if paused/busy/disconnected and an
  announcement becomes more than `late_threshold` (default 60 s) late, it is
  skipped and logged; the GUI shows it and offers "play now".
- Re-read the timetable every minute (configurable). If the source fails,
  keep using the last known schedule, show a warning in the GUI. Persist the
  last good schedule to disk so a restart works offline.
- Cancelled/removed matches drop out; changed times reschedule.
- Use the tournament timezone (Europe/Amsterdam). The laptop clock should be
  NTP-synced; the GUI shows the current time prominently.
- Keep the laptop awake while running (inhibit sleep/screensaver).

### 5.7 Schedule source

- **Now: scraper of the public matches page**
  `https://cupkit.nl/messedup/isstt-36/senior/matches` (no login; saved copy
  `docs/reference/cupkit-public-matches.html`). Per round, per start time
  ("18 December 2026 at 09:00"): hall and field ("SC1, Field 1"), poule,
  teams ("A1 v A4"), referee, score or "To be played". It holds all 198
  matches / 39 start times, the same as the organiser pages. It has no match
  length, which comes from config (§5.6). Organiser/admin pages are not used
  and must not be committed.
- **Later: API.** The site owner has been asked to add
  `GET /api/v1/tournaments/{id}/schedule` (bearer token, ETag/304, separate
  hall/field, per-round match minutes, ISO times, status). Not guaranteed
  before the 18th.
- The source sits behind one small interface (returns a list of matches with
  start, end/match length, hall, field, teams, referee, status) so scraper and
  API are interchangeable, plus a **file source** (local JSON/CSV) for
  testing and as an emergency fallback (e.g. schedule typed in by hand).

### 5.8 Hardware

- **Controller:** an STM32 board Tim already has, connected to the laptop
  over USB serial. Simple line-based protocol (e.g. `PRESS SC1`,
  `HOLD SPREKEN`, `RELEASE ALL`, `SET 3 ANGLE 95`, `PING`), with acks, so it
  can be driven by hand from a terminal for testing.
- **Actuators (my call): micro servos (MG90S, metal gear)**, one per button,
  one PWM channel each. Chosen because press depth is set in software
  (calibrate in seconds on site), they hold Spreken without heating, are
  cheap and quiet. Solenoids and linear actuators were rejected (fixed
  stroke, heat when holding, noise, driver circuits / slow, expensive).
- Separate 5 V supply for servos (enough current for all servos moving at
  once), common ground with the STM32.
- **Controller board (my call):** the **NUCLEO-F767ZI** (dedicated to this
  project); the NUCLEO-F746ZG, used elsewhere, is the spare. Same family, so
  firmware should build for both. Builder decides between the ST-Link virtual
  COM port and the board's user USB port, as long as the board stays powered
  from the external 5 V supply (E5V/VIN) when the laptop USB is unplugged.
- **Mounting:** 3D-printed on Tim's Bambu Lab H2D. A **rigid bridge/rail**
  across the panel, clamped to the black case edges with padded clamps (no
  adhesive, no marks). Servo modules bolt onto slots in the rail and can be
  positioned over any button. **Stiffness is a requirement**: holding
  Spreken pushes back on the frame continuously; the frame must not deflect
  enough to lose the press (consider aluminium extrusion or a ribbed print,
  and clamping on both sides of the case). The frame shape must leave the
  evacuation alarm (top-left area, red covered button) free to reach and its
  cover free to open — e.g. a rail that does not span over it, or an open
  bridge high enough to clear it.
- **Desk measurements:** Tim will measure the desk in the coming weeks (case
  outer size and height, edge profile, button size/pitch/travel, Spreken
  press force). *My call:* design the printed parts parametrically so they
  can be built from the photo-based estimates now and reprinted once real
  numbers arrive. Size servos for at least 2–3× the measured press force at
  the arm length used.
- Each module plugs into the controller with a standard servo connector;
  channel numbers are labelled.
- **Speaker:** small powered speaker or laptop audio → amp → small driver,
  in a 3D-printed holder that clips to the gooseneck at a fixed distance.
  Volume calibrated on site.
- Initial actuators: SC 1, SC 2, SC 3, SPREKEN. Spare channels for more.

### 5.9 GUI (NiceGUI, on the laptop)

- Big status: running/paused, controller connected, schedule age/source
  status, current time, next announcement with countdown.
- Pause/resume everything (scheduled and manual).
- Upcoming announcements list (time, type, slot info), recent history
  (played/skipped/failed).
- Manual announcement: pick halls, then either type text (Piper speaks it) or
  "Talk": the system selects halls and holds Spreken while the button is held
  in the GUI, and the operator speaks at the gooseneck. Talk still has the
  hard maximum hold.
- Calibration page: per actuator jog press angle, test press, test the full
  sequence with a test phrase; adjust chime/tail delays and volume; save to
  config.
- Settings: message texts (with preview), halls, source.

### 5.10 Tooling and platform

Python, managed with **uv** (Tim's standard), NiceGUI for the GUI, Piper for
TTS. Firmware for the STM32 in whatever toolchain fits the board.

The app runs on **Tim's own laptop (Arch Linux)** at the venue; no other
machine/OS needs supporting.

### 5.11 Parts and power (my calls)

- No hardware is on hand except an STM32 board; servos, 5 V supply, speaker
  /amp and any frame material must be **ordered first** — ordering is the
  first task on the critical path (allow for 2–4 week shipping).
- The STM32 is **powered from the servo 5 V supply** (not only from USB), so
  pulling USB does not kill the controller and the keep-alive watchdog can
  still release Spreken. Firmware release = drive servos to their rest angle.

## 6. Testing without the desk (critical)

There may be no access to the real desk before the morning of 18 December.
Therefore:

- A **mock controller** (software) so the whole app runs without hardware,
  logging button actions with timestamps.
- A **simulated clock / time-acceleration** mode to run a full tournament day
  in minutes against the saved schedule.
- Schedule parsing tested against the saved pages in `docs/reference/`.
- A **cardboard/printed replica** of the panel layout (button pitch and
  sizes measured from the photo or on site if possible) to test mechanics
  and frame stiffness.
- Firmware failsafes (watchdog release, release on boot) tested by pulling
  USB mid-hold.
- An on-site checklist for 18 Dec: mount, calibrate each servo, check
  whether zones need deselecting, measure chime length, set volume, run a
  test announcement, verify schedule fetch, start.

## 7. Left to the builder

- Exact firmware design, serial protocol details, STM32 board choice among
  those available, pin assignment.
- 3D-printed part designs (within the stiffness and no-marks requirements).
- Internal software architecture, file formats, persistence details.
- Scraping technique (HTML parsing details).
- GUI layout.
- Piper voice choice (pending Tim's preference; a clear English voice by
  default).

## 8. Open items to verify on site / with Tim

- Do zone buttons need deselecting after an announcement?
- Chime length.
- Button force, travel and pitch (Tim measures before 18 Dec; method: put a
  small cup on the button and add water/coins until it clicks, then weigh
  cup + contents; measure travel with calipers).
