"""Servo controller on the STM32 firmware over USB serial (protocol: firmware/PROTOCOL.md).

Every command waits for its OK/ERR reply. A single asyncio lock serialises command/reply
pairs; each exchange (write + read until the reply) runs in one worker thread via
asyncio.to_thread. The port is opened with read and write timeouts, so every exchange ends
within its reply timeout plus one port timeout, and once started it runs to the end even if
the caller is cancelled: replies never get out of step. EVT lines are read during exchanges;
the keep-alive PING makes sure that happens at least every keepalive_ms.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from typing import Any

import serial

from announcer.clock import Clock
from announcer.config import Actuator
from announcer.controller.base import ControllerError

log = logging.getLogger(__name__)

BAUDRATE = 115200
IO_TIMEOUT_S = 0.25  # pyserial read/write timeout: no blocking call can hang a thread
REPLY_TIMEOUT_S = 1.0
REST_TIMEOUT_S = 5.0  # a flash erase stalls the MCU for a few seconds
RECONNECT_S = 2.0
MAX_DRAIN_LINES = 100
# firmware limits (PROTOCOL.md); config.validate enforces them as well
MAX_WATCHDOG_MS = 10_000
MAX_MAXHOLD_MS = 120_000


class SerialController:
    def __init__(
        self,
        port: str,
        actuators: dict[str, Actuator],
        keepalive_ms: int,
        watchdog_ms: int,
        max_hold_s: int,
        clock: Clock,
        *,
        port_factory: Callable[..., Any] = serial.Serial,
        reply_timeout_s: float = REPLY_TIMEOUT_S,
        rest_timeout_s: float = REST_TIMEOUT_S,
        reconnect_s: float = RECONNECT_S,
        io_timeout_s: float = IO_TIMEOUT_S,
    ) -> None:
        self._port_name = port
        self.actuators: dict[str, Actuator] = dict(actuators)
        self._keepalive_s = keepalive_ms / 1000
        self._watchdog_ms = watchdog_ms
        self._max_hold_ms = max_hold_s * 1000
        self._clock = clock
        self._factory = port_factory
        self._reply_timeout_s = reply_timeout_s
        self._rest_timeout_s = rest_timeout_s
        self._reconnect_s = reconnect_s
        self._io_timeout_s = io_timeout_s
        self.connected = False
        self.last_event: str | None = None
        self._port: Any = None
        self._buf = b""
        self._lock = asyncio.Lock()  # one command/reply pair at a time
        self._setup_lock = asyncio.Lock()  # one connect sequence at a time
        self._reconfigure = False  # set by EVT BOOT: the board reset
        self._closing = False
        self._keepalive: asyncio.Task[None] | None = None

    # Controller protocol

    async def connect(self) -> None:
        """Open the port and configure the board; raises if it is not there.

        Either way the keep-alive task runs afterwards and reconnects while disconnected.
        """
        if not 1 <= self._watchdog_ms <= MAX_WATCHDOG_MS:
            raise ControllerError(f"watchdog_ms {self._watchdog_ms} not in 1..{MAX_WATCHDOG_MS}")
        if not 1 <= self._max_hold_ms <= MAX_MAXHOLD_MS:
            raise ControllerError(f"max hold {self._max_hold_ms} ms not in 1..{MAX_MAXHOLD_MS}")
        self._closing = False
        if self._keepalive is None or self._keepalive.done():
            self._keepalive = asyncio.create_task(self._keepalive_loop(), name="keepalive")
        await self._setup()

    async def close(self) -> None:
        """Stop the keep-alive, put every servo at rest (best effort), close the port."""
        self._closing = True
        if self._keepalive is not None:
            self._keepalive.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._keepalive
            self._keepalive = None
        if self.connected:
            try:
                await self._command("RELEASE ALL")
            except ControllerError:
                log.exception("RELEASE ALL on close failed")
        async with self._lock:
            await self._drop()

    async def configure(self, actuators: dict[str, Actuator]) -> None:
        self.actuators = dict(actuators)
        if self.connected:
            failed = await self._send_rests()
            if failed:
                raise ControllerError("REST failed: " + "; ".join(failed))

    async def tap(self, button: str) -> None:
        ch, act = self._lookup(button)
        await self._command(f"ANGLE {ch} {act.press}")
        try:
            await self._clock.sleep(act.press_ms / 1000)
        except BaseException:  # cancelled mid-press: do not leave the button pressed
            try:
                await self._command(f"RELEASE {ch}")
            except Exception:
                log.exception("releasing %s after a cancelled tap failed", button)
            raise
        await self._command(f"RELEASE {ch}")
        await self._clock.sleep(act.release_ms / 1000)

    async def hold(self, button: str) -> None:
        ch, act = self._lookup(button)
        await self._command(f"ANGLE {ch} {act.press}")
        await self._clock.sleep(act.press_ms / 1000)

    async def release(self, button: str) -> None:
        ch, _ = self._lookup(button)
        await self._command(f"RELEASE {ch}")

    async def release_all(self) -> None:
        await self._command("RELEASE ALL")

    async def set_angle(self, button: str, angle: int) -> None:
        ch, _ = self._lookup(button)
        await self._command(f"ANGLE {ch} {int(angle)}")

    # connection

    def _lookup(self, button: str) -> tuple[int, Actuator]:
        act = self.actuators.get(button)
        if act is None:
            raise ControllerError(f"no actuator configured for {button!r}")
        return act.channel, act

    async def _setup(self) -> None:
        """Open the port and run the connect sequence (PING, WATCHDOG, MAXHOLD, RESTs)."""
        async with self._setup_lock:
            if self.connected:  # a concurrent connect sequence just finished
                return
            async with self._lock:
                await self._drop()
                try:
                    self._port = await asyncio.to_thread(self._open)
                except (serial.SerialException, OSError) as e:
                    raise ControllerError(f"cannot open {self._port_name}: {e}") from e
            try:
                await self._command("PING", require_connected=False)
                await self._configure_board(require_connected=False)
            except BaseException:
                async with self._lock:
                    await self._drop()
                raise
            self.connected = True
            log.info("controller connected on %s", self._port_name)

    def _open(self) -> Any:
        """Worker thread: open the port and discard boot output."""
        port = self._factory(
            self._port_name,
            baudrate=BAUDRATE,
            timeout=self._io_timeout_s,
            write_timeout=self._io_timeout_s,
        )
        try:
            if self._closing:  # close() ran while this thread was opening
                raise ControllerError("controller closed")
            port.reset_input_buffer()
            for _ in range(MAX_DRAIN_LINES):  # until one read timeout passes in silence
                if not port.readline():
                    break
        except BaseException:
            port.close()
            raise
        self._buf = b""
        return port

    async def _configure_board(self, *, require_connected: bool = True) -> None:
        self._reconfigure = False  # an EVT BOOT from here on means: do it again
        await self._command(f"WATCHDOG {self._watchdog_ms}", require_connected=require_connected)
        await self._command(f"MAXHOLD {self._max_hold_ms}", require_connected=require_connected)
        # a channel whose REST failed stays safe: the firmware refuses ANGLE without a rest
        await self._send_rests(require_connected=require_connected)

    async def _send_rests(self, *, require_connected: bool = True) -> list[str]:
        """REST for every actuator, one at a time; returns the ERR replies.

        Raises only if the link is gone. ERR flash still sets the rest (RAM, this session).
        """
        failed: list[str] = []
        for name, act in list(self.actuators.items()):
            try:
                await self._command(
                    f"REST {act.channel} {act.rest}",
                    self._rest_timeout_s,
                    require_connected=require_connected,
                )
            except ControllerError as e:
                if self._port is None:  # timeout or serial error: disconnected
                    raise
                log.error("REST for %s failed: %s", name, e)
                failed.append(f"{name}: {e}")
        return failed

    async def _drop(self) -> None:
        """Mark disconnected and close the port. Call with the lock held."""
        was = self.connected
        self.connected = False
        port, self._port = self._port, None
        if port is not None:
            try:
                await asyncio.to_thread(port.close)
            except Exception:
                log.exception("closing %s failed", self._port_name)
        if was:
            log.error("controller disconnected from %s", self._port_name)

    async def _keepalive_loop(self) -> None:
        while not self._closing:
            if not self.connected:
                await asyncio.sleep(self._reconnect_s)
                try:
                    await self._setup()
                except ControllerError as e:
                    log.debug("reconnect failed: %s", e)
                continue
            # real time, not the clock: the firmware watchdog runs in real time
            await asyncio.sleep(self._keepalive_s)
            if not self.connected:
                continue
            try:
                if self._reconfigure:
                    log.warning("board reset: sending WATCHDOG, MAXHOLD and rests again")
                    await self._configure_board()
                else:
                    await self._command("PING")
            except ControllerError as e:
                log.warning("keep-alive: %s", e)

    # command/reply

    async def _command(
        self, cmd: str, timeout: float | None = None, *, require_connected: bool = True
    ) -> str:
        """Send one command and return its OK reply; ERR or a timeout raise ControllerError."""
        await self._lock.acquire()  # cancellable: nothing has been sent yet
        try:
            if self._port is None or (require_connected and not self.connected):
                raise ControllerError(f"{cmd}: not connected")
            task = asyncio.create_task(self._exchange(cmd, timeout or self._reply_timeout_s))
        except BaseException:
            self._lock.release()
            raise
        task.add_done_callback(self._exchange_done)
        return await asyncio.shield(task)  # a cancelled caller leaves the exchange to finish

    def _exchange_done(self, task: asyncio.Task[str]) -> None:
        self._lock.release()
        if not task.cancelled():
            task.exception()  # retrieved here too, in case the caller was cancelled

    async def _exchange(self, cmd: str, timeout: float) -> str:
        port = self._port
        try:
            reply = await asyncio.to_thread(self._exchange_blocking, port, cmd, timeout)
        except (serial.SerialException, OSError) as e:
            await self._drop()
            raise ControllerError(f"{cmd}: serial error: {e}") from e
        if reply is None:
            await self._drop()
            raise ControllerError(f"{cmd}: timeout after {timeout:g} s, no reply")
        if reply.startswith("ERR"):
            raise ControllerError(f"{cmd}: {reply[3:].strip() or 'ERR'}")
        return reply

    def _exchange_blocking(self, port: Any, cmd: str, timeout: float) -> str | None:
        """Worker thread: write cmd, read lines until OK/ERR (returned) or the deadline (None)."""
        port.write(f"{cmd}\n".encode())
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = port.readline()
            if not chunk:
                continue
            self._buf += chunk
            if not self._buf.endswith(b"\n"):  # a read timeout split the line
                continue
            line = self._buf.decode(errors="replace").strip()
            self._buf = b""
            if not line:
                continue
            if line.startswith("EVT"):
                self._event(line)
            elif line.startswith(("OK", "ERR")):
                return line
            else:
                log.warning("unexpected line from board: %r", line)
        return None

    def _event(self, line: str) -> None:
        self.last_event = line
        if line.startswith("EVT BOOT"):
            self._reconfigure = True  # handled by the keep-alive task, not inside a reply wait
        log.warning("board: %s", line)
