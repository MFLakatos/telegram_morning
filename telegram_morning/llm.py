from __future__ import annotations

import os
import sys

import requests


def _build_messages(cfg: dict, character: dict, weather: dict, twist: str | None = None) -> list[dict]:
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
    if twist:
        system += f" Today's twist (stay in character while doing this): {twist}"

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
    # Provider-specific extras from config, e.g. {"reasoning_effort": "low"}.
    payload.update((llm_cfg.get("providers") or {}).get(name, {}).get("extra_params") or {})
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers=headers,
        timeout=llm_cfg.get("timeout_seconds", 60),
    )
    if not r.ok:
        # Include the provider's explanation (e.g. "model ... does not exist").
        raise RuntimeError(f"HTTP {r.status_code} from {name} ({model}): {r.text[:300]}")
    content = (r.json()["choices"][0]["message"].get("content") or "").strip()
    if not content:
        raise RuntimeError(f"{name} ({model}) returned an empty message; try a higher llm.max_tokens")
    return content


def generate_message(cfg: dict, character: dict, weather: dict,
                     twist: str | None = None) -> tuple[str, bool]:
    """Try the primary provider, then the fallback, then a templated message.

    Returns (text, used_llm). used_llm is False when the templated message was used.
    """
    llm_cfg = cfg.get("llm") or {}
    order = [llm_cfg.get("provider", "ollama")]
    fb = llm_cfg.get("fallback_provider")
    if fb and fb not in order:
        order.append(fb)

    messages = _build_messages(cfg, character, weather, twist)
    last_err: Exception | None = None
    for name in order:
        try:
            return _call_provider(cfg, name, messages), True
        except Exception as err:  # network down, model missing, bad key, etc.
            print(f"[llm] provider '{name}' failed: {type(err).__name__}: {err}", file=sys.stderr)
            last_err = err
    return _fallback_message(cfg, character, weather, last_err), False


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
