from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from announcer.config import Actuator, Config
from announcer.model import Match
from announcer.planner import group_sessions, lead_seconds, plan_announcements, render_message
from announcer.schedule.cupkit import parse_matches_html

FIXTURE = Path(__file__).parent.parent / "docs" / "reference" / "cupkit-public-matches.html"
TZ = "Europe/Amsterdam"
ROUND_MINUTES = {"Round 1": 15, "Round 2": 15, "Round 3": 20, "Round 4": 20, "Round 5": 20}


def fixture_matches() -> list[Match]:
    return parse_matches_html(FIXTURE.read_text(encoding="utf-8"), TZ)


def _match(**kw) -> Match:
    base = dict(
        start=datetime(2026, 12, 18, 9, 0, tzinfo=ZoneInfo(TZ)),
        hall="SC1",
        field="Field 1",
        home="A1",
        away="A2",
        referee="E1",
        round_name="Round 1",
        match_minutes=None,
    )
    base.update(kw)
    return Match(**base)


def _cfg(**announce) -> Config:
    cfg = Config(
        actuators={
            n: Actuator(channel=i, rest=0, press=90, press_ms=250, release_ms=250)
            for i, n in enumerate(["SC1", "SC2", "SC3", "SPREKEN"])
        }
    )
    for k, v in announce.items():
        setattr(cfg.announce, k, v)
    return cfg


def test_fixture_counts():
    anns = plan_announcements(fixture_matches(), ROUND_MINUTES, 20)
    assert sum(a.kind == "match_start" for a in anns) == 39
    assert sum(a.kind == "match_end" for a in anns) == 39
    first_end = min(a.due for a in anns if a.kind == "match_end")
    assert first_end.strftime("%d %H:%M") == "18 09:15"


def test_collisions_merge_end_first():
    sessions = group_sessions(
        plan_announcements(fixture_matches(), ROUND_MINUTES, 20), ["SC1", "SC2", "SC3"], 30, 5
    )
    assert len(sessions) == 76
    merged = [s for s in sessions if len(s.announcements) == 2]
    assert [s.announcements[0].due.strftime("%d %H:%M") for s in merged] == ["19 14:55", "19 16:30"]
    assert all([a.kind for a in s.announcements] == ["match_end", "match_start"] for s in merged)


def test_unknown_round_uses_default_minutes():
    anns = plan_announcements([_match(round_name="Round 6")], ROUND_MINUTES, 20)
    end = next(a for a in anns if a.kind == "match_end")
    assert end.due.strftime("%H:%M") == "09:20"


def test_match_minutes_overrides_round():
    anns = plan_announcements([_match(match_minutes=10)], ROUND_MINUTES, 20)
    end = next(a for a in anns if a.kind == "match_end")
    assert end.due.strftime("%H:%M") == "09:10"


def test_render_plain_and_placeholders():
    ms = [_match(hall="SC1", field=f"Field {i}") for i in range(7)]
    ann = next(a for a in plan_announcements(ms, ROUND_MINUTES, 20) if a.kind == "match_start")
    plain = "Referees, you may start the matches."
    assert render_message(plain, ann) == plain
    assert render_message("{count} matches at {time}", ann) == "7 matches at 09:00"
    assert render_message("{fields} / {halls}", ann).endswith("/ SC1")


def test_lead_seconds_computed():
    assert lead_seconds(_cfg()) == 4.75


def test_lead_seconds_override():
    assert lead_seconds(_cfg(lead_seconds=7)) == 7


def test_session_start_at_is_due_minus_lead():
    anns = plan_announcements([_match()], ROUND_MINUTES, 20)
    s = group_sessions(anns, ["SC1"], 30, 5)[0]
    assert s.start_at == anns[0].due - timedelta(seconds=5)
    assert s.halls == ("SC1",)

