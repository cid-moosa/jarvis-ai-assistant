"""
skills/web/skill.py
===================
Web search via browser — no API key needed.
Also handles: open file explorer, open specific sites.
"""
import re
import webbrowser
import subprocess
from core import voice, intent, logger


def handle(cmd: str, config: dict):
    c = cmd.lower()

    # Extract search query
    query = cmd
    for trigger in ["search for", "search", "google", "look up", "find", "browse"]:
        idx = c.find(trigger)
        if idx != -1:
            query = cmd[idx + len(trigger):].strip()
            break

    if "file explorer" in c or "files" in c or "my computer" in c:
        voice.speak("Opening File Explorer.")
        subprocess.Popen("explorer")
        return

    if "github" in c:
        q = query.replace("github", "").strip()
        url = f"https://github.com/search?q={q.replace(' ', '+')}" if q else "https://github.com"
        voice.speak(f"Opening GitHub.")
        webbrowser.open(url)
        return

    if "reddit" in c:
        q = query.replace("reddit", "").strip()
        url = f"https://reddit.com/search?q={q.replace(' ', '+')}" if q else "https://reddit.com"
        voice.speak("Opening Reddit.")
        webbrowser.open(url)
        return

    if query:
        encoded = query.replace(" ", "+")
        voice.speak(f"Searching for {query}.")
        webbrowser.open(f"https://www.google.com/search?q={encoded}")
    else:
        voice.speak("What do you want me to search for?")


SKILL = intent.Skill(
    name        = "web",
    handler     = handle,
    description = "Web search via browser. No API. Handles: search for X, google X, open github, open reddit, file explorer.",
    keywords    = ["search", "google", "look up", "browse", "find", "website", "github", "reddit", "explorer"],
    patterns    = [
        intent.IntentPattern("search for",          92),
        intent.IntentPattern("google",              80),
        intent.IntentPattern("look up",             88),
        intent.IntentPattern("browse",              82),
        intent.IntentPattern("open github",         92),
        intent.IntentPattern("open reddit",         90),
        intent.IntentPattern("file explorer",       90),
        intent.IntentPattern("open my files",       88),
    ],
)