# On-site checklist, ISSTT IMPRO announcer

- **Friday 18 December:** setup, then the evening test on the real desk. Sections 0 to 8.
- **Saturday 19 December:** matches. Morning go-live, section 9.
- **Sunday 20 December:** matches. Morning steps, section 10.

Work top to bottom. Every step has a PASS you can see. If a step says STOP, do not go on until it is fixed.
Numbers for the rig (squeeze, gauge, pull force) live in [`hardware/cad/README.md`](../hardware/cad/README.md) and may change once the desk is measured. This list points there instead of copying them.

## 0. Safety (read first, do first)

**STOP rules. Any one of these means the rig does not run on the desk.**

- The real Ontruimingsalarm or Koppel ruimtes cover cannot be opened and the button reached with one hand, seated, with the full rig fitted.
- Anything (speaker, holder, mic, gooseneck, servo lead) is in the hand volume above either cover.
- Spreken stays pressed after any test below.
- The jaw plastic touches the case, or the GO blade of the gauge does not fit.

**If something goes wrong during an announcement, in this order:**

1. **EMERGENCY STOP** on the Dashboard or Manual page.
2. **Ctrl+C** in the terminal running `announcer`.
3. Pull the laptop USB from the Nucleo: the firmware watchdog releases within 2 s.
4. The manual recovery in 0.5.

### 0.1 Before power-on

- [ ] **Rest and press first.** Open `config.toml` and set, for the four actuators, `rest` to about 135 and `press` to a safe angle close to it, for example 120. The real press angle comes from calibration in section 2. PASS: `rest` is not 90 and `press` is not 60 in `config.toml`. See "Cam calibration" in the README.
- [ ] **Plungers out** until one connect with the final rest has happened (section 1), unless the last bench step in the [README](../README.md#last-bench-step) was done with this rest. The firmware drives the servos to the rest in its flash at power-on, before the host sends any config, and the cam at rest 90 holds the plunger about 1.5 mm into the button travel. PASS: no plunger in a guide, or the bench step is ticked here: ____
- [ ] **Speaker power** is the separate USB wall charger, not the laptop and not the servo rail. PASS: speaker on, no hum.

### 0.2 Mount the frame and set the squeeze

- [ ] Mount the frame on the desk. Set the squeeze with the tensioner **with the stop collars fitted**, then check with the go/no-go gauge: "Setting the squeeze" in the README.
  - PASS: the GO blade fits and the NO blade does not, at the front and back edge of both posts.
  - **Never run a push bolt without its collar.** The collar is what stops the jaw plastic reaching the case.
- [ ] **Upward pull test.** Pull the frame up with a spring scale (or a weighed pull) to at least 2x the measured press force. PASS: it does not lift or slip. Repeat after the rig has been clamped for some hours. If the foam has relaxed, redo the squeeze (foam take-up in the README).

### 0.3 Covers reachable

- [ ] **Fit the rest of the rig first:** the modules on the rail (plungers still out, see 0.1), the speaker holder and speaker on the gooseneck, the mic where it will stay, and the servo leads along their route. The checks below only count with all of it in place. PASS: nothing is left to fit.
- [ ] **Alarm cover.** Sit at the operator position. With one hand, open the real *Ontruimingsalarm* cover and reach the button. PASS: you can, without touching the rig. FAIL: STOP. Do not run the rig on the desk; use the fallback in the README ("Cover, real desk"). This is unproven until done on site.
- [ ] **Koppel cover.** Same, for *Koppel ruimtes*. PASS or STOP, as above.
- [ ] **Hand volume.** The speaker, holder, mic and all servo leads (also after the gooseneck sags) stay out of the volume above both covers. Servo leads follow the routing rule in `wiring.md`. PASS: nothing in that volume. Write the allowed mic position here: ____________________ (mic distance to the speaker driver face as in the README, "Speaker holder").
- [ ] **Gooseneck sag.** Leave the speaker on the gooseneck for a while (suggestion: 10 minutes). PASS: it does not drop towards the covers or away from the mic.

### 0.4 Spreken must release (do after section 3, once the GUI is up)

Run these with the real rig on the real SPREKEN button. After each one, turn any zone lights off by hand: these stops skip the deselect.

- [ ] **Hold to talk.** Manual page, hold "Hold to talk" for a few seconds, then let go. PASS: the SPREKEN button comes up as soon as you let go (suggestion: under a second) and the Manual page status clears.
- [ ] **Emergency stop during a hold.** Open the Dashboard in a second tab. On the Calibration page click **Test full sequence**, switch to the Dashboard, and click **EMERGENCY STOP** while SPREKEN is held. (Not with Hold to talk and a mouse: moving the pointer off that button already ends the talk.) PASS: the servo returns to rest at once, the Dashboard says `EMERGENCY STOP: PAUSED`, the session shows FAILED (emergency stop) with "play now", and nothing fires until you click **Resume**. Evidence so far (not the real rig): driven through the NiceGUI socket with `--mock` on 2026-11-02, `release_all` logged within 1 ms of the click, then the session's own `release SPREKEN`, then a second `release_all`. The next session did not fire until Resume. The real-servo part is untested until you do this.
- [ ] Pause alone releases nothing and does not end a hold or a running session. "Release all" on the Calibration page is refused while a session or talk is running. Use EMERGENCY STOP.
- [ ] **Ctrl+C during a hold.** Hold "Hold to talk", then press Ctrl+C in the terminal. PASS: the servo returns to rest and the program exits. Evidence so far (not the real rig): the final review drove Hold to talk through the NiceGUI socket with `--mock`; SIGINT reached `release SPREKEN` in about 80 ms and `release_all` in about 180 ms. Still untested on real servos.
- [ ] **Unplug USB during a hold.** Hold "Hold to talk", then pull the laptop USB cable from the Nucleo. PASS: the servo is back at rest within 2 s (firmware watchdog). Plug it back in and confirm the dashboard says "controller connected" again.
- [ ] **Max hold, GUI side.** Hold "Hold to talk" past `max_hold_s` (60 s in `config.example.toml`) without letting go. PASS: the host ends the talk and releases SPREKEN at that time (log: `talk reached max hold`). This is the host limit, not the firmware one.
- [ ] **Firmware max hold: bench only, replica.** The GUI cannot trigger it, because the host releases first. Stop the announcer: it locks the port. Run `pio device monitor -d firmware --echo` (commands in `firmware/PROTOCOL.md`), then `MAXHOLD 5000`, `ANGLE 3 <press angle>`, and keep sending `PING` lines. If `ANGLE` answers `ERR no rest`, send `REST 3 <rest>` first. PASS: `EVT MAXHOLD 3` after about 5 s and the servo is at rest, although the keep-alives continue. Channel 3 is SPREKEN in `config.example.toml`. Restart the announcer afterwards so the configured MAXHOLD is back.

### 0.5 5 V loss during a hold: accepted risk

**Accepted by Tim on 2026-11-02.** If the 5 V adapter dies or is unplugged during a hold, the servo loses power and the Nucleo (on E5V) loses power too. No failsafe can act, and a stuck servo may leave SPREKEN pressed or not. Nothing in software covers this. These steps are so you know what to expect, not a decision to make.

- [ ] Bench-test it on the replica: pull the adapter during a Spreken hold. Result: ____________________
- [ ] Put the adapter and the desk on **one power strip** where possible. This covers mains loss only, not a pulled plug or a failed adapter.
- [ ] **Manual recovery** if SPREKEN is stuck down: either lift the whole frame straight up off the desk with both hands (it is held by clamp friction; the README's estimate is about 33 N per side, under "Clamp grip", so measure the real pull first), or free just that button: loosen the module's height bolt with a hex key through the bracket slot (assembly step 8 in the README) and slide the bracket up the carriage until the plunger is clear of the cap. The module route has only +6 mm of height travel and is **unproven: try it on the bench first**, and do not count on it until it has worked. PASS: the button comes up and the PA stops transmitting. Practise both on the replica first.

## 1. Power up and connect

- [ ] Power order: servo rail first, then the laptop USB (see `wiring.md`).
- [ ] Laptop on **mains power**.
- [ ] Start: `uv run announcer` in `/datim/repos/isstt-impro-announcer`, then open `http://127.0.0.1:8080`. **The app starts RUNNING.** If setup overruns into a real announcement, click **Pause** first.
- [ ] PASS: the terminal logs `controller connected on` and the Dashboard header shows **controller connected**. FAIL (`CONTROLLER DISCONNECTED`): check the cable and `controller.port` in `config.toml`, and that no `pio device monitor` has the port open.
- [ ] PASS: all four servos sit at rest and no button is pressed.
- [ ] That was the connect with the final rest: now put the plungers in, with the dot in the tip, if they were out.

## 2. Calibrate each servo (Calibration page)

**Good to know:**

- Save rewrites `config.toml` without its comments. If the file was changed by hand after the announcer started, Save refuses: restart the announcer.
- A rest slider moved away from the saved rest counts as away for the firmware. After `max_hold_s` (60 s) the servo snaps back to the saved rest, with `EVT MAXHOLD` on the Dashboard. That is expected during module adjustment: move the slider again, or Save first.
- Test tap uses the two sliders, not the saved values.
- The SPREKEN rest must stay at least 10 degrees from its press. Closer than that, the servo goes back to the saved rest after about 1.5 s, and Save refuses.

For SC1, SC2, SC3 and SPREKEN, one at a time:

- [ ] **Module height first**, not the slider: with the eccentric pointing up (the cam's clear position), adjust the module height so the plunger rests on the cap with about 1 mm gap to the cam (README assembly step 9). Do not set this at servo angle 90. Then set the **rest** slider so the cam is clear of the plunger. Expect about 135.
- [ ] Move the **press** slider to the angle where the button **just bottoms out**. Expect about 65. Do not go further: overdriving draws current and lifts the frame. PASS: the button clicks or bottoms and the frame does not lift. Eccentrics all point the same side.
- [ ] Click **Test tap**. PASS: the button is pressed once and the servo comes back to rest.

Then:

- [ ] After all four: click **Save**. PASS: a green "saved to ..." message. (The SPREKEN press slider is temporary and returns to rest after about 1.5 s.)
- [ ] Click **Release all (servos to rest)**. PASS: all servos at rest, and no "CALIBRATION: off rest" tag on the Dashboard.
- [ ] **Adapter voltage.** Meter at the servo rail, **Test tap** on each servo in turn. Taps are sequential, so this is one servo at a time. PASS: stays within 4.75 to 5.25 V under load. FAIL: STOP, fix the adapter or wiring ([`hardware/wiring.md`](../hardware/wiring.md)).

## 3. Time the chime

- [ ] Time from Spreken going down until the chime ends: ______ s. Use **Hold to talk** on the Manual page with a stopwatch, or press by hand **before the module is fitted**. Do not press by hand under a fitted module.
- [ ] On the Calibration page set **chime seconds** to that time (plus a small safety margin), then **Save**. PASS: the value is shown after reloading the page.
- [ ] Do the section 0.4 release tests now.

## 4. Full sequence, volume and speaker distance

- [ ] **All zone lights off, by hand if needed.** Zones are toggles, and Test tap, Hold to talk and the stops in 0.4 can leave them on. A session that starts with a light on turns that zone off. PASS: no zone light on.
- [ ] **Do-not-disturb on** in the desktop, so no notification sound can reach the mic. PASS: `notify-send test` makes no sound and no popup.
- [ ] Dashboard is RUNNING (the Calibration test does not play while PAUSED). The speaker is aimed at the mic at the distance in the README.
- [ ] Click **Save**, then **Test full sequence** ("This is a test announcement."). PASS: the halls tap, SPREKEN is held through the chime and the speech, then released.
- [ ] Walk to a hall. PASS: the test is audible and clear. If not, change **volume** or the speaker distance, **Save** and test again. Both speaker channels play mono speech, which is expected.
- [ ] Listen for hum from the speaker. PASS: none.
- [ ] Preview buttons on the Settings page are refused during a session and for 30 s before one, because they share the audio device. They still play on the same speaker; that is harmless, because the mic is live only while Spreken is held.
- [ ] **Hall lights after the test.** Look at them.
  - All off by themselves: leave **deselect zones after** unticked. PASS.
  - Still on: tick **deselect zones after** on the Calibration page, **Save**, turn all zone lights off **by hand**, and test again. PASS: lights on during the announcement, off after it.
- [ ] Failed starts toggle the zones back whatever this option says. EMERGENCY STOP and Ctrl+C never deselect: after either one, turn zone lights off by hand.

## 5. Schedule

The schedule is not fixed: it changes as teams register. There is no expected match count. Check this now, and again each morning.

- [ ] Dashboard, "Schedule:" line. PASS: no red banner (a source error, or time blocks that could not be read), and "last fetched" is recent (suggestion: within a couple of poll intervals, `poll_seconds` is 60).
- [ ] Open the current Cupkit page next to the Dashboard. PASS: the matches count, the first and the last times in "Upcoming" match the page, including the date. Times show as start and due: `Sat 08:59:55 (due 09:00:00)`, where due is the listed time.
- [ ] Settings page: the halls are the ones to announce in, and the match minutes per round are right. **Save**. PASS: green message, and the end times in "Upcoming" follow.

## 6. Laptop

- [ ] In another terminal, `systemd-inhibit --list`. PASS: a line with `announcer` appears, with `sleep:idle:handle-lid-switch`.
- [ ] **Lid-close test.** With the announcer running, close the lid for a minute and open it again. PASS: the laptop did not sleep, and the Dashboard clock and "controller connected" are still live.
- [ ] **Clock.** `timedatectl`. PASS: `System clock synchronized: yes` and `Time zone: Europe/Amsterdam`. Compare the Dashboard clock with your phone. The schedule runs on this clock (spec 5.6). No venue internet: compare with your phone and set it by hand.
- [ ] Mains is connected.

## 7. Speaker auto power-off (AUX)

- [ ] Leave the speaker idle in AUX for 30 to 60 minutes, then click **Test full sequence**. PASS: it still plays. If it shut off, tell Tim: a keep-alive tone is a possible future feature, not built.

## 8. End of Friday

- [ ] **Stop calibrating from here on.** The Calibration page refuses moves only while a session or talk runs, so it cannot protect the moment one starts. Do not calibrate while live.
- [ ] All zone lights off, by hand if needed.
- [ ] Ctrl+C the announcer for the night. PASS: the log says `engine stopped, controller released`.

## 9. Saturday morning, go live

- [ ] Rig: squeeze gauge and covers as in 0.2 and 0.3. PASS: GO fits, NO does not, covers reachable with one hand.
- [ ] Power order as in section 1, then `uv run announcer`. **It starts RUNNING**, so click **Pause** if you are not ready before the first session's start time.
- [ ] Clock and do-not-disturb as in sections 4 and 6.
- [ ] Schedule as in section 5. PASS: it matches the current Cupkit page.
- [ ] Remove any test leftovers: Calibration "away" tag gone, no queued text in "Upcoming" on the Dashboard (each has a **cancel** button).
- [ ] **All zone lights off, by hand if needed.**
- [ ] If the Dashboard says PAUSED, click **Resume**. Do this **before the first session's start time** in "Next:". PASS: green "RUNNING".
- [ ] Final glance: controller connected, no red banner, covers reachable, mic and speaker where recorded in 0.3.

## 10. Sunday morning

The schedule spans both days, and what was already played or skipped is kept in `state/`, so a restart is safe.

- [ ] Pull test again by hand, and the squeeze gauge. If the foam relaxed overnight, redo the squeeze (foam take-up in the README).
- [ ] Gooseneck and mic at the position recorded in 0.3. Speaker on its charger.
- [ ] Do the steps of section 9 again, from the power order down.
- [ ] Dashboard history after the start: anything MISSED that you did not expect? "Play now" is there if it still makes sense.

## Rehearsal (bench, before the day)

- Simulator runs (`--sim-start 2026-12-19T14:45 --sim-speed 1`) use `state/sim/`, so they do not touch the real state.

## Parts still to get

- EVA or rubber sheet, 3 mm (pads): Tim is getting it.
- Speaker strap: any velcro cable tie or elastic strap that fits the cradle slots, 3 x 18.8 mm.
- M2x8 screws for the servo horns: only if the stock screw is too short with the cam fitted. Check on one servo first.
