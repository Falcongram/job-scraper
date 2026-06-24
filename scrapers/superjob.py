import logging
import requests
from typing import List
from datetime import datetime, timedelta, timezone
from models import Job
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://api.superjob.ru/2.0/vacancies/"

_REMOTE_MARKERS = ("дистанционн", "удалённ", "удаленн", "remote", "дистанц")


class SuperjobScraper(BaseScraper):

    def parse(self) -> List[Job]:
        api_key = self.config.get("sources", {}).get("superjob", {}).get("api_key", "")
        if not api_key:
            logger.warning("superjob.ru: api_key не задан в secrets.yaml — пропускаем")
            return []

        keywords = self.config["search"]["keywords"]
        days_back = self.config["search"].get("days_back", 0)
        cutoff = None
        if days_back:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        jobs: List[Job] = []
        for keyword in keywords:
            try:
                jobs.extend(self._fetch(keyword, api_key, cutoff))
            except Exception as e:
                logger.warning("superjob.ru: %s — %s", keyword, e)
        return jobs

    def _fetch(self, keyword: str, api_key: str, cutoff) -> List[Job]:
        params = {
            "keyword": keyword,
            "count": 100,
            "page": 0,
            "order_field": "date",
        }
        headers = {"X-Api-App-Id": api_key}
        resp = requests.get(API_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()

        result = []
        for v in resp.json().get("objects", []):
            if not self._is_remote(v):
                continue
            if cutoff:
                ts = v.get("date_published")
                if ts:
                    pub = datetime.fromtimestamp(ts, tz=timezone.utc)
                    if pub < cutoff:
                        continue
            result.append(self._map(v))
        return result

    def _is_remote(self, v: dict) -> bool:
        # Проверяем type_of_work и текст описания
        wow = (v.get("type_of_work") or {}).get("title", "").lower()
        desc = (v.get("candidat") or v.get("work") or "").lower()
        text = wow + " " + desc
        return any(m in text for m in _REMOTE_MARKERS)

    def _map(self, v: dict) -> Job:
        s_from = v.get("payment_from") or 0
        s_to = v.get("payment_to") or 0
        currency = v.get("currency", "RUB")
        parts = []
        if s_from:
            parts.append(f"от {s_from}")
        if s_to:
            parts.append(f"до {s_to}")
        salary = (" ".join(parts) + f" {currency}").strip() if parts else ""

        town = (v.get("town") or {}).get("title", "")

        return Job(
            title=v.get("profession", ""),
            company=v.get("firm_name", ""),
            url=v.get("link", ""),
            source="superjob.ru",
            city=town,
            schedule=(v.get("type_of_work") or {}).get("title", ""),
            salary=salary,
        )
