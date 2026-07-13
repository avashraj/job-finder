import json
from pathlib import Path

from job_finder.source import discover_swe_embed, parse_jobs

FIX = Path(__file__).parent / "fixtures"


def test_discover_swe_embed():
    html = (FIX / "landing_snippet.html").read_text()
    app_id, share_id = discover_swe_embed(html)
    assert app_id == "appjDG7vmPOm1pO7S"
    assert share_id == "shr763VHjlzPBDCgN"


def test_parse_jobs_extracts_fields():
    payload = json.loads((FIX / "airtable_rows.json").read_text())
    jobs = parse_jobs(payload)
    assert len(jobs) == 2
    j = jobs[0]
    assert j.id == "6a550bec268af95237be8d61"
    assert j.jobright_url == "https://jobright.ai/jobs/info/6a550bec268af95237be8d61"
    assert j.title == "Junior Data Engineer"
    assert j.company == "Tata Consultancy Services"
    assert j.location == "Plano, TX, United States"
    assert j.work_model == "Onsite"
    assert j.date == "2026-07-13"
    assert "Snowflake" in j.qualifications
    assert j.posted_at is None


def test_parse_jobs_skips_rows_without_apply_url():
    payload = {"data": {"table": {
        "columns": [{"id": "fldhbYjhYPgayPoKp", "name": "Apply", "type": "button"}],
        "rows": [{"id": "r", "cellValuesByColumnId": {"fldhbYjhYPgayPoKp": None}}],
    }}}
    assert parse_jobs(payload) == []
