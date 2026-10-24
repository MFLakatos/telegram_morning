import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from telegram_morning import characters, config, llm, scheduler

UTC = ZoneInfo("UTC")


def _cfg(tmp):
    return {
        "_repo_root": str(tmp),
        "language": "es",
        "timezone": "Europe/Madrid",
        "send_time": "07:30",
        "send_window_minutes": 60,
        "character_selection": "random",
        "characters": [
            {"id": "pirate", "emoji": "P", "persona": {"es": "un pirata", "en": "a pirate"}},
            {"id": "robot", "emoji": "R", "persona": {"es": "un robot", "en": "a robot"}},
        ],
        "location": {"city": "Madrid"},
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
        "_secrets": {"telegram_bot_token": "t", "telegram_chat_id": "1"},
    }


def test_pick_character_random_is_from_roster(tmp_path):
    assert characters.pick_character(_cfg(tmp_path))["id"] in ("pirate", "robot")


def test_pick_character_fixed(tmp_path):
    c = _cfg(tmp_path)
    c["character_selection"] = "fixed"
    c["character"] = "robot"
    for _ in range(10):
        assert characters.pick_character(c)["id"] == "robot"


def test_pick_character_sequential_rotates_by_day(tmp_path):
    c = _cfg(tmp_path)
    c["character_selection"] = "sequential"
    a = characters.pick_character(c, today=date(2026, 1, 1))["id"]
    b = characters.pick_character(c, today=date(2026, 1, 2))["id"]
    assert a != b


def test_validate_rejects_unknown_fixed_character(tmp_path):
    c = _cfg(tmp_path)
    c["character_selection"] = "fixed"
    c["character"] = "wizard"
    with pytest.raises(ValueError, match="not in the roster"):
        config._validate(c)


def test_validate_rejects_bad_timezone_and_time(tmp_path):
    c = _cfg(tmp_path)
    c["timezone"] = "Mars/Olympus"
    with pytest.raises(ValueError, match="timezone"):
        config._validate(c)
    c = _cfg(tmp_path)
    c["send_time"] = "7.30"
    with pytest.raises(ValueError, match="send_time"):
        config._validate(c)


def test_window_and_dedupe(tmp_path):
    c = _cfg(tmp_path)
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    c["send_time"] = now.strftime("%H:%M")
    ok, _ = scheduler.should_send_now(c, now=now)
    assert ok is True
    scheduler.mark_sent(c)
    ok2, reason = scheduler.should_send_now(c, now=now)
    assert ok2 is False and "sent today" in reason.lower()


def test_dst_winter_and_summer_same_wall_clock(tmp_path):
    """07:30 in Madrid is 06:30 UTC in winter (CET) and 05:30 UTC in summer (CEST)."""
    c = _cfg(tmp_path)
    c["send_window_minutes"] = 30
    winter = datetime(2026, 1, 15, 6, 35, tzinfo=UTC)
    summer = datetime(2026, 7, 15, 5, 35, tzinfo=UTC)
    summer_one_hour_late = datetime(2026, 7, 15, 6, 35, tzinfo=UTC)
    assert scheduler.should_send_now(c, now=winter)[0] is True
    assert scheduler.should_send_now(c, now=summer)[0] is True
    assert scheduler.should_send_now(c, now=summer_one_hour_late)[0] is False


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


def test_real_config_yaml_is_valid(monkeypatch):
    """The committed config.yaml must load (with dummy Telegram secrets)."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN") or "dummy")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", os.environ.get("TELEGRAM_CHAT_ID") or "1")
    cfg = config.get_config()
    assert characters.pick_character(cfg)["id"]


class _Resp:
    def __init__(self, status, data):
        self.status_code, self.ok, self._d, self.text = status, status < 400, data, str(data)

    def json(self):
        return self._d


def _weather():
    return {"location_name": "Montevideo", "description": "llovizna", "emoji": "W",
            "temp_max": 16, "temp_min": 13, "precip_prob": 75, "wind_max": 20,
            "temp_unit": "C", "wind_unit": "kmh"}


def test_extra_params_are_sent_and_content_returned(tmp_path, monkeypatch):
    c = _cfg(tmp_path)
    c["llm"]["provider"] = "groq"
    c["llm"]["providers"]["groq"]["extra_params"] = {"reasoning_effort": "low"}
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.update(json)
        return _Resp(200, {"choices": [{"message": {"content": " Arr! ", "reasoning": "..."}}]})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert llm.generate_message(c, c["characters"][0], _weather()) == "Arr!"
    assert sent["reasoning_effort"] == "low"


def test_retired_model_or_empty_reply_falls_back(tmp_path, monkeypatch):
    c = _cfg(tmp_path)
    c["llm"]["provider"] = "groq"
    replies = iter([
        _Resp(404, {"error": {"message": "The model does not exist"}}),
        _Resp(200, {"choices": [{"message": {"content": ""}}]}),
    ])
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: next(replies))
    for _ in range(2):
        msg = llm.generate_message(c, c["characters"][0], _weather())
        assert msg.startswith("¡Buenos dias!") and "RuntimeError" in msg
