import re
from urllib.parse import urlsplit, urlunsplit

import requests

from job_finder.models import Job

LANDING_URL = "https://www.newgrad-jobs.com/"
AIRTABLE_HEADERS = {
    "x-requested-with": "XMLHttpRequest",
    "x-time-zone": "America/Los_Angeles",
    "x-user-locale": "en",
    "User-Agent": "Mozilla/5.0",
}


def discover_swe_embed(html: str) -> tuple[str, str]:
    """Find the /us/swe tile and return (app_id, share_id) from its airtable-link."""
    m = re.search(
        r'data-job-path="/us/swe"[^>]*airtable-link="https://airtable\.com/embed/(app\w+)/(shr\w+)',
        html,
    )
    if not m:
        raise RuntimeError("Could not find /us/swe airtable embed on landing page")
    return m.group(1), m.group(2)


def _canonical_jobright(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def parse_jobs(payload: dict) -> list[Job]:
    table = payload["data"]["table"]
    by_name = {c["name"]: c for c in table["columns"]}

    def col_id(name: str) -> str | None:
        c = by_name.get(name)
        return c["id"] if c else None

    def select_label(col_name: str, value):
        c = by_name.get(col_name)
        if not c or not value:
            return ""
        choices = (c.get("typeOptions") or {}).get("choices") or {}
        return choices.get(value, {}).get("name", "")

    ids = {name: col_id(name) for name in (
        "Position Title", "Date", "Apply", "Work Model",
        "Location", "Company", "Salary", "Qualifications")}

    jobs: list[Job] = []
    for row in table["rows"]:
        cells = row.get("cellValuesByColumnId", {})
        apply_val = cells.get(ids["Apply"])
        if not apply_val or not apply_val.get("url"):
            continue
        url = _canonical_jobright(apply_val["url"])
        jobs.append(Job(
            id=url.rstrip("/").split("/")[-1],
            title=cells.get(ids["Position Title"], "") or "",
            company=cells.get(ids["Company"], "") or "",
            location=cells.get(ids["Location"], "") or "",
            salary=cells.get(ids["Salary"], "") or "",
            qualifications=cells.get(ids["Qualifications"], "") or "",
            work_model=select_label("Work Model", cells.get(ids["Work Model"])),
            jobright_url=url,
            date=cells.get(ids["Date"], "") or "",
        ))
    return jobs


def fetch_landing() -> str:
    resp = requests.get(LANDING_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_rows(app_id: str, share_id: str) -> dict:
    embed = requests.get(
        f"https://airtable.com/embed/{app_id}/{share_id}",
        headers={"User-Agent": "Mozilla/5.0"}, timeout=30,
    )
    embed.raise_for_status()
    m = re.search(r'urlWithParams["\']?\s*[:=]\s*"(.*?)"', embed.text)
    if not m:
        raise RuntimeError("Could not extract urlWithParams from Airtable embed page")
    url_path = m.group(1).encode().decode("unicode_escape")
    headers = dict(AIRTABLE_HEADERS, **{"x-airtable-application-id": app_id})
    resp = requests.get("https://airtable.com" + url_path, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_jobs() -> list[Job]:
    app_id, share_id = discover_swe_embed(fetch_landing())
    return parse_jobs(fetch_rows(app_id, share_id))
