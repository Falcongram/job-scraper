from datetime import datetime
from typing import List, Optional

from models import Job
from scrapers.telegram import BaseTelegramScraper


class DevopsJobScraper(BaseTelegramScraper):
    """
    Шаблон @devopssjob:
      line 0 — "💻" (один символ)
      line 1 — должность (короткая; если длинная — реклама, пропускаем)
      line 2 — Удалёнка / Гибрид (Город) | зарплата
      line 3 — зарплата | компания
      line 4 — компания | описание
    Компания может быть "Name" отдельно или "Name — описание" в одну строку.
    """
    CHANNEL = "devopssjob"

    _SCHEDULE_MARKERS = ("Удалёнк", "Удаленк", "Гибрид", "Офис", "Remote", "Дистанц")
    _SALARY_MARKERS   = ("₽", "руб", "$", "€", "USD", "EUR")
    _SKIP_STARTS      = ("–", "-", "•", "Требован", "Опыт", "Обязанност")

    def _extract_job(
        self, text: str, links: List[str], tg_url: str, post_date: datetime
    ) -> Optional[Job]:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines or lines[0] != "💻":
            return None

        if len(lines) < 3:
            return None

        title = lines[1]
        # Рекламные посты — слишком длинный "заголовок"
        if len(title) > 80:
            return None

        schedule = ""
        salary = ""
        company = ""

        for line in lines[2:8]:
            if not schedule and any(m in line for m in self._SCHEDULE_MARKERS):
                schedule = line
            elif not salary and any(m in line for m in self._SALARY_MARKERS):
                salary = line
            elif not company and not any(line.startswith(s) for s in self._SKIP_STARTS):
                # Компания может быть "KODE" или "KODE — описание компании"
                raw = line.split(" —")[0].split(" – ")[0].strip()
                if raw and len(raw) < 60:
                    company = raw

        return Job(
            title=title,
            company=company,
            url=self._best_link(links, tg_url),
            source=f"t.me/{self.CHANNEL}",
            schedule=schedule or "remote",
            salary=salary,
            found_at=post_date.replace(tzinfo=None),
        )
