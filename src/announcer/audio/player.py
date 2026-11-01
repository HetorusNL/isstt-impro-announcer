"""Audio playback: real (sounddevice) and mock (sleeps on the clock)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Protocol

import soundfile as sf

from announcer.clock import Clock


def wav_duration(path: Path) -> float:
    info = sf.info(str(path))
    return info.frames / info.samplerate


class Player(Protocol):
    async def play(self, path: Path) -> None: ...

    def duration(self, path: Path) -> float: ...


class SoundPlayer:
    def __init__(self, device: str | None, volume: float) -> None:
        self.device = device
        self.volume = volume

    def duration(self, path: Path) -> float:
        return wav_duration(path)

    async def play(self, path: Path) -> None:
        import sounddevice as sd  # imported lazily: needs PortAudio at runtime

        data, samplerate = sf.read(str(path), dtype="float32")
        data = data * self.volume

        def _blocking() -> None:
            sd.play(data, samplerate, device=self.device)
            sd.wait()

        try:
            await asyncio.to_thread(_blocking)
        except asyncio.CancelledError:
            sd.stop()
            raise


class MockPlayer:
    def __init__(self, clock: Clock, fail: bool = False) -> None:
        self._clock = clock
        self.fail = fail
        self.played: list[Path] = []
        self.played_at: list[datetime] = []

    def duration(self, path: Path) -> float:
        return wav_duration(path)

    async def play(self, path: Path) -> None:
        if self.fail:
            raise RuntimeError(f"mock playback failure: {path}")
        self.played_at.append(self._clock.now())
        self.played.append(path)
        await self._clock.sleep(self.duration(path))
