import logging
import requests
from typing import List
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from models import Job
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://geekjob.ru/vacancies"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


class GeekjobScraper(BaseScraper):

    def parse(self) -> List[Job]:
        days_back = self.config["search"].get("days_back", 0)
        cutoff = None
        if days_back:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        jobs: List[Job] = []
        max_pages = self._get_page_count()
        for page in range(1, max_pages + 1):
            url = BASE_URL if page == 1 else f"{BASE_URL}/{page}"
            try:
                resp = requests.get(url, timeout=15, headers=_HEADERS)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("geekjob.ru page %d: %s", page, e)
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            page_jobs = self._extract(soup, cutoff)
            jobs.extend(page_jobs)
            # Если страница вернула 0 — дальше нет смысла
            if not page_jobs and page > 1:
                break

        logger.info("geekjob.ru: найдено %d вакансий (%d страниц)", len(jobs), max_pages)
        return jobs

    def _get_page_count(self) -> int:
        try:
            resp = requests.get(BASE_URL, timeout=15, headers=_HEADERS)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            pager = soup.select("ul.pagination li a[href]")
            pages = []
            for a in pager:
                href = a.get("href", "")
                # href вида /vacancies/3 или /vacancies/
                parts = href.rstrip("/").split("/")
                if parts and parts[-1].isdigit():
                    pages.append(int(parts[-1]))
            return max(pages) if pages else 1
        except Exception:
            return 1

    def _extract(self, soup: BeautifulSoup, cutoff) -> List[Job]:
        jobs = []
        for card in soup.select("li.collection-item"):
            try:
                if not card.select_one("span.remote-label"):
                    continue

                title_a = card.select_one("p.vacancy-name a") or card.select_one("a.title")
                if not title_a:
                    continue

                title = title_a.get_text(strip=True)
                url = "https://geekjob.ru" + title_a["href"]

                company_el = card.select_one("p.company-name a") or card.select_one("p.company-name")
                company = company_el.get_text(strip=True) if company_el else ""

                salary_el = card.select_one("span.salary")
                salary = salary_el.get_text(strip=True) if salary_el else ""

                if cutoff:
                    time_el = card.select_one("time")
                    if time_el and time_el.get("datetime"):
                        try:
                            pub = datetime.fromisoformat(time_el["datetime"])
                            if pub.tzinfo is None:
                                pub = pub.replace(tzinfo=timezone.utc)
                            if pub < cutoff:
                                continue
                        except ValueError:
                            pass

                jobs.append(Job(
                    title=title,
                    company=company,
                    url=url,
                    source="geekjob.ru",
                    city="",
                    schedule="Удалённо",
                    salary=salary,
                ))
            except Exception as e:
                logger.debug("geekjob card parse error: %s", e)
        return jobs
