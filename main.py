import argparse
import logging
import logging.handlers
import sys
import yaml
from pathlib import Path

from scrapers.hh import HHScraper
from scrapers.habr import HabrScraper
from scrapers.trudvsem import TrudvsemScraper
from scrapers.superjob import SuperjobScraper
from scrapers.geekjob import GeekjobScraper
from scrapers.tg_fordevops import ForDevopsScraper
from scrapers.tg_devopssjob import DevopsJobScraper
from filter import apply_filters
from storage import Storage
from notifier import send_digest, send_error


def _deep_merge(base: dict, override: dict) -> None:
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    secrets_path = Path(path).parent / "secrets.yaml"
    if secrets_path.exists():
        with open(secrets_path, "r", encoding="utf-8") as f:
            secrets = yaml.safe_load(f) or {}
        _deep_merge(config, secrets)

    return config


def setup_logging(config: dict):
    log_cfg = config.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO"))
    log_file = log_cfg.get("file", "data/scraper.log")

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        ),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Job scraper")
    parser.add_argument("--no-dedup", action="store_true",
                        help="Не фильтровать уже виденные вакансии (для дебага)")
    parser.add_argument("--no-send", action="store_true",
                        help="Не отправлять в Telegram, только вывод в лог")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()
    setup_logging(config)
    logger = logging.getLogger("main")

    if args.no_dedup:
        logger.info("Режим --no-dedup: дедупликация отключена")

    storage = Storage(
        db_path=config["dedup"]["db_path"],
        ttl_days=config["dedup"]["ttl_days"],
    )
    storage.cleanup()

    scrapers = []
    sources = config.get("sources", {})

    if sources.get("hh", {}).get("enabled"):
        scrapers.append(("hh.ru", HHScraper(config)))
    if sources.get("habr", {}).get("enabled"):
        scrapers.append(("career.habr.com", HabrScraper(config)))
    if sources.get("trudvsem", {}).get("enabled"):
        scrapers.append(("trudvsem.ru", TrudvsemScraper(config)))
    if sources.get("superjob", {}).get("enabled"):
        scrapers.append(("superjob.ru", SuperjobScraper(config)))
    if sources.get("geekjob", {}).get("enabled"):
        scrapers.append(("geekjob.ru", GeekjobScraper(config)))
    tg_cfg = sources.get("telegram", {})
    if tg_cfg.get("enabled"):
        if "fordevops" in tg_cfg.get("channels", []):
            scrapers.append(("t.me/fordevops", ForDevopsScraper(config)))
        if "devopssjob" in tg_cfg.get("channels", []):
            scrapers.append(("t.me/devopssjob", DevopsJobScraper(config)))

    all_jobs = []
    failed_sources = []

    for name, scraper in scrapers:
        logger.info("Парсим %s...", name)
        try:
            jobs = scraper.parse()
            logger.info("%s: получено %d вакансий", name, len(jobs))
            all_jobs.extend(jobs)
        except Exception as e:
            logger.error("%s: ошибка — %s", name, e)
            failed_sources.append(name)

    filtered = apply_filters(all_jobs, config)

    if args.no_dedup:
        seen_urls: set = set()
        new_jobs = []
        for j in filtered:
            if j.url not in seen_urls:
                seen_urls.add(j.url)
                new_jobs.append(j)
    else:
        new_jobs = storage.filter_new(filtered)
        storage.mark_seen(new_jobs)

    tg = config["telegram"]
    token = tg["token"]
    chat_id = tg["chat_id"]

    if new_jobs:
        if args.no_send:
            from notifier import format_source_message
            from datetime import datetime
            date_str = datetime.now().strftime("%d.%m.%Y")
            grouped = {}
            for j in new_jobs:
                grouped.setdefault(j.source, []).append(j)
            for src, src_jobs in grouped.items():
                logger.info("--no-send preview [%s]:\n%s",
                            src, format_source_message(src, src_jobs[:3], date_str))
        else:
            send_digest(new_jobs, token, chat_id)
    else:
        logger.info("Новых вакансий нет")

    if failed_sources and not args.no_send:
        send_error(failed_sources, token, chat_id)

    logger.info("Готово. Всего: %d, отфильтровано: %d, новых: %d",
                len(all_jobs), len(filtered), len(new_jobs))


if __name__ == "__main__":
    main()
