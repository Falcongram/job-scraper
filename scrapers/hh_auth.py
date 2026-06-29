import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_TOKEN_FILE = Path("data/hh_token.json")
_TOKEN_URL = "https://hh.ru/oauth/token"
_REFRESH_BUFFER = 86400  # обновить за сутки до истечения


def get_valid_token(client_id: str, client_secret: str, user_agent: str) -> str:
    """Возвращает действующий access_token, при необходимости запрашивает новый."""
    cached = _load_cached()
    if cached and cached.get("expires_at", 0) - time.time() > _REFRESH_BUFFER:
        logger.debug("hh.ru: используем кешированный токен (истекает через %.0f ч)",
                     (cached["expires_at"] - time.time()) / 3600)
        return cached["access_token"]

    logger.info("hh.ru: запрашиваем новый app token")
    data = _request_token(client_id, client_secret, user_agent)
    _save_cached(data)
    return data["access_token"]


def _load_cached() -> dict | None:
    try:
        if _TOKEN_FILE.exists():
            return json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _save_cached(token_data: dict) -> None:
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": token_data["access_token"],
        "expires_at": time.time() + token_data.get("expires_in", 2592000),
    }
    _TOKEN_FILE.write_text(json.dumps(payload), encoding="utf-8")
    logger.info("hh.ru: токен сохранён, действителен %.0f дней",
                token_data.get("expires_in", 2592000) / 86400)


def _request_token(client_id: str, client_secret: str, user_agent: str) -> dict:
    resp = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"HH-User-Agent": user_agent},
        timeout=10,
    )
    if not resp.ok:
        raise RuntimeError(f"hh.ru token error {resp.status_code}: {resp.text}")
    return resp.json()
