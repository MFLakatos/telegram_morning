from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def _state_path(cfg: dict) -> Path:
    return Path(cfg["_repo_root"]) / "state" / "last_sent.json"


def _read_state(cfg: dict) -> dict:
    p = _state_path(cfg)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def should_send_now(cfg: dict, now: datetime | None = None) -> tuple[bool, str]:
    """True if current local time is in the send window and nothing sent today.

    zoneinfo applies DST rules automatically, so send_time is always wall-clock
    local time in cfg['timezone'] — correct in both winter and summer.
    """
    tz = ZoneInfo(cfg["timezone"])
    now = now.astimezone(tz) if now else datetime.now(tz)

    hh, mm = str(cfg["send_time"]).split(":")
    target = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    window = int(cfg.get("send_window_minutes", 60))
    end = target + timedelta(minutes=window)

    if not (target <= now <= end):
        return False, (
            f"Not in window: send_time {cfg['send_time']} +{window}m "
            f"({cfg['timezone']}); now {now.strftime('%Y-%m-%d %H:%M')}"
        )

    today = now.date().isoformat()
    if _read_state(cfg).get("last_sent_date") == today:
        return False, f"Already sent today ({today})"

    return True, "In window and not yet sent today"


def mark_sent(cfg: dict) -> None:
    tz = ZoneInfo(cfg["timezone"])
    now = datetime.now(tz)
    p = _state_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "last_sent_date": now.date().isoformat(),
        "last_sent_at": now.isoformat(),
    }))
