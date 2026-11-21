"""Kokoro TTS for English and Japanese, with an on-disk cache.

The cache key holds the model, voice, language, speed and text, so changing a voice or a
speed never plays an old file. Loaded models are shared by every Tts (the engine's and the
settings preview's), so a new Tts for changed settings starts at once. Japanese text is turned into phonemes with misaki's
JAG2P (cutlet + fugashi + unidic-lite): it works offline, unlike misaki's pyopenjtalk
mode, which downloads a dictionary on first use.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import threading
from pathlib import Path
from typing import Any

from announcer.config import Tts as TtsConfig
from announcer.speech import Lang, NoSpeech

KOKORO_LANG = {"en": "en-us", "ja": "ja"}
# Loaded once per process and shared by every Tts: loading Kokoro takes seconds. Keys:
# ("kokoro", model, voices) and ("g2p",).
_models: dict[tuple[str, ...], Any] = {}
# One synthesis at a time across all Tts objects: the engine's and the settings preview's
# may want the same file at once.
_synth_lock = threading.Lock()


class Tts:
    def __init__(self, cfg: TtsConfig) -> None:
        self.cfg = cfg
        self.cache_dir = Path(cfg.cache_dir)
        self._lock = asyncio.Lock()

    def _voice(self, lang: Lang) -> tuple[str, float]:
        if lang == "ja":
            return self.cfg.japanese_voice, self.cfg.japanese_speed
        return self.cfg.english_voice, self.cfg.english_speed

    def cache_path(self, text: str, lang: Lang) -> Path:
        voice, speed = self._voice(lang)
        key = f"kokoro|{self.cfg.model}|{voice}|{lang}|{speed}|{text}"
        return self.cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.wav"

    def _load_kokoro(self) -> Any:
        from kokoro_onnx import Kokoro

        return Kokoro(self.cfg.model, self.cfg.voices)

    def _load_g2p(self) -> Any:
        from misaki import ja

        return ja.JAG2P()

    def _model(self, key: tuple[str, ...], load: Any) -> Any:
        if key not in _models:
            _models[key] = load()
        return _models[key]

    def _synth_to(self, text: str, lang: Lang, path: Path) -> None:
        with _synth_lock:
            if not path.exists():  # another Tts may have written it meanwhile
                self._write(text, lang, path)

    def _write(self, text: str, lang: Lang, path: Path) -> None:
        import soundfile as sf

        kokoro = self._model(("kokoro", self.cfg.model, self.cfg.voices), self._load_kokoro)
        voice, speed = self._voice(lang)
        if lang == "ja":
            g2p = self._model(("g2p",), self._load_g2p)
            phonemes, _ = g2p(text)
            if not any(ch.isalpha() for ch in phonemes):  # e.g. "★": Kokoro would raise
                raise NoSpeech(f"nothing speakable in Japanese text {text!r}")
            samples, rate = kokoro.create(
                phonemes, voice=voice, speed=speed, lang=KOKORO_LANG[lang], is_phonemes=True
            )
        else:
            samples, rate = kokoro.create(
                text, voice=voice, speed=speed, lang=KOKORO_LANG[lang], is_phonemes=False
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        sf.write(tmp, samples, rate, subtype="PCM_16", format="WAV")
        tmp.replace(path)

    async def synth(self, text: str, lang: Lang) -> Path:
        path = self.cache_path(text, lang)
        async with self._lock:
            if not path.exists():
                await asyncio.to_thread(self._synth_to, text, lang, path)
        return path


async def _main(lang: Lang, text: str) -> None:
    from announcer.audio.player import SoundPlayer
    from announcer.config import Config

    cfg = Config()
    path = await Tts(cfg.tts).synth(text, lang)
    player = SoundPlayer(cfg.audio.device, cfg.audio.volume)
    print(f"{path} ({player.duration(path):.2f} s)")
    await player.play(path)


if __name__ == "__main__":
    # python -m announcer.audio.tts [en|ja] "text"
    args = sys.argv[1:]
    lang: Lang = "en"
    if args and args[0] in ("en", "ja"):
        lang = "ja" if args.pop(0) == "ja" else "en"
    asyncio.run(_main(lang, args[0] if args else "Referees, you may start the matches."))
