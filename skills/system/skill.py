"""
skills/system/skill.py
======================
OS-level controls: apps, volume, sleep, time/date, task manager.
"""
import os
import time
import webbrowser
import pyautogui
from datetime import datetime
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from core import voice, intent, logger


def _speaker():
    try:
        d = AudioUtilities.GetSpeakers()
        i = d.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(i, POINTER(IAudioEndpointVolume))
    except Exception:
        return None


def _vol_up():
    v = _speaker()
    if v:
        v.SetMasterVolumeLevelScalar(min(1.0, v.GetMasterVolumeLevelScalar() + 0.1), None)
        voice.speak("Volume up.")
    else:
        voice.speak("Volume control unavailable.")


def _vol_down():
    v = _speaker()
    if v:
        v.SetMasterVolumeLevelScalar(max(0.0, v.GetMasterVolumeLevelScalar() - 0.1), None)
        voice.speak("Volume down.")
    else:
        voice.speak("Volume control unavailable.")


def _mute():
    v = _speaker()
    if v:
        muted = v.GetMute()
        v.SetMute(not muted, None)
        voice.speak("Muted." if not muted else "Unmuted.")
    else:
        voice.speak("Volume control unavailable.")


def handle(cmd: str, config: dict):
    c = cmd.lower()

    if "discord" in c:
        voice.speak("Opening Discord.")
        pyautogui.press("win"); time.sleep(0.5)
        pyautogui.write("discord"); pyautogui.press("enter")

    elif "youtube" in c:
        voice.speak("Opening YouTube.")
        webbrowser.open("https://www.youtube.com")

    elif "spotify" in c:
        voice.speak("Opening Spotify.")
        pyautogui.press("win"); time.sleep(0.5)
        pyautogui.write("spotify"); pyautogui.press("enter")

    elif "browser" in c or "google" in c or "internet" in c:
        voice.speak("Opening browser.")
        webbrowser.open("https://www.google.com")

    elif "task manager" in c or "processes" in c:
        voice.speak("Opening Task Manager.")
        pyautogui.hotkey("ctrl", "shift", "esc")

    elif "volume up" in c or "louder" in c or "increase volume" in c or "turn up" in c:
        _vol_up()

    elif "volume down" in c or "quieter" in c or "decrease volume" in c or "turn down" in c:
        _vol_down()

    elif "mute" in c or "unmute" in c:
        _mute()

    elif "time" in c:
        now = datetime.now()
        h = now.strftime("%I").lstrip("0") or "12"
        voice.speak(f"It is {h}:{now.strftime('%M')} {now.strftime('%p')}.")

    elif "date" in c or "day" in c:
        voice.speak(f"Today is {datetime.now().strftime('%A, %B %d')}.")

    elif "sleep" in c and "computer" in c:
        voice.speak("Putting computer to sleep.", blocking=True)
        time.sleep(2)
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    elif "terminate" in c or "shutdown" in c or "shut down" in c or "goodbye" in c or "exit" in c:
        voice.speak("Goodbye.", blocking=True)
        os._exit(0)

    elif "desktop" in c or "show desktop" in c:
        pyautogui.hotkey("win", "d")
        voice.speak("Showing desktop.")

    elif "lock" in c:
        voice.speak("Locking.")
        pyautogui.hotkey("win", "l")

    else:
        voice.speak("System command not recognized.")


SKILL = intent.Skill(
    name        = "system",
    handler     = handle,
    description = "OS controls: apps, volume, time, sleep, lock, task manager.",
    keywords    = ["discord", "youtube", "spotify", "browser", "volume", "time", "date", "sleep", "lock", "mute", "task", "desktop", "terminate", "shutdown", "goodbye", "exit"],
    patterns    = [
        intent.IntentPattern("open discord",        92),
        intent.IntentPattern("open youtube",        92),
        intent.IntentPattern("open spotify",        92),
        intent.IntentPattern("open browser",        88),
        intent.IntentPattern("google",              75),
        intent.IntentPattern("task manager",        90),
        intent.IntentPattern("volume up",           95),
        intent.IntentPattern("volume down",         95),
        intent.IntentPattern("louder",              88),
        intent.IntentPattern("quieter",             88),
        intent.IntentPattern("mute",                90),
        intent.IntentPattern("unmute",              90),
        intent.IntentPattern("what time",           93),
        intent.IntentPattern("what is the time",    92),
        intent.IntentPattern("what date",           92),
        intent.IntentPattern("what day is it",      90),
        intent.IntentPattern("sleep computer",      90),
        intent.IntentPattern("terminate",           95),
        intent.IntentPattern("shut down",           93),
        intent.IntentPattern("goodbye",             90),
        intent.IntentPattern("show desktop",        88),
        intent.IntentPattern("lock computer",       88),
        intent.IntentPattern("lock screen",         88),
    ],
)