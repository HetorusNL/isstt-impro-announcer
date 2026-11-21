from announcer.config import Tts
from announcer.speech import spoken_parts


def test_parts_order_japanese_first():
    assert spoken_parts(Tts(), "Hello.", "こんにちは。") == [("ja", "こんにちは。"), ("en", "Hello.")]


def test_parts_english_off():
    assert spoken_parts(Tts(english=False), "Hello.", "こんにちは。") == [("ja", "こんにちは。")]


def test_parts_japanese_off():
    assert spoken_parts(Tts(japanese=False), "Hello.", "こんにちは。") == [("en", "Hello.")]


def test_parts_both_off():
    assert spoken_parts(Tts(english=False, japanese=False), "Hello.", "こんにちは。") == []


def test_parts_whitespace_is_empty():
    assert spoken_parts(Tts(), "Hello.", "　 \n") == [("en", "Hello.")]
