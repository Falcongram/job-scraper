from abc import ABC, abstractmethod
from typing import List
from models import Job


class BaseScraper(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.cities = config["search"]["cities"]

    @abstractmethod
    def parse(self) -> List[Job]:
        """Возвращает список вакансий."""
        ...

    def _normalize_salary(self, raw: str) -> str:
        return raw.strip() if raw else ""
