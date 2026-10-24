from __future__ import annotations

import argparse
import sys

from . import characters, llm, scheduler, telegram_client
from . import config as config_mod
from . import weather as weather_mod


def _decorate(cfg: dict, character: dict, message: str) -> str:
    if (cfg.get("message") or {}).get("show_character_name", False):
        label = f"{character.get('emoji', '')} {character['id'].replace('_', ' ').title()}".strip()
        return f"{label}\n\n{message}"
    return message


def run(force=False, dry_run=False, check_only=False, config_path=None, character_id=None) -> int:
    cfg = config_mod.get_config(config_path)

    if check_only:
        ok, reason = scheduler.should_send_now(cfg)
        print(f"would_send={ok} :: {reason}")
        return 0

    if not force:
        ok, reason = scheduler.should_send_now(cfg)
        if not ok:
            print(f"Skipping: {reason}")
            return 0

    weather = weather_mod.get_weather(cfg)
    character = (
        characters.get_character(cfg, character_id)
        if character_id
        else characters.pick_character(cfg)
    )
    message = _decorate(cfg, character, llm.generate_message(cfg, character, weather))

    print(f"[character={character['id']}]\n{message}\n")

    if dry_run:
        print("(dry-run: not sending, not marking state)")
        return 0

    telegram_client.send_message(cfg, message)
    scheduler.mark_sent(cfg)
    print("Sent OK")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Telegram morning weather character bot")
    ap.add_argument("--force", action="store_true", help="Ignore schedule + dedupe; send now")
    ap.add_argument("--dry-run", action="store_true", help="Generate but do not send")
    ap.add_argument("--check", action="store_true", help="Print whether it would send now")
    ap.add_argument("--config", default=None, help="Path to a config.yaml")
    ap.add_argument("--character", default=None, help="Use this character id for this run only")
    args = ap.parse_args()
    sys.exit(run(force=args.force, dry_run=args.dry_run, check_only=args.check,
                 config_path=args.config, character_id=args.character))


if __name__ == "__main__":
    main()
