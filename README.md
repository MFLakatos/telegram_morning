# telegram_morning

Every morning at the time you choose, you get a Telegram message about today's weather, written in
the voice of a character (pirate, detective, scientist, grumpy, caveman, …) — either one you pick
or a random one each day. Spanish or English. Everything is set in `config.yaml`; secrets live in
`.env`.

It runs on **GitHub Actions with a free cloud LLM (Groq)**, so your computer can be off. It can also
run on your own machine with a local model (Ollama) if you prefer.

## Table of contents
- [How it works](#how-it-works)
- [Quick start (GitHub, computer off)](#quick-start-github-computer-off)
- [Configure](#configure)
- [Run locally](#run-locally)
- [Schedule it on your own machine instead](#schedule-it-on-your-own-machine-instead)
- [Modify & extend](#modify--extend)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## How it works
A scheduler wakes the program up every ~30 minutes. Each run checks the wall-clock time in your
configured IANA timezone (winter/summer time handled automatically by Python's `zoneinfo`). If it's
within `[send_time, send_time + send_window_minutes]` and nothing was sent today, it fetches today's
weather (Open-Meteo, free, no key), picks the character, asks the LLM to write the message in that
character's voice and your language, sends it via the Telegram Bot API, and records the date in
`state/last_sent.json` so you get at most one message per day. There is no always-on process.

```
scheduler tick ─► should_send_now()? ─no─► exit
                        │ yes
                        ├─► get_weather()      (Open-Meteo)
                        ├─► pick_character()   (fixed / random / sequential)
                        ├─► generate_message() (Groq, OpenAI, Ollama… + fallback)
                        ├─► send_message()     (Telegram)
                        └─► mark_sent()        (state/last_sent.json)
```

## Quick start (GitHub, computer off)

1. **Telegram bot** (skip if `.env` already has them): message @BotFather → `/newbot` → copy the
   token. Send your bot any message, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `result[0].message.chat.id`.
2. **Free Groq key:** sign in at <https://console.groq.com> → *API Keys* → *Create API key*.
   Paste it into `.env` as `GROQ_API_KEY=...`.
3. **Push to a GitHub repo** (private is fine). With the GitHub CLI:
   ```bash
   git add . && git commit -m "telegram_morning bot"
   gh repo create telegram_morning --private --source=. --push
   ```
   (`.env` is git-ignored, so your secrets are never pushed.)
4. **Add the secrets to GitHub:** `make github-secrets` (copies them from `.env` with `gh`), or by
   hand in *Settings → Secrets and variables → Actions → New repository secret*:
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GROQ_API_KEY`.
5. **Test it:** repo → *Actions* → *telegram-morning* → *Run workflow*. A message should arrive within
   a minute. From then on it sends itself every morning.

To change the time, character, city or language later: edit `config.yaml`, commit, push.

## Configure
All settings live in `config.yaml`; secrets live in `.env` (locally) and GitHub secrets (cloud).

| Field | Meaning |
|---|---|
| `language` | `es` or `en` |
| `timezone` | IANA name, e.g. `America/Montevideo` (DST automatic) |
| `send_time` | local `HH:MM` to send |
| `send_window_minutes` | how long after `send_time` a run may still send (keep ≥ 60 on GitHub) |
| `location.city` / `latitude`+`longitude` | where to get weather |
| `weather.units` | `metric` or `imperial` |
| `llm.provider` | active provider key (`groq`, `openai`, `openrouter`, `ollama`) |
| `llm.fallback_provider` | tried if the primary fails (or `null`) |
| `llm.providers.<name>` | `base_url`, `model`, `api_key_env` per provider |
| `telegram.parse_mode` | `none` (safest), `HTML`, or `Markdown` |
| `message.show_character_name` | prepend the character label, e.g. "🏴‍☠️ Pirate" |
| `character_selection` | `random`, `sequential`, or `fixed` |
| `character` | the character id used when `character_selection: fixed` |
| `characters` | roster; each has `id`, `emoji`, `persona.en`, `persona.es` |

### Always the same character
```yaml
character_selection: fixed
character: pirate          # any id from the roster
```

### Switch language
Set `language: en` (or `es`). Every persona exists in both languages.

### Use a local model instead of the cloud
Install Ollama, `make ollama-pull`, set `llm.provider: ollama`, and schedule it on your machine
(below). GitHub's servers can't reach a model running on your computer.

## Run locally
Needs pyenv + Poetry (`brew install pyenv poetry`), then `make setup` once.
```bash
make check                  # would it send right now?
make dry                    # generate + print, don't send
make dry CHARACTER=pirate   # try a specific character's voice
make send                   # force-send now (test)
make run                    # run respecting the schedule (what a scheduler calls)
make test                   # offline unit tests
```
CLI: `poetry run python -m telegram_morning.main [--check|--dry-run|--force] [--character ID] [--config PATH]`.

## Schedule it on your own machine instead
Only needed if you don't use GitHub Actions (e.g. for Ollama). Pick one; each runs `run.sh` every
30 minutes and the program decides when to send. Don't run both this and GitHub, or you'll get two
messages.
- **macOS launchd:** `cp deploy/com.telegram-morning.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.telegram-morning.plist`
- **cron:** `crontab -e` and paste the line from `deploy/crontab.example`
- **Linux systemd:** see `deploy/telegram-morning.service` and `.timer`

The machine must be awake at send time.

## Modify & extend
- **Add a character:** add an entry under `characters` with `id`, `emoji`, `persona.en`, `persona.es`.
- **Change send time / zone / city:** edit `send_time`, `timezone`, `location`.
- **Add an LLM provider:** add an entry under `llm.providers` (`base_url`, `model`, `api_key_env`),
  put the key in `.env` (and GitHub secrets + the workflow's `env:` list), point `llm.provider` at it.
  Anything OpenAI-compatible works without code changes.
- **Add a weather field:** extend the `daily=` list and the returned dict in `telegram_morning/weather.py`.

## Troubleshooting
- **Message ends with "(mensaje sin LLM: …)":** the LLM call failed; the reason is printed in the
  run log (GitHub: Actions → the run → the last step). Usually a missing/invalid `GROQ_API_KEY` or a
  retired model name — check <https://console.groq.com/docs/models>.
- **Telegram 400 "chat not found":** wrong chat id, or you never sent the bot a message first.
- **Telegram 400 "can't parse entities":** set `telegram.parse_mode: "none"`.
- **Message arrives a bit late:** GitHub's scheduled runs can lag 5–30 minutes. Runs fire at :07 and
  :37 past each hour, so a 07:00 send usually lands around 07:07–07:20.
- **`make` says "missing separator":** a Makefile recipe used spaces instead of a tab.

## FAQ
**Does my computer need to be on?** Not with GitHub Actions + a cloud provider (the default).
**Is it free?** Open-Meteo and Groq's free tier are free. GitHub Actions is free for public repos;
private repos get 2,000 minutes/month and this uses roughly 1,500 (48 short runs a day).
**Will it send twice?** No — `state/last_sent.json` (kept in the Actions cache on GitHub) enforces
one message per local day.
**Does winter/summer time matter?** No. `send_time` is always local wall-clock time in `timezone`.
