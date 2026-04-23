"""
skills/notes/skill.py
=====================
Local note-taking. Saves to data/memory.json via memory module.
Zero cloud, zero API.
"""
import re
from core import voice, intent, logger, memory


def handle(cmd: str, config: dict):
    log = logger.get()
    c = cmd.lower()

    if any(x in c for x in ["clear notes", "delete notes", "remove notes", "erase notes"]):
        memory.delete("notes")
        voice.speak("Notes cleared.")

    elif any(x in c for x in ["read notes", "what are my notes", "show notes", "list notes", "my notes"]):
        notes = memory.get("notes", [])
        if not notes:
            voice.speak("You have no notes.")
        else:
            voice.speak(f"You have {len(notes)} note{'s' if len(notes) > 1 else ''}.")
            for i, n in enumerate(notes, 1):
                voice.speak(f"Note {i}: {n['value']}")

    else:
        # Extract content: "note that X", "remember X", "make a note X"
        content = cmd
        for trigger in ["note that", "make a note", "take a note", "remember", "note:"]:
            idx = c.find(trigger)
            if idx != -1:
                content = cmd[idx + len(trigger):].strip()
                break
        if content:
            memory.append("notes", content)
            voice.speak(f"Note saved: {content}")
        else:
            voice.speak("What should I note?")


SKILL = intent.Skill(
    name        = "notes",
    handler     = handle,
    description = "Local note-taking stored in data/memory.json. No cloud. Handles: make a note, read notes, clear notes.",
    keywords    = ["note", "notes", "remember", "reminder", "write down"],
    patterns    = [
        intent.IntentPattern("make a note",         95),
        intent.IntentPattern("take a note",         93),
        intent.IntentPattern("note that",           92),
        intent.IntentPattern("remember",            85),
        intent.IntentPattern("what are my notes",   95),
        intent.IntentPattern("read my notes",       93),
        intent.IntentPattern("show notes",          90),
        intent.IntentPattern("clear notes",         92),
        intent.IntentPattern("delete notes",        90),
    ],
)