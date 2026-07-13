# job-finder

Scrapes today's software-engineering jobs from newgrad-jobs.com, keeps only
those posted in the last 4 hours that fit (skill match to any resume in
`resumes/`, OR NYC location, OR agentic-AI role), and emails the jobright
links via Resend.

## Setup

```bash
uv sync --dev
cp .env.example .env   # then fill in DEEPSEEK_API_KEY, RESEND_API_KEY, and RECIPIENT_EMAIL
```

## Run

```bash
uv run python main.py
```

State is kept in `seen.json` so re-runs never re-email a job.

> **Note:** the sender is `onboarding@resend.dev` (Resend sandbox), which only
> delivers to the email that owns your Resend account. To send elsewhere,
> verify a domain in Resend and change `SENDER` in `job_finder/main.py`.

Modify system prompt in `job_finder/matcher.py`
