# job-scraper

Парсер вакансий DevOps/SRE с российских площадок. Собирает свежие удалённые вакансии, фильтрует по ключевым словам, дедуплицирует и отправляет дайджест в Telegram.

## Источники

| Сайт | Метод |
|---|---|
| hh.ru | HTML (curl-cffi с имитацией браузерного TLS) |
| career.habr.com | HTML (curl-cffi) |
| trudvsem.ru | Публичный REST API (без токена) |
| superjob.ru | REST API v2.0 (нужен API-ключ) |
| geekjob.ru | HTML с поддержкой SSR-пагинации |

## Как работает

1. Каждый скрейпер забирает вакансии из своего источника (с учётом `days_back`)
2. `filter.py` оставляет только вакансии с ключевым словом в названии и без стоп-слов
3. `storage.py` убирает уже виденные (SQLite, TTL 30 дней)
4. `notifier.py` форматирует дайджест, группирует по источнику, отправляет в Telegram

## Структура проекта

```
job-scraper/
├── main.py          # точка входа
├── config.yaml      # настройки поиска, источники, дедупликация
├── secrets.yaml     # токены и ключи (не в git)
├── models.py        # датакласс Job
├── filter.py        # фильтрация по ключевым словам и стоп-словам
├── storage.py       # SQLite-дедупликация
├── notifier.py      # форматирование и отправка в Telegram
├── scrapers/
│   ├── base.py      # базовый класс BaseScraper
│   ├── hh.py
│   ├── habr.py
│   ├── trudvsem.py
│   ├── superjob.py
│   └── geekjob.py
└── data/            # рабочие данные, не в git
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
python main.py                     # обычный запуск
python main.py --no-dedup          # без дедупликации (дебаг)
python main.py --no-send           # только логи, без отправки в Telegram
python main.py --no-dedup --no-send
```

## Справка по конфигу

```yaml
search:
  keywords: [devops, sre, kubernetes]
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

dedup:
  db_path: data/seen_jobs.db
  ttl_days: 30
```

## Добавление нового источника

1. Создай `scrapers/newsite.py`, унаследовав `BaseScraper`
2. Реализуй метод `parse(self) -> List[Job]`
3. Подключи в `main.py` по аналогии с остальными
4. Добавь запись под `sources:` в `config.yaml`

## Зависимости

- `curl-cffi` — TLS-фингерпринт браузера (обход антибота / Cloudflare)
- `beautifulsoup4` + `lxml` — парсинг HTML
- `requests` — HTTP для REST API
- `pyyaml` — чтение конфига
