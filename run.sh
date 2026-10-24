#!/usr/bin/env bash
set -euo pipefail

# Schedulers (cron/launchd/systemd) start with a minimal PATH; add common locations.
export PATH="$HOME/.local/bin:$HOME/.pyenv/shims:$HOME/.pyenv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

cd "$(dirname "$0")"
exec poetry run python -m telegram_morning.main "$@"
