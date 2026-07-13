from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from job_finder.models import Job
from job_finder import main as M


def _job(id_, date):
    return Job(id=id_, title="Eng", company="Acme", location="NYC",
               salary="$1", qualifications="q", work_model="Onsite",
               jobright_url=f"https://jobright.ai/jobs/info/{id_}", date=date)


def test_run_filters_dedups_emails_and_records(tmp_path, monkeypatch):
    now = datetime(2026, 7, 13, 20, 0, 0, tzinfo=timezone.utc)
    today = "2026-07-13"
    seen_path = str(tmp_path / "seen.json")
    monkeypatch.setattr(M, "SEEN_PATH", seen_path)
    monkeypatch.setattr(M, "DEEPSEEK_API_KEY", "dk")
    monkeypatch.setattr(M, "RESEND_API_KEY", "rk")

    jobs = [
        _job("fresh", today),          # today, recent, kept -> emailed
        _job("old_date", "2026-07-10"),  # filtered by date
        _job("seen", today),            # today but already seen
    ]

    def fake_posted(url):
        return now - timedelta(hours=1)

    with patch.object(M.source, "get_jobs", return_value=jobs), \
         patch.object(M.freshness, "fetch_posted_at", side_effect=fake_posted), \
         patch.object(M.matcher, "load_resumes", return_value=["resume"]), \
         patch.object(M.matcher, "keep", return_value=M.matcher.Decision(True, "fit")), \
         patch.object(M.emailer, "send") as send, \
         patch.object(M.state, "load_seen", return_value={"seen"}):
        emailed = M.run(now=now)

    assert emailed == 1
    assert send.called
    html = send.call_args.args[0]
    assert "fresh" in html and "old_date" not in html and "seen" not in html
    import json
    with open(seen_path) as f:
        assert "fresh" in json.load(f)


def test_today_filter_uses_pacific_date(tmp_path, monkeypatch):
    # 2026-07-14 03:00 UTC == 2026-07-13 20:00 Pacific — job dated "2026-07-13" must NOT be excluded
    now = datetime(2026, 7, 14, 3, 0, 0, tzinfo=timezone.utc)
    pacific_date = "2026-07-13"
    seen_path = str(tmp_path / "seen.json")
    monkeypatch.setattr(M, "SEEN_PATH", seen_path)
    monkeypatch.setattr(M, "DEEPSEEK_API_KEY", "dk")
    monkeypatch.setattr(M, "RESEND_API_KEY", "rk")

    jobs = [_job("pacific_job", pacific_date)]

    def fake_posted(url):
        return now - timedelta(hours=1)

    with patch.object(M.source, "get_jobs", return_value=jobs), \
         patch.object(M.freshness, "fetch_posted_at", side_effect=fake_posted), \
         patch.object(M.matcher, "load_resumes", return_value=["resume"]), \
         patch.object(M.matcher, "keep", return_value=M.matcher.Decision(True, "fit")), \
         patch.object(M.emailer, "send") as send, \
         patch.object(M.state, "load_seen", return_value=set()):
        emailed = M.run(now=now)

    assert emailed == 1, "job with Pacific date should not be filtered out when UTC is already the next day"
    assert send.called


def test_run_skips_email_when_no_matches(tmp_path, monkeypatch):
    now = datetime(2026, 7, 13, 20, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(M, "SEEN_PATH", str(tmp_path / "seen.json"))
    monkeypatch.setattr(M, "DEEPSEEK_API_KEY", "dk")
    monkeypatch.setattr(M, "RESEND_API_KEY", "rk")
    with patch.object(M.source, "get_jobs", return_value=[]), \
         patch.object(M.matcher, "load_resumes", return_value=["r"]), \
         patch.object(M.emailer, "send") as send, \
         patch.object(M.state, "load_seen", return_value=set()):
        emailed = M.run(now=now)
    assert emailed == 0
    assert not send.called
