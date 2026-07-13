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
