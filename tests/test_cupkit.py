from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from announcer.schedule.cupkit import CupkitSource, parse_matches_html, parse_matches_page
from announcer.schedule.source import SourceError

FIXTURE = Path(__file__).parent.parent / "docs" / "reference" / "cupkit-public-matches.html"
PUBLIC = FIXTURE.read_text(encoding="utf-8")
TZ = "Europe/Amsterdam"


def test_parses_all_matches():
    ms = parse_matches_html(PUBLIC, TZ)
    assert len(ms) == 198
    first = min(ms, key=lambda m: (m.start, m.field))
    assert first.start == datetime(2026, 12, 18, 9, 0, tzinfo=ZoneInfo(TZ))
    assert (first.hall, first.field, first.home, first.away, first.referee, first.round_name) == (
        "SC1",
        "Field 1",
        "A1",
        "A4",
        "E1",
        "Round 1",
    )
    assert first.match_minutes is None
    assert len({m.start for m in ms}) == 39
    assert {m.hall for m in ms} == {"SC1", "SC2", "SC3"}
    assert {m.round_name for m in ms} == {f"Round {i}" for i in range(1, 6)}


def test_page_without_matches_is_source_error():
    with pytest.raises(SourceError):
        parse_matches_html("<html><main><h2>Senior</h2></main></html>", TZ)


async def test_cupkit_concatenates_urls():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=PUBLIC)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = CupkitSource(["https://x.test/a", "https://x.test/b"], TZ, client=client)
        assert len(await source.fetch()) == 396


async def test_cupkit_http_error_is_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError):
            await CupkitSource(["https://x.test/a"], TZ, client=client).fetch()


async def test_cupkit_network_failure_is_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError):
            await CupkitSource(["https://x.test/a"], TZ, client=client).fetch()


def test_malformed_line_is_logged_and_skipped(caplog):
    html = (
        '<section><h2 class="x__roundName">Round 1</h2><div class="x__time">'
        '<h3 class="x__moment">18 December 2026 at 09:00</h3><ul>'
        '<li class="x__line"><span class="x__where">SC1, Field 1 · Poule A</span>'
        '<span class="x__side">A1</span><span class="x__side">A4</span>'
        '<span class="x__referee">Referee: E1</span></li>'
        '<li class="x__line"><span class="x__where">SC1, Field 2 · Poule A</span>'
        '<span class="x__side">A2</span></li>'
        "</ul></div></section>"
    )
    with caplog.at_level("WARNING", logger="announcer.schedule.cupkit"):
        ms = parse_matches_html(html, TZ)
    assert len(ms) == 1
    assert any("Field 2" in r.getMessage() for r in caplog.records)


def _block(moment: str, field: str = "Field 1") -> str:
    return (
        f'<div class="x__time"><h3 class="x__moment">{moment}</h3><ul>'
        f'<li class="x__line"><span class="x__where">SC1, {field} · Poule A</span>'
        '<span class="x__side">A1</span><span class="x__side">A4</span>'
        '<span class="x__referee">Referee: E1</span></li></ul></div>'
    )


def _page(*blocks: str) -> str:
    return f'<section><h2 class="x__roundName">Round 1</h2>{"".join(blocks)}</section>'


GOOD = "18 December 2026 at 09:00"


def test_one_unparseable_moment_skips_only_that_block(caplog):
    html = _page(_block(GOOD), _block("sometime soon", "Field 2"))
    with caplog.at_level("WARNING", logger="announcer.schedule.cupkit"):
        matches, skipped = parse_matches_page(html, TZ)
    assert [m.field for m in matches] == ["Field 1"]
    assert skipped == 1
    assert "sometime soon" in caplog.text


def test_every_moment_unparseable_is_source_error():
    with pytest.raises(SourceError, match="2 match times"):
        parse_matches_page(_page(_block("soon"), _block("later")), TZ)


async def test_cupkit_source_counts_skipped_blocks_over_urls():
    pages = {
        "https://x.test/a": _page(_block(GOOD), _block("soon")),
        "https://x.test/b": _page(_block(GOOD), _block("later"), _block("never")),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=pages[str(request.url)])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = CupkitSource(list(pages), TZ, client=client)
        assert source.skipped_blocks == 0
        assert len(await source.fetch()) == 2
        assert source.skipped_blocks == 3
        pages["https://x.test/a"] = _page(_block(GOOD))
        pages["https://x.test/b"] = _page(_block(GOOD))
        await source.fetch()
        assert source.skipped_blocks == 0
