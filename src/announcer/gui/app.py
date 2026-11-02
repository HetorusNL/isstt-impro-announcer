"""NiceGUI pages, built from engine state. Logic worth testing lives in gui.view."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING

from nicegui import app, ui

from announcer.audio.player import SoundPlayer
from announcer.config import SAMPLE_RENDER, Config
from announcer.engine import Engine, Key
from announcer.gui import view
from announcer.sequencer import SPREKEN

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


def _pages(rt: Runtime, engine: Engine, cal: view.Calibrator) -> None:
    @ui.page("/")
    def dashboard() -> None:
        _header(rt)
        clock = ui.label().classes("text-7xl font-mono")
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

        @ui.refreshable
        def lists() -> None:
            with ui.row().classes("w-full items-start gap-12"):
                with ui.column():
                    ui.label("Upcoming").classes("text-xl font-bold")
                    for s in engine.upcoming[:UPCOMING_SHOWN]:
                        ui.label(
                            f"{s.start_at:%a %H:%M:%S}  {view.session_kinds(s)}"
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
            state.text = "PAUSED" if engine.paused else "RUNNING"
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
            banner.text = f"Schedule source error: {engine.source_error}"
            banner.visible = engine.source_error is not None
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
                nxt.text = f"Next: {s.start_at:%a %H:%M:%S} {view.session_kinds(s)}"
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
        cfg = engine.cfg
        ui.label("Halls").classes("text-xl font-bold")
        halls = _hall_boxes(cfg, cfg.announce.halls)
        text = ui.textarea("Text to speak").classes("w-full max-w-2xl")

        async def speak() -> None:
            if not halls() or not (text.value or "").strip():
                ui.notify("select halls and type a text", type="warning")
                return
            try:
                await engine.manual_text(halls(), text.value.strip())
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
            rest = sliders[name][1]
            if angle is None or rest.value is None:
                return
            # moving the rest slider moves to rest; the press slider presses
            target_rest = int(angle) if slider == "rest" else int(rest.value)
            if not cal.jog(name, int(angle), target_rest):
                refused()

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
                    ui.button(
                        "Test tap",
                        on_click=partial(act, partial(cal.tap, name), f"tap {name}"),
                    )
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
                c.announce.chime_seconds = float(chime.value)
                c.announce.tail_seconds = float(tail.value)
                c.audio.volume = float(volume.value)
                c.announce.deselect_zones_after = bool(deselect.value)

            async def save() -> None:
                error = await view.apply_config(engine, rt.cfg_path, edit, rt.player)
                _notify_error(error, f"saved to {rt.cfg_path}")

            async def test_sequence() -> None:
                try:
                    await engine.manual_text(engine.cfg.announce.halls, view.TEST_PHRASE)
                except RuntimeError as e:
                    ui.notify(str(e), type="negative")
                    return
                ui.notify(f"queued: {view.TEST_PHRASE}")

            with ui.row():
                ui.button("Save", on_click=save)
                ui.button("Test full sequence", on_click=test_sequence)
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
        ui.label("Placeholders: {time} {count} {fields} {halls}").classes("text-sm")
        texts = {}

        async def preview(key: str) -> None:
            try:
                text = (texts[key].value or "").format_map(SAMPLE_RENDER)
                tts = rt.tts_factory(engine.cfg.tts)
                path = await tts.synth(text)
                await SoundPlayer(None, engine.cfg.audio.volume).play(path)  # laptop speakers
            except Exception as e:
                ui.notify(f"preview failed: {e!r}", type="negative", multi_line=True)

        for key, template in cfg.messages.items():
            with ui.row().classes("w-full items-center"):
                texts[key] = ui.input(key, value=template).classes("grow max-w-2xl")
                ui.button("Preview", on_click=partial(preview, key))
        ui.label("Halls to announce in").classes("text-xl font-bold")
        halls = _hall_boxes(cfg, cfg.announce.halls)
        poll = ui.number("poll interval (s)", value=cfg.schedule.poll_seconds, min=10, step=10)
        ui.label(f"Schedule source: {cfg.schedule.kind} (edit config.toml to change)")

        def edit(c: Config) -> None:
            for key, box in texts.items():
                c.messages[key] = box.value or ""
            c.announce.halls = halls()
            c.schedule.poll_seconds = int(poll.value)

        async def save() -> None:
            error = await view.apply_config(engine, rt.cfg_path, edit, rt.player)
            _notify_error(error, f"saved to {rt.cfg_path}")

        ui.button("Save", on_click=save)
