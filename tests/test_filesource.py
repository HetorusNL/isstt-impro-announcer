from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from announcer.schedule.filesource import FileSource
from announcer.schedule.source import SourceError

TZ = "Europe/Amsterdam"


async def test_reads_naive_times_with_tz_and_optional_minutes(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(
        '{"matches": ['
        '{"start": "2026-12-18T09:00", "hall": "SC1", "field": "Field 1", "home": "A1",'
        ' "away": "A4", "referee": "E1", "round": "Round 1", "match_minutes": 20},'
        '{"start": "2026-12-18T09:30", "hall": "SC2", "field": "Field 4", "home": "B1",'
        ' "away": "B2", "referee": "F1", "round": "Round 2"}]}'
    )
    ms = await FileSource(path, TZ).fetch()
    assert ms[0].start == datetime(2026, 12, 18, 9, 0, tzinfo=ZoneInfo(TZ))
    assert ms[0].match_minutes == 20
    assert ms[1].match_minutes is None
    assert ms[1].round_name == "Round 2"


async def test_missing_file_is_source_error(tmp_path):
    with pytest.raises(SourceError):
        await FileSource(tmp_path / "nope.json", TZ).fetch()


async def test_bad_json_is_source_error(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{not json")
    with pytest.raises(SourceError):
        await FileSource(path, TZ).fetch()


async def test_wrong_shape_is_source_error(tmp_path):
    path = tmp_path / "s.json"
    path.write_text('{"matches": [{"start": "2026-12-18T09:00"}]}')
    with pytest.raises(SourceError):
        await FileSource(path, TZ).fetch()


@pytest.mark.parametrize("content", ['{"matches": []}', "[]"])
async def test_empty_schedule_is_source_error(tmp_path, content):
    path = tmp_path / "s.json"
    path.write_text(content)
    with pytest.raises(SourceError):
        await FileSource(path, TZ).fetch()
