PYTHON_VERSION := 3.11.9
OLLAMA_MODEL   ?= llama3.2

.PHONY: help setup install ollama-pull run check dry send test github-secrets clean

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

dry:               ## Generate a message and print it, WITHOUT sending (optional CHARACTER=pirate)
	poetry run python -m telegram_morning.main --force --dry-run $(if $(CHARACTER),--character $(CHARACTER))

send:              ## Force-send a message right now (optional CHARACTER=pirate)
	poetry run python -m telegram_morning.main --force $(if $(CHARACTER),--character $(CHARACTER))

test:              ## Run offline unit tests
	poetry run pytest -q

github-secrets:    ## Copy Telegram + LLM keys from .env into GitHub Actions secrets (needs gh)
	@for k in TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID GROQ_API_KEY OPENAI_API_KEY OPENROUTER_API_KEY; do \
		v=$$(grep -E "^$$k=" .env | cut -d= -f2-); \
		if [ -n "$$v" ]; then printf '%s' "$$v" | gh secret set $$k && echo "  set $$k"; fi; \
	done

clean:             ## Remove caches and runtime state
	rm -rf .pytest_cache **/__pycache__ __pycache__ state/*.json state/*.log
