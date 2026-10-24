from __future__ import annotations

import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from dotenv import load_dotenv

# telegram_morning/config.py -> parents[0]=package dir, parents[1]=repo root
REPO_ROOT = Path(__file__).resolve().parents[1]

CHARACTER_STRATEGIES = ("random", "sequential", "fixed")


def get_config(config_path: str | None = None) -> dict:
    """Load .env + config.yaml, attach secrets, validate, and return a dict."""
    load_dotenv(REPO_ROOT / ".env")

    path = Path(config_path) if config_path else REPO_ROOT / "config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    cfg["_secrets"] = {
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    }
    cfg["_repo_root"] = str(REPO_ROOT)

    # Optional: override local Ollama host from the environment.
    ollama_host = os.environ.get("OLLAMA_HOST")
    providers = (cfg.get("llm") or {}).get("providers") or {}
    if ollama_host and "ollama" in providers:
        providers["ollama"]["base_url"] = ollama_host.rstrip("/") + "/v1"

    _validate(cfg)
    return cfg


def _validate(cfg: dict) -> None:
    if cfg.get("language") not in ("es", "en"):
        raise ValueError("config.language must be 'es' or 'en'")

    tz = cfg.get("timezone")
    if not tz:
        raise ValueError("config.timezone is required (IANA name, e.g. 'America/Montevideo')")
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"config.timezone '{tz}' is not a valid IANA timezone name")

    send_time = str(cfg.get("send_time") or "")
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", send_time):
        raise ValueError("config.send_time must be 24h 'HH:MM', e.g. '07:30'")

    loc = cfg.get("location") or {}
    has_coords = loc.get("latitude") is not None and loc.get("longitude") is not None
    if not (loc.get("city") or has_coords):
        raise ValueError("config.location needs either 'city' or 'latitude'+'longitude'")

    chars = cfg.get("characters") or []
    if not chars:
        raise ValueError("config.characters must have at least one character")

    strategy = cfg.get("character_selection", "random")
    if strategy not in CHARACTER_STRATEGIES:
        raise ValueError(f"config.character_selection must be one of {CHARACTER_STRATEGIES}")
    if strategy == "fixed":
        ids = [c.get("id") for c in chars]
        if cfg.get("character") not in ids:
            raise ValueError(
                f"config.character '{cfg.get('character')}' is not in the roster. "
                f"Pick one of: {', '.join(map(str, ids))}"
            )

    llm = cfg.get("llm") or {}
    providers = llm.get("providers") or {}
    if not providers:
        raise ValueError("config.llm.providers must define at least one provider")
    if llm.get("provider") not in providers:
        raise ValueError(f"config.llm.provider '{llm.get('provider')}' is not in llm.providers")
    fb = llm.get("fallback_provider")
    if fb and fb not in providers:
        raise ValueError(f"config.llm.fallback_provider '{fb}' is not in llm.providers")

    s = cfg["_secrets"]
    if not s["telegram_bot_token"] or not s["telegram_chat_id"]:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set "
            "(in .env when running locally, or as GitHub Actions secrets)"
        )
