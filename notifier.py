import logging
from typing import List, Dict
from datetime import datetime
import requests
from models import Job

logger = logging.getLogger(__name__)

MAX_MSG_LEN = 4000

SOURCE_META = {
    "hh.ru":           ("🟡", "https://hh.ru"),
    "career.habr.com": ("🟠", "https://career.habr.com"),
    "trudvsem.ru":     ("🔵", "https://trudvsem.ru"),
    "superjob.ru":     ("🟢", "https://superjob.ru"),
    "geekjob.ru":      ("🟣", "https://geekjob.ru"),
}

# Эти значения schedule — просто подтверждение удалёнки, не несут доп. инфо
_REMOTE_NOISE = {
    "можно удалённо", "можно удаленно",
    "дистанционная (удаленная) работа", "дистанционная (удалённая) работа",
    "удалённая работа", "удаленная работа",
    "remote", "удалённо", "удаленно",
}


def format_source_message(source: str, jobs: List[Job], date_str: str) -> str:
    emoji, url = SOURCE_META.get(source, ("⚪️", ""))
    lines = [
        f"{emoji} {url or source} — вакансии DevOps",
        f"📅 {date_str} · найдено новых: {len(jobs)}",
        "",
    ]
    for job in jobs:
        line = [f"• *{_escape(job.title)}*"]
        if job.company:
            line.append(f"  🏢 {_escape(job.company)}")
        meta = []
        if job.city:
            meta.append(f"📍 {job.city}")
        if job.schedule and job.schedule.lower() not in _REMOTE_NOISE:
            meta.append(f"🕐 {job.schedule}")
        if meta:
            line.append("  " + "  |  ".join(meta))
        if job.salary:
            line.append(f"  💰 {job.salary}")
        line.append(f"  🔗 {job.url}")
        lines.append("\n".join(line))
        lines.append("")

    return "\n".join(lines).strip()


def _escape(text: str) -> str:
    return text.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")


def send_digest(jobs: List[Job], token: str, chat_id: str):
    if not jobs:
        logger.info("Нет новых вакансий — ничего не отправляем")
        return

    date_str = datetime.now().strftime("%d.%m.%Y")

    # Группируем по источнику
    grouped: Dict[str, List[Job]] = {}
    for job in jobs:
        grouped.setdefault(job.source, []).append(job)

    # Итоговое сообщение-шапка
    total_msg = f"💼 *Дайджест вакансий DevOps — {date_str}*\n"
    for source, src_jobs in grouped.items():
        emoji, src_url = SOURCE_META.get(source, ("⚪️", ""))
        total_msg += f"\n{emoji} {src_url or source}: *{len(src_jobs)}* новых"
    _send(total_msg, token, chat_id)

    # Отдельное сообщение на каждый источник
    for source, src_jobs in grouped.items():
        text = format_source_message(source, src_jobs, date_str)
        for chunk in _split(text):
            _send(chunk, token, chat_id)


def send_error(failed_sources: List[str], token: str, chat_id: str):
    if not failed_sources:
        return
    msg = "⚠️ *Ошибки при сборе вакансий:*\n" + "\n".join(f"• {s}" for s in failed_sources)
    _send(msg, token, chat_id)


def _send(text: str, token: str, chat_id: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }, timeout=15)
    if not resp.ok:
        logger.error("Telegram error: %s", resp.text)
    else:
        logger.info("Отправлено в Telegram (%d символов)", len(text))


def _split(text: str) -> List[str]:
    if len(text) <= MAX_MSG_LEN:
        return [text]
    chunks = []
    while text:
        chunk = text[:MAX_MSG_LEN]
        last_nl = chunk.rfind("\n")
        if last_nl > 0:
            chunk = chunk[:last_nl]
        chunks.append(chunk)
        text = text[len(chunk):].lstrip("\n")
    return chunks
