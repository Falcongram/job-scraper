# job-scraper

Настраиваемый парсер IT-вакансий, преднастроенный для DevOps/SRE.
Собирает свежие удалённые вакансии с российских площадок, фильтрует по ключевым словам, дедуплицирует и отправляет дайджест в Telegram.

> Ключевые слова в `config.yaml` — единственное, что нужно поменять для другой роли (backend, QA, data engineer и т.д.).

## Источники

| Сайт | Метод |
|---|---|
| hh.ru | HTML (curl-cffi с имитацией браузерного TLS) |
| career.habr.com | HTML (curl-cffi) |
| trudvsem.ru | Публичный REST API (без токена) |
| superjob.ru | REST API v2.0 (нужен API-ключ) |
| geekjob.ru | HTML с поддержкой SSR-пагинации |
| Telegram-каналы | Публичный веб-превью `t.me/s/channel` — без авторизации |

## Как работает

1. Каждый скрейпер забирает вакансии из своего источника (с учётом `days_back`)
2. `filter.py` оставляет только вакансии с ключевым словом в названии и без стоп-слов
3. `storage.py` убирает уже виденные вакансии (SQLite, TTL 30 дней)
4. `notifier.py` форматирует дайджест, группирует по источнику, отправляет в Telegram

## Структура проекта

```
job-scraper/
├── main.py                  # точка входа
├── config.yaml              # настройки поиска, источники, дедупликация
├── secrets.yaml             # токены и ключи (не в git)
├── models.py                # датакласс Job
├── filter.py                # фильтрация по ключевым словам и стоп-словам
├── storage.py               # SQLite-дедупликация
├── notifier.py              # форматирование и отправка в Telegram
├── scrapers/
│   ├── base.py              # базовый класс BaseScraper
│   ├── hh.py
│   ├── habr.py
│   ├── trudvsem.py
│   ├── superjob.py
│   ├── geekjob.py
│   ├── telegram.py          # базовый класс BaseTelegramScraper
│   ├── tg_fordevops.py      # парсер @fordevops (пример реализации)
│   └── tg_devopssjob.py     # парсер @devopssjob (пример реализации)
└── data/                    # рабочие данные, не в git
    ├── seen_jobs.db
    └── scraper.log
```

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Создай `secrets.yaml` (не коммить его):

```yaml
telegram:
  token: "BOT_TOKEN"   # токен от @BotFather
  chat_id: "CHAT_ID"   # узнать через @userinfobot

sources:
  superjob:
    api_key: "YOUR_KEY"  # с superjob.ru/api/
```

В `config.yaml` настрой ключевые слова, стоп-слова и включи/выключи нужные источники.

## Запуск

```bash
python main.py                      # обычный запуск
python main.py --no-dedup           # без дедупликации (дебаг)
python main.py --no-send            # только логи, без отправки в Telegram
python main.py --no-dedup --no-send
```

## Автоматизация (cron)

Добавь в crontab (`crontab -e`):

```
0 9 * * * cd /path/to/job-scraper && .venv/bin/python main.py >> data/cron.log 2>&1
```

Запускать можно с любой периодичностью — дедупликация не даст повторных уведомлений.

## Справка по конфигу

```yaml
search:
  keywords: [devops, sre, kubernetes]  # замени под свой стек
  stopwords: [windows, 1с, менеджер]
  remote_only: true
  days_back: 7          # 0 = без ограничения по дате

sources:
  hh:
    enabled: true
    use_api: false      # true + hh_api_token в secrets.yaml для официального API
  superjob:
    enabled: true
    api_key: ""         # задаётся через secrets.yaml
  telegram:
    enabled: true
    channels:
      - fordevops       # имя канала (часть после t.me/)
      - devopssjob

dedup:
  db_path: data/seen_jobs.db
  ttl_days: 30
```

## Добавление Telegram-канала

Каждый канал имеет свою структуру постов, поэтому для него нужен отдельный парсер.
Используй `scrapers/tg_fordevops.py` как шаблон:

1. Создай `scrapers/tg_mychannel.py`, унаследовав `BaseTelegramScraper`
2. Укажи `CHANNEL = "mychannel"` (имя канала в `t.me/s/mychannel`)
3. Реализуй `_extract_job(text, links, tg_url, post_date)`:
   - `text` — текст поста (`\n`-разделённые строки)
   - `links` — внешние ссылки из поста (без `t.me`)
   - `tg_url` — ссылка на пост (`https://t.me/channel/12345`)
   - Верни `Job(...)` или `None` если пост не вакансия
4. Подключи в `main.py` и добавь имя канала в `config.yaml`

Логика фильтрации вакансий vs. рекламы у каждого канала своя — посмотри на реальные посты в `t.me/s/mychannel` перед написанием парсера.

## Добавление job-борда

1. Создай `scrapers/newsite.py`, унаследовав `BaseScraper`
2. Реализуй метод `parse(self) -> List[Job]`
3. Подключи в `main.py` по аналогии с остальными
4. Добавь запись под `sources:` в `config.yaml`

Интернациональные борды (LinkedIn, Greenhouse, Lever, Ashby) — welcome-контрибьюция, фильтр и дедупликация уже готовы.

## Зависимости

- `curl-cffi` — TLS-фингерпринт браузера (обход антибота / Cloudflare)
- `beautifulsoup4` + `lxml` — парсинг HTML
- `requests` — HTTP для REST API
- `pyyaml` — чтение конфига

## Лицензия

GNU General Public License v3.0 — см. [LICENSE](LICENSE).

## Автор

[github.com/falcongram](https://github.com/falcongram)
