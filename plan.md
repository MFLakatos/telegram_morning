# Build Plan — `telegram_morning`

A self-activating bot that once per day, at a configurable local time, fetches the day's weather
and sends a **Telegram** message written **in the voice of a randomly chosen character** (pirate,
detective, scientist, cheerful, grumpy, …). Everything is configured through `config.yaml`; secrets
live in `.env`. The message language is switchable between **Spanish (`es`)** and **English
(`en`)**. The LLM can be a **local model (Ollama)** *or* a **cloud provider** — both configurable,
with automatic fallback.

Toolchain: **pyenv** (Python version) + **Poetry** (dependencies) + **Makefile** (shortcuts).

---

## 0. How to use this plan (READ FIRST — for the executing agent)

You are going to build this repository by following the steps **in order**. Rules:

1. **Do steps in the exact order given.** Each step depends on earlier ones.
2. **Create each file with the exact contents shown.** Do not paraphrase code. Copy it verbatim.
3. **Put each file at the exact path in its heading.** Paths are relative to the repo root
   `telegram_morning/`.
4. **After each "✅ Verify" block, run the command and confirm the expected output.** If it fails,
   fix that step before continuing. Do not move on with a failing verify.
5. **Do not invent extra files, dependencies, or "improvements."** Build exactly what is here.
6. **Makefile recipe lines must start with a TAB character, not spaces.** This is the single most
   common mistake — check it.
7. If a shell command needs an absolute path, get it with `pwd` from the repo root and substitute
   it; never guess.

That's it. Work top to bottom.

---

## 1. What you're building & how it works (documentation)

### 1.1 One-line summary
An external scheduler runs a small Python program every ~30 minutes. Each run asks: *"Is it the
right local time, and have I not already sent today?"* If yes, it fetches weather, picks a random
character, asks an LLM to write a good-morning weather message in that character's voice and in the
chosen language, sends it to Telegram, and records that today is done. Otherwise it exits silently.

### 1.2 Why there is no "on state"
There is **no long-running process** and no `while True` loop. The program runs, does its check,
and exits. The operating system's scheduler (cron / launchd / systemd) — or GitHub Actions in the
cloud — is what "wakes it up." So nothing has to be manually turned on and left running.

### 1.3 Data flow (one run)
```
scheduler tick (every ~30 min)
        │
        ▼
main.py ──► scheduler.should_send_now()   # timezone + DST aware, once-per-day guard
        │            │
        │            ├─ not time / already sent ──► exit quietly
        │            ▼ yes
        ├──► weather.get_weather()         # Open-Meteo (free, no key)
        ├──► characters.pick_character()   # random from config roster
        ├──► llm.generate_message()        # provider from config; fallback if it fails
        ├──► telegram_client.send_message()# Telegram Bot API
        └──► scheduler.mark_sent()         # write state/last_sent.json
```

### 1.4 How timezone & winter/summer (DST) are handled
`config.yaml` has a `timezone` (an IANA name like `Europe/Madrid`) and a `send_time` like `07:30`.
The program uses Python's `zoneinfo`, which knows each zone's daylight-saving rules. So `07:30 local`
is always 07:30 wall-clock — correct in winter (e.g. CET) and summer (e.g. CEST) — without you ever
computing UTC offsets. Because the scheduler fires often and the program self-checks the local time,
it doesn't matter what timezone the host machine or GitHub's servers are in.

A tiny state file `state/last_sent.json` records the date of the last send (in the configured
timezone), so even though the scheduler fires many times inside the send window, **at most one
message is sent per local day.**

### 1.5 How the LLM is chosen (local *and* cloud, configurable)
Ollama and every major cloud LLM expose the **same OpenAI-compatible HTTP API**
(`POST /v1/chat/completions`). So the program has **one** code path and just points it at whichever
`base_url`/`model` you select in `config.yaml`. You define named **providers** and pick one:

- `provider: ollama` → local model, free, private, but your machine must be awake at send time.
- `provider: groq` (or `openai`, etc.) → cloud model, works with your computer off (pair with
  GitHub Actions), depends on a provider and possibly a small cost.

You can also set `fallback_provider`: if the primary fails (e.g. Ollama is off), it automatically
tries the fallback before giving up. If everything fails, a plain templated message is sent so you
still get the forecast.

### 1.6 Where weather comes from
[Open-Meteo](https://open-meteo.com) — free, no API key. Give a city name (auto-geocoded to
coordinates) or explicit latitude/longitude. WMO weather codes are mapped to localized text + emoji.

### 1.7 The toolchain (why these tools)
- **pyenv** installs and pins the exact Python version (`.python-version`), independent of system Python.
- **Poetry** manages dependencies and the virtual environment (`pyproject.toml` / `poetry.lock`).
- **Makefile** gives short memorable commands (`make setup`, `make run`, `make send`, …).

---

## 2. Final file tree (what you will have built)

```
telegram_morning/                 <- repo root
├── telegram_morning/             <- the Python package
│   ├── __init__.py
│   ├── main.py                   <- entry point + CLI flags
│   ├── config.py                 <- loads config.yaml + .env, validates
│   ├── weather.py                <- Open-Meteo fetch + WMO code -> text (es/en)
│   ├── characters.py             <- pick a character (random / sequential)
│   ├── llm.py                    <- provider selection + call + fallback chain
│   ├── telegram_client.py        <- send message via Telegram Bot API
│   └── scheduler.py              <- timezone/DST-aware "should I send now?" + dedupe
├── tests/
│   └── test_core.py              <- offline unit tests (no network)
├── deploy/
│   ├── crontab.example
│   ├── com.telegram-morning.plist
│   ├── telegram-morning.service
│   └── telegram-morning.timer
├── .github/workflows/morning.yml <- cloud path (GitHub Actions)
├── state/
│   └── .gitkeep                  <- runtime files here (git-ignored)
├── .python-version               <- pyenv
├── pyproject.toml                <- Poetry
├── Makefile
├── run.sh                        <- wrapper used by schedulers
├── config.yaml                   <- your live config (edit this)
├── config.example.yaml           <- template committed to git
├── .env                          <- your secrets (NEVER commit)
├── .env-example                  <- template committed to git
├── .gitignore
├── README.md                     <- full user documentation
└── plan.md                       <- this file
```

---

## 3. Step 1 — Install the toolchain

You need **pyenv**, **Poetry**, and **Ollama** (the local LLM runtime). You do **not** have a model
yet; you'll download one in Step 20.

**macOS (Homebrew):**
```bash
brew install pyenv poetry
brew install --cask ollama          # or download the app from https://ollama.com/download
```

**Linux:**
```bash
curl -fsSL https://pyenv.run | bash                      # pyenv
curl -sSL https://install.python-poetry.org | python3 -  # poetry
curl -fsSL https://ollama.com/install.sh | sh            # ollama
```

Then make sure pyenv is initialized in your shell (add to `~/.zshrc` or `~/.bashrc` if not already):
```bash
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```
Open a new terminal after editing your shell file.

✅ **Verify:**
```bash
pyenv --version && poetry --version && ollama --version
```
All three print a version. If `ollama --version` errors, ensure the Ollama app/service is installed
and running.

---

## 4. Step 2 — Get Telegram credentials

1. In Telegram, message **@BotFather** → send `/newbot` → follow prompts → copy the **bot token**
   (looks like `123456789:AAE...`).
2. Send any message (e.g. "hi") to your new bot so it can see you.
3. Get your **chat id**: open this URL in a browser (replace `<TOKEN>`):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Read `result[0].message.chat.id`. (Or message **@userinfobot**, which replies with your id.)

✅ **Verify:** you have a bot token and a numeric chat id written down for Step 8.

---

## 5. Step 3 — Initialize the repo

From the repo root `telegram_morning/`:
```bash
git init
mkdir -p telegram_morning tests deploy state .github/workflows
touch state/.gitkeep
```

✅ **Verify:** `ls` shows `telegram_morning/ tests/ deploy/ state/ .github/`.

---

## 6. Step 4 — `.python-version` (pyenv)

Create **`.python-version`** with exactly one line:
```text
3.11.9
```

Install that Python with pyenv:
```bash
pyenv install -s 3.11.9
```

✅ **Verify:** `pyenv versions` lists `3.11.9`.

---

## 7. Step 5 — `pyproject.toml` (Poetry)

Create **`pyproject.toml`**:
```toml
[tool.poetry]
name = "telegram-morning"
version = "1.0.0"
description = "Daily Telegram weather message in a random character's voice (ES/EN)."
authors = ["Your Name <you@example.com>"]
readme = "README.md"
packages = [{ include = "telegram_morning" }]

[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.31"
PyYAML = "^6.0"
python-dotenv = "^1.0"
tzdata = "^2024.1"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"

[tool.poetry.scripts]
telegram-morning = "telegram_morning.main:main"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry-core"
```

✅ **Verify:** `python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('toml ok')"`
prints `toml ok`.

---

## 8. Step 6 — `Makefile`

Create **`Makefile`**. ⚠️ **Every indented recipe line must begin with a real TAB, not spaces.**
```makefile
PYTHON_VERSION := 3.11.9
OLLAMA_MODEL   ?= llama3.2

.PHONY: help setup install ollama-pull run check dry send test clean

help:              ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup:             ## First-time setup: Python, deps, and config/.env from templates
	pyenv install -s $(PYTHON_VERSION)
	pyenv local $(PYTHON_VERSION)
	poetry env use $$(pyenv which python)
	poetry install
	@[ -f .env ] || cp .env-example .env
	@[ -f config.yaml ] || cp config.example.yaml config.yaml
	@echo ">> Setup done. Now edit .env and config.yaml, then run: make ollama-pull"

install:           ## Install/refresh Python dependencies
	poetry install

ollama-pull:       ## Download the local LLM model (needed for provider: ollama)
	ollama pull $(OLLAMA_MODEL)

run:               ## Run once, respecting the schedule (this is what cron calls)
	poetry run python -m telegram_morning.main

check:             ## Print whether it WOULD send right now (no send)
	poetry run python -m telegram_morning.main --check

dry:               ## Generate a message and print it, WITHOUT sending
	poetry run python -m telegram_morning.main --force --dry-run

send:              ## Force-send a message right now (end-to-end test)
	poetry run python -m telegram_morning.main --force

test:              ## Run offline unit tests
	poetry run pytest -q

clean:             ## Remove caches and runtime state
	rm -rf .pytest_cache **/__pycache__ __pycache__ state/*.json state/*.log
```

✅ **Verify:** `make help` prints the list of commands. If you get
`Makefile:NN: *** missing separator`, a recipe line uses spaces instead of a tab — fix it.

---

## 9. Step 7 — `.gitignore`

Create **`.gitignore`**:
```gitignore
# secrets
.env

# runtime state
state/*.json
state/*.log

# python / poetry
__pycache__/
*.pyc
.pytest_cache/
.venv/
dist/
```

✅ **Verify:** `cat .gitignore` includes `.env`.

---

## 10. Step 8 — `.env-example` and `.env`

Create **`.env-example`** (committed; no real secrets):
```dotenv
# ---- Telegram (required) ---------------------------------------------------
# From @BotFather and the getUpdates URL (see plan Step 2).
TELEGRAM_BOT_TOKEN=123456789:AA-replace-with-your-bot-token
TELEGRAM_CHAT_ID=123456789

# ---- Cloud LLM keys (optional) ---------------------------------------------
# Only needed if you select a cloud provider in config.yaml. Ollama needs none.
# The provider entry in config.yaml points to ONE of these by name (api_key_env).
GROQ_API_KEY=
OPENAI_API_KEY=
OPENROUTER_API_KEY=

# ---- Optional overrides ----------------------------------------------------
# Override where local Ollama lives (default http://localhost:11434):
# OLLAMA_HOST=http://localhost:11434
```

Copy to **`.env`** and fill in real values (at minimum the two Telegram lines):
```bash
cp .env-example .env
```

✅ **Verify:** `.env` has your real `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, and `git status`
does **not** list `.env`.

---

## 11. Step 9 — `config.example.yaml` and `config.yaml`

Create **`config.example.yaml`** (full schema, commented):
```yaml
# ============================ telegram_morning ==============================

# Message language: "es" (Spanish) or "en" (English)
language: es

# IANA timezone — handles winter/summer (DST) automatically.
# Examples: "Europe/Madrid", "America/Argentina/Buenos_Aires", "America/New_York"
timezone: "Europe/Madrid"

# Local wall-clock time to send (24h "HH:MM"), interpreted in `timezone` above.
send_time: "07:30"

# The scheduler fires often; the program sends once when local time is within
# [send_time, send_time + send_window_minutes]. Keep this >= your scheduler
# interval (and >= expected GitHub Actions delay, so >= 60 for the cloud path).
send_window_minutes: 60

# Weather location: give a city (auto-geocoded) OR latitude+longitude.
location:
  city: "Madrid"          # used if latitude/longitude are omitted
  # latitude: 40.4168
  # longitude: -3.7038
  name: "Madrid"          # friendly name shown in the message (optional)

weather:
  units: metric           # "metric" (°C, km/h) or "imperial" (°F, mph)

# --------------------------------- LLM -------------------------------------
# Both LOCAL (Ollama) and CLOUD providers use the same OpenAI-compatible API.
# Pick the active one with `provider`. Optionally set `fallback_provider`
# (tried automatically if the primary errors). Cloud keys live in .env and are
# referenced by name via `api_key_env`.
llm:
  provider: ollama              # active provider (a key under `providers`)
  fallback_provider: null       # e.g. "groq" to fall back when Ollama is off
  temperature: 0.9
  max_tokens: 300
  timeout_seconds: 60
  providers:
    ollama:
      base_url: "http://localhost:11434/v1"
      model: "llama3.2"
      api_key_env: null         # local Ollama needs no key
    groq:
      base_url: "https://api.groq.com/openai/v1"
      model: "llama-3.3-70b-versatile"
      api_key_env: GROQ_API_KEY
    openai:
      base_url: "https://api.openai.com/v1"
      model: "gpt-4o-mini"
      api_key_env: OPENAI_API_KEY
    openrouter:
      base_url: "https://openrouter.ai/api/v1"
      model: "meta-llama/llama-3.1-8b-instruct"
      api_key_env: OPENROUTER_API_KEY

telegram:
  parse_mode: "none"            # "none" (safest), "HTML", or "Markdown"
  disable_notification: false

message:
  include_emoji: true
  max_chars: 800
  show_character_name: true     # prepend e.g. "🏴‍☠️ Pirate" above the message

# How to choose the character each day:
#   "random"     -> random every run
#   "sequential" -> deterministic rotation by day-of-year
character_selection: random

# The character roster. Each has an id, an emoji, and a persona in BOTH languages.
# Fully editable — add, remove, or rewrite personas freely.
characters:
  - id: pirate
    emoji: "🏴‍☠️"
    persona:
      en: "a boisterous pirate who describes the weather like conditions on the high seas, using 'arr' and nautical slang"
      es: "un pirata escandaloso que describe el clima como si fueran las condiciones en alta mar, usando '¡arr!' y jerga náutica"
  - id: detective
    emoji: "🕵️"
    persona:
      en: "a hard-boiled noir detective who treats today's weather like a case to crack"
      es: "un detective de novela negra que trata el clima de hoy como un caso por resolver"
  - id: scientist
    emoji: "🔬"
    persona:
      en: "an excitable scientist who explains the weather with precise, nerdy enthusiasm"
      es: "una cientifica entusiasta que explica el clima con precision y emocion friki"
  - id: cheerful
    emoji: "😄"
    persona:
      en: "a relentlessly cheerful optimist who finds delight in any forecast"
      es: "una optimista incansablemente alegre que encuentra encanto en cualquier pronostico"
  - id: grumpy
    emoji: "😠"
    persona:
      en: "a grumpy curmudgeon who complains about the weather no matter what it is"
      es: "un cascarrabias grunon que se queja del clima sin importar como sea"
  - id: poet
    emoji: "🪶"
    persona:
      en: "a romantic poet who renders the forecast as a short lyrical verse"
      es: "un poeta romantico que convierte el pronostico en un breve verso lirico"
  - id: robot
    emoji: "🤖"
    persona:
      en: "a deadpan robot reporting weather as clipped system diagnostics"
      es: "un robot inexpresivo que reporta el clima como diagnosticos de sistema"
  - id: cowboy
    emoji: "🤠"
    persona:
      en: "a laid-back cowboy drawling about the sky over the prairie"
      es: "un vaquero relajado que habla con acento sobre el cielo de la pradera"
  - id: caveman
    emoji: "🪨"
    persona:
      en: "a caveman with a very limited vocabulary who grunts short, simple words about the weather"
      es: "un cavernicola con vocabulario muy limitado que grune palabras cortas y simples sobre el clima"
  - id: surfer
    emoji: "🏄"
    persona:
      en: "a chill surfer rating the day by vibes and whether it's gnarly out there"
      es: "un surfista relajado que evalua el dia por las buenas ondas y si esta bravo el clima"
```

> **Note on the roster:** the original "person with limited capacity" idea is written here as a
> **caveman with a very limited vocabulary** — a comedic limited-vocabulary voice that does not mock
> real people or disabilities. Everything is editable in `config.yaml`.

Copy to the live config (or let `make setup` do it):
```bash
cp config.example.yaml config.yaml
```

✅ **Verify:** `python3 -c "import yaml; yaml.safe_load(open('config.yaml')); print('yaml ok')"`
prints `yaml ok`.

---

## 12. Step 10 — `telegram_morning/__init__.py`

Create **`telegram_morning/__init__.py`**:
```python
"""telegram_morning — daily weather message in a random character's voice."""
__version__ = "1.0.0"
```

---

## 13. Step 11 — `telegram_morning/config.py`

Create **`telegram_morning/config.py`**:
```python
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# telegram_morning/config.py -> parents[0]=package dir, parents[1]=repo root
REPO_ROOT = Path(__file__).resolve().parents[1]


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
    if not cfg.get("timezone"):
        raise ValueError("config.timezone is required (IANA name, e.g. 'Europe/Madrid')")
    if not cfg.get("send_time"):
        raise ValueError("config.send_time is required, e.g. '07:30'")

    loc = cfg.get("location") or {}
    has_coords = loc.get("latitude") is not None and loc.get("longitude") is not None
    if not (loc.get("city") or has_coords):
        raise ValueError("config.location needs either 'city' or 'latitude'+'longitude'")

    if not cfg.get("characters"):
        raise ValueError("config.characters must have at least one character")

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
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
```

✅ **Verify:**
```bash
poetry run python -c "from telegram_morning.config import get_config; c=get_config(); print('config ok:', c['language'], c['timezone'], c['llm']['provider'])"
```
Prints `config ok: <lang> <tz> <provider>`. (If Poetry env isn't ready yet, do Step 20 first, then
re-run this verify.)

---

## 14. Step 12 — `telegram_morning/weather.py`

Create **`telegram_morning/weather.py`**:
```python
from __future__ import annotations

import requests

# WMO weather codes -> localized text + emoji (Open-Meteo daily.weather_code)
WMO = {
    0:  {"en": "clear sky", "es": "cielo despejado", "emoji": "☀️"},
    1:  {"en": "mainly clear", "es": "mayormente despejado", "emoji": "🌤️"},
    2:  {"en": "partly cloudy", "es": "parcialmente nublado", "emoji": "⛅"},
    3:  {"en": "overcast", "es": "nublado", "emoji": "☁️"},
    45: {"en": "fog", "es": "niebla", "emoji": "🌫️"},
    48: {"en": "rime fog", "es": "niebla con escarcha", "emoji": "🌫️"},
    51: {"en": "light drizzle", "es": "llovizna ligera", "emoji": "🌦️"},
    53: {"en": "drizzle", "es": "llovizna", "emoji": "🌦️"},
    55: {"en": "dense drizzle", "es": "llovizna densa", "emoji": "🌦️"},
    61: {"en": "light rain", "es": "lluvia ligera", "emoji": "🌧️"},
    63: {"en": "rain", "es": "lluvia", "emoji": "🌧️"},
    65: {"en": "heavy rain", "es": "lluvia fuerte", "emoji": "🌧️"},
    66: {"en": "freezing rain", "es": "lluvia helada", "emoji": "🌧️"},
    67: {"en": "heavy freezing rain", "es": "lluvia helada fuerte", "emoji": "🌧️"},
    71: {"en": "light snow", "es": "nieve ligera", "emoji": "🌨️"},
    73: {"en": "snow", "es": "nieve", "emoji": "🌨️"},
    75: {"en": "heavy snow", "es": "nieve fuerte", "emoji": "❄️"},
    77: {"en": "snow grains", "es": "granos de nieve", "emoji": "🌨️"},
    80: {"en": "rain showers", "es": "chubascos", "emoji": "🌦️"},
    81: {"en": "moderate showers", "es": "chubascos moderados", "emoji": "🌧️"},
    82: {"en": "violent showers", "es": "chubascos violentos", "emoji": "⛈️"},
    85: {"en": "snow showers", "es": "chubascos de nieve", "emoji": "🌨️"},
    86: {"en": "heavy snow showers", "es": "chubascos de nieve fuertes", "emoji": "❄️"},
    95: {"en": "thunderstorm", "es": "tormenta", "emoji": "⛈️"},
    96: {"en": "thunderstorm w/ hail", "es": "tormenta con granizo", "emoji": "⛈️"},
    99: {"en": "severe thunderstorm w/ hail", "es": "tormenta fuerte con granizo", "emoji": "⛈️"},
}


def _geocode(city: str):
    r = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
        timeout=20,
    )
    r.raise_for_status()
    results = r.json().get("results")
    if not results:
        raise ValueError(f"Could not geocode city: {city!r}")
    top = results[0]
    return top["latitude"], top["longitude"], top.get("name", city)


def get_weather(cfg: dict) -> dict:
    loc = cfg["location"]
    lang = cfg["language"]
    units = (cfg.get("weather") or {}).get("units", "metric")

    if loc.get("latitude") is not None and loc.get("longitude") is not None:
        lat, lon = loc["latitude"], loc["longitude"]
        name = loc.get("name") or loc.get("city") or "your location"
    else:
        lat, lon, geo_name = _geocode(loc["city"])
        name = loc.get("name") or geo_name

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,wind_speed_10m_max",
        "timezone": cfg["timezone"],
        "forecast_days": 1,
        "temperature_unit": "celsius" if units == "metric" else "fahrenheit",
        "wind_speed_unit": "kmh" if units == "metric" else "mph",
    }
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=20)
    r.raise_for_status()
    daily = r.json()["daily"]

    code = daily["weather_code"][0]
    desc = WMO.get(code, {"en": "unknown", "es": "desconocido", "emoji": "🌡️"})

    return {
        "location_name": name,
        "description": desc[lang],
        "emoji": desc["emoji"],
        "temp_max": daily["temperature_2m_max"][0],
        "temp_min": daily["temperature_2m_min"][0],
        "precip_prob": daily["precipitation_probability_max"][0],
        "wind_max": daily["wind_speed_10m_max"][0],
        "temp_unit": "°C" if units == "metric" else "°F",
        "wind_unit": "km/h" if units == "metric" else "mph",
    }
```

✅ **Verify:**
```bash
poetry run python -c "from telegram_morning.config import get_config; from telegram_morning.weather import get_weather; print(get_weather(get_config()))"
```
Prints a dict with a description and today's temps.

---

## 15. Step 13 — `telegram_morning/characters.py`

Create **`telegram_morning/characters.py`**:
```python
from __future__ import annotations

import random
from datetime import date


def pick_character(cfg: dict) -> dict:
    chars = cfg.get("characters") or []
    if not chars:
        raise ValueError("config.characters is empty")

    strategy = cfg.get("character_selection", "random")
    if strategy == "sequential":
        # Deterministic rotation: same character all day, advances by day.
        return chars[date.today().toordinal() % len(chars)]
    return random.choice(chars)
```

✅ **Verify:**
```bash
poetry run python -c "from telegram_morning.config import get_config; from telegram_morning.characters import pick_character; print(pick_character(get_config())['id'])"
```
Prints a character id.

---

## 16. Step 14 — `telegram_morning/llm.py` (local + cloud + fallback)

Create **`telegram_morning/llm.py`**:
```python
from __future__ import annotations

import os

import requests


def _build_messages(cfg: dict, character: dict, weather: dict) -> list[dict]:
    lang = cfg["language"]
    persona = character["persona"][lang]
    lang_name = "Spanish" if lang == "es" else "English"
    msg_cfg = cfg.get("message") or {}
    include_emoji = msg_cfg.get("include_emoji", True)
    max_chars = msg_cfg.get("max_chars", 800)

    system = (
        f"You are {persona}. "
        f"You are sending a short good-morning weather message to a friend. "
        f"Write the ENTIRE message in {lang_name}. Stay fully in character: match that "
        f"voice, tone and vocabulary. Keep it under {max_chars} characters. "
        + ("Use a few fitting emojis. " if include_emoji else "Do not use any emojis. ")
        + "Do not mention that you are playing a character; just speak as them."
    )

    w = weather
    if lang == "es":
        facts = (
            f"Clima de hoy en {w['location_name']}: {w['description']} {w['emoji']}. "
            f"Maxima {w['temp_max']}{w['temp_unit']}, minima {w['temp_min']}{w['temp_unit']}. "
            f"Probabilidad de precipitacion {w['precip_prob']}%. "
            f"Viento maximo {w['wind_max']} {w['wind_unit']}. "
            f"Escribe el mensaje de buenos dias sobre este clima."
        )
    else:
        facts = (
            f"Today's weather in {w['location_name']}: {w['description']} {w['emoji']}. "
            f"High {w['temp_max']}{w['temp_unit']}, low {w['temp_min']}{w['temp_unit']}. "
            f"Chance of precipitation {w['precip_prob']}%. "
            f"Max wind {w['wind_max']} {w['wind_unit']}. "
            f"Write the good-morning message about this weather."
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": facts},
    ]


def _resolve_provider(cfg: dict, name: str):
    """Return (name, base_url, model, api_key) for the named provider."""
    providers = (cfg.get("llm") or {}).get("providers") or {}
    if name not in providers:
        raise ValueError(f"llm.providers has no entry named '{name}'")
    p = providers[name]
    base_url = str(p["base_url"]).rstrip("/")
    model = p["model"]
    key_env = p.get("api_key_env")
    api_key = (os.environ.get(key_env) if key_env else None) or "ollama"
    return name, base_url, model, api_key


def _call_provider(cfg: dict, name: str, messages: list[dict]) -> str:
    llm_cfg = cfg.get("llm") or {}
    _, base_url, model, api_key = _resolve_provider(cfg, name)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": llm_cfg.get("temperature", 0.9),
        "max_tokens": llm_cfg.get("max_tokens", 300),
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers=headers,
        timeout=llm_cfg.get("timeout_seconds", 60),
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def generate_message(cfg: dict, character: dict, weather: dict) -> str:
    """Try the primary provider, then the fallback, then a templated message."""
    llm_cfg = cfg.get("llm") or {}
    order = [llm_cfg.get("provider", "ollama")]
    fb = llm_cfg.get("fallback_provider")
    if fb and fb not in order:
        order.append(fb)

    messages = _build_messages(cfg, character, weather)
    last_err: Exception | None = None
    for name in order:
        try:
            return _call_provider(cfg, name, messages)
        except Exception as err:  # network down, model missing, bad key, etc.
            last_err = err
    return _fallback_message(cfg, character, weather, last_err)


def _fallback_message(cfg: dict, character: dict, weather: dict, err) -> str:
    lang = cfg["language"]
    w = weather
    if lang == "es":
        return (
            f"¡Buenos dias! Hoy en {w['location_name']}: {w['description']} {w['emoji']}, "
            f"max {w['temp_max']}{w['temp_unit']} / min {w['temp_min']}{w['temp_unit']}, "
            f"lluvia {w['precip_prob']}%. (mensaje sin LLM: {type(err).__name__})"
        )
    return (
        f"Good morning! Today in {w['location_name']}: {w['description']} {w['emoji']}, "
        f"high {w['temp_max']}{w['temp_unit']} / low {w['temp_min']}{w['temp_unit']}, "
        f"rain {w['precip_prob']}%. (LLM-free message: {type(err).__name__})"
    )
```

✅ **Verify (after Step 20, with Ollama running):**
```bash
poetry run python -c "from telegram_morning.config import get_config; from telegram_morning.weather import get_weather; from telegram_morning.characters import pick_character; from telegram_morning.llm import generate_message; c=get_config(); w=get_weather(c); ch=pick_character(c); print(ch['id']); print(generate_message(c, ch, w))"
```
Prints an in-character message in the configured language (or the fallback line if the LLM is
unreachable — that is expected behavior).

---

## 17. Step 15 — `telegram_morning/telegram_client.py`

Create **`telegram_morning/telegram_client.py`**:
```python
from __future__ import annotations

import requests


def send_message(cfg: dict, text: str) -> dict:
    token = cfg["_secrets"]["telegram_bot_token"]
    chat_id = cfg["_secrets"]["telegram_chat_id"]
    tg = cfg.get("telegram") or {}

    payload = {"chat_id": chat_id, "text": text}
    parse_mode = tg.get("parse_mode")
    if parse_mode and parse_mode.lower() != "none":
        payload["parse_mode"] = parse_mode
    if tg.get("disable_notification"):
        payload["disable_notification"] = True

    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
```

> Keep `telegram.parse_mode: "none"` (plain text). LLM output can contain characters that break
> Telegram's HTML/Markdown parser and cause a 400 error.

---

## 18. Step 16 — `telegram_morning/scheduler.py`

Create **`telegram_morning/scheduler.py`**:
```python
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


def should_send_now(cfg: dict) -> tuple[bool, str]:
    """True if current local time is in the send window and nothing sent today.

    zoneinfo applies DST rules automatically, so send_time is always wall-clock
    local time in cfg['timezone'] — correct in both winter and summer.
    """
    tz = ZoneInfo(cfg["timezone"])
    now = datetime.now(tz)

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
```

> Don't set a `send_time` + window that crosses midnight (e.g. `23:40` + 60 min). For a morning
> bot this never happens.

✅ **Verify:**
```bash
poetry run python -c "from telegram_morning.config import get_config; from telegram_morning.scheduler import should_send_now; print(should_send_now(get_config()))"
```
Prints `(True, ...)` if the current local time is within your window, else `(False, reason)`.

---

## 19. Step 17 — `telegram_morning/main.py`

Create **`telegram_morning/main.py`**:
```python
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


def run(force=False, dry_run=False, check_only=False, config_path=None) -> int:
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
    character = characters.pick_character(cfg)
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
    args = ap.parse_args()
    sys.exit(run(force=args.force, dry_run=args.dry_run, check_only=args.check, config_path=args.config))


if __name__ == "__main__":
    main()
```

---

## 20. Step 18 — `run.sh` (wrapper for schedulers)

Create **`run.sh`**. It sets a robust PATH (cron/launchd start with a minimal PATH and won't find
pyenv/poetry otherwise) and runs via Poetry:
```bash
#!/usr/bin/env bash
set -euo pipefail

# Schedulers (cron/launchd/systemd) start with a minimal PATH; add common locations.
export PATH="$HOME/.local/bin:$HOME/.pyenv/shims:$HOME/.pyenv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

cd "$(dirname "$0")"
exec poetry run python -m telegram_morning.main "$@"
```
Make it executable:
```bash
chmod +x run.sh
```

✅ **Verify (after Step 20 setup):** `./run.sh --check` prints a `would_send=...` line.

---

## 21. Step 19 — `tests/test_core.py` (offline unit tests)

Create **`tests/test_core.py`**:
```python
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram_morning import characters, scheduler, llm


def _cfg(tmp):
    return {
        "_repo_root": str(tmp),
        "language": "es",
        "timezone": "Europe/Madrid",
        "send_time": "07:30",
        "send_window_minutes": 60,
        "character_selection": "random",
        "characters": [{"id": "pirate", "emoji": "P", "persona": {"es": "un pirata", "en": "a pirate"}}],
        "message": {"include_emoji": True, "max_chars": 800},
        "llm": {
            "provider": "ollama",
            "temperature": 0.9,
            "max_tokens": 300,
            "providers": {
                "ollama": {"base_url": "http://localhost:11434/v1", "model": "m", "api_key_env": None},
                "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "g", "api_key_env": "GROQ_API_KEY"},
            },
        },
        "_secrets": {},
    }


def test_pick_character(tmp_path):
    assert characters.pick_character(_cfg(tmp_path))["id"] == "pirate"


def test_window_and_dedupe(tmp_path):
    c = _cfg(tmp_path)
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    c["send_time"] = now.strftime("%H:%M")
    ok, _ = scheduler.should_send_now(c)
    assert ok is True
    scheduler.mark_sent(c)
    ok2, reason = scheduler.should_send_now(c)
    assert ok2 is False and "sent today" in reason.lower()


def test_build_messages_language(tmp_path):
    c = _cfg(tmp_path)
    ch = c["characters"][0]
    w = {"location_name": "Madrid", "description": "despejado", "emoji": "S",
         "temp_max": 30, "temp_min": 18, "precip_prob": 10, "wind_max": 12,
         "temp_unit": "C", "wind_unit": "kmh"}
    assert "Spanish" in llm._build_messages(c, ch, w)[0]["content"]
    c["language"] = "en"
    assert "English" in llm._build_messages(c, ch, w)[0]["content"]


def test_resolve_provider(tmp_path):
    c = _cfg(tmp_path)
    os.environ["GROQ_API_KEY"] = "secret123"
    name, base, model, key = llm._resolve_provider(c, "groq")
    assert base == "https://api.groq.com/openai/v1" and model == "g" and key == "secret123"
    # Ollama needs no key -> defaults to the harmless placeholder.
    _, _, _, k2 = llm._resolve_provider(c, "ollama")
    assert k2 == "ollama"
```

✅ **Verify:** run in Step 21 via `make test`.

---

## 22. Step 20 — Set up the environment & download the model

Now wire everything together with the toolchain.

```bash
make setup          # pyenv python + poetry install + copies .env/config.yaml if missing
# (If you already created .env and config.yaml, setup keeps them.)
```

Edit `.env` (Telegram token + chat id) and `config.yaml` (language, timezone, send_time, location)
if you haven't. Then **download the local model** (you don't have one yet):

```bash
make ollama-pull                     # downloads llama3.2 (~2 GB) — needs internet + disk space
# smaller option for low-RAM machines:  OLLAMA_MODEL=llama3.2:1b make ollama-pull
ollama list                          # confirm the model is present
curl http://localhost:11434/v1/models  # confirm Ollama's API answers
```

Model size guidance: `llama3.2` (3B) ≈ 2 GB download, comfortable on 8 GB RAM. `llama3.2:1b` ≈ 1.3 GB
for tighter machines. Bigger models = better prose but more RAM/disk. Whatever you pull, set the same
name in `config.yaml` → `llm.providers.ollama.model`.

✅ **Verify:**
```bash
make test           # all offline unit tests pass
make check          # prints a would_send=... line, no error
```

---

## 23. Step 21 — End-to-end tests

With Ollama running (or a cloud provider configured) and `.env` filled in:
```bash
make dry            # prints an in-character message in your language; sends nothing
make send           # actually sends to Telegram; you should receive it on your phone
```
After `make send`, `state/last_sent.json` exists. Running `make run` again the same day prints
`Skipping: Already sent today`.

Test language switching: set `language: en` in `config.yaml`, run `make dry` again, confirm English;
set it back to `es` if you prefer Spanish.

✅ **Verify:** message received in Telegram; `cat state/last_sent.json` shows today's date; both
languages work via `make dry`.

---

## 24. Step 22 — Local scheduling (recommended for local Ollama)

Because a local Ollama model needs this machine awake, use a local scheduler. Pick **one**. All of
them just run `run.sh` every 30 minutes; the program itself decides whether to send. Replace
`/ABS/PATH/TO/telegram_morning` with the real path (`pwd` from the repo root prints it).

### 24a. cron (macOS or Linux) — simplest
Create **`deploy/crontab.example`**:
```cron
# Run every 30 minutes; the program decides if it's actually time to send.
*/30 * * * * /ABS/PATH/TO/telegram_morning/run.sh >> /ABS/PATH/TO/telegram_morning/state/cron.log 2>&1
```
Install:
```bash
crontab -e     # paste the line with real absolute paths, save
crontab -l     # confirm
```
The machine must be awake at send time. On macOS, if the job can't read files, grant
Terminal/cron **Full Disk Access** in System Settings → Privacy & Security.

### 24b. launchd (macOS-native, survives sleep better)
Create **`deploy/com.telegram-morning.plist`**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.telegram-morning</string>
  <key>ProgramArguments</key>
  <array>
    <string>/ABS/PATH/TO/telegram_morning/run.sh</string>
  </array>
  <key>StartInterval</key>
  <integer>1800</integer>
  <key>StandardOutPath</key>
  <string>/ABS/PATH/TO/telegram_morning/state/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>/ABS/PATH/TO/telegram_morning/state/launchd.err</string>
</dict>
</plist>
```
Install:
```bash
cp deploy/com.telegram-morning.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.telegram-morning.plist
launchctl list | grep telegram-morning
# remove later: launchctl unload ~/Library/LaunchAgents/com.telegram-morning.plist
```

### 24c. systemd (Linux server)
Create **`deploy/telegram-morning.service`** (set `User=` and `HOME` to the real user):
```ini
[Unit]
Description=Telegram morning weather bot (one-shot)
After=network-online.target

[Service]
Type=oneshot
User=YOURUSER
Environment=HOME=/home/YOURUSER
WorkingDirectory=/ABS/PATH/TO/telegram_morning
ExecStart=/ABS/PATH/TO/telegram_morning/run.sh
```
Create **`deploy/telegram-morning.timer`**:
```ini
[Unit]
Description=Run telegram-morning every 30 minutes

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```
Install:
```bash
sudo cp deploy/telegram-morning.service /etc/systemd/system/
sudo cp deploy/telegram-morning.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-morning.timer
systemctl list-timers | grep telegram-morning
```
`Persistent=true` runs a missed job after the machine powers back on.

✅ **Verify:** temporarily set `send_time` to a couple of minutes ahead, wait for the next tick,
confirm a message arrives, then restore `send_time`. The chosen scheduler's log in `state/` records
runs.

---

## 25. Step 23 — GitHub Actions (cloud path, computer OFF)

This makes the bot run entirely in the cloud so your computer can be off — **but GitHub's runners
cannot reach a local Ollama.** Use a **cloud provider** for this path: in `config.yaml` set
`llm.provider` to e.g. `groq` (or `openai`), and add that provider's key as a GitHub secret.

Create **`.github/workflows/morning.yml`**:
```yaml
name: telegram-morning

on:
  schedule:
    # Every 30 min. GitHub cron is UTC; the program converts to your timezone
    # (DST-safe). Top-of-hour runs can be delayed 5-30 min, so keep
    # send_window_minutes >= 60.
    - cron: "*/30 * * * *"
  workflow_dispatch: {}   # manual "Run workflow" button for testing

jobs:
  send:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Persist the once-per-day guard across ephemeral runs.
      - uses: actions/cache@v4
        with:
          path: state
          key: telegram-morning-state-${{ github.run_id }}
          restore-keys: telegram-morning-state-

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pipx install poetry
      - run: poetry install --only main
      - run: poetry run python -m telegram_morning.main
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```
Setup: push the repo to GitHub, then **Settings → Secrets and variables → Actions** → add
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and your cloud key (e.g. `GROQ_API_KEY`). Set
`llm.provider` in `config.yaml` to that cloud provider before relying on this.

**Cost/limits:** public repos run free; private repos include 2,000 Linux min/month (a ~2-min daily
job ≈ 60 min/month). Scheduled runs can lag 5–30 min at the top of the hour; workflows auto-disable
after 60 days of repo inactivity.

✅ **Verify:** in the Actions tab, use **Run workflow** (workflow_dispatch) with `--force` behavior
by temporarily widening the window, and confirm a Telegram message arrives.

---

## 26. Step 24 — `README.md` (full documentation)

Create **`README.md`**:
```markdown
# telegram_morning

Sends a daily Telegram message about today's weather, written in the voice of a **random character**
(pirate, detective, scientist, grumpy, …). Configurable in **Spanish or English**. The LLM can be a
**local model (Ollama)** or a **cloud provider** — your choice, in `config.yaml`.

## Table of contents
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Install](#install)
- [Configure](#configure)
- [Run](#run)
- [Schedule it](#schedule-it)
- [Modify & extend](#modify--extend)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## How it works
A scheduler runs the program every ~30 minutes. Each run checks the current wall-clock time in your
configured IANA timezone (DST handled automatically by Python's `zoneinfo`). If it's within
`[send_time, send_time + send_window_minutes]` and nothing was sent today, it: fetches today's
weather (Open-Meteo), picks a random character, asks the LLM to write the message in that character's
voice and your language, sends it via the Telegram Bot API, and records the date in
`state/last_sent.json` (so at most one message per day). There is no always-on process — the OS
scheduler (or GitHub Actions) triggers each run.

## Requirements
- pyenv, Poetry, and Python 3.11 (installed via pyenv)
- For a local LLM: Ollama + a downloaded model
- For a cloud LLM: an API key from a provider (Groq, OpenAI, OpenRouter, …)
- A Telegram bot token + your chat id

## Install
```bash
# 1. Tools (macOS)
brew install pyenv poetry
brew install --cask ollama          # or https://ollama.com/download

# 2. Project
make setup                          # installs Python 3.11 + deps, copies templates
#   edit .env         -> TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
#   edit config.yaml  -> language, timezone, send_time, location, llm.provider

# 3. Local model (skip if using a cloud provider)
make ollama-pull                    # downloads llama3.2
```
Get Telegram credentials: message @BotFather → `/newbot` (token); message your bot, then open
`https://api.telegram.org/bot<TOKEN>/getUpdates` and read `result[0].message.chat.id`.

## Configure
All settings live in `config.yaml`; secrets live in `.env`. Key fields:

| Field | Meaning |
|---|---|
| `language` | `es` or `en` |
| `timezone` | IANA name, e.g. `Europe/Madrid` (DST automatic) |
| `send_time` | local `HH:MM` to send |
| `send_window_minutes` | how long after `send_time` a run may still send |
| `location.city` / `latitude`+`longitude` | where to get weather |
| `weather.units` | `metric` or `imperial` |
| `llm.provider` | active provider key (e.g. `ollama`, `groq`) |
| `llm.fallback_provider` | tried if the primary fails (or `null`) |
| `llm.providers.<name>` | `base_url`, `model`, `api_key_env` per provider |
| `telegram.parse_mode` | `none` (safest), `HTML`, or `Markdown` |
| `message.show_character_name` | prepend the character label |
| `character_selection` | `random` or `sequential` |
| `characters` | roster; each has `id`, `emoji`, `persona.en`, `persona.es` |

### Switch language
Set `language: en` (or `es`) in `config.yaml`. Personas exist per language.

### Switch to a cloud LLM (computer can be off)
1. Put the key in `.env`, e.g. `GROQ_API_KEY=...`
2. Set `llm.provider: groq` in `config.yaml`
3. (Optional) keep local as fallback at home: `llm.provider: ollama`, `llm.fallback_provider: groq`

## Run
```bash
make check     # would it send right now?
make dry       # generate + print, don't send
make send      # force-send now (test)
make run       # run respecting the schedule (what cron calls)
make test      # offline unit tests
```
CLI equivalents: `poetry run python -m telegram_morning.main [--check|--dry-run|--force] [--config PATH]`.

## Schedule it
- **Local (for Ollama):** cron, launchd (macOS), or systemd (Linux) — see `deploy/`. They run
  `run.sh` every 30 min; the program self-checks the time.
- **Cloud (computer off):** GitHub Actions (`.github/workflows/morning.yml`) with a cloud provider.

## Modify & extend
- **Add a character:** add an entry under `characters` with `id`, `emoji`, `persona.en`, `persona.es`.
- **Change send time / zone:** edit `send_time` and `timezone`.
- **Change location:** edit `location.city` or set `latitude`+`longitude`.
- **Add a new LLM provider:** add an entry under `llm.providers` (`base_url`, `model`,
  `api_key_env`), put the key in `.env`, point `llm.provider` at it. No code changes needed —
  everything OpenAI-compatible just works.
- **Add a weather field:** extend the `daily=` list and the returned dict in `telegram_morning/weather.py`.

## Troubleshooting
- **Telegram 400 "chat not found":** wrong chat id, or you never messaged the bot first.
- **Telegram 400 "can't parse entities":** set `telegram.parse_mode: "none"`.
- **Always getting the fallback line:** the LLM is unreachable. For Ollama run `ollama list` /
  `ollama serve` and check `curl http://localhost:11434/v1/models`; for cloud, check the API key.
- **`make` says "missing separator":** a Makefile recipe used spaces instead of a tab.
- **cron never fires:** machine was asleep; use launchd/systemd or keep it awake.

## FAQ
**Does my computer need to be on?** With `provider: ollama` (local), yes — that machine must be
awake at send time. With a cloud provider + GitHub Actions, no.
**Is it free?** Open-Meteo is free; Ollama is free; GitHub Actions is free for public repos. Cloud
LLMs may have free tiers or small costs.
**Will it send twice?** No — `state/last_sent.json` enforces one message per local day.
```

✅ **Verify:** `README.md` exists and renders.

---

## 27. Step 25 — Final verification checklist (Definition of Done)

Run each; all must pass:

1. `pyenv --version && poetry --version && ollama --version` → all print versions
2. `make test` → all unit tests pass
3. `make check` → prints a `would_send=...` line, no error
4. `make dry` → prints an **in-character** message; switch `language` es↔en and re-run → both work
5. `make send` → message arrives in Telegram; `state/last_sent.json` written
6. `make run` again same day → `Skipping: Already sent today`
7. Provider switch: set `llm.provider` to a cloud provider with its key in `.env`, `make dry` →
   still works (proves both paths); then set `fallback_provider` and stop Ollama → `make dry` still
   produces a message via fallback
8. `git status` → `.env` is **not** listed
9. One scheduler from Step 22 (or GitHub Actions) is installed and its log shows runs

Then commit:
```bash
git add .
git commit -m "telegram_morning: daily character weather bot (ES/EN, local+cloud LLM)"
```

---

## 28. Requirement traceability (original ask → this plan)

- *Activates automatically without an on-state* → one-shot program + external scheduler (Steps 19, 22, 25).
- *Telegram message* → `telegram_client.py` (Step 17).
- *LLM-configurable character voice* → `llm.py` persona-driven prompt (Step 16).
- *All config via config.yaml* → Step 11 schema + `config.py` loader (Step 13).
- *.env and .env-example with Telegram info* → Step 10.
- *Configurable send time with timezone + winter/summer change* → `scheduler.py` + `zoneinfo` (Step 18).
- *Random character from a list* → `characters.py` + roster (Steps 15, 11).
- *Spanish/English configurable* → `language:` + per-language personas (Steps 11, 16).
- *Local LLM must be downloaded* → Ollama install + `make ollama-pull` (Steps 3, 20).
- *Both local and cloud, configurable* → provider map + fallback in `config.yaml`/`llm.py` (Steps 11, 16).
- *Python + Poetry + Makefile + pyenv* → Steps 6, 7, 8.
- *Plenty of documentation (how it works / install / configure / modify)* → Section 1 + README (Step 24).
```
