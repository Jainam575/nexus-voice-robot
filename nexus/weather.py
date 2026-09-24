"""
Nexus Robot — Weather (Open-Meteo, no API key needed).

Primary source: Open-Meteo (https + geocoding, free, no key).
wttr.in was the previous source but it periodically serves an expired
TLS certificate which breaks HTTPS clients entirely (seen 2026-09-16),
so it is no longer used.

Location resolution:
  1. WEATHER_LOCATION env var (e.g. "Surat", "Mumbai") — geocoded via
     Open-Meteo's geocoding API.
  2. If unset, the robot's public IP is geolocated (ipapi.co, then
     ip-api.com) and that position is used.
"""
import logging
import requests

from .config import WEATHER_LOCATION

logger = logging.getLogger("Nexus.Weather")

# WMO weather interpretation codes → short spoken description
_WMO = {
    0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy with frost",
    51: "lightly drizzling", 53: "drizzling", 55: "heavily drizzling",
    56: "freezing drizzle", 57: "freezing drizzle",
    61: "raining lightly", 63: "raining", 65: "raining heavily",
    66: "freezing rain", 67: "freezing rain",
    71: "snowing lightly", 73: "snowing", 75: "snowing heavily",
    77: "snowing",
    80: "having light showers", 81: "having showers", 82: "having heavy showers",
    85: "having snow showers", 86: "having snow showers",
    95: "thunderstorming", 96: "thunderstorming with hail",
    99: "thunderstorming with hail",
}


def _wmo_desc(code):
    try:
        return _WMO.get(int(code), "conditions unavailable")
    except (TypeError, ValueError):
        return "conditions unavailable"


def _locate():
    """Return (lat, lon, city) from WEATHER_LOCATION or IP geolocation."""
    loc = (WEATHER_LOCATION or "").strip()
    if loc:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": loc, "count": 1},
            timeout=6)
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            raise ValueError(f"unknown location: {loc}")
        g = results[0]
        return g["latitude"], g["longitude"], g.get("name", loc)

    # No configured location — approximate from the public IP
    for url in ("https://ipapi.co/json/", "http://ip-api.com/json/"):
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            d = r.json()
            if "latitude" in d:  # ipapi.co shape
                return d["latitude"], d["longitude"], d.get("city", "")
            if "lat" in d:       # ip-api.com shape
                return d["lat"], d["lon"], d.get("city", "")
        except Exception:
            continue
    raise ValueError("could not determine location")


def get_weather():
    try:
        lat, lon, city = _locate()
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,weather_code"},
            timeout=6)
        r.raise_for_status()
        cur = (r.json() or {}).get("current", {}) or {}
        temp = cur.get("temperature_2m", "?")
        feels = cur.get("apparent_temperature", temp)
        desc = _wmo_desc(cur.get("weather_code"))
        where = f" in {city}" if city else ""
        return (f"It's {desc} and {temp} degrees{where} right now, "
                f"feels like {feels}.")
    except requests.exceptions.Timeout:
        return "The weather service is taking too long to respond."
    except requests.exceptions.ConnectionError:
        return "I can't reach the weather service right now. Check your internet connection."
    except Exception as e:
        logger.error("Weather fetch error: %s", e, exc_info=True)
        return ("Sorry, I couldn't get the weather right now. "
                "You can set the WEATHER_LOCATION environment variable "
                "to your city.")
