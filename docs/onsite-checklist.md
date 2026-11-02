# On-site checklist, Friday 18 December (morning, target 1 h)

Work top to bottom. Every step has a PASS you can see. If a step says STOP, do not go on until it is fixed.
Numbers for the rig (squeeze, gauge, pull force) live in [`hardware/cad/README.md`](../hardware/cad/README.md) and may change once the desk is measured. This list points there instead of copying them.

## 0. Safety (read first, do first)

**STOP rules. Any one of these means the rig does not run on the desk.**

- The real Ontruimingsalarm or Koppel ruimtes cover cannot be opened and the button reached with one hand, seated, with the full rig fitted.
- Anything (speaker, holder, mic, gooseneck, servo lead) is in the hand volume above either cover.
- Spreken stays pressed after any test below.
- The jaw plastic touches the case, or the GO blade of the gauge does not fit.

### 0.1 Before power-on

- [ ] **Rest angle first.** Open `config.toml` and set `rest` to about 135 for the four actuators (or take the plungers out for the first connect). The cam at rest 90 holds the plunger about 1.5 mm into the button travel, the host sends rest on every connect, and the failsafes return to it. PASS: `rest` is not 90 in `config.toml`, or the plungers are out. See "Cam calibration" in the README.
- [ ] **Speaker power** is the separate USB wall charger, not the laptop and not the servo rail. PASS: speaker on, no hum.

### 0.2 Mount the frame and set the squeeze

- [ ] Mount the frame on the desk. Set the squeeze with the tensioner **with the stop collars fitted**, then check with the go/no-go gauge: "Setting the squeeze" in the README.
  - PASS: the GO blade fits and the NO blade does not, at the front and back edge of both posts.
  - **Never run a push bolt without its collar.** The collar is what stops the jaw plastic reaching the case.
- [ ] **Upward pull test.** Pull the frame up with a spring scale (or a weighed pull) to at least 2x the measured press force. PASS: it does not lift or slip. Repeat after the rig has been clamped for some hours. If the foam has relaxed, redo the squeeze (foam take-up in the README).

### 0.3 Covers reachable (full rig fitted, including speaker and mic)

- [ ] **Alarm cover.** Sit at the operator position. With one hand, open the real *Ontruimingsalarm* cover and reach the button. PASS: you can, without touching the rig. FAIL: STOP. Do not run the rig on the desk; use the fallback in the README ("Cover, real desk"). This is unproven until done on site.
- [ ] **Koppel cover.** Same, for *Koppel ruimtes*. PASS or STOP, as above.
- [ ] **Hand volume.** The speaker, holder, mic and all servo leads (also after the gooseneck sags) stay out of the volume above both covers. Servo leads follow the routing rule in `wiring.md`. PASS: nothing in that volume. Write the allowed mic position here: ____________________ (mic distance to the speaker driver face as in the README, "Speaker holder").
- [ ] **Gooseneck sag.** Leave the speaker on the gooseneck for a while (suggestion: 10 minutes). PASS: it does not drop towards the covers or away from the mic.

### 0.4 Spreken must release (do after step 3, once the GUI is up)

Run these with the real rig on the real SPREKEN button.

- [ ] **Hold to talk.** Manual page, hold "Hold to talk" for a few seconds, then let go. PASS: the SPREKEN button comes up as soon as you let go (suggestion: under a second) and the Manual page status clears.
- [ ] **There is no emergency-stop button in the GUI.** Pause only sets a flag: it releases nothing and does not end a hold or a running session. The substitute is **Ctrl+C in the terminal running `announcer`**. Releasing "Hold to talk" ends a talk. "Release all" on the Calibration page is refused while a session or talk is running.
- [ ] **Ctrl+C during a hold.** Hold "Hold to talk", then press Ctrl+C in the terminal. PASS: the servo returns to rest and the program exits. Evidence so far (not the real rig): SIGINT to a headless `--mock` simulator run logged `engine stopped, controller released` and the process exited; `tests/test_engine.py::test_stop_releases_all_during_talk` passes (release SPREKEN, then release_all). A hold itself could not be scripted headless, so the real-servo part is untested until you do this.
- [ ] **Unplug USB during a hold.** Hold "Hold to talk", then pull the laptop USB cable from the Nucleo. PASS: the servo is back at rest within 2 s (firmware watchdog). Plug it back in and confirm the dashboard says "controller connected" again.
- [ ] **Max hold, GUI side.** Hold "Hold to talk" past `max_hold_s` (60 s in `config.example.toml`) without letting go. PASS: the host ends the talk and releases SPREKEN at that time (log: `talk reached max hold`). This is the host limit, not the firmware one.
- [ ] **Firmware max hold: bench only, replica.** The GUI cannot trigger it, because the host releases first. With the program stopped, use `picocom -b 115200 /dev/ttyACM0` (commands in `firmware/PROTOCOL.md`): `MAXHOLD 5000`, `ANGLE 3 <press angle>`, then keep sending `PING` lines. PASS: `EVT MAXHOLD 3` after about 5 s and the servo is at rest, although the keep-alives continue. Channel 3 is SPREKEN in `config.example.toml`.

### 0.5 5 V loss during a hold: OPEN DECISION for Tim

**Known exception to "Spreken is always released" until Tim accepts it.** If the 5 V adapter dies or is unplugged during a hold, the servo loses power and the Nucleo (on E5V) loses power too. No failsafe can act, and a stuck servo may leave SPREKEN pressed or not. Nothing in software covers this.

- [ ] Bench-test it on the replica: pull the adapter during a Spreken hold. Result: ____________________
- [ ] Repeat on the real button. Result: ____________________
- [ ] Put the adapter and the desk on **one power strip** where possible. This covers mains loss only, not a pulled plug or a failed adapter.
- [ ] **Manual recovery** if SPREKEN is stuck down: either lift the whole frame straight up off the desk with both hands (it is held by clamp friction, about 30 N, an estimate from the README, so measure the real pull first), or free just that button: loosen the module's height bolt with a hex key through the bracket slot (assembly step 8 in the README) and slide the bracket up the carriage until the plunger is clear of the cap. The module route has only +6 mm of height travel and is **unproven: try it on the bench first**, and do not count on it until it has worked. PASS: the button comes up and the PA stops transmitting. Practise both on the replica first.
- [ ] **Ask the venue:** does a held Spreken block other stations or the alarm path? Answer: ____________________
- [ ] Decision (Tim): accept / change the design. Date: ____________________

## 1. Power up and connect

- [ ] Power order: servo rail first, then the laptop USB (see `wiring.md`).
- [ ] Laptop on **mains power**.
- [ ] Start: `uv run announcer` in `/datim/repos/isstt-impro-announcer`, then open `http://127.0.0.1:8080`.
- [ ] PASS: the terminal logs `EVT BOOT` from the controller and the Dashboard header shows **controller connected**. FAIL (`CONTROLLER DISCONNECTED`): check the cable and `controller.port` in `config.toml`.
- [ ] PASS: all four servos sit at rest and no button is pressed.
- [ ] **Adapter voltage.** Needs powered servos, so do it here, after the Calibration page is open. Meter at the servo rail, move all four servos together (for example **Test tap** on each in quick succession): PASS = stays within 4.75 to 5.25 V under load. FAIL: STOP, fix the adapter or wiring ([`hardware/wiring.md`](../hardware/wiring.md)).

## 2. Calibrate each servo (Calibration page)

For SC1, SC2, SC3 and SPREKEN, one at a time:

- [ ] **Module height first**, not the slider: with the eccentric pointing up (the cam's clear position), adjust the module height so the plunger rests on the cap with about 1 mm gap to the cam (README assembly step 9). Do not set this at servo angle 90. Then set the **rest** slider so the cam is clear of the plunger. Expect about 135.
- [ ] Move the **press** slider to the angle where the button **just bottoms out**. Expect about 65. Do not go further: overdriving draws current and lifts the frame. PASS: the button clicks or bottoms and the frame does not lift. Eccentrics all point the same side.
- [ ] Click **Test tap**. PASS: the button is pressed once and the servo comes back to rest.
- [ ] After all four: click **Save**. PASS: a green "saved to ..." message. (The SPREKEN press slider is temporary and returns to rest after about 1.5 s.)
- [ ] Click **Release all (servos to rest)**. PASS: all servos at rest, and no "CALIBRATION: off rest" tag on the Dashboard.

## 3. Time the chime

- [ ] Press SC1 and Spreken **by hand** on the desk. Time from pressing Spreken until the chime ends: ______ s.
- [ ] On the Calibration page set **chime seconds** to that time (plus a small safety margin), then **Save**. PASS: the value is shown after reloading the page.
- [ ] Do the section 0.4 release tests now.

## 4. Full sequence, volume and speaker distance

- [ ] Dashboard is RUNNING (the Calibration test does not play while PAUSED). The speaker is aimed at the mic at the distance in the README.
- [ ] Click **Save**, then **Test full sequence** ("This is a test announcement."). PASS: the halls tap, SPREKEN is held through the chime and the speech, then released.
- [ ] Walk to a hall. PASS: the test is audible and clear. If not, change **volume** or the speaker distance, **Save** and test again. Both speaker channels play mono speech, which is expected.
- [ ] Listen for hum from the speaker. PASS: none.
- [ ] Preview buttons on the Settings page play on the same speaker; that is harmless, because the mic is live only while Spreken is held.
- [ ] **Hall lights.** After the test, are the hall lights still on? If yes, tick **deselect zones after** on the Calibration page, **Save** and test again. PASS: lights are off after the test.

## 5. Schedule

- [ ] Dashboard, "Schedule:" line. PASS: no red "Schedule source error" banner, and "last fetched" is recent (suggestion: within a couple of poll intervals, `poll_seconds` is 60).
- [ ] PASS: the matches count is what you expect. **Live Cupkit showed 198 matches, 32 start times, and a first match on 2026-12-19 09:00** where the test fixture has 18 Dec and 39 start times. Check the dates with the committee and re-check `schedule` the day before.
- [ ] PASS: "Next:" shows the first session at the right day and time (09:00 as announced).
- [ ] Settings page: the halls are the ones to announce in. **Save**.

## 6. Laptop stays awake

- [ ] In another terminal, `systemd-inhibit --list`. PASS: a line with `announcer` appears, with `sleep:idle`.
- [ ] Mains is connected.

## 7. Speaker auto power-off (AUX)

- [ ] Leave the speaker idle in AUX for 30 to 60 minutes, then click **Test full sequence**. PASS: it still plays. If it shut off, tell Tim: a keep-alive tone is a possible future feature, not built.

## 8. Go live

- [ ] Remove any test leftovers: Calibration "away" tag gone, no manual text queued.
- [ ] If the Dashboard says PAUSED, click **Resume**. Do this **before 08:59**. PASS: green "RUNNING".
- [ ] Final glance: controller connected, no schedule error, covers reachable, mic and speaker where recorded in 0.3.

## Rehearsal (bench, before the day)

- Simulator runs (`--sim-start 2026-12-19T14:45 --sim-speed 1`) use `state/sim/`, so they do not touch the real state.

## Parts still to get

- EVA or rubber sheet, 3 mm (pads)
- Speaker strap
- Possibly M2x8 screws for the servo horns

## Open items (not for the morning)

- Dates with the committee: first match 19 Dec 09:00 versus the 18 Dec fixture.
- 5 V loss decision (0.5).
