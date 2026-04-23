"""
skills/gaming/skill.py
======================
Gaming section — Minecraft launcher, folders, server ping.

Launch flow:
  1. Ctrl+Alt+G fires SKLauncher instantly via hotkey
  2. Window manager waits for the window, force-focuses it,
     scans for the blue Start button by pixel colour, clicks it
  3. Retries up to 3x if click doesn't start the game
  4. Once Minecraft (javaw.exe) is confirmed running, Jarvis
     self-terminates to free all PC resources for the game
"""
import os
import time
import socket
import subprocess
import pyautogui
from core import voice, intent, logger
from utils import window

_config = {}


# ── Path helpers ───────────────────────────────────────────────────────────────

def _mc_path(*sub):
    base = os.path.expandvars(_config.get("minecraft_path", r"%APPDATA%\.minecraft"))
    return os.path.join(base, *sub)


def _open_folder(path: str):
    if os.path.exists(path):
        os.startfile(path)
    else:
        voice.speak("That folder doesn't exist yet.")


# ── App openers (hotkeys = fastest possible method) ───────────────────────────

def _open_discord():
    logger.get().info("Discord: Ctrl+Alt+D")
    pyautogui.hotkey("ctrl", "alt", "d")


def _open_launcher():
    logger.get().info("SKLauncher: Ctrl+Alt+G")
    pyautogui.hotkey("ctrl", "alt", "g")


# ── Launch sequences ───────────────────────────────────────────────────────────

def _launch_game_only():
    """Open SKLauncher, run boot sequence, then self-terminate once game is stable."""
    log = logger.get()
    voice.speak("Launching Minecraft.")

    _open_launcher()

    ok = window.run_launcher_sequence(_config)

    if ok:
        voice.speak("Game starting. Jarvis going offline to save resources. Good luck.")
        log.info("Launch confirmed — starting game watcher.")
        window.watch_and_terminate_when_game_starts(check_interval=3.0, stable_checks=3)
    else:
        voice.speak("Launcher didn't start the game. Check the screen.")


def _launch_full_session():
    """
    Discord first -> pause -> SKLauncher.
    Window manager focuses SKLauncher exclusively for the boot sequence.
    After launch confirmed, self-terminate.
    """
    log = logger.get()
    voice.speak("Setting up gaming session.")

    # Open Discord first — it's fast, gets out of the way quickly
    _open_discord()
    log.info("Discord launched. Pausing before SKLauncher...")
    time.sleep(2.5)

    # Now open SKLauncher
    _open_launcher()
    log.info("SKLauncher launched — window manager taking over.")

    ok = window.run_launcher_sequence(_config)

    if ok:
        # Tile windows so nothing overlaps when user alt-tabs
        launcher_name = _config.get("launcher_name", "SKLauncher")
        time.sleep(1)
        window.tile_side_by_side("Discord", launcher_name)
        voice.speak("Session ready. Jarvis going offline to save resources. Good luck.")
        log.info("Full session launch confirmed — starting game watcher.")
        window.watch_and_terminate_when_game_starts(check_interval=3.0, stable_checks=3)
    else:
        voice.speak("Launcher didn't respond. Discord is open. Check the screen.")


def _close_minecraft():
    voice.speak("Closing Minecraft.")
    killed = any(
        subprocess.call(["taskkill", "/F", "/IM", proc],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
        for proc in ["javaw.exe", "minecraft.exe"]
    )
    voice.speak("Minecraft closed." if killed else "Minecraft doesn't seem to be running.")


def _ping_server(cmd: str):
    import re
    m = re.search(r"ping\s+([\w.]+)", cmd)
    host = m.group(1) if m else _config.get("ping_server", "hypixel.net")
    port = _config.get("ping_port", 25565)
    voice.speak(f"Pinging {host}.")
    try:
        t = time.time()
        with socket.create_connection((host, port), timeout=5):
            ms = int((time.time() - t) * 1000)
        voice.speak(f"{host} is online. Ping: {ms} milliseconds.")
    except Exception:
        voice.speak(f"Could not reach {host}. It may be offline.")


# ── Main handler ───────────────────────────────────────────────────────────────

def handle(cmd: str, config: dict):
    global _config
    _config = config
    c = cmd.lower()

    if any(x in c for x in ["launch", "start", "play", "open", "boot", "run"]) and "minecraft" in c:
        _launch_game_only()
    elif any(x in c for x in ["session", "free", "gaming session", "set up", "start session"]):
        _launch_full_session()
    elif any(x in c for x in ["close", "kill", "stop", "quit", "exit"]) and "minecraft" in c:
        _close_minecraft()
    elif "mods" in c:
        voice.speak("Opening mods folder."); _open_folder(_mc_path("mods"))
    elif "shader" in c:
        voice.speak("Opening shaderpacks."); _open_folder(_mc_path("shaderpacks"))
    elif "resource" in c or "texture" in c:
        voice.speak("Opening resource packs."); _open_folder(_mc_path("resourcepacks"))
    elif "screenshot" in c:
        voice.speak("Opening screenshots."); _open_folder(_mc_path("screenshots"))
    elif "save" in c or "world" in c:
        voice.speak("Opening saves."); _open_folder(_mc_path("saves"))
    elif "config" in c and "minecraft" in c:
        voice.speak("Opening config folder."); _open_folder(_mc_path("config"))
    elif "log" in c and "minecraft" in c:
        voice.speak("Opening logs folder."); _open_folder(_mc_path("logs"))
    elif "minecraft" in c and any(x in c for x in ["folder", "directory", "dir"]):
        voice.speak("Opening Minecraft folder."); _open_folder(_mc_path())
    elif "ping" in c or ("server" in c and "status" in c):
        _ping_server(cmd)
    else:
        _launch_game_only()


# ── Skill registration ─────────────────────────────────────────────────────────

SKILL = intent.Skill(
    name        = "gaming",
    handler     = handle,
    description = "Minecraft launcher (Ctrl+Alt+G), Discord (Ctrl+Alt+D), folders, ping. Self-terminates after launch.",
    keywords    = ["minecraft", "mods", "shader", "resource", "screenshot", "saves",
                   "server", "ping", "launcher", "session", "gaming"],
    patterns    = [
        intent.IntentPattern("launch minecraft",  95),
        intent.IntentPattern("start minecraft",   93),
        intent.IntentPattern("play minecraft",    90),
        intent.IntentPattern("open minecraft",    88),
        intent.IntentPattern("boot minecraft",    88),
        intent.IntentPattern("close minecraft",   93),
        intent.IntentPattern("kill minecraft",    90),
        intent.IntentPattern("minecraft folder",  88),
        intent.IntentPattern("open mods folder",  92),
        intent.IntentPattern("mods folder",       88),
        intent.IntentPattern("open shaders",      88),
        intent.IntentPattern("shader packs",      85),
        intent.IntentPattern("resource packs",    88),
        intent.IntentPattern("open screenshots",  88),
        intent.IntentPattern("open saves",        88),
        intent.IntentPattern("server ping",       88),
        intent.IntentPattern("check ping",        85),
        intent.IntentPattern("gaming session",    90),
        intent.IntentPattern("set up session",    90),
        intent.IntentPattern("i am free",         85),
        intent.IntentPattern("start session",     88),
    ],
)