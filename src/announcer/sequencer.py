"""One desk session (spec 5.3), with Spreken released under all circumstances."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TypeVar

from announcer.audio.player import Player
from announcer.clock import Clock
from announcer.config import Config
from announcer.controller.base import Controller, ControllerError

log = logging.getLogger(__name__)

SPREKEN = "SPREKEN"
PLAY_MARGIN_S = 5.0  # a clip may take this much longer than its duration, then it counts as hung
T = TypeVar("T")


async def _uninterruptible(aw: Awaitable[T]) -> T:
    """Run aw to completion even if the caller is cancelled (again) meanwhile.

    A cancel that arrives while waiting is re-raised once aw has finished.
    """
    task = asyncio.ensure_future(aw)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True  # before the done() check: the cancel may land with completion
            if task.done():
                break
    if cancelled:
        raise asyncio.CancelledError
    return task.result()


async def _do_release(ctrl: Controller) -> bool:
    try:
        await ctrl.release(SPREKEN)
        return True
    except Exception:
        log.exception("releasing SPREKEN failed; falling back to release_all")
    try:
        await ctrl.release_all()
    except Exception as e:
        log.critical("release_all failed too: SPREKEN may still be held")
        raise ControllerError("could not release SPREKEN") from e
    return False


async def release_spreken(ctrl: Controller) -> bool:
    """Release SPREKEN; fall back to release_all. True if SPREKEN itself was released.

    Raises ControllerError if both fail. Cannot be skipped by a pending cancel.
    """
    return await _uninterruptible(_do_release(ctrl))


async def run_session(
    ctrl: Controller,
    player: Player,
    clock: Clock,
    cfg: Config,
    halls: Sequence[str],
    audio: Sequence[Path],
) -> None:
    selected: list[str] = []  # halls whose step-1 tap completed
    interruptions = 0
    held = False  # step 2 completed
    try:
        for hall in halls:  # 1. zones on (toggle)
            try:
                await ctrl.tap(hall)
            except Exception:
                log.warning("tap of %s failed: its zone state is unknown, not deselecting it", hall)
                raise
            selected.append(hall)
        interruptions = ctrl.interruptions
        await ctrl.hold(SPREKEN)  # 2.
        held = True
        await clock.sleep(cfg.announce.chime_seconds)  # 3.
        for path in audio:  # 4.
            await _play_bounded(player, path)
        await clock.sleep(cfg.announce.tail_seconds)  # 5.
    except asyncio.CancelledError:
        await _release_after_error(ctrl)
        raise  # 6. skipped when cancelled
    except Exception:
        # never reached the hold: nothing was announced, so the zones go back whatever the
        # option says (they are toggles: left on, the next session would turn them off)
        if await _release_after_error(ctrl) and (cfg.announce.deselect_zones_after or not held):
            try:
                await _deselect(ctrl, selected, best_effort=True)
            except asyncio.CancelledError:
                pass  # cancelled while deselecting; the original error still wins
        raise  # the original error
    except BaseException:
        await _release_after_error(ctrl)
        raise
    await release_spreken(ctrl)
    # checked after the release: the serial controller reads EVT lines during exchanges
    interrupted = ctrl.interruptions != interruptions
    if cfg.announce.deselect_zones_after:  # 6. also after the release_all fallback
        await _deselect(ctrl, selected, best_effort=interrupted)
    if interrupted:
        raise ControllerError(f"SPREKEN hold was interrupted (last event: {ctrl.last_event})")


async def _play_bounded(player: Player, path: Path) -> None:
    """Play path; a player that does not finish in time is cancelled and raises TimeoutError."""
    timeout = player.duration(path) + PLAY_MARGIN_S
    try:
        await asyncio.wait_for(player.play(path), timeout)
    except TimeoutError as e:
        raise TimeoutError(f"audio {path.name} did not finish within {timeout:g} s") from e


async def _release_after_error(ctrl: Controller) -> bool:
    """Release while another error propagates; True if it succeeded (incl. fallback)."""
    try:
        await release_spreken(ctrl)
        return True
    except Exception:
        log.exception("release after a failed session also failed")
    except asyncio.CancelledError:
        pass  # cancelled again; the release itself still ran to completion
    return False


async def _deselect(ctrl: Controller, halls: Sequence[str], best_effort: bool = False) -> None:
    """Toggle the zones off again, so the next session's step 1 turns them on."""
    for hall in halls:
        try:
            await ctrl.tap(hall)
        except Exception:
            if not best_effort:
                raise
            log.exception("deselecting %s failed", hall)


@asynccontextmanager
async def talk_session(
    ctrl: Controller, clock: Clock, cfg: Config, halls: Sequence[str]
) -> AsyncIterator[None]:
    """Zones on and SPREKEN held while inside; released on exit or after max_hold_s.

    With deselect_zones_after, the selected zones are toggled off again after a
    successful release on exit (also when the watchdog released), not on a cancel.
    """
    released = False
    lock = asyncio.Lock()

    async def release_once() -> None:
        nonlocal released
        async with lock:
            if not released:
                await release_spreken(ctrl)
                released = True

    async def watchdog() -> None:
        await clock.sleep(cfg.controller.max_hold_s)
        log.warning("SPREKEN held for %s s: max hold reached, releasing", cfg.controller.max_hold_s)
        await _uninterruptible(release_once())  # exit's cancel must not cut this short

    wd: asyncio.Task[None] | None = None

    async def finish() -> None:
        if wd is not None:
            wd.cancel()
            await asyncio.gather(wd, return_exceptions=True)
        await release_once()  # no-op if the watchdog already released

    selected: list[str] = []  # halls whose tap completed
    held = False  # the hold completed
    outcome = "ok"  # "ok" | "error" | "abort" (cancelled or other BaseException)
    try:
        for hall in halls:
            try:
                await ctrl.tap(hall)
            except Exception:
                log.warning("tap of %s failed: its zone state is unknown, not deselecting it", hall)
                raise
            selected.append(hall)
        wd = asyncio.create_task(watchdog(), name="talk-watchdog")
        await ctrl.hold(SPREKEN)
        held = True
        yield
    except Exception:
        outcome = "error"
        raise
    except BaseException:
        outcome = "abort"
        raise
    finally:
        await _uninterruptible(finish())  # raises if the release failed: no deselect then
        # same rules as run_session: step 6, and the zones go back if the hold was never reached
        if outcome == "ok" and cfg.announce.deselect_zones_after:
            await _deselect(ctrl, selected)
        elif outcome == "error" and (cfg.announce.deselect_zones_after or not held):
            try:
                await _deselect(ctrl, selected, best_effort=True)
            except asyncio.CancelledError:
                pass  # cancelled while deselecting; the original error still wins
