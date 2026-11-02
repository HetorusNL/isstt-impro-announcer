import asyncio
import threading
import time
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from announcer.clock import SimClock
from announcer.config import Actuator
from announcer.controller.base import ControllerError
from announcer.controller.serial_ctrl import SerialController

TZ = ZoneInfo("Europe/Amsterdam")
ACTUATORS = {
    "SC1": Actuator(channel=0, rest=90, press=60),
    "SPREKEN": Actuator(channel=3, rest=80, press=50),
}


class FakePort:
    """In-memory stand-in for serial.Serial that answers like the firmware."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.written: list[str] = []
        self.out: deque[tuple[float, bytes]] = deque()  # (ready_at monotonic, line)
        self.is_open = False
        self.opens: list[dict] = []
        self.silent = False  # answer nothing (board hung / unplugged)
        self.fail_open = 0  # number of opens that raise
        self.errors: dict[str, str] = {}  # command prefix -> ERR reason
        self.delays: dict[str, float] = {}  # command prefix -> reply delay (s)
        self.events_before_reply: list[str] = []  # emitted before the next reply
        self.noise_before_reply = b""  # raw bytes (no newline) emitted before the next reply
        self.open_delay = 0.0  # seconds an open takes
        self.read_sizes: set[int] = set()
        self.rests: dict[int, int] = {}

    # factory
    def open(self, port: str, **kwargs) -> "FakePort":
        self.opens.append({"port": port, **kwargs})
        time.sleep(self.open_delay)
        if self.fail_open:
            self.fail_open -= 1
            raise OSError("no such device")
        self.is_open = True
        return self

    # serial.Serial API
    def write(self, data: bytes) -> int:
        assert self.is_open
        line = data.decode().strip()
        with self.lock:
            self.written.append(line)
            if not self.silent:
                self._answer(line)
        return len(data)

    def readline(self, size: int) -> bytes:
        assert self.is_open
        self.read_sizes.add(size)
        with self.lock:
            if self.out and self.out[0][0] <= time.monotonic():
                ready_at, data = self.out.popleft()
                if len(data) > size:  # like pyserial: at most size bytes per call
                    self.out.appendleft((ready_at, data[size:]))
                    data = data[:size]
                return data
        time.sleep(0.002)  # a read timeout with nothing received
        return b""

    def reset_input_buffer(self) -> None:
        with self.lock:
            self.out.clear()

    def close(self) -> None:
        self.is_open = False

    # firmware behaviour
    def emit(self, line: str, delay: float = 0.0) -> None:
        self.out.append((time.monotonic() + delay, (line + "\r\n").encode()))

    def push_event(self, line: str) -> None:
        with self.lock:
            self.emit(line)
            if line.startswith("EVT BOOT"):
                self.rests.clear()  # F746 after a power cycle: rests gone

    def _answer(self, line: str) -> None:
        for ev in self.events_before_reply:
            self.emit(ev)
        self.events_before_reply = []
        if self.noise_before_reply:
            self.out.append((time.monotonic(), self.noise_before_reply))
            self.noise_before_reply = b""
        delay = next((d for p, d in self.delays.items() if line.startswith(p)), 0.0)
        err = next((e for p, e in self.errors.items() if line.startswith(p)), None)
        tok = line.split()
        if err is not None:
            if tok[0] == "REST" and err == "flash":  # kept in RAM for this session
                self.rests[int(tok[1])] = int(tok[2])
            reply = f"ERR {err}"
        elif tok[0] == "PING":
            reply = "OK PONG"
        elif tok[0] == "REST":
            self.rests[int(tok[1])] = int(tok[2])
            reply = "OK"
        elif tok[0] in ("ANGLE", "RELEASE") and tok[1] != "ALL" and int(tok[1]) not in self.rests:
            reply = "ERR no rest"
        else:
            reply = "OK"
        self.emit(reply, delay)

    def commands(self, prefix: str = "") -> list[str]:
        with self.lock:
            return [c for c in self.written if c.startswith(prefix)]


@pytest.fixture
def port() -> FakePort:
    return FakePort()


def make(port: FakePort, speed: float = 1000, **kw) -> SerialController:
    clock = SimClock(datetime(2026, 12, 18, 9, 0, tzinfo=TZ), speed=speed)
    opts: dict = {"reply_timeout_s": 0.1, "rest_timeout_s": 0.5, "reconnect_s": 0.05}
    opts.update(kw)
    keepalive_ms = opts.pop("keepalive_ms", 1000)
    return SerialController(
        "/dev/fake", ACTUATORS, keepalive_ms, 2000, 60, clock, port_factory=port.open, **opts
    )


async def wait_for(cond, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not cond():
        assert time.monotonic() < deadline, "condition not reached"
        await asyncio.sleep(0.005)


async def test_connect_sends_rest_for_each_actuator(port: FakePort) -> None:
    ctrl = make(port)
    await ctrl.connect()
    try:
        assert ctrl.connected
        assert port.commands() == [
            "PING",
            "WATCHDOG 2000",
            "MAXHOLD 60000",
            "REST 0 90",
            "REST 3 80",
        ]
        opened = port.opens[0]
        assert opened["port"] == "/dev/fake" and opened["baudrate"] == 115200
        assert 0 < opened["timeout"] <= 0.5 and 0 < opened["write_timeout"] <= 0.5
    finally:
        await ctrl.close()


async def test_tap_sends_angle_then_release(port: FakePort) -> None:
    ctrl = make(port)
    await ctrl.connect()
    try:
        await ctrl.tap("SC1")
        await ctrl.hold("SPREKEN")
        await ctrl.release("SPREKEN")
        await ctrl.set_angle("SC1", 70)
        await ctrl.release_all()
        assert port.commands()[5:] == [
            "ANGLE 0 60",
            "RELEASE 0",
            "ANGLE 3 50",
            "RELEASE 3",
            "ANGLE 0 70",
            "RELEASE ALL",
        ]
    finally:
        await ctrl.close()


async def test_unknown_button_raises(port: FakePort) -> None:
    ctrl = make(port)
    await ctrl.connect()
    try:
        with pytest.raises(ControllerError, match="SC9"):
            await ctrl.tap("SC9")
        with pytest.raises(ControllerError):
            await ctrl.release("ONTRUIMINGSALARM")
        assert ctrl.connected
    finally:
        await ctrl.close()


async def test_timeout_marks_disconnected(port: FakePort) -> None:
    ctrl = make(port, reconnect_s=60)
    await ctrl.connect()
    try:
        port.silent = True
        t0 = time.monotonic()
        with pytest.raises(ControllerError, match="timeout"):
            await ctrl.tap("SC1")
        assert time.monotonic() - t0 < 0.5
        assert not ctrl.connected
        assert not port.is_open
        with pytest.raises(ControllerError, match="not connected"):
            await ctrl.release_all()  # fails fast while disconnected
    finally:
        await ctrl.close()


async def test_keepalive_pings(port: FakePort) -> None:
    ctrl = make(port, keepalive_ms=20)
    await ctrl.connect()
    try:
        await wait_for(lambda: len(port.commands("PING")) >= 4)
        assert ctrl.connected
    finally:
        await ctrl.close()


async def test_first_ping_does_not_wait_for_reconnect_interval(port: FakePort) -> None:
    ctrl = make(port, keepalive_ms=20, reconnect_s=60)
    await ctrl.connect()
    try:
        await wait_for(lambda: port.commands("PING")[1:], timeout=0.5)
    finally:
        await ctrl.close()


async def test_err_reply_raises(port: FakePort) -> None:
    ctrl = make(port)
    await ctrl.connect()
    try:
        port.errors["ANGLE"] = "degrees"
        with pytest.raises(ControllerError, match="degrees"):
            await ctrl.set_angle("SC1", 200)
        port.errors.clear()
        port.rests.clear()  # e.g. a board without stored rests
        with pytest.raises(ControllerError, match="no rest"):
            await ctrl.hold("SPREKEN")
        assert ctrl.connected  # an ERR is an answer: the link is fine
    finally:
        await ctrl.close()


async def test_evt_before_ok_is_not_a_reply(port: FakePort) -> None:
    ctrl = make(port)
    await ctrl.connect()
    try:
        port.events_before_reply = ["EVT MAXHOLD 3"]
        port.errors["RELEASE 3"] = "no rest"
        with pytest.raises(ControllerError, match="no rest"):  # the ERR, not the EVT, answers
            await ctrl.release("SPREKEN")
        assert ctrl.last_event == "EVT MAXHOLD 3"
        port.errors.clear()
        port.events_before_reply = ["EVT WATCHDOG"]
        await ctrl.release("SPREKEN")
        assert ctrl.last_event == "EVT WATCHDOG"
        await ctrl.tap("SC1")  # replies stay in step
        assert port.commands()[-2:] == ["ANGLE 0 60", "RELEASE 0"]
    finally:
        await ctrl.close()


async def test_evt_boot_triggers_reconfigure(port: FakePort) -> None:
    ctrl = make(port, keepalive_ms=20)
    await ctrl.connect()
    try:
        port.push_event("EVT BOOT IWDG")
        await wait_for(lambda: len(port.commands("REST")) == 4)
        assert ctrl.last_event == "EVT BOOT IWDG"
        assert port.commands("WATCHDOG") == ["WATCHDOG 2000"] * 2
        assert port.commands("MAXHOLD") == ["MAXHOLD 60000"] * 2
        assert port.rests == {0: 90, 3: 80}
        assert ctrl.connected
        await ctrl.hold("SPREKEN")  # works again after the reconfigure
    finally:
        await ctrl.close()


async def test_reconnect_after_timeout(port: FakePort) -> None:
    ctrl = make(port, keepalive_ms=20)
    await ctrl.connect()
    try:
        port.fail_open = 1  # the first reopen fails (USB still gone)
        port.silent = True
        await wait_for(lambda: not ctrl.connected)
        await wait_for(lambda: port.fail_open == 0)
        port.silent = False
        await wait_for(lambda: ctrl.connected)
        assert port.commands("REST")[-2:] == ["REST 0 90", "REST 3 80"]
        await ctrl.tap("SC1")
    finally:
        await ctrl.close()


async def test_first_connect_failure_reconnects_later(port: FakePort) -> None:
    port.fail_open = 1
    ctrl = make(port, keepalive_ms=20)
    with pytest.raises(ControllerError, match="no such device"):
        await ctrl.connect()
    try:
        assert not ctrl.connected
        await wait_for(lambda: ctrl.connected)
        assert port.commands()[:2] == ["PING", "WATCHDOG 2000"]
    finally:
        await ctrl.close()


async def test_rest_uses_long_timeout(port: FakePort) -> None:
    port.delays["REST"] = 0.25  # a flash erase: longer than the 0.1 s command timeout
    ctrl = make(port)
    await ctrl.connect()
    try:
        assert ctrl.connected
        port.delays = {"ANGLE": 0.25}  # any other command gets the short timeout
        with pytest.raises(ControllerError, match="timeout"):
            await ctrl.set_angle("SC1", 70)
        assert not ctrl.connected
    finally:
        await ctrl.close()


async def test_configure_sends_rests_when_connected(port: FakePort) -> None:
    ctrl = make(port)
    await ctrl.configure({"SC1": Actuator(channel=0, rest=95, press=60)})
    assert port.commands() == []  # not connected: only stored
    await ctrl.connect()
    try:
        assert port.commands("REST") == ["REST 0 95"]
        await ctrl.configure({"SC2": Actuator(channel=1, rest=85, press=60)})
        assert port.commands("REST") == ["REST 0 95", "REST 1 85"]
        with pytest.raises(ControllerError):
            await ctrl.tap("SC1")  # no longer configured
    finally:
        await ctrl.close()


async def test_cancelled_tap_still_releases(port: FakePort) -> None:
    ctrl = make(port, speed=1)  # press_ms 250 in real time: room to cancel mid-press
    await ctrl.connect()
    try:
        task = asyncio.create_task(ctrl.tap("SC1"))
        await wait_for(lambda: port.commands("ANGLE"))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert port.commands()[-2:] == ["ANGLE 0 60", "RELEASE 0"]
        await ctrl.set_angle("SPREKEN", 55)  # replies still in step after the cancel
        assert port.commands()[-1] == "ANGLE 3 55"
    finally:
        await ctrl.close()


async def test_close_releases_all_and_closes_port(port: FakePort) -> None:
    ctrl = make(port, keepalive_ms=20)
    await ctrl.connect()
    await ctrl.close()
    assert port.commands()[-1] == "RELEASE ALL"
    assert not port.is_open and not ctrl.connected
    n = len(port.commands())
    await asyncio.sleep(0.08)
    assert len(port.commands()) == n  # keep-alive stopped


async def test_close_is_bounded_when_board_is_silent(port: FakePort) -> None:
    ctrl = make(port)
    await ctrl.connect()
    port.silent = True
    t0 = time.monotonic()
    await ctrl.close()  # best effort: does not raise
    assert time.monotonic() - t0 < 0.5
    assert not port.is_open


@pytest.mark.parametrize("action", ["tap", "hold"])
async def test_cancel_during_press_exchange_releases(port: FakePort, action: str) -> None:
    ctrl = make(port)
    await ctrl.connect()
    try:
        port.delays["ANGLE"] = 0.05  # cancel lands while the ANGLE waits for its reply
        task = asyncio.create_task(getattr(ctrl, action)("SPREKEN"))
        await wait_for(lambda: port.commands("ANGLE"))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert port.commands()[-2:] == ["ANGLE 3 50", "RELEASE 3"]
    finally:
        await ctrl.close()


async def test_cancelled_command_does_not_take_next_reply(port: FakePort) -> None:
    ctrl = make(port)
    await ctrl.connect()
    try:
        port.delays["ANGLE"] = 0.05
        task = asyncio.create_task(ctrl.set_angle("SC1", 70))
        await wait_for(lambda: port.commands("ANGLE"))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        port.errors["RELEASE"] = "no rest"
        # the late OK belongs to the cancelled ANGLE; RELEASE must get its own ERR
        with pytest.raises(ControllerError, match="no rest"):
            await ctrl.release("SC1")
        assert ctrl.connected
    finally:
        await ctrl.close()


async def test_rest_err_flash_is_tolerated_on_connect(port: FakePort) -> None:
    port.errors["REST 0"] = "flash"
    ctrl = make(port)
    await ctrl.connect()
    try:
        assert ctrl.connected
        assert port.commands("REST") == ["REST 0 90", "REST 3 80"]
        await ctrl.tap("SC1")  # the rest is kept in RAM for this session
    finally:
        await ctrl.close()


async def test_rest_other_err_fails_connect(port: FakePort) -> None:
    port.errors["REST 0"] = "channel"
    ctrl = make(port, reconnect_s=60)
    try:
        with pytest.raises(ControllerError, match="channel"):
            await ctrl.connect()
        assert not ctrl.connected and not port.is_open
    finally:
        await ctrl.close()


async def test_rest_other_err_on_reconfigure_disconnects(port: FakePort) -> None:
    ctrl = make(port, keepalive_ms=20, reconnect_s=60)
    await ctrl.connect()
    try:
        port.errors["REST 3"] = "channel"
        port.push_event("EVT BOOT")
        # _drop marks disconnected first, then closes the port in a worker thread
        await wait_for(lambda: not ctrl.connected and not port.is_open)
    finally:
        await ctrl.close()


async def test_cancel_during_open_closes_port(port: FakePort) -> None:
    port.open_delay = 0.05
    ctrl = make(port, reconnect_s=60)
    task = asyncio.create_task(ctrl.connect())
    await wait_for(lambda: port.opens)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not port.is_open  # the thread's port was awaited and closed
    assert ctrl._port is None
    await ctrl.close()


async def test_reads_are_bounded(port: FakePort) -> None:
    ctrl = make(port)
    await ctrl.connect()
    try:
        assert port.read_sizes == {256}
        port.noise_before_reply = b"x" * 10_000  # line noise without a newline
        await ctrl.set_angle("SC1", 70)  # the reply after the noise is still found
        assert len(ctrl._buf) < 2048
    finally:
        await ctrl.close()
