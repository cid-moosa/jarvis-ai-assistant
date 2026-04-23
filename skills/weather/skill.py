"""
skills/weather/skill.py
=======================
Live weather via wttr.in — NO API KEY, fully free.
"""
import re
import requests
from core import voice, intent, logger, memory


def handle(cmd: str, config: dict):
    log = logger.get()
    c = cmd.lower()

    # Extract city from command e.g. "weather in london", "temperature in tokyo"
    city_match = re.search(r"\bin\s+([a-z\s]+)$", c)
    if city_match:
        city = city_match.group(1).strip().replace(" ", "+")
    else:
        city = memory.get("weather_city") or config.get("weather_city", "London")

    # Save city preference
    if city_match:
        memory.set("weather_city", city.replace("+", " "))

    url = f"https://wttr.in/{city}?format=%l:+%c+%t+(feels+like+%f),+%w+wind,+%h+humidity"
    voice.speak(f"Checking weather for {city.replace('+', ' ')}.")
    try:
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            text = r.text.strip()
            # Clean up for TTS
            text = re.sub(r"[+]", " ", text)
            text = re.sub(r"[^\x00-\x7F]+", "", text)  # strip emoji for clean TTS
            voice.speak(text)
        else:
            voice.speak("Could not get weather data right now.")
    except requests.exceptions.ConnectionError:
        voice.speak("No internet connection. Cannot check weather.")
    except Exception as e:
        log.error(f"Weather error: {e}")
        voice.speak("Weather lookup failed.")


SKILL = intent.Skill(
    name        = "weather",
    handler     = handle,
    description = "Live weather via wttr.in. No API key needed.",
    keywords    = ["weather", "temperature", "rain", "forecast", "wind", "humidity", "sunny", "cloudy"],
    patterns    = [
        intent.IntentPattern("what is the weather",  95),
        intent.IntentPattern("what's the weather",   95),
        intent.IntentPattern("weather today",        92),
        intent.IntentPattern("weather forecast",     90),
        intent.IntentPattern("will it rain",         90),
        intent.IntentPattern("temperature",          85),
        intent.IntentPattern("how is the weather",   88),
        intent.IntentPattern("weather in",           88),
    ],
)