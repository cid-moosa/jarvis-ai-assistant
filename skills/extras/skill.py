"""
skills/extras/skill.py
======================
Help, jokes, easter eggs, status. All local.
"""
import random
import webbrowser
import pyautogui
import time
from core import voice, intent, logger
from skills import SKILL_REGISTRY

_JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "Why did the programmer quit his job? Because he didn't get arrays.",
    "How many programmers does it take to change a light bulb? None. That's a hardware problem.",
    "Why do Java developers wear glasses? Because they don't C sharp.",
    "A SQL query walks into a bar, walks up to two tables and asks: Can I join you?",
    "Why was the computer cold? It left its Windows open.",
    "I told my computer I needed a break. Now it won't stop sending me Kit-Kat ads.",
    "Why did the developer go broke? Because he used up all his cache.",
]


def handle(cmd: str, config: dict):
    c = cmd.lower()

    if "help" in c or "what can you do" in c or "commands" in c:
        names = [s.name for s in SKILL_REGISTRY]
        voice.speak(f"I have {len(names)} skills loaded: {', '.join(names)}. "
                    "Double clap anytime to give me a command.")

    elif "joke" in c:
        voice.speak(random.choice(_JOKES))

    elif "status" in c or "how are you" in c:
        voice.speak("All systems operational. I am standing by.")

    elif "hello" in c or "hey" in c or "hi" in c:
        voice.speak("Hello. I'm Jarvis. Double clap anytime to give me a command.")

    elif "rickroll" in c or "surprise" in c:
        voice.speak("Executing surprise protocol.")
        pyautogui.hotkey("win", "r"); time.sleep(0.5)
        pyautogui.write("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        pyautogui.press("enter")

    elif "flip" in c or "coin" in c:
        result = random.choice(["Heads", "Tails"])
        voice.speak(f"It's {result}.")

    elif "roll" in c or "dice" in c:
        import re
        m = re.search(r"(\d+)\s*d\s*(\d+)", c)
        if m:
            rolls = int(m.group(1))
            sides = int(m.group(2))
        else:
            rolls, sides = 1, 6
        import random as r
        total = sum(r.randint(1, sides) for _ in range(rolls))
        voice.speak(f"You rolled {total}.")

    else:
        voice.speak("I didn't understand that. Say 'help' for available commands.")


SKILL = intent.Skill(
    name        = "extras",
    handler     = handle,
    description = "Help, jokes, coin flip, dice roll, easter eggs. Fully local.",
    keywords    = ["help", "joke", "hello", "hi", "status", "coin", "dice", "roll", "flip", "rickroll", "surprise"],
    patterns    = [
        intent.IntentPattern("help",                85),
        intent.IntentPattern("what can you do",     90),
        intent.IntentPattern("tell me a joke",      95),
        intent.IntentPattern("tell a joke",         92),
        intent.IntentPattern("joke",                80),
        intent.IntentPattern("hello",               80),
        intent.IntentPattern("how are you",         82),
        intent.IntentPattern("system status",       85),
        intent.IntentPattern("flip a coin",         92),
        intent.IntentPattern("roll a dice",         92),
        intent.IntentPattern("roll the dice",       90),
        intent.IntentPattern("rickroll",            90),
        intent.IntentPattern("surprise me",         85),
    ],
)