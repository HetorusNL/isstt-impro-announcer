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
            if task.done():
                break
            cancelled = True
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
    try:
        for hall in halls:  # 1. zones on (toggle)
            await ctrl.tap(hall)
        await ctrl.hold(SPREKEN)  # 2.
        await clock.sleep(cfg.announce.chime_seconds)  # 3.
        for path in audio:  # 4.
            await player.play(path)
        await clock.sleep(cfg.announce.tail_seconds)  # 5.
    except BaseException:
        try:
            await release_spreken(ctrl)
        except Exception:
            log.exception("release after a failed session also failed")
        except asyncio.CancelledError:
            pass  # cancelled again; the release itself still ran to completion
        raise  # the original error
    released = await release_spreken(ctrl)
    if released and cfg.announce.deselect_zones_after:  # 6.
        for hall in halls:
            await ctrl.tap(hall)


@asynccontextmanager
async def talk_session(
    ctrl: Controller, clock: Clock, cfg: Config, halls: Sequence[str]
) -> AsyncIterator[None]:
    """Zones on and SPREKEN held while inside; released on exit or after max_hold_s."""
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

    try:
        for hall in halls:
            await ctrl.tap(hall)
        wd = asyncio.create_task(watchdog(), name="talk-watchdog")
        await ctrl.hold(SPREKEN)
        yield
    finally:
        await _uninterruptible(finish())
