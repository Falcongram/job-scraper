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

_REMOTE_NOISE = {
    "можно удалённо", "можно удаленно",
    "дистанционная (удаленная) работа", "дистанционная (удалённая) работа",
    "удалённая работа", "удаленная работа",
    "remote", "удалённо", "удаленно",
}


def _h(text: str) -> str:
    """Экранирование для HTML parse_mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _is_tg(source: str) -> bool:
    return source.startswith("t.me/")


def format_source_message(source: str, jobs: List[Job], date_str: str) -> str:
    if _is_tg(source):
        return _format_tg_message(source, jobs, date_str)
    return _format_board_message(source, jobs, date_str)


def _format_board_message(source: str, jobs: List[Job], date_str: str) -> str:
    emoji, url = SOURCE_META.get(source, ("⚪️", source))
    lines = [
        f"{emoji} <a href=\"{url}\">{_h(source)}</a> — вакансии DevOps",
        f"📅 {date_str} · найдено новых: {len(jobs)}",
        "",
    ]
    for job in jobs:
        line = [f"• <b>{_h(job.title)}</b>"]
        if job.company:
            line.append(f"  🏢 {_h(job.company)}")
        meta = []
        if job.city:
            meta.append(f"📍 {job.city}")
        if job.schedule and job.schedule.lower() not in _REMOTE_NOISE:
            meta.append(f"🕐 {_h(job.schedule)}")
        if meta:
            line.append("  " + "  |  ".join(meta))
        if job.salary:
            line.append(f"  💰 {_h(job.salary)}")
        line.append(f"  🔗 {job.url}")
        lines.append("\n".join(line))
        lines.append("")

    return "\n".join(lines).strip()


def _format_tg_message(source: str, jobs: List[Job], date_str: str) -> str:
    channel = source  # "t.me/fordevops"
    channel_url = f"https://{channel}"
    channel_name = channel.replace("t.me/", "@")

    lines = [
        f"📢 <a href=\"{channel_url}\">{channel_name}</a> — вакансии из Telegram",
        f"📅 {date_str} · найдено новых: {len(jobs)}",
        "",
    ]
    for job in jobs:
        lines.append(f"📌 <b>{_h(job.title)}</b>")
        lines.append(f"   🔗 {job.url}")
        lines.append("")

    return "\n".join(lines).strip()


def send_digest(jobs: List[Job], token: str, chat_id: str):
    if not jobs:
        logger.info("Нет новых вакансий — ничего не отправляем")
        return

    date_str = datetime.now().strftime("%d.%m.%Y")

    grouped: Dict[str, List[Job]] = {}
    for job in jobs:
        grouped.setdefault(job.source, []).append(job)

    # Шапка-сводка
    total_lines = [f"💼 <b>Дайджест вакансий DevOps — {date_str}</b>"]
    for source, src_jobs in grouped.items():
        if _is_tg(source):
            ch = source.replace("t.me/", "@")
            total_lines.append(f"📢 {ch}: <b>{len(src_jobs)}</b> новых")
        else:
            emoji, _ = SOURCE_META.get(source, ("⚪️", ""))
            total_lines.append(f"{emoji} {source}: <b>{len(src_jobs)}</b> новых")
    _send("\n".join(total_lines), token, chat_id)

    # Детальное сообщение на каждый источник
    for source, src_jobs in grouped.items():
        text = format_source_message(source, src_jobs, date_str)
        for chunk in _split(text):
            _send(chunk, token, chat_id)


def send_error(failed_sources: List[str], token: str, chat_id: str):
    if not failed_sources:
        return
    msg = "⚠️ <b>Ошибки при сборе вакансий:</b>\n" + "\n".join(f"• {_h(s)}" for s in failed_sources)
    _send(msg, token, chat_id)


def _send(text: str, token: str, chat_id: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=15)
    if not resp.ok:
        logger.error("Telegram API error %s: %s", resp.status_code, resp.text)
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
