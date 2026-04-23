"""
skills/media/skill.py
=====================
Media playback controls via keyboard hotkeys — works with any player.
Fully local, no API.
"""
import time
import webbrowser
import pyautogui
from core import voice, intent, logger


def handle(cmd: str, config: dict):
    c = cmd.lower()

    if "play" in c or "resume" in c:
        pyautogui.press("playpause")
        voice.speak("Playing.")
    elif "pause" in c or "stop music" in c:
        pyautogui.press("playpause")
        voice.speak("Paused.")
    elif "next" in c or "skip" in c:
        pyautogui.press("nexttrack")
        voice.speak("Next track.")
    elif "previous" in c or "back" in c or "prev" in c:
        pyautogui.press("prevtrack")
        voice.speak("Previous track.")
    elif "youtube music" in c or "yt music" in c:
        voice.speak("Opening YouTube Music.")
        webbrowser.open("https://music.youtube.com")
    elif "soundcloud" in c:
        voice.speak("Opening SoundCloud.")
        webbrowser.open("https://soundcloud.com")
    else:
        pyautogui.press("playpause")
        voice.speak("Toggling playback.")


SKILL = intent.Skill(
    name        = "media",
    handler     = handle,
    description = "Media playback via keyboard hotkeys. No API. Handles: play, pause, next track, previous track, YouTube Music.",
    keywords    = ["play", "pause", "next", "skip", "previous", "track", "music", "song"],
    patterns    = [
        intent.IntentPattern("play music",          90),
        intent.IntentPattern("pause music",         90),
        intent.IntentPattern("stop music",          88),
        intent.IntentPattern("next track",          92),
        intent.IntentPattern("skip track",          90),
        intent.IntentPattern("previous track",      90),
        intent.IntentPattern("resume music",        88),
        intent.IntentPattern("youtube music",       92),
        intent.IntentPattern("soundcloud",          90),
    ],
)