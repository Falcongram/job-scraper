# job-scraper

A Python scraper that aggregates remote DevOps/SRE job postings from Russian job boards, filters them by keywords, deduplicates, and sends a Telegram digest.

## Sources

| Site | Method |
|---|---|
| hh.ru | HTML scraping (curl-cffi with browser TLS) |
| career.habr.com | HTML scraping (curl-cffi) |
| trudvsem.ru | Public REST API (no token required) |
| superjob.ru | REST API v2.0 (API key required) |
| geekjob.ru | HTML scraping with SSR pagination |

## How it works

1. Each scraper fetches vacancies from its source (respecting `days_back` cutoff)
2. `filter.py` keeps only jobs matching at least one keyword with no stopwords in the title
3. `storage.py` removes already-seen jobs (SQLite, 30-day TTL)
4. `notifier.py` formats a grouped digest and sends it to Telegram

## Project structure

```
job-scraper/
├── main.py          # entry point
├── config.yaml      # search settings, sources, dedup config
├── secrets.yaml     # tokens and keys (not in git)
├── models.py        # Job dataclass
├── filter.py        # keyword/stopword filtering
├── storage.py       # SQLite deduplication
├── notifier.py      # Telegram formatting and delivery
├── scrapers/
│   ├── base.py      # BaseScraper abstract class
│   ├── hh.py
│   ├── habr.py
│   ├── trudvsem.py
│   ├── superjob.py
│   └── geekjob.py
└── data/            # runtime data, not in git
    ├── seen_jobs.db
    └── scraper.log
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `secrets.yaml` (never commit this):

```yaml
telegram:
  token: "BOT_TOKEN"    # from @BotFather
  chat_id: "CHAT_ID"    # from @userinfobot

sources:
  superjob:
    api_key: "YOUR_KEY"  # from superjob.ru/api/
```

Edit `config.yaml` to set your keywords, stopwords, and toggle sources on/off.

## Usage

```bash
python main.py                    # normal run
python main.py --no-dedup         # skip deduplication (debug)
python main.py --no-send          # dry run, log only
python main.py --no-dedup --no-send
```

## Config reference

```yaml
search:
  keywords: [devops, sre, kubernetes]
  stopwords: [windows, 1с, менеджер]
  remote_only: true
  days_back: 7          # 0 = no date limit

sources:
  hh:
    enabled: true
    use_api: false      # set true + hh_api_token in secrets.yaml for official API
  superjob:
    enabled: true
    api_key: ""         # set via secrets.yaml

dedup:
  db_path: data/seen_jobs.db
  ttl_days: 30
```

## Adding a new source

1. Create `scrapers/newsite.py` extending `BaseScraper`
2. Implement `parse(self) -> List[Job]`
3. Wire it in `main.py` following the existing pattern
4. Add an entry under `sources:` in `config.yaml`

## Dependencies

- `curl-cffi` — browser-grade TLS fingerprinting (bypasses bot detection)
- `beautifulsoup4` + `lxml` — HTML parsing
- `requests` — plain HTTP for REST APIs
- `pyyaml` — config parsing
