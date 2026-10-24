from __future__ import annotations

import requests


def send_message(cfg: dict, text: str) -> dict:
    token = cfg["_secrets"]["telegram_bot_token"]
    chat_id = cfg["_secrets"]["telegram_chat_id"]
    tg = cfg.get("telegram") or {}

    payload = {"chat_id": chat_id, "text": text}
    parse_mode = tg.get("parse_mode")
    if parse_mode and str(parse_mode).lower() != "none":
        payload["parse_mode"] = parse_mode
    if tg.get("disable_notification"):
        payload["disable_notification"] = True

    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=30,
    )
    if not r.ok:
        # Show Telegram's own explanation (e.g. "chat not found") without leaking the token.
        raise RuntimeError(f"Telegram error {r.status_code}: {r.text[:300]}")
    return r.json()
