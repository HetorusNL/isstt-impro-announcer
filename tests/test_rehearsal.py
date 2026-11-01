"""Headless dress rehearsal on the saved Cupkit page (plan Task 7 step 3, automated part)."""

import asyncio
import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import soundfile as sf

from announcer import config
from announcer.audio.player import MockPlayer
from announcer.clock import SimClock
from announcer.controller.mock import MockController
from announcer.engine import Engine
from announcer.schedule import store
from announcer.schedule.cupkit import parse_matches_html
from announcer.schedule.filesource import FileSource

REPO = Path(__file__).resolve().parents[1]
TZ = "Europe/Amsterdam"
START_MSG = "Referees, you may start the matches."
END_MSG = "Referees, you may end the matches."


def at(day: int, h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 12, day, h, m, s, tzinfo=ZoneInfo(TZ))


class SilentTts:
    def __init__(self, cache: Path) -> None:
        self.cache = cache
        self.by_path: dict[Path, str] = {}

    async def synth(self, text: str) -> Path:
        self.cache.mkdir(parents=True, exist_ok=True)
        path = self.cache / f"{hashlib.sha256(text.encode()).hexdigest()}.wav"
        if not path.exists():
            sf.write(path, np.zeros(16000, dtype="int16"), 16000)  # 1 s of silence
        self.by_path[path] = text
        return path


class Rehearsal:
    def __init__(self, tmp_path: Path, start: datetime, speed: float) -> None:
        html = (REPO / "docs/reference/cupkit-public-matches.html").read_text(encoding="utf-8")
        schedule = tmp_path / "schedule.json"
        store.save(parse_matches_html(html, TZ), schedule)
        self.cfg = config.load(REPO / "config.example.toml")
        # at speed 2000 the default 60 s is ~30 ms of real time: a loaded machine would
        # skip sessions as late. 600 s (0.3 s real) keeps the run deterministic; on-time
        # playback is checked at speed 60 in the merged-session test.
        self.cfg.announce.late_threshold_seconds = 600
        self.clock = SimClock(start, speed)
        self.ctrl = MockController(self.clock, self.cfg.actuators)
        self.player = MockPlayer(self.clock)
        self.tts = SilentTts(tmp_path / "tts")
        self.engine = Engine(
            self.cfg,
            FileSource(schedule, TZ),
            tmp_path / "state" / "schedule.json",
            self.ctrl,
            self.player,
            self.tts,
            self.clock,
        )

    async def run_until(self, end: datetime) -> None:
        await self.engine.start()
        try:
            while self.clock.now() < end:
                await asyncio.sleep(0.01)
        finally:
            await self.engine.stop()

    def played_texts(self) -> list[str]:
        return [self.tts.by_path[p] for p in self.player.played]


async def test_full_day_18_dec_plays_24_sessions(tmp_path: Path) -> None:
    r = Rehearsal(tmp_path, at(18, 8, 55), speed=2000)
    await r.run_until(at(18, 14, 0))
    day = [h for h in r.engine.history if h.key[1].startswith("2026-12-18")]
    statuses = Counter((h.key[0], h.status) for h in day)
    assert statuses == {("match_start", "played"): 12, ("match_end", "played"): 12}
    assert r.played_texts().count(START_MSG) == 12
    assert r.played_texts().count(END_MSG) == 12
    # every session held and released SPREKEN once
    kinds = Counter((k, b) for _, k, b in r.ctrl.events)
    assert kinds[("hold", "SPREKEN")] == kinds[("release", "SPREKEN")] == 24


async def test_merged_19_dec_1455_end_then_start_in_one_hold(tmp_path: Path) -> None:
    # speed 60: at higher speeds each clock sleep overshoots by a sim-second or so
    r = Rehearsal(tmp_path, at(19, 14, 53), speed=60)
    await r.run_until(at(19, 14, 56))
    keys = [(h.key, h.status) for h in r.engine.history if h.status == "played"]
    due = at(19, 14, 55).isoformat()
    assert keys == [(("match_end", due), "played"), (("match_start", due), "played")]
    assert r.played_texts() == [END_MSG, START_MSG]
    holds = [t for t, k, b in r.ctrl.events if (k, b) == ("hold", "SPREKEN")]
    releases = [t for t, k, b in r.ctrl.events if (k, b) == ("release", "SPREKEN")]
    assert len(holds) == len(releases) == 1
    assert all(holds[0] < t < releases[0] for t in r.player.played_at)
    # the first word on the minute (spec 5.6), within sim-clock scheduling jitter
    assert abs((r.player.played_at[0] - at(19, 14, 55)).total_seconds()) < 1
