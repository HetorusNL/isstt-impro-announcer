"""NiceGUI pages, built from engine state. Logic worth testing lives in gui.view."""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING

from nicegui import app, ui

from announcer.audio.player import SoundPlayer
from announcer.config import (
    ENGLISH_VOICES,
    JA_SUFFIX,
    MAX_PAUSE_S,
    MAX_SPEED,
    MIN_SPEED,
    SAMPLE_RENDER,
    Config,
    ja_key,
)
from announcer.config import Tts as TtsConfig
from announcer.controller.base import ControllerError
from announcer.engine import Engine, Key
from announcer.gui import view
from announcer.model import Session
from announcer.sequencer import SPREKEN
from announcer.speech import spoken_parts

if TYPE_CHECKING:
    from announcer.main import Runtime

log = logging.getLogger(__name__)

REFRESH_S = 0.5
UPCOMING_SHOWN = 15
HISTORY_SHOWN = 40
PAGES = [
    ("/", "Dashboard"),
    ("/manual", "Manual"),
    ("/calibration", "Calibration"),
    ("/settings", "Settings"),
]


def serve(rt: Runtime, host: str, port: int) -> None:
    engine = Engine(
        rt.cfg,
        rt.source,
        rt.store_path,
        rt.ctrl,
        rt.player,
        rt.tts_factory(rt.cfg.tts),
        rt.clock,
        tts_factory=rt.tts_factory,
    )

    async def startup() -> None:
        try:
            await rt.ctrl.connect()
            await rt.ctrl.configure(rt.cfg.actuators)
        except Exception:
            log.exception("controller not ready; the dashboard shows it disconnected")
        await engine.start()
        log.info("engine started; GUI on http://%s:%s", host, port)

    async def shutdown() -> None:
        try:
            await engine.stop()  # always ends with release_all
        finally:
            await rt.ctrl.close()
        log.info("engine stopped, controller released")

    app.on_startup(startup)
    app.on_shutdown(shutdown)
    cal = view.Calibrator(rt.ctrl, lambda: view.desk_busy(engine))
    _pages(rt, engine, cal)
    ui.run(
        host=host,
        port=port,
        title="ISSTT IMPRO announcer",
        reload=False,
        show=False,
        show_welcome_message=False,
    )


def _notify_error(message: str | None, ok: str) -> None:
    if message is None:
        ui.notify(ok, type="positive")
    else:
        ui.notify(message, type="negative", multi_line=True, timeout=10000)


def _header(rt: Runtime) -> None:
    with ui.header().classes("items-center"):
        ui.label("IMPRO announcer").classes("text-lg font-bold")
        for path, name in PAGES:
            ui.link(name, path).classes("text-white")
        if rt.sim:
            ui.label("SIMULATION").classes("bg-orange-600 px-2 rounded")


def _hall_boxes(cfg: Config, selected: list[str]) -> Callable[[], list[str]]:
    with ui.row():
        boxes = {h: ui.checkbox(h, value=h in selected) for h in view.hall_choices(cfg)}
    return lambda: [h for h, box in boxes.items() if box.value]


def _estop_button(engine: Engine, cal: view.Calibrator) -> None:
    async def stop() -> None:
        cal.abort()
        try:
            await engine.emergency_stop()
        except ControllerError as e:
            ui.notify(
                f"RELEASE FAILED ({e}): the firmware watchdog is the fallback. Check the servos.",
                type="negative",
                multi_line=True,
                timeout=0,
            )
            return
        ui.notify("Emergency stop: all released, PAUSED until Resume", type="warning")

    ui.button("EMERGENCY STOP", on_click=stop, color="red").classes("text-2xl p-6 font-bold")


def _pages(rt: Runtime, engine: Engine, cal: view.Calibrator) -> None:
    @ui.page("/")
    def dashboard() -> None:
        _header(rt)
        clock = ui.label().classes("text-7xl font-mono")
        _estop_button(engine, cal)
        with ui.row().classes("items-center gap-6"):
            state = ui.label().classes("text-3xl font-bold")
            toggle = ui.button(
                on_click=lambda: engine.resume() if engine.paused else engine.pause()
            )
            ctrl = ui.label().classes("text-lg")
            talk = ui.label("TALKING").classes("text-lg bg-red-600 text-white px-2 rounded")
            away = ui.label().classes("text-lg bg-orange-600 text-white px-2 rounded")
            event = ui.label().classes("text-lg")
        banner = ui.label().classes("w-full bg-red-600 text-white p-2 text-lg")
        source = ui.label()
        playing = ui.label().classes("text-2xl bg-green-600 text-white px-2 rounded")
        with ui.row().classes("items-baseline gap-4"):
            nxt = ui.label().classes("text-2xl")
            countdown = ui.label().classes("text-4xl font-mono")

        async def play_now(key: Key) -> None:
            ui.notify(f"playing {view.fmt_key(key)} next")
            try:
                await engine.play_now(key)
            except (KeyError, RuntimeError) as e:
                ui.notify(str(e), type="warning")

        def cancel(session: Session) -> None:
            error = view.cancel_queued(engine, session)
            if error is not None:
                ui.notify(error, type="warning")

        @ui.refreshable
        def lists() -> None:
            with ui.row().classes("w-full items-start gap-12"):
                with ui.column():
                    ui.label("Upcoming").classes("text-xl font-bold")
                    for s in engine.queued:
                        with ui.row().classes("items-center"):
                            ui.label(view.queued_label(s)).classes("font-mono")
                            ui.button("cancel", on_click=partial(cancel, s)).props("dense")
                    for s in engine.upcoming[:UPCOMING_SHOWN]:
                        ui.label(
                            f"{view.fmt_session_times(s)}  {view.session_kinds(s)}"
                            f"  ({view.session_matches(s)} matches)"
                        ).classes("font-mono")
                with ui.column():
                    ui.label("History (newest first)").classes("text-xl font-bold")
                    for row in view.history_rows(engine.history)[:HISTORY_SHOWN]:
                        with ui.row().classes("items-center"):
                            detail = f" ({row.detail})" if row.detail else ""
                            ui.label(
                                f"{row.at:%a %H:%M:%S}  {view.fmt_key(row.key)}"
                                f"  {row.status.upper()}{detail}"
                            ).classes("font-mono")
                            if row.replayable:
                                ui.button("play now", on_click=partial(play_now, row.key)).props(
                                    "dense"
                                )

        lists()
        last = [None]

        def tick() -> None:
            now = rt.clock.now()
            clock.text = f"{now:%a %H:%M:%S}"
            state.text = "RUNNING"
            if engine.paused:
                state.text = "EMERGENCY STOP: PAUSED" if engine.estopped else "PAUSED"
            state.classes(
                replace="text-3xl font-bold "
                + ("text-orange-600" if engine.paused else "text-green-700")
            )
            toggle.text = "Resume" if engine.paused else "Pause"
            ctrl.text = "controller connected" if rt.ctrl.connected else "CONTROLLER DISCONNECTED"
            talk.visible = engine.talking
            away.visible = bool(cal.away)
            away.text = "CALIBRATION: off rest: " + ", ".join(
                f"{n} {a}" for n, a in sorted(cal.away.items())
            )
            event.text = f"Last board event: {rt.ctrl.last_event}"
            event.visible = rt.ctrl.last_event is not None
            banner.text = view.banner_text(engine) or ""
            banner.visible = bool(banner.text)
            source.text = (
                f"Schedule: {engine.matches_count} matches, last fetched "
                f"{view.fmt_age(now, engine.source_ok_at)}"
            )
            cur = engine.current
            playing.visible = cur is not None
            if cur is not None:
                playing.text = f"NOW PLAYING: {view.session_kinds(cur)} ({', '.join(cur.halls)})"
            if engine.upcoming:
                s = engine.upcoming[0]
                nxt.text = f"Next: {view.fmt_session_times(s)} {view.session_kinds(s)}"
                countdown.text = view.fmt_countdown((s.start_at - now).total_seconds())
            else:
                nxt.text, countdown.text = "No upcoming sessions", ""
            sig = view.list_signature(engine, UPCOMING_SHOWN)
            if sig != last[0]:
                last[0] = sig
                lists.refresh()

        tick()
        ui.timer(REFRESH_S, tick)

    @ui.page("/manual")
    def manual() -> None:
        _header(rt)
        _estop_button(engine, cal)
        cfg = engine.cfg
        ui.label("Halls").classes("text-xl font-bold")
        halls = _hall_boxes(cfg, cfg.announce.halls)
        text_ja = ui.textarea("Japanese text (spoken first)").classes("w-full max-w-2xl")
        text = ui.textarea("English text").classes("w-full max-w-2xl")

        async def speak() -> None:
            en, ja = (text.value or "").strip(), (text_ja.value or "").strip()
            if not halls() or not (en or ja):
                ui.notify("select halls and type a text", type="warning")
                return
            if not spoken_parts(engine.cfg.tts, en, ja):
                ui.notify(
                    "nothing to say: the typed language is switched off (Settings)",
                    type="warning",
                )
                return
            try:
                await engine.manual_text(halls(), en, ja)
            except RuntimeError as e:
                ui.notify(str(e), type="negative")
                return
            ui.notify("queued: plays after a running session, and only while RUNNING")

        ui.button("Speak", on_click=speak)
        ui.label("Talk: hold the button and speak at the gooseneck (runs even when paused).")
        hold = view.TalkHold(engine)

        def press() -> None:
            if halls():
                hold.press(halls())
            else:
                ui.notify("select halls first", type="warning")

        btn = ui.button("Hold to talk").classes("text-2xl p-8")
        btn.style("touch-action: none; user-select: none; -webkit-user-select: none")
        # touchstart.prevent: no emulated mousedown after a touch, so one press = one talk
        for ev in ("mousedown", "touchstart.prevent"):
            btn.on(ev, press)
        for ev in ("mouseup", "mouseleave", "touchend", "touchcancel"):
            btn.on(ev, hold.release)
        btn.on("contextmenu.prevent", lambda: None)  # long press: no menu
        ui.context.client.on_disconnect(hold.release)
        status = ui.label()

        def tick() -> None:
            if engine.talking:
                status.text = "TALKING: SPREKEN held"
            elif hold.pressed:
                status.text = "waiting for the desk..."
            else:
                status.text = f"talk failed: {hold.error}" if hold.error else ""

        ui.timer(REFRESH_S, tick)

    @ui.page("/calibration")
    def calibration() -> None:
        _header(rt)
        cfg = engine.cfg
        ui.label(
            "Calibration only: these move servos directly, outside the scheduler. "
            "Not while a session or talk is running."
        ).classes("bg-orange-200 p-2")

        def refused() -> None:
            ui.notify("desk busy (session or talk running)", type="warning")

        async def act(action: Callable[[], Awaitable[bool]], what: str) -> None:
            try:
                if not await action():
                    refused()
            except Exception as e:
                ui.notify(f"{what} failed: {e!r}", type="negative")

        def jog(name: str, slider: str, angle: float | None) -> None:
            press, rest = sliders[name]
            if angle is None or rest.value is None or press.value is None:
                return
            # moving the rest slider moves to rest; the press slider presses
            target_rest = int(angle) if slider == "rest" else int(rest.value)
            if name == SPREKEN:
                target_rest = view.safe_spreken_rest(
                    target_rest, int(press.value), engine.cfg.actuators[SPREKEN].rest
                )
            if not cal.jog(name, int(angle), target_rest):
                refused()

        async def test_tap(name: str) -> None:
            press, rest = sliders[name]
            if press.value is None or rest.value is None:
                return
            saved = engine.cfg.actuators[name]
            target_rest = int(rest.value)
            if name == SPREKEN:
                target_rest = view.safe_spreken_rest(target_rest, int(press.value), saved.rest)
            tap = partial(
                cal.tap, name, int(press.value), target_rest, saved.press_ms, saved.release_ms
            )
            await act(tap, f"tap {name}")

        async def release_on_close() -> None:
            try:
                await cal.release_all()  # refused (no-op) while a session or talk runs
            except Exception:
                log.exception("release_all on calibration tab close failed")

        ui.context.client.on_disconnect(release_on_close)

        sliders: dict[str, tuple[ui.slider, ui.slider]] = {}
        for name, a in cfg.actuators.items():
            with ui.card().classes("w-full max-w-3xl"):
                with ui.row().classes("w-full items-center"):
                    ui.label(name).classes("text-lg font-bold w-24")
                    ui.button("Test tap", on_click=partial(test_tap, name))
                    if name == SPREKEN:
                        ui.label(
                            f"press is temporary: back to rest {view.SPREKEN_RETURN_S:g} s "
                            "after the slider stops"
                        ).classes("text-sm")
                pairs = []
                for label, value in (("press", a.press), ("rest", a.rest)):
                    with ui.row().classes("w-full items-center"):
                        ui.label(label).classes("w-12")
                        s = ui.slider(min=0, max=180, step=1, value=value).props("label-always")
                        s.classes("grow")
                        s.on_value_change(lambda e, n=name, k=label: jog(n, k, e.value))
                        pairs.append(s)
                sliders[name] = (pairs[0], pairs[1])
        with ui.row().classes("items-center"):
            ui.button(
                "Release all (servos to rest)",
                on_click=partial(act, cal.release_all, "release_all"),
            )
            cal_error = ui.label().classes("text-red-700")
        ui.timer(REFRESH_S, lambda: cal_error.set_text(cal.error or ""))

        ann = cfg.announce
        with ui.card().classes("w-full max-w-3xl"):
            ui.label("Full sequence").classes("text-lg font-bold")
            chime = ui.number("chime seconds", value=ann.chime_seconds, step=0.1, min=0)
            tail = ui.number("tail seconds", value=ann.tail_seconds, step=0.1, min=0)
            ui.label("volume")
            volume = ui.slider(min=0, max=1, step=0.05, value=cfg.audio.volume).props(
                "label-always"
            )
            deselect = ui.checkbox("deselect zones after", value=ann.deselect_zones_after)

            def edit(c: Config) -> None:
                for n, (press, rest) in sliders.items():
                    c.actuators[n].press = int(press.value)
                    c.actuators[n].rest = int(rest.value)
                c.announce.chime_seconds = view.number(chime.value, "chime seconds")
                c.announce.tail_seconds = view.number(tail.value, "tail seconds")
                c.audio.volume = float(volume.value)
                c.announce.deselect_zones_after = bool(deselect.value)

            async def save() -> None:
                error = await view.apply_config(engine, rt.cfg_path, edit, rt.player, rt.cfg_guard)
                _notify_error(error, f"saved to {rt.cfg_path}")

            async def test_sequence() -> None:
                try:
                    await engine.manual_text(engine.cfg.announce.halls, view.TEST_PHRASE)
                except RuntimeError as e:
                    ui.notify(str(e), type="negative")
                    return
                ui.notify(f"queued: {view.TEST_PHRASE}")

            async def test_japanese() -> None:
                parts = spoken_parts(engine.cfg.tts, view.TEST_PHRASE, view.TEST_PHRASE_JA)
                if not parts:
                    ui.notify("nothing to say: both languages are off (Settings)", type="warning")
                    return
                try:
                    await engine.manual_text(
                        engine.cfg.announce.halls, view.TEST_PHRASE, view.TEST_PHRASE_JA
                    )
                except RuntimeError as e:
                    ui.notify(str(e), type="negative")
                    return
                ui.notify(view.queued_notice(parts))

            with ui.row():
                ui.button("Save", on_click=save)
                ui.button("Test full sequence", on_click=test_sequence)
                ui.button("Test Japanese", on_click=test_japanese)
            ui.label(
                "Test full sequence uses the SAVED settings (press Save first) and the "
                "configured halls. It goes through the desk queue: it waits for a running "
                "session and does not play while PAUSED."
            ).classes("text-sm")

    @ui.page("/settings")
    def settings() -> None:
        _header(rt)
        cfg = engine.cfg
        ui.label("Messages").classes("text-xl font-bold")
        ui.label(
            "Placeholders in English: {time} {count} {fields} {halls}. "
            "Japanese phrases are fixed, spoken first; leave empty for none."
        ).classes("text-sm")
        texts = {}

        def edited_tts() -> TtsConfig:
            return dataclasses.replace(
                engine.cfg.tts,
                english=bool(english.value),
                english_voice=str(english_voice.value),
                english_speed=view.number(english_speed.value, "English speed"),
                japanese=bool(japanese.value),
                japanese_speed=view.number(japanese_speed.value, "Japanese speed"),
                pause_seconds=view.number(pause.value, "pause"),
            )

        async def preview(key: str) -> None:
            refusal = view.preview_refusal(engine, rt.clock.now())
            if refusal is not None:
                ui.notify(refusal, type="warning")
                return
            try:
                tts_cfg = edited_tts()
                en = (texts[key].value or "").format_map(SAMPLE_RENDER)
                parts = spoken_parts(tts_cfg, en, texts[ja_key(key)].value or "")
                if not parts:
                    ui.notify("nothing to say: both languages off or empty", type="warning")
                    return
                tts = rt.tts_factory(tts_cfg)  # cheap: the loaded model is shared
                for lang, text in parts:  # synthesise first: that takes a while
                    await tts.synth(text, lang)
                refusal = view.preview_refusal(engine, rt.clock.now())
                if refusal is not None:
                    ui.notify(refusal, type="warning")
                    return
                player = SoundPlayer(None, engine.cfg.audio.volume)  # laptop speakers
                await view.play_preview(tts, player, parts, tts_cfg.pause_seconds)
            except Exception as e:
                ui.notify(f"preview failed: {e!r}", type="negative", multi_line=True)

        for key, template in cfg.messages.items():
            if key.endswith(JA_SUFFIX):
                continue
            with ui.column().classes("w-full max-w-2xl gap-0"):
                with ui.row().classes("w-full items-center"):
                    texts[key] = ui.input(key, value=template).classes("grow")
                    ui.button("Preview", on_click=partial(preview, key))
                jk = ja_key(key)
                texts[jk] = ui.input(jk, value=cfg.messages.get(jk, "")).classes("w-full")
        ui.label("Speech").classes("text-xl font-bold")
        t = cfg.tts
        with ui.row().classes("items-center gap-6"):
            japanese = ui.switch("Speak Japanese", value=t.japanese)
            english = ui.switch("Speak English", value=t.english)
            english_voice = ui.select(
                list(ENGLISH_VOICES), value=t.english_voice, label="English voice"
            )
        with ui.row().classes("items-center gap-6"):
            speed = {"min": MIN_SPEED, "max": MAX_SPEED, "step": 0.05}
            japanese_speed = ui.number("Japanese speed", value=t.japanese_speed, **speed)
            english_speed = ui.number("English speed", value=t.english_speed, **speed)
            pause = ui.number(
                "Pause between Japanese and English (s)",
                value=t.pause_seconds,
                min=0,
                max=MAX_PAUSE_S,
                step=0.1,
            ).classes("w-72")
        ui.label("Halls to announce in").classes("text-xl font-bold")
        halls = _hall_boxes(cfg, cfg.announce.halls)
        poll = ui.number("poll interval (s)", value=cfg.schedule.poll_seconds, min=10, step=10)
        ui.label("Match minutes per round").classes("text-xl font-bold")
        rounds = {}
        with ui.row():
            for round_name, minutes in cfg.schedule.round_minutes.items():
                rounds[round_name] = ui.number(round_name, value=minutes, min=1, step=1)
            default_minutes = ui.number(
                "other rounds", value=cfg.schedule.default_match_minutes, min=1, step=1
            )
        ui.label(f"Schedule source: {cfg.schedule.kind} (edit config.toml to change)")

        def edit(c: Config) -> None:
            for key, box in texts.items():
                c.messages[key] = box.value or ""
            c.tts = edited_tts()
            c.announce.halls = halls()
            c.schedule.poll_seconds = int(view.number(poll.value, "poll interval"))
            c.schedule.round_minutes = {
                name: int(view.number(box.value, name)) for name, box in rounds.items()
            }
            c.schedule.default_match_minutes = int(view.number(default_minutes.value, "other rounds"))

        async def save() -> None:
            error = await view.apply_config(engine, rt.cfg_path, edit, rt.player, rt.cfg_guard)
            _notify_error(error, f"saved to {rt.cfg_path}")

        ui.button("Save", on_click=save)
