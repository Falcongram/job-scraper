from datetime import datetime
from typing import List, Optional

from models import Job
from scrapers.telegram import BaseTelegramScraper


class ForDevopsScraper(BaseTelegramScraper):
    """
    Шаблон @fordevops:
      строка 1 — должность (нет ведущего emoji)
      строка 2 — компания (короткая, до 60 символов)
      далее    — описание, локация, ссылки
    Посты-статьи/реклама начинаются с emoji → пропускаем.
    """
    CHANNEL = "fordevops"

    def _extract_job(
        self, text: str, links: List[str], tg_url: str, post_date: datetime
    ) -> Optional[Job]:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return None

        # Посты-статьи начинаются с emoji (codepoint > U+2500)
        if lines[0] and ord(lines[0][0]) > 0x2500:
            return None

        title = lines[0]
        company = ""
        if len(lines) > 1 and len(lines[1]) < 60 and not lines[1].startswith(("–", "-", "•")):
            company = lines[1]

        return Job(
            title=title,
            company=company,
            url=self._best_link(links, tg_url),
            source=f"t.me/{self.CHANNEL}",
            schedule="remote",
            found_at=post_date.replace(tzinfo=None),
        )
