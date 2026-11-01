from pathlib import Path

from announcer.schedule import store
from announcer.schedule.cupkit import parse_matches_html
from announcer.schedule.filesource import FileSource

FIXTURE = Path(__file__).parent.parent / "docs" / "reference" / "cupkit-public-matches.html"
TZ = "Europe/Amsterdam"


async def test_filesource_roundtrip_with_store(tmp_path):
    matches = parse_matches_html(FIXTURE.read_text(encoding="utf-8"), TZ)
    path = tmp_path / "state" / "schedule.json"
    store.save(matches, path)
    assert await FileSource(path, TZ).fetch() == matches
    assert store.load(path, TZ) == matches
    assert not list(path.parent.glob("*.tmp"))


def test_save_overwrites_atomically(tmp_path):
    path = tmp_path / "schedule.json"
    matches = parse_matches_html(FIXTURE.read_text(encoding="utf-8"), TZ)
    store.save(matches[:3], path)
    store.save(matches[:5], path)
    assert store.load(path, TZ) == matches[:5]
