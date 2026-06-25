import logging
import re
from abc import abstractmethod
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import curl_cffi.requests as req
from bs4 import BeautifulSoup

from models import Job
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

KNOWN_JOB_SITES = re.compile(
    r"https?://(hh\.ru|career\.habr\.com|superjob\.ru|geekjob\.ru|"
    r"trudvsem\.ru|linkedin\.com|headhunter\.ru|zarplata\.ru|"
    r"rabota\.ru|work\.ua|djinni\.co|jobs\.dou\.ua|getmatch\.ru|"
    r"comeet\.com|greenhouse\.io|lever\.co|ashbyhq\.com|yandex\.ru/jobs)"
)


class BaseTelegramScraper(BaseScraper):
    CHANNEL = ""  # переопределить в подклассе

    def __init__(self, config: dict):
        super().__init__(config)
        self.days_back = config["search"].get("days_back", 7)

    def parse(self) -> List[Job]:
        url = f"https://t.me/s/{self.CHANNEL}"
        r = req.get(url, impersonate="chrome", timeout=15)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "lxml")
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self.days_back)
            if self.days_back > 0
            else None
        )

        jobs = []
        for wrap in soup.select(".tgme_widget_message_wrap"):
            msg = wrap.select_one(".tgme_widget_message[data-post]")
            if not msg:
                continue

            time_el = wrap.select_one("time[datetime]")
            if not time_el:
                continue
            post_date = datetime.fromisoformat(time_el["datetime"])
            if cutoff and post_date < cutoff:
                continue

            data_post = msg["data-post"]
            tg_url = f"https://t.me/{data_post}"

            text_el = wrap.select_one(".tgme_widget_message_text")
            raw_text = text_el.get_text("\n", strip=True) if text_el else ""

            ext_links = [
                a["href"] for a in wrap.select("a[href]")
                if a.get("href", "").startswith("http") and "t.me" not in a["href"]
            ]

            job = self._extract_job(raw_text, ext_links, tg_url, post_date)
            if job:
                jobs.append(job)

        logger.info("t.me/%s: найдено %d вакансий", self.CHANNEL, len(jobs))
        return jobs

    @abstractmethod
    def _extract_job(
        self, text: str, links: List[str], tg_url: str, post_date: datetime
    ) -> Optional[Job]:
        ...

    def _best_link(self, links: List[str], tg_url: str) -> str:
        for link in links:
            if KNOWN_JOB_SITES.search(link):
                return link
        return links[0] if links else tg_url
