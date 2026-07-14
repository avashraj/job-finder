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
    "Each resume is labeled with a NAME. "
    "KEEP the job if ANY of these is true: "
    "(1) the job is a good fit for the skills in ANY resume; "
    "(2) the job location is in New York City (NYC); "
    "(3) the job is an agentic AI engineering role. "
    'Respond with ONLY a JSON object: '
    '{"keep": <true|false>, "reason": "<short reason>", '
    '"resume": "<NAME of the best-fit resume to apply with>"}. '
    "The resume value MUST be one of the provided resume NAMEs. "
    "No prose, no markdown."
)


@dataclass
class Decision:
    keep: bool
    reason: str
    resume: str = ""


def load_resumes(resume_dir: str) -> list[tuple[str, str]]:
    resumes = []
    for path in sorted(glob.glob(os.path.join(resume_dir, "*.md"))):
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path) as f:
            resumes.append((name, f.read()))
    return resumes


def _named(resumes: list) -> list[tuple[str, str]]:
    out = []
    for r in resumes:
        if isinstance(r, (tuple, list)):
            out.append((str(r[0]), str(r[1])))
        else:
            out.append(("general", str(r)))
    return out


def build_messages(job, resumes: list) -> list[dict]:
    named = _named(resumes)
    resume_block = "\n\n---\n\n".join(
        f"NAME: {name}\n{text}" for name, text in named
    )
    names = ", ".join(name for name, _ in named)
    resume_block = f"Available resume NAMEs: {names}\n\n{resume_block}"
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
        return Decision(bool(data.get("keep")), str(data.get("reason", "")),
                        str(data.get("resume", "")))
    except Exception as e:  # network / parse errors -> drop, don't crash the run
        return Decision(False, f"error: {e}")
