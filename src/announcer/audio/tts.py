"""Piper TTS with an on-disk cache keyed by voice model, speech rate and text."""

from __future__ import annotations

import asyncio
import hashlib
import sys
import wave
from pathlib import Path
from typing import Any


class Tts:
    def __init__(self, voice_model: Path, length_scale: float, cache_dir: Path) -> None:
        self.voice_model = Path(voice_model)
        self.length_scale = length_scale
        self.cache_dir = Path(cache_dir)
        self._voice: Any = None
        self._lock = asyncio.Lock()

    def cache_path(self, text: str) -> Path:
        key = f"{self.voice_model}|{self.length_scale}|{text}"
        return self.cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.wav"

    def _load_voice(self) -> Any:
        from piper import PiperVoice

        return PiperVoice.load(self.voice_model)

    def _synth_to(self, text: str, path: Path) -> None:
        from piper import SynthesisConfig

        if self._voice is None:
            self._voice = self._load_voice()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with wave.open(str(tmp), "wb") as wav_file:
            self._voice.synthesize_wav(
                text, wav_file, syn_config=SynthesisConfig(length_scale=self.length_scale)
            )
        tmp.replace(path)

    async def synth(self, text: str) -> Path:
        path = self.cache_path(text)
        async with self._lock:
            if not path.exists():
                await asyncio.to_thread(self._synth_to, text, path)
        return path


async def _main(text: str) -> None:
    from announcer.audio.player import SoundPlayer
    from announcer.config import Config

    cfg = Config()
    tts = Tts(Path(cfg.tts.voice_model), cfg.tts.length_scale, Path(cfg.tts.cache_dir))
    path = await tts.synth(text)
    player = SoundPlayer(cfg.audio.device, cfg.audio.volume)
    print(f"{path} ({player.duration(path):.2f} s)")
    await player.play(path)


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1] if len(sys.argv) > 1 else "Referees, you may start the matches."))
