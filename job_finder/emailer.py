import html as _html

import requests

RESEND_URL = "https://api.resend.com/emails"


def build_digest(jobs: list[tuple]) -> str:
    rows = []
    for item in jobs:
        job, reason = item[0], item[1]
        resume = item[2] if len(item) > 2 else ""
        resume_line = (
            f"<br><strong>Resume to use:</strong> {_html.escape(resume)}"
            if resume else ""
        )
        rows.append(
            "<li style='margin-bottom:14px'>"
            f"<a href='{_html.escape(job.jobright_url)}'>"
            f"<strong>{_html.escape(job.title)}</strong></a>"
            f" — {_html.escape(job.company)}<br>"
            f"<small>{_html.escape(job.location)} · "
            f"{_html.escape(job.work_model)} · {_html.escape(job.salary)}</small><br>"
            f"<em>{_html.escape(reason)}</em>"
            f"{resume_line}"
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
