import wave
from pathlib import Path

from announcer.audio.tts import Tts


class FakeVoice:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def synthesize_wav(self, text, wav_file: wave.Wave_write, syn_config=None) -> None:
        self.calls.append(text)
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 2205)


def make(tmp_path: Path, voice: FakeVoice, length_scale: float = 1.0) -> Tts:
    tts = Tts(tmp_path / "voice.onnx", length_scale, tmp_path / "cache")
    tts._load_voice = lambda: voice  # no model needed
    return tts


async def test_tts_cache_key_changes_with_text(tmp_path):
    voice = FakeVoice()
    tts = make(tmp_path, voice)
    a = await tts.synth("Referees, you may start the matches.")
    b = await tts.synth("Referees, you may end the matches.")
    assert a != b
    assert a.exists() and b.exists()
    assert a.parent == tmp_path / "cache"
    with wave.open(str(a)) as w:
        assert w.getnframes() == 2205


async def test_tts_cache_hit_does_not_resynthesise(tmp_path):
    voice = FakeVoice()
    tts = make(tmp_path, voice)
    a = await tts.synth("hello")
    again = await tts.synth("hello")
    assert a == again
    assert voice.calls == ["hello"]


async def test_tts_cache_key_changes_with_length_scale(tmp_path):
    a = await make(tmp_path, FakeVoice(), 1.0).synth("hello")
    b = await make(tmp_path, FakeVoice(), 1.2).synth("hello")
    assert a != b


async def test_tts_loads_voice_lazily(tmp_path):
    loads = []
    tts = Tts(tmp_path / "voice.onnx", 1.0, tmp_path / "cache")

    def loader():
        loads.append(1)
        return FakeVoice()

    tts._load_voice = loader
    assert loads == []
    await tts.synth("one")
    await tts.synth("two")
    await tts.synth("one")
    assert loads == [1]
