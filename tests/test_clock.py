import time
from datetime import datetime
from zoneinfo import ZoneInfo

from announcer.clock import RealClock, SimClock

TZ = ZoneInfo("Europe/Amsterdam")


async def test_simclock_advances_fast():
    start = datetime(2026, 12, 18, 9, 0, tzinfo=TZ)
    clock = SimClock(start, speed=600)
    t0 = time.monotonic()
    await clock.sleep(60)
    assert time.monotonic() - t0 < 0.5
    assert (clock.now() - start).total_seconds() >= 60


def test_realclock_is_aware():
    now = RealClock("Europe/Amsterdam").now()
    assert now.tzinfo is not None
    assert getattr(now.tzinfo, "key", None) == "Europe/Amsterdam"
