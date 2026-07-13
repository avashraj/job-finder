from dataclasses import dataclass
from datetime import datetime


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    salary: str
    qualifications: str
    work_model: str
    jobright_url: str
    date: str
    posted_at: datetime | None = None
