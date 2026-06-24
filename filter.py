import logging
from typing import List
from models import Job

logger = logging.getLogger(__name__)


def apply_filters(jobs: List[Job], config: dict) -> List[Job]:
    keywords = [k.lower() for k in config["search"]["keywords"]]
    stopwords = [s.lower() for s in config["search"].get("stopwords", [])]

    result = []
    for job in jobs:
        text = (job.title + " " + job.company).lower()

        if any(sw in text for sw in stopwords):
            logger.debug("Стоп-слово: %s", job.title)
            continue

        if not any(kw in text for kw in keywords):
            logger.debug("Нет ключевых слов: %s", job.title)
            continue

        result.append(job)

    logger.info("Фильтр: %d → %d вакансий", len(jobs), len(result))
    return result
