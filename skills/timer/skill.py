"""
skills/timer/skill.py
=====================
Local countdown timers and alarms. Fully offline.
Runs timers in daemon threads — non-blocking.
"""
import re
import time
import threading
from core import voice, intent, logger


def _parse_seconds(cmd: str) -> int:
    c = cmd.lower()
    total = 0
    for val, unit in re.findall(r"(\d+)\s*(hour|hr|minute|min|second|sec)s?", c):
        v = int(val)
        if unit.startswith("hour") or unit.startswith("hr"):
            total += v * 3600
        elif unit.startswith("min"):
            total += v * 60
        else:
            total += v
    return total


def _timer_thread(seconds: int, label: str):
    time.sleep(seconds)
    voice.speak(f"Timer done! {label}")


def handle(cmd: str, config: dict):
    log = logger.get()
    c = cmd.lower()

    seconds = _parse_seconds(c)
    if seconds <= 0:
        voice.speak("I couldn't understand the timer duration. Say something like: set a timer for 5 minutes.")
        return

    # Build human label
    parts = []
    if seconds >= 3600:
        parts.append(f"{seconds//3600} hour{'s' if seconds//3600 > 1 else ''}")
    if (seconds % 3600) >= 60:
        parts.append(f"{(seconds%3600)//60} minute{'s' if (seconds%3600)//60 > 1 else ''}")
    if seconds % 60:
        parts.append(f"{seconds%60} second{'s' if seconds%60 > 1 else ''}")
    label = " and ".join(parts)

    voice.speak(f"Timer set for {label}.")
    log.info(f"Timer started: {seconds}s")
    t = threading.Thread(target=_timer_thread, args=(seconds, label), daemon=True)
    t.start()


SKILL = intent.Skill(
    name        = "timer",
    handler     = handle,
    description = "Local countdown timers. No API. Handles: set timer for X minutes/seconds/hours.",
    keywords    = ["timer", "alarm", "remind", "countdown", "minutes", "seconds", "hours"],
    patterns    = [
        intent.IntentPattern("set a timer",          95),
        intent.IntentPattern("set timer",            93),
        intent.IntentPattern("timer for",            92),
        intent.IntentPattern("alarm for",            90),
        intent.IntentPattern("remind me in",         88),
        intent.IntentPattern("countdown",            85),
    ],
)