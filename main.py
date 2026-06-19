"""
main.py - Jarvis Entry Point
=============================
Hybrid AI voice assistant -- local skills + LLM fallback + WebUI.

Usage:
    python main.py           -> run Jarvis (opens browser to localhost:5000)
    python main.py --check   -> import + skill check only
    python main.py --skills  -> list all loaded skills
    python main.py --no-browser -> run without auto-opening browser
"""
import sys
import os
import yaml
from colorama import init, Fore, Style

init(autoreset=True)

BANNER = (
    f"\n{Fore.CYAN}"
    "==================================================\n"
    "  J A R V I S  v2.0 -- Hybrid AI Assistant\n"
    "  Local Skills + LLM Routing + Animated WebUI\n"
    "  Double-clap for voice, or use the WebUI\n"
    f"=================================================={Style.RESET_ALL}\n"
)


def load_config(path: str = "config.yaml") -> dict:
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.exists(path):
        print(f"{Fore.YELLOW}[!] config.yaml not found at {path}. Using defaults.{Style.RESET_ALL}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def import_check(config: dict) -> bool:
    print(f"  {Fore.CYAN}Running checks...{Style.RESET_ALL}")
    errors = []

    modules = [
        "pyaudio", "pyautogui", "edge_tts", "pygame",
        "speech_recognition", "pygetwindow", "pycaw",
        "rapidfuzz", "yaml", "colorama", "psutil", "requests",
        "flask", "flask_sock", "cv2", "google.generativeai",
    ]
    for m in modules:
        try:
            __import__(m)
            print(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} {m}")
        except ImportError:
            print(f"  {Fore.YELLOW}[MISS]{Style.RESET_ALL} {m}")
            errors.append(m)

    from skills import load_all
    from core import intent, logger as log_mod
    log_mod.setup(config)
    skills = load_all()
    print(f"\n  {Fore.CYAN}Skills loaded:{Style.RESET_ALL}")
    for s in skills:
        print(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} {s.name:15} -- {s.description[:60]}")

    if errors:
        print(f"\n  {Fore.YELLOW}Optional/missing: {', '.join(errors)}{Style.RESET_ALL}")
        print(f"  Run: pip install -r requirements.txt")
    print(f"\n  {Fore.GREEN}Check complete.{Style.RESET_ALL}")
    return True


def main():
    print(BANNER)
    config = load_config()

    if "--no-browser" in sys.argv:
        config["web_open_browser"] = False

    if "--check" in sys.argv:
        ok = import_check(config)
        sys.exit(0 if ok else 1)

    from core import logger as log_mod, voice as voice_mod
    from core import recognizer as rec_mod, memory as mem_mod, intent as intent_mod
    log = log_mod.setup(config)
    voice_mod.setup(config)
    rec_mod.setup(config)
    mem_mod.setup(config)
    intent_mod.setup(config)

    from skills import load_all
    skills = load_all()
    log.info(f"Loaded {len(skills)} skills: {', '.join(s.name for s in skills)}")

    if "--skills" in sys.argv:
        for s in skills:
            print(f"  [{s.name}] {s.description}")
        sys.exit(0)

    try:
        from core import server as srv
        srv.start(config)
        log.info("Web server started.")
    except Exception as e:
        log.error(f"Web server failed to start: {e} -- continuing without WebUI.")

    from core import engine
    engine.run(config)


if __name__ == "__main__":
    main()