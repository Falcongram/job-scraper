import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List
from models import Job

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, db_path: str, ttl_days: int = 30):
        self.db_path = db_path
        self.ttl_days = ttl_days
        self._init()

    def _init(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen (
                    url TEXT PRIMARY KEY,
                    found_at TEXT NOT NULL
                )
            """)

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def filter_new(self, jobs: List[Job]) -> List[Job]:
        seen_urls: set[str] = set()
        unique_jobs = []
        for job in jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique_jobs.append(job)

        new_jobs = []
        with self._conn() as conn:
            for job in unique_jobs:
                row = conn.execute(
                    "SELECT 1 FROM seen WHERE url = ?", (job.url,)
                ).fetchone()
                if not row:
                    new_jobs.append(job)
        logger.info("Новых вакансий: %d из %d (уникальных URL: %d)", len(new_jobs), len(jobs), len(unique_jobs))
        return new_jobs

    def mark_seen(self, jobs: List[Job]):
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO seen (url, found_at) VALUES (?, ?)",
                [(job.url, now) for job in jobs],
            )

    def cleanup(self):
        cutoff = (datetime.utcnow() - timedelta(days=self.ttl_days)).isoformat()
        with self._conn() as conn:
            deleted = conn.execute(
                "DELETE FROM seen WHERE found_at < ?", (cutoff,)
            ).rowcount
        if deleted:
            logger.info("Удалено устаревших записей: %d", deleted)
