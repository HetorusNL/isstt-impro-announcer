"""Pure planning: matches -> announcements -> sessions -> message text."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from announcer.config import Config
from announcer.model import Announcement, Match, Session


def _match_minutes(m: Match, round_minutes: dict[str, int], default_minutes: int) -> int:
    if m.match_minutes is not None:
        return m.match_minutes
    return round_minutes.get(m.round_name, default_minutes)


def plan_announcements(
    matches: list[Match], round_minutes: dict[str, int], default_minutes: int
) -> list[Announcement]:
    starts: dict[datetime, list[Match]] = {}
    ends: dict[datetime, list[Match]] = {}
    for m in matches:
        starts.setdefault(m.start, []).append(m)
        end = m.start + timedelta(minutes=_match_minutes(m, round_minutes, default_minutes))
        ends.setdefault(end, []).append(m)
    anns = [Announcement(due, "match_start", tuple(ms)) for due, ms in starts.items()]
    anns += [Announcement(due, "match_end", tuple(ms)) for due, ms in ends.items()]
    # at equal due, end sorts before start
    anns.sort(key=lambda a: (a.due, a.kind != "match_end"))
    return anns


def group_sessions(
    anns: list[Announcement], halls: Sequence[str], merge_window_s: float, lead_s: float
) -> list[Session]:
    groups: list[list[Announcement]] = []
    for a in anns:
        if groups and (a.due - groups[-1][0].due).total_seconds() <= merge_window_s:
            groups[-1].append(a)
        else:
            groups.append([a])
    return [
        Session(g[0].due - timedelta(seconds=lead_s), tuple(g), tuple(halls)) for g in groups
    ]


def _distinct(values: list[str]) -> str:
    return ", ".join(dict.fromkeys(values))


def render_message(template: str, ann: Announcement) -> str:
    return template.format_map(
        {
            "time": ann.due.strftime("%H:%M"),
            "count": len(ann.matches),
            "fields": _distinct([m.field for m in ann.matches]),
            "halls": _distinct([m.hall for m in ann.matches]),
        }
    )


def lead_seconds(cfg: Config) -> float:
    if cfg.announce.lead_seconds is not None:
        return cfg.announce.lead_seconds
    acts = cfg.actuators
    halls_ms = sum(acts[h].press_ms + acts[h].release_ms for h in cfg.announce.halls)
    return halls_ms / 1000 + acts["SPREKEN"].press_ms / 1000 + cfg.announce.chime_seconds
