import logging
import requests
from typing import List
from datetime import datetime, timedelta, timezone
from models import Job
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://opendata.trudvsem.ru/api/v1/vacancies"


class TrudvsemScraper(BaseScraper):

    def parse(self) -> List[Job]:
        jobs: List[Job] = []
        keywords = self.config["search"]["keywords"]

        days_back = self.config["search"].get("days_back", 0)
        cutoff = None
        if days_back:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        for keyword in keywords:
            params = {"text": keyword, "limit": 100, "offset": 0}
            try:
                jobs.extend(self._fetch(params, cutoff))
            except Exception as e:
                logger.warning("trudvsem.ru: %s — %s", keyword, e)
        return jobs

    def _fetch(self, params: dict, cutoff: datetime | None) -> List[Job]:
        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
        vacancies = resp.json().get("results", {}).get("vacancies", [])
        result = []
        for v in vacancies:
            if not self._is_remote(v):
                continue
            if cutoff and not self._is_fresh(v, cutoff):
                continue
            result.append(self._map(v))
        return result

    def _is_fresh(self, v: dict, cutoff: datetime) -> bool:
        vac = v.get("vacancy", {})
        date_str = vac.get("date_modify") or vac.get("creation-date", "")
        if not date_str:
            return True
        try:
            pub = datetime.fromisoformat(date_str)
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            return pub >= cutoff
        except ValueError:
            return True

    def _is_remote(self, v: dict) -> bool:
        vac = v.get("vacancy", {})
        text = " ".join([
            vac.get("employment", "") or "",
            vac.get("schedule", "") or "",
            vac.get("duty", "") or "",
            vac.get("requirements", "") or "",
        ]).lower()
        return "удалённо" in text or "удаленно" in text or "удалённая" in text or "удаленная" in text or "дистанционн" in text

    def _map(self, v: dict) -> Job:
        vac = v.get("vacancy", {})
        company = vac.get("company", {})
        region = vac.get("region", {}).get("name", "")
        salary = vac.get("salary", "") or ""
        if not salary:
            s_min = vac.get("salary_min")
            s_max = vac.get("salary_max")
            parts = []
            if s_min:
                parts.append(f"от {s_min}")
            if s_max:
                parts.append(f"до {s_max}")
            salary = " ".join(parts)

        return Job(
            title=vac.get("job-name", "") or vac.get("typicalPosition", ""),
            company=company.get("name", ""),
            url=vac.get("vac_url", "") or f"https://trudvsem.ru/vacancy/card/{vac.get('id', '')}",
            source="trudvsem.ru",
            city=region,
            schedule=vac.get("employment", ""),
            salary=salary.strip(),
        )
