"""
skills/gaming/skill.py
======================
Gaming section — Minecraft launcher, folders, server ping.

Launch strategy:
  - SKLauncher opens via Ctrl+Alt+G (hotkey you configured)
  - Discord opens via Ctrl+Alt+D (hotkey you configured)
  - When opening BOTH, Discord is launched first (it is fast and reliable),
    then SKLauncher is launched; the window manager then exclusively focuses
    the SKLauncher window and runs the boot sequence on it so Discord
    can never steal focus and break the play-button click.
  - When opening GAME ONLY, same focused sequence without Discord.
"""
import os
import time
import socket
import subprocess
import threading
import pyautogui
from core import voice, intent, logger
from utils import window

_config = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mc_path(*sub):
    base = os.path.expandvars(_config.get("minecraft_path", r"%APPDATA%\.minecraft"))
    return os.path.join(base, *sub)


def _open_folder(path: str):
    if os.path.exists(path):
        os.startfile(path)
    else:
        voice.speak("That folder doesn't exist yet.")


# ---------------------------------------------------------------------------
# App launchers (use your hotkeys — fast and reliable, no Start menu typing)
# ---------------------------------------------------------------------------

def _open_discord():
    """Launch Discord via Ctrl+Alt+D hotkey."""
    log = logger.get()
    log.info("Launching Discord via Ctrl+Alt+D")
    pyautogui.hotkey("ctrl", "alt", "d")


def _open_launcher():
    """Launch SKLauncher via Ctrl+Alt+G hotkey."""
    log = logger.get()
    log.info("Launching SKLauncher via Ctrl+Alt+G")
    pyautogui.hotkey("ctrl", "alt", "g")


# ---------------------------------------------------------------------------
# Core launch sequences
# ---------------------------------------------------------------------------

def _launch_game_only():
    """
    Open SKLauncher and run the full boot sequence.
    Focused mode — no other app launched, no overlap possible.
    """
    voice.speak("Launching Minecraft. Stand by.")
    _open_launcher()
    ok = window.run_launcher_sequence(_config)
    if ok:
        voice.speak("Game is starting. Good luck.")
    else:
        voice.speak("Launcher did not respond. Check your screen.")


def _launch_full_session():
    """
    Open Discord + SKLauncher with window overlap prevention.

    Sequence:
      1. Launch Discord (fast, non-blocking)
      2. Short pause so Discord window appears
      3. Launch SKLauncher
      4. Window manager focuses SKLauncher EXCLUSIVELY for the boot sequence
         (Enter to dismiss error, click Play)
      5. After Play is clicked, tile Discord left / Launcher right
    """
    log = logger.get()
    voice.speak("Setting up your gaming session. Stand by.")

    # Step 1: Open Discord first (it loads quickly)
    _open_discord()
    log.info("Discord launched. Waiting 2s before opening launcher...")
    time.sleep(2)

    # Step 2: Open SKLauncher
    _open_launcher()
    log.info("SKLauncher launched. Handing off to window manager...")

    # Step 3: Window manager takes over — focused SKLauncher sequence
    # Discord window is deliberately left unfocused until Play is clicked
    ok = window.run_launcher_sequence(_config)

    if ok:
        voice.speak("Minecraft starting.")
        # Step 4: Tile windows so they don't overlap
        # Give the launcher a moment before tiling
        time.sleep(1.5)
        launcher_name = _config.get("launcher_name", "SKLauncher")
        window.tile_side_by_side("Discord", launcher_name)
        log.info("Windows tiled: Discord left, SKLauncher right.")
        voice.speak("Session ready. Good luck out there.")
    else:
        voice.speak("Launcher didn't respond. Discord is open. Check the screen.")


def _close_minecraft():
    voice.speak("Closing Minecraft.")
    killed = False
    for proc in ["javaw.exe", "minecraft.exe"]:
        result = subprocess.call(
            ["taskkill", "/F", "/IM", proc],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if result == 0:
            killed = True
    voice.speak("Minecraft closed." if killed else "Minecraft doesn't seem to be running.")


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


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handle(cmd: str, config: dict):
    global _config
    _config = config
    c = cmd.lower()

    # --- Launch ---
    if any(x in c for x in ["launch", "start", "play", "open", "boot", "run"]) and "minecraft" in c:
        _launch_game_only()

    # --- Full session (Discord + Minecraft) ---
    elif any(x in c for x in ["session", "free", "gaming session", "set up"]):
        _launch_full_session()

    # --- Close ---
    elif any(x in c for x in ["close", "kill", "stop", "quit", "exit"]) and "minecraft" in c:
        _close_minecraft()

    # --- Folders ---
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

    # --- Server ping ---
    elif "ping" in c or ("server" in c and "status" in c):
        _ping_server(cmd)

    # --- Default: just launch ---
    else:
        _launch_game_only()


# ---------------------------------------------------------------------------
# Skill registration
# ---------------------------------------------------------------------------

SKILL = intent.Skill(
    name        = "gaming",
    handler     = handle,
    description = "Minecraft launcher (Ctrl+Alt+G), Discord (Ctrl+Alt+D), folders, server ping. Window-managed to prevent overlap.",
    keywords    = ["minecraft", "mods", "shader", "resource", "screenshot", "saves", "server", "ping", "launcher", "session", "gaming"],
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
        intent.IntentPattern("gaming session",           90),
        intent.IntentPattern("set up session",           90),
        intent.IntentPattern("i am free",                85),
        intent.IntentPattern("start session",            88),
    ],
)