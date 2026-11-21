"""What an announcement says: its Japanese and English parts, in playing order."""

from __future__ import annotations

from typing import Literal

from announcer.config import Tts as TtsConfig

Lang = Literal["en", "ja"]
Part = tuple[Lang, str]


def spoken_parts(tts: TtsConfig, en: str, ja: str) -> list[Part]:
    """Japanese first, then English; a part is left out if switched off or empty."""
    parts: list[Part] = []
    if tts.japanese and ja.strip():
        parts.append(("ja", ja.strip()))
    if tts.english and en.strip():
        parts.append(("en", en.strip()))
    return parts
