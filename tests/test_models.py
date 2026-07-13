from datetime import datetime, timezone

from job_finder.models import Job


def test_job_defaults_posted_at_none():
    job = Job(
        id="abc123",
        title="Software Engineer",
        company="Acme",
        location="New York, NY, United States",
        salary="$100,000 /yr",
        qualifications="Python, SQL",
        work_model="Onsite",
        jobright_url="https://jobright.ai/jobs/info/abc123",
        date="2026-07-13",
    )
    assert job.posted_at is None
    assert job.id == "abc123"


def test_job_accepts_posted_at():
    ts = datetime(2026, 7, 13, 17, 2, 34, tzinfo=timezone.utc)
    job = Job(
        id="x", title="t", company="c", location="l", salary="s",
        qualifications="q", work_model="w",
        jobright_url="u", date="2026-07-13", posted_at=ts,
    )
    assert job.posted_at == ts
