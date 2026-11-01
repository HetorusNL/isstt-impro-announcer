"""Scraper for the Cupkit public matches page."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from selectolax.lexbor import LexborHTMLParser, LexborNode

from announcer.model import Match
from announcer.schedule.source import SourceError

# CSS-module class names carry a hash suffix that changes per deploy, so match by substring.
MOMENT_FORMAT = "%d %B %Y at %H:%M"
REFEREE_PREFIX = "Referee:"


def _text(node: LexborNode | None) -> str:
    return node.text().strip() if node is not None else ""


def _parse_line(li: LexborNode, start: datetime, round_name: str) -> Match | None:
    where = _text(li.css_first('span[class*="where"]'))
    sides = [_text(s) for s in li.css('span[class*="side"]')]
    if not where or len(sides) != 2:
        return None
    place, _, _poule = where.partition(" · ")
    hall, _, field = place.partition(", ")
    referee = _text(li.css_first('span[class*="referee"]')).removeprefix(REFEREE_PREFIX).strip()
    return Match(
        start=start,
        hall=hall.strip(),
        field=field.strip(),
        home=sides[0],
        away=sides[1],
        referee=referee,
        round_name=round_name,
        match_minutes=None,
    )


def parse_matches_html(html: str, tz: str) -> list[Match]:
    zone = ZoneInfo(tz)
    tree = LexborHTMLParser(html)
    matches: list[Match] = []
    for section in tree.css("section"):
        round_name = _text(section.css_first('h2[class*="roundName"]'))
        for block in section.css('div[class*="__time"]'):
            moment = _text(block.css_first('h3[class*="moment"]'))
            try:
                start = datetime.strptime(moment, MOMENT_FORMAT).replace(tzinfo=zone)
            except ValueError as e:
                raise SourceError(f"unrecognised match time {moment!r}") from e
            for li in block.css('li[class*="line"]'):
                match = _parse_line(li, start, round_name)
                if match is not None:
                    matches.append(match)
    if not matches:
        raise SourceError("no matches found on the page (did the site change?)")
    return matches


class CupkitSource:
    def __init__(
        self,
        matches_urls: list[str],
        tz: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._urls = list(matches_urls)
        self._tz = tz
        self._client = client

    async def _get(self, client: httpx.AsyncClient, url: str) -> str:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise SourceError(f"cannot fetch {url}: {e!r}") from e
        return response.text

    async def fetch(self) -> list[Match]:
        if not self._urls:
            raise SourceError("no matches_urls configured")
        matches: list[Match] = []
        if self._client is not None:
            pages = [await self._get(self._client, url) for url in self._urls]
        else:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                pages = [await self._get(client, url) for url in self._urls]
        for page in pages:
            matches.extend(parse_matches_html(page, self._tz))
        return matches
