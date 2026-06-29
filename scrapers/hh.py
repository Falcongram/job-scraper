import logging
from typing import List
from curl_cffi import requests
from bs4 import BeautifulSoup
from models import Job
from scrapers.base import BaseScraper
from scrapers.hh_auth import get_valid_token

logger = logging.getLogger(__name__)


def _extract_salary(card) -> str:
    """Ищет зарплату по символу ₽ — data-qa у неё нет, классы нестабильны."""
    for el in card.find_all(["span", "div"]):
        text = el.get_text(strip=True)
        if "₽" in text and len(text) < 80:
            # Убираем частоту выплат если попала в тот же элемент
            return text.split(",")[0].strip()
    return ""


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
}

SCHEDULE_MAP = {
    "fullDay": "Полный день",
    "part": "Частичная занятость",
    "remote": "Удалёнка",
    "flyInFlyOut": "Вахта",
    "flexible": "Гибкий",
}


class HHScraper(BaseScraper):
    BASE_URL = "https://hh.ru/search/vacancy"

    def parse(self) -> List[Job]:
        cfg = self.config["sources"]["hh"]
        if cfg.get("use_api"):
            client_id = cfg.get("client_id", "")
            client_secret = cfg.get("client_secret", "")
            if not client_id or not client_secret:
                logger.warning("hh.ru API: нет client_id/client_secret в secrets.yaml, fallback на HTML")
                return self._parse_html()
            user_agent = cfg.get("user_agent", "job-scraper/1.0")
            token = get_valid_token(client_id, client_secret, user_agent)
            return self._parse_api(token, user_agent)
        return self._parse_html()

    # ------------------------------------------------------------------ HTML
    def _parse_html(self) -> List[Job]:
        jobs: List[Job] = []
        keywords = self.config["search"]["keywords"]
        schedules = self._build_schedule_params()
        days_back = self.config["search"].get("days_back", 0)

        for city in self.cities:
            for keyword in keywords:
                params = {
                    "text": keyword,
                    "area": city["hh_area_id"],
                    "schedule": "remote",
                    "employment": schedules,
                    "per_page": "50",
                    "order_by": "publication_time",
                }
                if days_back:
                    from datetime import datetime, timedelta
                    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                    params["date_from"] = date_from
                try:
                    jobs.extend(self._fetch_page(params, city["name"]))
                except Exception as e:
                    logger.warning("hh.ru HTML: %s / %s — %s", city["name"], keyword, e)
        return jobs

    def _fetch_page(self, params: dict, city_name: str) -> List[Job]:
        resp = requests.get(
            self.BASE_URL,
            params=params,
            headers=HEADERS,
            impersonate="chrome124",
            timeout=15,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return self._extract_jobs(soup, city_name)

    def _extract_jobs(self, soup: BeautifulSoup, city_name: str) -> List[Job]:
        jobs = []
        for card in soup.select("div[data-qa='vacancy-serp__vacancy']"):
            try:
                title_el = card.select_one("a[data-qa='serp-item__title']")
                company_el = card.select_one("[data-qa='vacancy-serp__vacancy-employer']")
                schedule_el = card.select_one("[data-qa='vacancy-label-work-schedule-remote']")

                if not title_el:
                    continue

                raw_url = title_el["href"].split("?")[0]
                # Нормализуем поддомен: spb.hh.ru → hh.ru
                url = raw_url.replace("://spb.hh.ru", "://hh.ru") \
                             .replace("://moscow.hh.ru", "://hh.ru") \
                             .replace("://tyumen.hh.ru", "://hh.ru")
                salary = _extract_salary(card)

                jobs.append(Job(
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else "",
                    url=url,
                    source="hh.ru",
                    city=city_name,
                    schedule=schedule_el.get_text(strip=True) if schedule_el else "",
                    salary=salary,
                ))
            except Exception as e:
                logger.debug("hh card parse error: %s", e)
        return jobs

    # ------------------------------------------------------------------ API
    def _parse_api(self, token: str, user_agent: str) -> List[Job]:
        import requests as req
        jobs: List[Job] = []
        keywords = self.config["search"]["keywords"]
        employment = self._build_schedule_params()

        for city in self.cities:
            for keyword in keywords:
                params = {
                    "text": keyword,
                    "area": city["hh_area_id"],
                    "schedule": "remote",
                    "per_page": 50,
                }
                if employment:
                    params["employment"] = employment
                try:
                    resp = req.get(
                        "https://api.hh.ru/vacancies",
                        params=params,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "HH-User-Agent": user_agent,
                        },
                        timeout=15,
                    )
                    resp.raise_for_status()
                    for item in resp.json().get("items", []):
                        salary = ""
                        if item.get("salary"):
                            s = item["salary"]
                            parts = []
                            if s.get("from"):
                                parts.append(f"от {s['from']}")
                            if s.get("to"):
                                parts.append(f"до {s['to']}")
                            salary = " ".join(parts) + f" {s.get('currency', '')}"

                        jobs.append(Job(
                            title=item["name"],
                            company=item.get("employer", {}).get("name", ""),
                            url=item["alternate_url"],
                            source="hh.ru",
                            city=city["name"],
                            schedule=item.get("schedule", {}).get("name", ""),
                            salary=salary.strip(),
                        ))
                except Exception as e:
                    logger.warning("hh.ru API: %s / %s — %s", city["name"], keyword, e)
        return jobs

    def _build_schedule_params(self) -> List[str]:
        sched = self.config["sources"]["hh"].get("schedule", {})
        result = []
        if sched.get("full_time"):
            result.append("full")
        if sched.get("part_time"):
            result.append("part")
        return result
