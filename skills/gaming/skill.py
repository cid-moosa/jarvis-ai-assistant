"""
skills/gaming/skill.py
======================
Gaming section skill: Minecraft launcher, folders, server ping.
"""
import os
import time
import socket
import subprocess
import pyautogui
from core import voice, intent, logger
from utils import window

_config = {}


def _mc_path(*sub):
    base = os.path.expandvars(_config.get("minecraft_path", r"%APPDATA%\.minecraft"))
    return os.path.join(base, *sub)


def _open(path):
    if os.path.exists(path):
        os.startfile(path)
    else:
        voice.speak("That folder doesn't exist yet.")


def _launch_minecraft():
    exe = _config.get("launcher_exe", "skl")
    voice.speak("Launching Minecraft. Stand by.")
    pyautogui.hotkey("win", "d"); time.sleep(0.5)
    pyautogui.press("win");       time.sleep(0.5)
    pyautogui.write(exe);         pyautogui.press("enter")
    if window.click_launcher_play(_config):
        voice.speak("Game is starting. Good luck.")
    else:
        voice.speak("Launcher did not respond. Check your screen.")


def _close_minecraft():
    voice.speak("Closing Minecraft.")
    for proc in ["javaw.exe", "minecraft.exe"]:
        subprocess.call(["taskkill", "/F", "/IM", proc],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    voice.speak("Done.")


def _ping_server(cmd: str):
    import re
    host_match = re.search(r"ping\s+([\w.]+)", cmd)
    host = host_match.group(1) if host_match else _config.get("ping_server", "hypixel.net")
    port = _config.get("ping_port", 25565)
    voice.speak(f"Pinging {host}.")
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=5):
            ms = int((time.time() - start) * 1000)
        voice.speak(f"{host} is online. Ping: {ms} milliseconds.")
    except Exception:
        voice.speak(f"Could not reach {host}. It may be offline.")


def handle(cmd: str, config: dict):
    global _config
    _config = config
    log = logger.get()

    c = cmd.lower()
    if any(x in c for x in ["launch", "start", "play", "open", "boot", "run"]) and "minecraft" in c:
        _launch_minecraft()
    elif any(x in c for x in ["close", "kill", "stop", "quit", "exit"]) and "minecraft" in c:
        _close_minecraft()
    elif "mods" in c:
        voice.speak("Opening mods folder."); _open(_mc_path("mods"))
    elif "shader" in c:
        voice.speak("Opening shaderpacks."); _open(_mc_path("shaderpacks"))
    elif "resource" in c or "texture" in c:
        voice.speak("Opening resource packs."); _open(_mc_path("resourcepacks"))
    elif "screenshot" in c:
        voice.speak("Opening screenshots."); _open(_mc_path("screenshots"))
    elif "save" in c or "world" in c:
        voice.speak("Opening saves."); _open(_mc_path("saves"))
    elif "config" in c and "minecraft" in c:
        voice.speak("Opening configs."); _open(_mc_path("config"))
    elif "log" in c and "minecraft" in c:
        voice.speak("Opening logs."); _open(_mc_path("logs"))
    elif "minecraft" in c and ("folder" in c or "directory" in c or "dir" in c):
        voice.speak("Opening Minecraft folder."); _open(_mc_path())
    elif "ping" in c or "server" in c:
        _ping_server(cmd)
    elif "session" in c or "free" in c or "game" in c:
        voice.speak("Setting up your gaming session.")
        pyautogui.hotkey("win", "d"); time.sleep(1)
        pyautogui.press("win"); time.sleep(0.5)
        pyautogui.write("discord"); pyautogui.press("enter"); time.sleep(2)
        _launch_minecraft()
    else:
        _launch_minecraft()


SKILL = intent.Skill(
    name        = "gaming",
    handler     = handle,
    description = "Minecraft launcher, folders, and server ping for the gaming section.",
    keywords    = ["minecraft", "mods", "shader", "resource", "screenshot", "saves", "server", "ping", "launcher"],
    patterns    = [
        intent.IntentPattern("launch minecraft",         95),
        intent.IntentPattern("start minecraft",          93),
        intent.IntentPattern("play minecraft",           90),
        intent.IntentPattern("open minecraft",           88),
        intent.IntentPattern("boot minecraft",           88),
        intent.IntentPattern("close minecraft",          93),
        intent.IntentPattern("kill minecraft",           90),
        intent.IntentPattern("minecraft folder",         88),
        intent.IntentPattern("open mods folder",         92),
        intent.IntentPattern("mods folder",              88),
        intent.IntentPattern("open shaders",             88),
        intent.IntentPattern("shader packs",             85),
        intent.IntentPattern("resource packs",           88),
        intent.IntentPattern("open screenshots",         88),
        intent.IntentPattern("open saves",               88),
        intent.IntentPattern("server ping",              88),
        intent.IntentPattern("check ping",               85),
        intent.IntentPattern("gaming session",           85),
        intent.IntentPattern("set up session",           85),
        intent.IntentPattern("i am free",                82),
    ],
)