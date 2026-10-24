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


def format_summary(cfg: dict, w: dict) -> str:
    """One line with the real numbers, e.g. for the end of the message."""
    rain, wind = ("lluvia", "viento") if cfg.get("language") == "es" else ("rain", "wind")
    return (
        f"{w['emoji']} {w['location_name']}: {w['description']} · "
        f"{w['temp_min']}–{w['temp_max']}{w['temp_unit']} · "
        f"{rain} {w['precip_prob']}% · {wind} {w['wind_max']} {w['wind_unit']}"
    )
