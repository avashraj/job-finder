# Job Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scrape today's software-engineering jobs from newgrad-jobs.com, keep only those posted in the last 4 hours that are a good fit, and email the jobright links.

**Architecture:** A small `job_finder` package of single-purpose modules (source, freshness, matcher, emailer, state, models) orchestrated by `main.py`. Jobs come from an Airtable shared-view JSON endpoint discovered off the landing page; true posting time comes from each jobright page. DeepSeek judges keep/drop; Resend sends the digest; `seen.json` prevents resends.

**Tech Stack:** Python 3.13, `requests`, `python-dotenv`, `pytest` (dev). No vendor SDKs — DeepSeek and Resend are called over plain REST.

## Global Constraints

- Python `>=3.13` (existing `pyproject.toml`).
- Dependencies managed by `uv`. Run everything via `uv run ...`.
- Only add deps: `python-dotenv` (runtime), `pytest` (dev). `requests` already present.
- No vendor SDKs — DeepSeek + Resend via `requests`.
- Secrets from `.env` only (`DEEPSEEK_API_KEY`, `RESEND_API_KEY`); never hardcode or commit them.
- Fixed config values (copy verbatim):
  - `RECIPIENT = "avashraj328@outlook.com"`
  - `SENDER = "onboarding@resend.dev"`
  - `FRESH_HOURS = 4`
  - `RESUME_DIR = "resumes"`
  - `SEEN_PATH = "seen.json"`
  - `LANDING_URL = "https://www.newgrad-jobs.com/"`
  - Airtable request headers: `x-airtable-application-id: <appId>`, `x-requested-with: XMLHttpRequest`, `x-time-zone: America/Los_Angeles`, `x-user-locale: en`, `User-Agent: Mozilla/5.0`
  - DeepSeek: `POST https://api.deepseek.com/chat/completions`, model `deepseek-chat`.
  - Resend: `POST https://api.resend.com/emails`.
- Times parsed from jobright (`publishTime` / `datePosted`, naive `YYYY-MM-DD HH:MM:SS`) are treated as UTC.
- Tests never make live network calls and never require real API keys — all HTTP is mocked or fed from committed fixtures.

---

### Task 1: Project scaffolding + `Job` model

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `job_finder/__init__.py`
- Create: `job_finder/models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `job_finder.models.Job` — a dataclass with fields
  `id: str, title: str, company: str, location: str, salary: str,
  qualifications: str, work_model: str, jobright_url: str, date: str,
  posted_at: datetime | None = None`.

- [ ] **Step 1: Add dev/runtime deps + gitignore secrets**

Add `python-dotenv` to runtime deps and a `pytest` dev group. Edit `pyproject.toml` dependencies list to:

```toml
dependencies = [
    "requests>=2.34.2",
    "python-dotenv>=1.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
]
```

Append to `.gitignore`:

```
# Secrets & local state
.env
seen.json
```

Then sync:

```bash
uv sync --dev
```

Expected: resolves and installs pytest + python-dotenv.

- [ ] **Step 2: Write the failing test**

Create `tests/__init__.py` (empty). Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'job_finder'`.

- [ ] **Step 4: Write minimal implementation**

Create `job_finder/__init__.py` (empty). Create `job_finder/models.py`:

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    salary: str
    qualifications: str
    work_model: str
    jobright_url: str
    date: str
    posted_at: datetime | None = None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .gitignore job_finder/__init__.py job_finder/models.py tests/__init__.py tests/test_models.py
git commit -m "feat: scaffold job_finder package and Job model"
```

---

### Task 2: `state.py` — seen-links persistence

**Files:**
- Create: `job_finder/state.py`
- Create: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `load_seen(path: str) -> set[str]` — returns `set()` if file missing.
  - `save_seen(path: str, ids: set[str]) -> None` — writes a sorted JSON list.

- [ ] **Step 1: Write the failing test**

Create `tests/test_state.py`:

```python
from job_finder.state import load_seen, save_seen


def test_load_missing_file_returns_empty(tmp_path):
    assert load_seen(str(tmp_path / "nope.json")) == set()


def test_save_then_load_round_trips(tmp_path):
    p = str(tmp_path / "seen.json")
    save_seen(p, {"b", "a", "c"})
    assert load_seen(p) == {"a", "b", "c"}


def test_saved_file_is_sorted_list(tmp_path):
    import json
    p = str(tmp_path / "seen.json")
    save_seen(p, {"b", "a"})
    with open(p) as f:
        assert json.load(f) == ["a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'job_finder.state'`.

- [ ] **Step 3: Write minimal implementation**

Create `job_finder/state.py`:

```python
import json
import os


def load_seen(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return set(json.load(f))


def save_seen(path: str, ids: set[str]) -> None:
    with open(path, "w") as f:
        json.dump(sorted(ids), f, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add job_finder/state.py tests/test_state.py
git commit -m "feat: add seen-links state persistence"
```

---

### Task 3: `source.py` — discover embed + parse Airtable rows

**Files:**
- Create: `job_finder/source.py`
- Create: `tests/fixtures/landing_snippet.html`
- Create: `tests/fixtures/airtable_rows.json`
- Create: `tests/test_source.py`

**Interfaces:**
- Consumes: `job_finder.models.Job`.
- Produces:
  - `discover_swe_embed(html: str) -> tuple[str, str]` — returns `(app_id, share_id)` parsed from the `/us/swe` tile's `airtable-link`.
  - `parse_jobs(payload: dict) -> list[Job]` — maps `readSharedViewData` JSON to `Job`s (`posted_at` left `None`).
  - `fetch_landing() -> str` — GET `LANDING_URL` (network).
  - `fetch_rows(app_id: str, share_id: str) -> dict` — fetch embed page, extract signed `urlWithParams`, call `readSharedViewData`, return parsed JSON (network).
  - `get_jobs() -> list[Job]` — compose the three above (network).

- [ ] **Step 1: Create fixtures**

Create `tests/fixtures/landing_snippet.html` (the exact tile shape from the live site):

```html
<div role="listitem" class="collection-item-3 w-dyn-item"><h2 data-job-path="/us/swe" airtable-link="https://airtable.com/embed/appjDG7vmPOm1pO7S/shr763VHjlzPBDCgN" class="airtable-link airtable-trigger">💻 Software Engineering</h2></div>
<div role="listitem" class="collection-item-3 w-dyn-item"><h2 data-job-path="/us/data_analysis" airtable-link="https://airtable.com/embed/appZ5SmkwkcW7Xd8C/shrXXXX" class="airtable-link airtable-trigger">📈 Data Analyst</h2></div>
```

Create `tests/fixtures/airtable_rows.json` (trimmed to the real nested schema, two rows):

```json
{
  "data": {
    "table": {
      "columns": [
        {"id": "fldMZwgmYAKznRUo6", "name": "Position Title", "type": "multilineText"},
        {"id": "fldbDjG5x0hw8Uuk8", "name": "Date", "type": "multilineText"},
        {"id": "fldhbYjhYPgayPoKp", "name": "Apply", "type": "button"},
        {"id": "fldcOSYUg4vWoPs5A", "name": "Work Model", "type": "select",
         "typeOptions": {"choices": {"sel3A6LbHGXxWf5zG": {"id": "sel3A6LbHGXxWf5zG", "name": "Onsite"}}}},
        {"id": "fldiPwR9Nhy5OjxDb", "name": "Location", "type": "multilineText"},
        {"id": "fldvfYMUzoI9D5ens", "name": "Company", "type": "multilineText"},
        {"id": "fldf2yoebT7ltpDIp", "name": "Salary", "type": "multilineText"},
        {"id": "fldjaERUKVKmOGbw2", "name": "Qualifications", "type": "multilineText"}
      ],
      "rows": [
        {
          "id": "rec1",
          "createdTime": "2026-07-13T18:57:22.000Z",
          "cellValuesByColumnId": {
            "fldMZwgmYAKznRUo6": "Junior Data Engineer",
            "fldbDjG5x0hw8Uuk8": "2026-07-13",
            "fldhbYjhYPgayPoKp": {"label": "👉 Apply", "url": "https://jobright.ai/jobs/info/6a550bec268af95237be8d61?utm_source=1100&utm_campaign=Software Engineering"},
            "fldcOSYUg4vWoPs5A": "sel3A6LbHGXxWf5zG",
            "fldiPwR9Nhy5OjxDb": "Plano, TX, United States",
            "fldvfYMUzoI9D5ens": "Tata Consultancy Services",
            "fldf2yoebT7ltpDIp": "$80,000-$100,000 /yr",
            "fldjaERUKVKmOGbw2": "ETL, SQL, Python, Snowflake, DBT"
          }
        },
        {
          "id": "rec2",
          "createdTime": "2026-07-13T18:57:25.000Z",
          "cellValuesByColumnId": {
            "fldMZwgmYAKznRUo6": "AI Agent Engineer",
            "fldbDjG5x0hw8Uuk8": "2026-07-12",
            "fldhbYjhYPgayPoKp": {"label": "👉 Apply", "url": "https://jobright.ai/jobs/info/68abc0000000000000000001"},
            "fldcOSYUg4vWoPs5A": "sel3A6LbHGXxWf5zG",
            "fldiPwR9Nhy5OjxDb": "New York, NY, United States",
            "fldvfYMUzoI9D5ens": "Acme AI",
            "fldf2yoebT7ltpDIp": "$150,000 /yr",
            "fldjaERUKVKmOGbw2": "LangGraph, Python, RAG, agentic pipelines"
          }
        }
      ]
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_source.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_source.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'job_finder.source'`.

- [ ] **Step 4: Write minimal implementation**

Create `job_finder/source.py`:

```python
import json
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
        r'data-job-path="/us/swe"[^>]*airtable-link="https://airtable\.com/embed/(app\w+)/(shr\w+)"',
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_source.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add job_finder/source.py tests/test_source.py tests/fixtures/landing_snippet.html tests/fixtures/airtable_rows.json
git commit -m "feat: discover SWE embed and parse Airtable job rows"
```

---

### Task 4: `freshness.py` — jobright posting time + 4h window

**Files:**
- Create: `job_finder/freshness.py`
- Create: `tests/fixtures/jobright_snippet.html`
- Create: `tests/test_freshness.py`

**Interfaces:**
- Consumes: `job_finder.models.Job`.
- Produces:
  - `parse_posted_at(html: str) -> datetime | None` — reads `publishTime` (fallback `datePosted`), returns a UTC-aware datetime or `None`.
  - `fetch_posted_at(url: str) -> datetime | None` — GET the jobright page, then `parse_posted_at` (network).
  - `within_last(jobs: list[Job], hours: int, now: datetime | None = None) -> list[Job]` — keeps jobs whose `posted_at` is within the window; drops `None`.

- [ ] **Step 1: Create fixture**

Create `tests/fixtures/jobright_snippet.html`:

```html
<script>window.__x = {"datePosted":"2026-07-13 17:02:34","workModel":"Onsite","publishTime":"2026-07-13 17:02:34"}</script>
<span class="index_publish-time__I31em"> · 2 hours ago</span>
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_freshness.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_freshness.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'job_finder.freshness'`.

- [ ] **Step 4: Write minimal implementation**

Create `job_finder/freshness.py`:

```python
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
```

Note: `publishTime` appears before `datePosted` in some pages and vice-versa; the alternation matches whichever comes first, and both carry the same value in practice.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_freshness.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add job_finder/freshness.py tests/test_freshness.py tests/fixtures/jobright_snippet.html
git commit -m "feat: parse jobright posting time and filter to last N hours"
```

---

### Task 5: `matcher.py` — DeepSeek keep/drop decision

**Files:**
- Create: `job_finder/matcher.py`
- Create: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `job_finder.models.Job`.
- Produces:
  - `Decision` dataclass: `keep: bool, reason: str`.
  - `load_resumes(resume_dir: str) -> list[str]` — reads every `*.md` file's text.
  - `build_messages(job: Job, resumes: list[str]) -> list[dict]` — DeepSeek chat messages encoding the keep rule.
  - `keep(job: Job, resumes: list[str], api_key: str) -> Decision` — calls DeepSeek, parses the JSON verdict; on any error returns `Decision(False, "<error text>")`.
  - `_call_deepseek(messages: list[dict], api_key: str) -> str` — POST to DeepSeek, return the assistant message content (network; mocked in tests).

- [ ] **Step 1: Write the failing test**

Create `tests/test_matcher.py`:

```python
from unittest.mock import patch

from job_finder.models import Job
from job_finder.matcher import Decision, load_resumes, keep


def _job():
    return Job(id="a", title="AI Agent Engineer", company="Acme",
               location="New York, NY, United States", salary="$150k",
               qualifications="LangGraph, RAG", work_model="Onsite",
               jobright_url="https://jobright.ai/jobs/info/a", date="2026-07-13")


def test_load_resumes_reads_markdown(tmp_path):
    (tmp_path / "general.md").write_text("# Resume\nPython, FastAPI")
    (tmp_path / "notes.txt").write_text("ignore me")
    resumes = load_resumes(str(tmp_path))
    assert len(resumes) == 1
    assert "FastAPI" in resumes[0]


def test_keep_true_on_positive_verdict():
    with patch("job_finder.matcher._call_deepseek",
               return_value='{"keep": true, "reason": "agentic AI role"}'):
        d = keep(_job(), ["Python, FastAPI"], "key")
    assert isinstance(d, Decision)
    assert d.keep is True
    assert "agentic" in d.reason.lower()


def test_keep_false_on_negative_verdict():
    with patch("job_finder.matcher._call_deepseek",
               return_value='{"keep": false, "reason": "no fit"}'):
        d = keep(_job(), ["Java only"], "key")
    assert d.keep is False


def test_keep_handles_fenced_json():
    with patch("job_finder.matcher._call_deepseek",
               return_value='```json\n{"keep": true, "reason": "NYC"}\n```'):
        d = keep(_job(), ["x"], "key")
    assert d.keep is True


def test_keep_drops_on_unparseable_response():
    with patch("job_finder.matcher._call_deepseek", return_value="not json"):
        d = keep(_job(), ["x"], "key")
    assert d.keep is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_matcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'job_finder.matcher'`.

- [ ] **Step 3: Write minimal implementation**

Create `job_finder/matcher.py`:

```python
import glob
import json
import os
import re
from dataclasses import dataclass

import requests

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = (
    "You are a job-fit filter for a new-grad software engineer. "
    "Given the candidate's resumes and one job posting, decide whether to KEEP it. "
    "KEEP the job if ANY of these is true: "
    "(1) the job is a good fit for the skills in ANY resume; "
    "(2) the job location is in New York City (NYC); "
    "(3) the job is an agentic AI engineering role. "
    'Respond with ONLY a JSON object: {"keep": <true|false>, "reason": "<short reason>"}. '
    "No prose, no markdown."
)


@dataclass
class Decision:
    keep: bool
    reason: str


def load_resumes(resume_dir: str) -> list[str]:
    texts = []
    for path in sorted(glob.glob(os.path.join(resume_dir, "*.md"))):
        with open(path) as f:
            texts.append(f.read())
    return texts


def build_messages(job, resumes: list[str]) -> list[dict]:
    resume_block = "\n\n---\n\n".join(resumes)
    job_block = (
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location}\n"
        f"Work Model: {job.work_model}\n"
        f"Salary: {job.salary}\n"
        f"Qualifications:\n{job.qualifications}"
    )
    user = f"RESUMES:\n{resume_block}\n\n=====\n\nJOB POSTING:\n{job_block}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _call_deepseek(messages: list[dict], api_key: str) -> str:
    resp = requests.post(
        DEEPSEEK_URL,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": messages,
              "temperature": 0, "stream": False},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON in response: {text!r}")
    return json.loads(m.group(0))


def keep(job, resumes: list[str], api_key: str) -> Decision:
    try:
        raw = _call_deepseek(build_messages(job, resumes), api_key)
        data = _extract_json(raw)
        return Decision(bool(data.get("keep")), str(data.get("reason", "")))
    except Exception as e:  # network / parse errors -> drop, don't crash the run
        return Decision(False, f"error: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_matcher.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add job_finder/matcher.py tests/test_matcher.py
git commit -m "feat: add DeepSeek keep/drop job matcher"
```

---

### Task 6: `emailer.py` — Resend digest

**Files:**
- Create: `job_finder/emailer.py`
- Create: `tests/test_emailer.py`

**Interfaces:**
- Consumes: `job_finder.models.Job`.
- Produces:
  - `build_digest(jobs: list[tuple[Job, str]]) -> str` — HTML for a list of `(job, reason)` pairs.
  - `send(html: str, subject: str, to: str, sender: str, api_key: str) -> None` — POST to Resend, raise on HTTP error (network; mocked in tests).

- [ ] **Step 1: Write the failing test**

Create `tests/test_emailer.py`:

```python
from unittest.mock import patch, MagicMock

from job_finder.models import Job
from job_finder.emailer import build_digest, send


def _job():
    return Job(id="a", title="AI Agent Engineer", company="Acme",
               location="New York, NY", salary="$150k", qualifications="q",
               work_model="Onsite", jobright_url="https://jobright.ai/jobs/info/a",
               date="2026-07-13")


def test_build_digest_contains_link_and_fields():
    html = build_digest([(_job(), "agentic AI role")])
    assert "https://jobright.ai/jobs/info/a" in html
    assert "AI Agent Engineer" in html
    assert "Acme" in html
    assert "agentic AI role" in html


def test_send_posts_to_resend():
    fake = MagicMock()
    fake.raise_for_status.return_value = None
    with patch("job_finder.emailer.requests.post", return_value=fake) as post:
        send("<p>hi</p>", "subj", "to@x.com", "from@y.com", "key")
    args, kwargs = post.call_args
    assert args[0] == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"] == "Bearer key"
    assert kwargs["json"]["to"] == "to@x.com"
    assert kwargs["json"]["from"] == "from@y.com"
    assert kwargs["json"]["subject"] == "subj"
    assert kwargs["json"]["html"] == "<p>hi</p>"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_emailer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'job_finder.emailer'`.

- [ ] **Step 3: Write minimal implementation**

Create `job_finder/emailer.py`:

```python
import html as _html

import requests

RESEND_URL = "https://api.resend.com/emails"


def build_digest(jobs: list[tuple]) -> str:
    rows = []
    for job, reason in jobs:
        rows.append(
            "<li style='margin-bottom:14px'>"
            f"<a href='{_html.escape(job.jobright_url)}'>"
            f"<strong>{_html.escape(job.title)}</strong></a>"
            f" — {_html.escape(job.company)}<br>"
            f"<small>{_html.escape(job.location)} · "
            f"{_html.escape(job.work_model)} · {_html.escape(job.salary)}</small><br>"
            f"<em>{_html.escape(reason)}</em>"
            "</li>"
        )
    return (
        f"<p>{len(jobs)} new software job match(es):</p>"
        f"<ul>{''.join(rows)}</ul>"
    )


def send(html: str, subject: str, to: str, sender: str, api_key: str) -> None:
    resp = requests.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"from": sender, "to": to, "subject": subject, "html": html},
        timeout=30,
    )
    resp.raise_for_status()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_emailer.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add job_finder/emailer.py tests/test_emailer.py
git commit -m "feat: add Resend digest builder and sender"
```

---

### Task 7: `main.py` orchestration + README

**Files:**
- Create: `job_finder/main.py`
- Modify: `main.py` (delegate to the package entrypoint)
- Modify: `README.md`
- Create: `tests/test_main.py`

**Interfaces:**
- Consumes: `source.get_jobs`, `freshness.fetch_posted_at` / `within_last`, `matcher.load_resumes` / `keep`, `emailer.build_digest` / `send`, `state.load_seen` / `save_seen`.
- Produces: `run(now: datetime | None = None) -> int` — executes the pipeline, returns the count of jobs emailed. `main() -> None` — loads `.env`, checks keys, calls `run()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_main.py`. It patches every network boundary so the pipeline runs offline, and verifies today-filter + dedup + email + state update:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL — `AttributeError`/`ImportError` (no `run` in `job_finder.main`).

- [ ] **Step 3: Write minimal implementation**

Create `job_finder/main.py`:

```python
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from job_finder import source, freshness, matcher, emailer, state

RECIPIENT = "avashraj328@outlook.com"
SENDER = "onboarding@resend.dev"
FRESH_HOURS = 4
RESUME_DIR = "resumes"
SEEN_PATH = "seen.json"

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")


def run(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()

    all_jobs = source.get_jobs()
    print(f"fetched: {len(all_jobs)}")

    today_jobs = [j for j in all_jobs if j.date == today]
    print(f"today ({today}): {len(today_jobs)}")

    seen = state.load_seen(SEEN_PATH)
    unseen = [j for j in today_jobs if j.id not in seen]
    print(f"unseen: {len(unseen)}")

    for j in unseen:
        try:
            j.posted_at = freshness.fetch_posted_at(j.jobright_url)
        except Exception as e:
            print(f"  posted_at fail {j.id}: {e}")
            j.posted_at = None
    fresh = freshness.within_last(unseen, FRESH_HOURS, now=now)
    print(f"fresh (<= {FRESH_HOURS}h): {len(fresh)}")

    resumes = matcher.load_resumes(RESUME_DIR)
    kept: list[tuple] = []
    for j in fresh:
        d = matcher.keep(j, resumes, DEEPSEEK_API_KEY)
        if d.keep:
            kept.append((j, d.reason))
    print(f"kept: {len(kept)}")

    if kept:
        html = emailer.build_digest(kept)
        subject = f"{len(kept)} new SWE job match(es) — {today}"
        emailer.send(html, subject, RECIPIENT, SENDER, RESEND_API_KEY)
        seen |= {j.id for j, _ in kept}
        state.save_seen(SEEN_PATH, seen)
        print(f"emailed: {len(kept)}")
    else:
        print("emailed: 0 (no send)")

    return len(kept)


def main() -> None:
    missing = [k for k, v in (("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY),
                              ("RESEND_API_KEY", RESEND_API_KEY)) if not v]
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)} (set them in .env)")
    run()


if __name__ == "__main__":
    main()
```

Replace the contents of the top-level `main.py` with a thin delegator:

```python
from job_finder.main import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: all tests pass (models, state, source, freshness, matcher, emailer, main).

- [ ] **Step 6: Write README**

Replace `README.md` with:

````markdown
# job-finder

Scrapes today's software-engineering jobs from newgrad-jobs.com, keeps only
those posted in the last 4 hours that fit (skill match to any resume in
`resumes/`, OR NYC location, OR agentic-AI role), and emails the jobright
links via Resend.

## Setup

```bash
uv sync --dev
cp .env.example .env   # then fill in DEEPSEEK_API_KEY and RESEND_API_KEY
```

## Run

```bash
uv run python main.py
```

State is kept in `seen.json` so re-runs never re-email a job.

> **Note:** the sender is `onboarding@resend.dev` (Resend sandbox), which only
> delivers to the email that owns your Resend account. To send elsewhere,
> verify a domain in Resend and change `SENDER` in `job_finder/main.py`.

## Run every 4 hours (macOS launchd)

Create `~/Library/LaunchAgents/com.avash.jobfinder.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.avash.jobfinder</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/uv</string>
    <string>run</string>
    <string>python</string>
    <string>main.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/avashadhikari/Projects/job-finder</string>
  <key>StartInterval</key><integer>14400</integer>
  <key>StandardOutPath</key><string>/tmp/jobfinder.log</string>
  <key>StandardErrorPath</key><string>/tmp/jobfinder.err</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.avash.jobfinder.plist
```

(Verify the `uv` path with `which uv`.)
````

- [ ] **Step 7: Commit**

```bash
git add job_finder/main.py main.py README.md tests/test_main.py
git commit -m "feat: orchestrate pipeline in main and document run/scheduling"
```

---

## Self-Review

**Spec coverage:**
- Source discovery + Airtable fetch/parse → Task 3. ✓
- No-timestamp finding / jobright `publishTime` freshness → Task 4. ✓
- Today filter, dedup, 4h window, keep-rule wiring, skip-empty-send, per-stage logs → Task 7 `run()`. ✓
- DeepSeek keep rule (skill OR NYC OR agentic-AI) → Task 5 system prompt + tests. ✓
- Resend digest to outlook, sandbox caveat → Task 6 + README. ✓
- `seen.json` state → Task 2, wired in Task 7. ✓
- Config/env, fail-fast on missing keys → Task 7 `main()`. ✓
- Error handling (per-job skip, retries) → per-job try/except in Task 7 and defensive parse in Task 5; note: simple try/except used instead of a retry library to avoid a new dependency (YAGNI). ✓
- Testing with fixtures + mocks, no live keys → every task. ✓
- Scheduling snippet, not auto-installed → README in Task 7. ✓

**Placeholder scan:** No TBD/TODO; every code + test step is complete. ✓

**Type consistency:** `Job` fields consistent across tasks; `Decision(keep, reason)` used identically in Tasks 5 and 7; `build_digest` consumes `list[(Job, reason)]` produced by `run()`; `within_last(jobs, hours, now)` and `fetch_posted_at(url)` signatures match their callers. ✓

**Deviation from spec:** Spec mentioned optional batching of DeepSeek calls and exponential-backoff retries. Plan uses one call per job (simpler, reliable JSON) and per-job try/except instead of a backoff library — both within the spec's stated intent (defensive parse, per-job skip, no new heavy deps). No functional gap.
