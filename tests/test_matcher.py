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
    assert resumes[0][0] == "general"
    assert "FastAPI" in resumes[0][1]


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
