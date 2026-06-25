# job-scraper

> Configurable IT job scraper, pre-configured for DevOps/SRE.
> Aggregates remote vacancies from Russian job boards, filters by keywords, deduplicates, and sends a Telegram digest.

**[Документация на русском → README.ru.md](README.ru.md)**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

## What it does

- Fetches fresh vacancies from multiple sources on a schedule
- Filters by your keywords and stopwords (fully configurable)
- Removes already-seen jobs (SQLite, 30-day TTL)
- Sends a grouped digest to a Telegram chat or channel

## Sources

| Site | Method |
|---|---|
| hh.ru | HTML scraping (curl-cffi with browser TLS) |
| career.habr.com | HTML scraping (curl-cffi) |
| trudvsem.ru | Public REST API (no token) |
| superjob.ru | REST API v2.0 (API key required) |
| geekjob.ru | HTML scraping with SSR pagination |
| Telegram channels | Public web preview (`t.me/s/channel`) — no auth required |

## Quick start

```bash
git clone https://github.com/falcongram/job-scraper.git
cd job-scraper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `secrets.yaml` (never commit this):

```yaml
telegram:
  token: "BOT_TOKEN"   # from @BotFather
  chat_id: "CHAT_ID"   # from @userinfobot

sources:
  superjob:
    api_key: "YOUR_KEY"
```

Edit `config.yaml` — set your `keywords` and toggle sources. Then run:

```bash
python main.py
python main.py --no-dedup --no-send  # dry run for testing
```

## Automation (cron)

```
0 9 * * * cd /path/to/job-scraper && .venv/bin/python main.py >> data/cron.log 2>&1
```

## Configuration

Keywords and stopwords in `config.yaml` are the only thing you need to change for a different role:

```yaml
search:
  keywords: [devops, sre, kubernetes]   # replace with your stack
  stopwords: [windows, 1с, менеджер]
  remote_only: true
  days_back: 7
```

The default config ships with a DevOps/SRE profile. Swap the keywords for `python developer`, `data engineer`, `qa automation`, etc.

## Contributing

Pull requests are welcome. Areas where contributions are especially valuable:

- **International job boards** — LinkedIn, Greenhouse, Lever, Ashby (the filter/dedup/notifier stack is board-agnostic)
- **New Telegram channels** — see `scrapers/tg_fordevops.py` as a reference implementation

For larger changes, open an issue first.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).

## Author

[github.com/falcongram](https://github.com/falcongram)
