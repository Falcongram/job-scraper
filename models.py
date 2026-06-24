from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    title: str
    company: str
    url: str
    source: str
    city: str = ""
    schedule: str = ""
    salary: str = ""
    found_at: datetime = field(default_factory=datetime.utcnow)

    def __hash__(self):
        return hash(self.url)
