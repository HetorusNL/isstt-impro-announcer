from dataclasses import replace
from pathlib import Path

import numpy as np
import soundfile as sf

from announcer.audio.tts import Tts
from announcer.config import Tts as TtsConfig


class FakeKokoro:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, text, voice, speed=1.0, lang="en-us", is_phonemes=False):
        self.calls.append(
            {"text": text, "voice": voice, "speed": speed, "lang": lang, "is_phonemes": is_phonemes}
        )
        return np.zeros(2400, dtype=np.float32), 24000


class FakeG2P:
    def __call__(self, text):
        return "PHONEMES:" + text, None


class Loads:
    def __init__(self) -> None:
        self.kokoro = FakeKokoro()
        self.kokoro_loads = 0
        self.g2p_loads = 0


def make(tmp_path: Path, cfg: TtsConfig | None = None, loads: Loads | None = None) -> Tts:
    cfg = cfg or TtsConfig(cache_dir=str(tmp_path / "cache"))
    loads = loads or Loads()
    tts = Tts(cfg)

    def load_kokoro():
        loads.kokoro_loads += 1
        return loads.kokoro

    def load_g2p():
        loads.g2p_loads += 1
        return FakeG2P()

    tts._load_kokoro = load_kokoro  # no model needed
    tts._load_g2p = load_g2p
    tts.loads = loads  # type: ignore[attr-defined]
    return tts


async def test_english_uses_english_voice(tmp_path):
    tts = make(tmp_path)
    await tts.synth("Hello.", "en")
    assert tts.loads.kokoro.calls == [
        {"text": "Hello.", "voice": "af_bella", "speed": 1.0, "lang": "en-us", "is_phonemes": False}
    ]


async def test_english_voice_jf_alpha(tmp_path):
    cfg = TtsConfig(cache_dir=str(tmp_path / "cache"), english_voice="jf_alpha")
    tts = make(tmp_path, cfg)
    await tts.synth("Hello.", "en")
    call = tts.loads.kokoro.calls[0]
    assert (call["voice"], call["lang"]) == ("jf_alpha", "en-us")


async def test_japanese_goes_through_g2p(tmp_path):
    cfg = TtsConfig(cache_dir=str(tmp_path / "cache"), japanese_speed=0.9)
    tts = make(tmp_path, cfg)
    await tts.synth("試合", "ja")
    assert tts.loads.kokoro.calls == [
        {"text": "PHONEMES:試合", "voice": "jf_alpha", "speed": 0.9, "lang": "ja", "is_phonemes": True}
    ]


async def test_cache_hit_does_not_resynthesise(tmp_path):
    tts = make(tmp_path)
    a = await tts.synth("hello", "en")
    again = await tts.synth("hello", "en")
    assert a == again
    assert len(tts.loads.kokoro.calls) == 1


async def test_cache_key_changes_with_voice_and_speed(tmp_path):
    base = TtsConfig(cache_dir=str(tmp_path / "cache"))
    ref = Tts(base).cache_path("hello", "en")
    assert Tts(replace(base, english_voice="jf_alpha")).cache_path("hello", "en") != ref
    assert Tts(replace(base, english_speed=1.2)).cache_path("hello", "en") != ref
    assert Tts(base).cache_path("hello", "ja") != ref
    assert Tts(base).cache_path("hello!", "en") != ref
    # a Japanese setting does not invalidate English audio
    assert Tts(replace(base, japanese_speed=1.2)).cache_path("hello", "en") == ref


async def test_models_load_lazily_and_once(tmp_path):
    loads = Loads()
    tts = make(tmp_path, loads=loads)
    assert (loads.kokoro_loads, loads.g2p_loads) == (0, 0)
    await tts.synth("one", "en")
    await tts.synth("二", "ja")
    await tts.synth("three", "en")
    await tts.synth("四", "ja")
    assert (loads.kokoro_loads, loads.g2p_loads) == (1, 1)


async def test_japanese_with_latin_letters(tmp_path):
    tts = make(tmp_path)
    path = await tts.synth("ようこそ、ISSTT 二千二十六へ。", "ja")
    assert path.exists()


async def test_wav_is_24k_mono(tmp_path):
    tts = make(tmp_path)
    path = await tts.synth("hello", "en")
    info = sf.info(path)
    assert (info.samplerate, info.channels) == (24000, 1)
    assert path.parent == tmp_path / "cache"
