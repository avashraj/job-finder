import re
from datetime import datetime, timedelta, timezone

import requests

from job_finder.models import Job

_TS_RE = re.compile(r'"(?:publishTime|datePosted)"\s*:\s*"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"')


def parse_posted_at(html: str) -> datetime | None:
    m = _TS_RE.search(html)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def fetch_posted_at(url: str) -> datetime | None:
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    return parse_posted_at(resp.text)


def within_last(jobs: list[Job], hours: int, now: datetime | None = None) -> list[Job]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    return [j for j in jobs if j.posted_at is not None and j.posted_at >= cutoff]
