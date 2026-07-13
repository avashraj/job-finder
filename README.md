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
