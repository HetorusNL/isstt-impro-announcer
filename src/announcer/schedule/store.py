"""JSON schedule format shared by FileSource and the on-disk store."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from announcer.model import Match
from announcer.schedule.source import SourceError


def _to_dict(m: Match) -> dict[str, Any]:
    data: dict[str, Any] = {
        "start": m.start.isoformat(),
        "hall": m.hall,
        "field": m.field,
        "home": m.home,
        "away": m.away,
        "referee": m.referee,
        "round": m.round_name,
    }
    if m.match_minutes is not None:
        data["match_minutes"] = m.match_minutes
    return data


def _from_dict(d: dict[str, Any], tz: ZoneInfo) -> Match:
    start = datetime.fromisoformat(d["start"])
    start = start.replace(tzinfo=tz) if start.tzinfo is None else start.astimezone(tz)
    minutes = d.get("match_minutes")
    if minutes is not None and not isinstance(minutes, int):
        raise TypeError("match_minutes must be an integer")
    return Match(
        start=start,
        hall=str(d["hall"]),
        field=str(d["field"]),
        home=str(d["home"]),
        away=str(d["away"]),
        referee=str(d["referee"]),
        round_name=str(d["round"]),
        match_minutes=minutes,
    )


def save(matches: Iterable[Match], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"matches": [_to_dict(m) for m in matches]}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load(path: Path, tz: str) -> list[Match]:
    """Read the JSON schedule format. Raises SourceError on a missing or malformed file."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return [_from_dict(d, ZoneInfo(tz)) for d in raw["matches"]]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise SourceError(f"cannot read schedule {path}: {e!r}") from e
