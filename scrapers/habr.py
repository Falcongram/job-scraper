import logging
from typing import List
from curl_cffi import requests
from bs4 import BeautifulSoup
from models import Job
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


class HabrScraper(BaseScraper):
    BASE_URL = "https://career.habr.com/vacancies"

    def parse(self) -> List[Job]:
        jobs: List[Job] = []
        keywords = self.config["search"]["keywords"]
        self._days_back = self.config["search"].get("days_back", 0)

        for keyword in keywords:
            params = {
                "q": keyword,
                "type": "remote",
                "sort": "date",
            }
            try:
                jobs.extend(self._fetch_page(params))
            except Exception as e:
                logger.warning("career.habr.com: %s — %s", keyword, e)
        return jobs

    def _fetch_page(self, params: dict) -> List[Job]:
        resp = requests.get(
            self.BASE_URL,
            params=params,
            headers=HEADERS,
            impersonate="chrome124",
            timeout=15,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return self._extract_jobs(soup)

    def _extract_jobs(self, soup: BeautifulSoup) -> List[Job]:
        from datetime import datetime, timedelta, timezone
        jobs = []
        cutoff = None
        if getattr(self, "_days_back", 0):
            cutoff = datetime.now(timezone.utc) - timedelta(days=self._days_back)

        for card in soup.select("div.vacancy-card"):
            try:
                title_el = card.select_one("a.vacancy-card__title-link")
                company_el = card.select_one("div.vacancy-card__company a")
                salary_el = card.select_one("div.basic-salary")

                if not title_el:
                    continue

                # Фильтр по дате публикации
                if cutoff:
                    time_el = card.select_one("time[datetime]")
                    if time_el:
                        pub = datetime.fromisoformat(time_el["datetime"])
                        if pub < cutoff:
                            continue

                url = "https://career.habr.com" + title_el["href"]

                # Чипы: город (icon-placemark), формат (icon-format)
                chips = card.select("div.chip-with-icon__text")
                icons = card.select("use")
                cities, schedule = [], ""
                for use_el in icons:
                    href = use_el.get("xlink:href", "")
                    chip_text = use_el.find_parent("div", class_="basic-chip")
                    if not chip_text:
                        continue
                    text = chip_text.select_one("div.chip-with-icon__text")
                    if not text:
                        continue
                    if "placemark" in href:
                        cities.append(text.get_text(strip=True))
                    elif "format" in href:
                        schedule = text.get_text(strip=True)

                jobs.append(Job(
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else "",
                    url=url,
                    source="career.habr.com",
                    city=", ".join(cities) if cities else "",
                    schedule=schedule,
                    salary=salary_el.get_text(strip=True) if salary_el else "",
                ))
            except Exception as e:
                logger.debug("habr card parse error: %s", e)
        return jobs
