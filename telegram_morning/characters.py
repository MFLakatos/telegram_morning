from __future__ import annotations

import random
from datetime import date, datetime
from zoneinfo import ZoneInfo


def get_character(cfg: dict, character_id: str) -> dict:
    for c in cfg.get("characters") or []:
        if c.get("id") == character_id:
            return c
    ids = ", ".join(str(c.get("id")) for c in cfg.get("characters") or [])
    raise ValueError(f"No character with id '{character_id}'. Available: {ids}")


def pick_character(cfg: dict, today: date | None = None) -> dict:
    """Choose today's character.

    character_selection:
      "fixed"      -> always the one named in `character`
      "sequential" -> deterministic rotation by local date (same all day)
      "random"     -> random every run (default)
    """
    chars = cfg.get("characters") or []
    if not chars:
        raise ValueError("config.characters is empty")

    strategy = cfg.get("character_selection", "random")
    if strategy == "fixed":
        return get_character(cfg, cfg.get("character"))
    if strategy == "sequential":
        if today is None:
            today = datetime.now(ZoneInfo(cfg["timezone"])).date()
        return chars[today.toordinal() % len(chars)]
    return random.choice(chars)
