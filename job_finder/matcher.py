import glob
import json
import os
import re
from dataclasses import dataclass

import requests

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = (
    "You are a STRICT job-fit filter for a new-grad software engineer. "
    "Given the candidate's resumes and one job posting, decide whether to KEEP it. "
    "Each resume is labeled with a NAME. Default to DROP; only KEEP when the "
    "requirements below are clearly met. "
    "HARD REQUIREMENT 1 (seniority, applies first): only KEEP roles that are "
    "new-grad / entry-level or require 0-2 years of experience. DROP the job if it "
    "is targeted at more senior candidates, e.g. titled Senior/Staff/Principal/Lead/Mgr, "
    "or the qualifications require more than 2 years of professional experience. "
    "If experience is unstated, assume it fits. "
    "HARD REQUIREMENT 2 (skill overlap, applies to EVERY job with no exceptions): "
    "KEEP only if there is CLEAR, EXPLICIT overlap between the concrete skills and "
    "technologies named in the job's qualifications and those named in ANY ONE resume. "
    "An overlap counts ONLY when the SAME skill/technology appears in both the job and "
    "the resume (e.g. the job asks for Python and a resume lists Python). "
    "Do NOT infer, generalize, or treat skills as transferable. Similar, adjacent, or "
    "'related' skills DO NOT count (e.g. Java on the resume does NOT satisfy a C++ "
    "requirement; React does NOT satisfy an Angular requirement; general 'programming' "
    "does NOT satisfy a specific named technology). "
    "If there is no clear, explicit, same-name skill overlap, DROP the job (keep=false), "
    "even for NYC or agentic-AI roles. Location and role type are NOT reasons to keep. "
    'Respond with ONLY a JSON object: '
    '{"keep": <true|false>, "reason": "<short reason naming the overlapping skills>", '
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
