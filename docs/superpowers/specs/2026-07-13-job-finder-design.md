# Job Finder — Design Spec

Date: 2026-07-13
Status: Approved

## Goal

Scrape software-engineering jobs from `newgrad-jobs.com`, keep only fresh
(posted within the last 4 hours) postings that are a good fit, and email the
`jobright.ai/jobs/info/<id>` links to `avashraj328@outlook.com`.

A job is **kept** when an LLM (DeepSeek) judges any of:

1. Good skill fit against any of the three resumes in `resumes/`, **OR**
2. Location is NYC (New York City), **OR**
3. Role is an agentic-AI-engineering job.

## Source Investigation (established facts)

`newgrad-jobs.com` is a Webflow site. Jobs are **not** in the landing-page
HTML. Each job category is a tile with:

```
<h2 data-job-path="/us/swe" airtable-link="https://airtable.com/embed/appjDG7vmPOm1pO7S/shr763VHjlzPBDCgN">💻 Software Engineering</h2>
```

The Software Engineering tile points at an **Airtable shared view**. Job data
is served by Airtable's `readSharedViewData` endpoint.

### Fetching Airtable data

1. GET the embed page `https://airtable.com/embed/<appId>/<shareId>`.
2. Extract `urlWithParams` from the page (unicode-escaped JS string). It is a
   path like
   `/v0.3/view/<viewId>/readSharedViewData?stringifiedObjectParams=...&requestId=...&accessPolicy=...`.
   `accessPolicy` is a signed token — **re-fetch the embed page each run** to
   get a valid one (do not hardcode/cache it).
3. GET `https://airtable.com` + `urlWithParams` with headers:
   - `x-airtable-application-id: <appId>`
   - `x-requested-with: XMLHttpRequest`
   - `x-time-zone: America/Los_Angeles`
   - `x-user-locale: en`
   - `User-Agent: Mozilla/5.0`
4. Response JSON → `data.table.rows` (nested response format). Confirmed
   returns all rows (1421 at investigation time).

### Row schema (`cellValuesByColumnId`)

| Column id            | Name             | Type          | Use                              |
|----------------------|------------------|---------------|----------------------------------|
| `fldMZwgmYAKznRUo6`  | Position Title   | multilineText | title                            |
| `fldbDjG5x0hw8Uuk8`  | Date             | multilineText | posting **date** only, e.g. `2026-07-13` |
| `fldhbYjhYPgayPoKp`  | Apply            | button        | `.url` = jobright link           |
| `fldcOSYUg4vWoPs5A`  | Work Model       | select id     | work model (id → label via columns) |
| `fldiPwR9Nhy5OjxDb`  | Location         | multilineText | location (NYC check)             |
| `fldvfYMUzoI9D5ens`  | Company          | multilineText | company                          |
| `fldf2yoebT7ltpDIp`  | Salary           | multilineText | salary                           |
| `fldjaERUKVKmOGbw2`  | Qualifications   | multilineText | skills text (LLM match)          |

Column ids are stable identifiers but MUST be resolved by **name** from
`data.table.columns` at runtime (do not trust ids to never change). Map select
ids to labels via each column's `typeOptions.choices`.

The Apply button value shape:

```json
{"label": "👉 Apply", "url": "https://jobright.ai/jobs/info/<id>?utm_source=..."}
```

Strip query params → canonical `https://jobright.ai/jobs/info/<id>`. The `<id>`
is the dedup key.

### Freshness — critical finding

There is **no per-job posting timestamp in the Airtable data**:

- `Date` is `multilineText`, date-only (`2026-07-13`), no time.
- Row `createdTime` is useless for age: the whole board is regenerated in bulk
  each sync (all 1421 rows created within an 87-second window), so it reflects
  the last refresh, not when a job was posted.

The authoritative posting time lives on the **jobright job page**, embedded in
page JSON:

```
"datePosted":"2026-07-13 17:02:34"
"publishTime":"2026-07-13 17:02:34"   → rendered as "· 2 hours ago"
```

So "last 4 hours" is computed by fetching each candidate's jobright page and
parsing `publishTime` (fallback `datePosted`). Times are naive
`YYYY-MM-DD HH:MM:SS`; treat as UTC (matches the "N hours ago" the site shows
relative to now-UTC). Keep when `publishTime >= now_utc − 4h`.

## Pipeline

```
newgrad-jobs.com landing page
        │  regex /us/swe airtable-link → appId, shareId
        ▼
Airtable embed page ──► urlWithParams (signed) ──► readSharedViewData JSON
        │  parse rows → list[Job]
        ▼
filter Date == today (local run date)
        │
        ▼
drop ids present in seen.json                  (bounds work, prevents resend)
        │
        ▼
for each survivor: GET jobright page → parse publishTime → keep if within 4h
        │
        ▼
DeepSeek batch match vs 3 resumes → keep if (skill fit OR NYC OR agentic-AI)
        │
        ▼
Resend HTML digest → avashraj328@outlook.com   (skip send if 0 kept)
        │
        ▼
append emailed ids → seen.json
```

## Modules

Each module has one purpose, a clear interface, and is unit-testable in
isolation.

- **`job_finder/models.py`** — `Job` dataclass:
  `id, title, company, location, salary, qualifications, work_model,
  jobright_url, posted_at (datetime | None)`.
- **`job_finder/source.py`** — `discover_swe_embed() -> (appId, shareId)`,
  `fetch_rows(appId, shareId) -> list[dict]`, `parse_jobs(payload) -> list[Job]`.
  Owns all Airtable/landing-page HTTP + parsing.
- **`job_finder/freshness.py`** — `fetch_posted_at(jobright_url) -> datetime | None`,
  `within_last(jobs, hours) -> list[Job]`. Owns jobright page fetch + timestamp
  parse.
- **`job_finder/matcher.py`** — `load_resumes(dir) -> list[str]`,
  `keep(job, resumes) -> Decision(keep: bool, reason: str)` via one DeepSeek
  chat call per job (or batched). Owns the prompt + keep rule.
- **`job_finder/emailer.py`** — `build_digest(kept) -> html`,
  `send(html, to) -> None` via Resend REST. Owns email format + send.
- **`job_finder/state.py`** — `load_seen(path) -> set[str]`,
  `save_seen(path, ids) -> None`. `seen.json` is a JSON list of jobright ids.
- **`job_finder/main.py`** — orchestrates the pipeline, logs per-stage counts,
  loads config.

## Config

- `.env` (via `python-dotenv`): `DEEPSEEK_API_KEY`, `RESEND_API_KEY`.
- Constants at top of `main.py`:
  - `RECIPIENT = "avashraj328@outlook.com"`
  - `SENDER = "onboarding@resend.dev"`
  - `FRESH_HOURS = 4`
  - `RESUME_DIR = "resumes"`
  - `SEEN_PATH = "seen.json"`

### Resend sandbox constraint (documented risk)

`onboarding@resend.dev` is Resend's sandbox sender. It delivers **only to the
email address that owns the Resend account**. If `avashraj328@outlook.com` is
not the Resend account email, the send call will fail / not deliver. To lift
this, verify a domain in Resend and change `SENDER`. Recorded, not blocking the
build.

## External APIs

- **DeepSeek** — `POST https://api.deepseek.com/chat/completions`,
  `Authorization: Bearer <DEEPSEEK_API_KEY>`, model `deepseek-chat`. Request a
  strict JSON verdict (`{"keep": bool, "reason": str}`); parse defensively.
- **Resend** — `POST https://api.resend.com/emails`,
  `Authorization: Bearer <RESEND_API_KEY>`, body `{from, to, subject, html}`.

Both called with plain `requests`; no vendor SDKs.

## Error Handling

- Airtable + jobright GETs: retry with exponential backoff (e.g. 3 tries);
  raise a clear error if the source structure can't be parsed (discovery/embed
  regex miss) so a site change is loud, not silent.
- Per-job failures (jobright fetch, timestamp parse, one LLM call): log and
  skip that job — never abort the whole run.
- Missing `DEEPSEEK_API_KEY` / `RESEND_API_KEY`: fail fast at startup with a
  clear message.
- Zero kept jobs: skip the email, log it, still update `seen.json` for the ids
  processed. (Only append ids actually emailed, so a same-day rerun can still
  surface a job if it wasn't emailed.)
- Log per-stage counts: fetched → today → unseen → fresh(4h) → kept → emailed.

## Scheduling

Script is idempotent and safe to run repeatedly (`seen.json` prevents
resends). Run every 4 hours via launchd (macOS) or cron. Provide the
plist/crontab snippet in the repo README; **do not auto-install** a scheduler.

## Testing

- Unit tests per module, no live network/keys.
- Fixtures: saved Airtable `readSharedViewData` JSON and one saved jobright
  page → assert `parse_jobs` and `fetch_posted_at` extract correct fields.
- `matcher`: mock the DeepSeek HTTP call; assert keep rule wiring (skill fit /
  NYC / agentic-AI each independently trigger keep) and defensive JSON parse.
- `emailer`: mock Resend HTTP call; assert digest HTML contains each kept
  job's link + payload shape.
- `state`: round-trip `seen.json` load/save; missing file → empty set.
- `freshness.within_last`: boundary cases around the 4h cutoff; `None`
  `posted_at` is dropped.

## Out of Scope (YAGNI)

- Non-SWE job categories.
- Canada (`/ca/*`) rows.
- A hosted/always-on daemon (use the external scheduler).
- Resume ranking / per-job cover letters — keep/drop only.
