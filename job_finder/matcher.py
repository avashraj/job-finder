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
