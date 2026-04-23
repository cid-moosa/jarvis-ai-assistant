"""
main.py - Jarvis Entry Point
=============================
A fully local, LLM-free, skill-based voice assistant.
Zero cloud API costs. Runs entirely on your machine.

Usage:
    python main.py           -> run Jarvis
    python main.py --check   -> import + skill check only
    python main.py --skills  -> list all loaded skills
"""
import sys
import os
import yaml
from colorama import init, Fore, Style

init(autoreset=True)

BANNER = f"""
{Fore.CYAN}╔══════════════════════════════════════════════╗
║              J A R V I S                    ║
║      Local Voice Assistant — No LLM        ║
║      Double-clap to give a command         ║
╚══════════════════════════════════════════════╝{Style.RESET_ALL}"""


def load_config(path: str = "config.yaml") -> dict:
    # Resolve relative to this script, not the launch CWD
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
        "rapidfuzz", "yaml", "colorama", "psutil", "requests"
    ]
    for m in modules:
        try:
            __import__(m)
            print(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} {m}")
        except ImportError:
            print(f"  {Fore.RED}[MISS]{Style.RESET_ALL} {m}")
            errors.append(m)

    # Load skills
    from skills import load_all
    from core import intent, logger as log_mod
    log_mod.setup(config)
    skills = load_all()
    print(f"\n  {Fore.CYAN}Skills loaded:{Style.RESET_ALL}")
    for s in skills:
        print(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} {s.name:15} — {s.description[:60]}")

    if errors:
        print(f"\n  {Fore.RED}Missing: {', '.join(errors)}{Style.RESET_ALL}")
        print(f"  Run: pip install -r requirements.txt")
        return False
    print(f"\n  {Fore.GREEN}All checks passed.{Style.RESET_ALL}")
    return True


def main():
    print(BANNER)
    config = load_config()

    if "--check" in sys.argv:
        ok = import_check(config)
        sys.exit(0 if ok else 1)

    # --- Initialize core ---
    from core import logger as log_mod, voice as voice_mod
    from core import recognizer as rec_mod, memory as mem_mod
    log = log_mod.setup(config)
    voice_mod.setup(config)
    rec_mod.setup(config)
    mem_mod.setup(config)

    # --- Load skills ---
    from skills import load_all
    skills = load_all()
    log.info(f"Loaded {len(skills)} skills: {', '.join(s.name for s in skills)}")

    if "--skills" in sys.argv:
        for s in skills:
            print(f"  [{s.name}] {s.description}")
        sys.exit(0)

    # --- Start engine ---
    from core import engine
    engine.run(config)


if __name__ == "__main__":
    main()