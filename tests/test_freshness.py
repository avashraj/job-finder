from datetime import datetime, timedelta, timezone
from pathlib import Path

from job_finder.models import Job
from job_finder.freshness import parse_posted_at, within_last

FIX = Path(__file__).parent / "fixtures"


def _job(id_, posted_at):
    return Job(id=id_, title="t", company="c", location="l", salary="s",
               qualifications="q", work_model="w",
               jobright_url=f"https://jobright.ai/jobs/info/{id_}",
               date="2026-07-13", posted_at=posted_at)


def test_parse_posted_at_reads_publish_time():
    html = (FIX / "jobright_snippet.html").read_text()
    ts = parse_posted_at(html)
    assert ts == datetime(2026, 7, 13, 17, 2, 34, tzinfo=timezone.utc)


def test_parse_posted_at_missing_returns_none():
    assert parse_posted_at("<html>no time here</html>") is None


def test_within_last_keeps_recent_drops_old_and_none():
    now = datetime(2026, 7, 13, 20, 0, 0, tzinfo=timezone.utc)
    recent = _job("a", now - timedelta(hours=1))
    old = _job("b", now - timedelta(hours=6))
    unknown = _job("c", None)
    kept = within_last([recent, old, unknown], hours=4, now=now)
    assert [j.id for j in kept] == ["a"]
