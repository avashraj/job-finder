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
