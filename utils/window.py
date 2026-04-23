"""
utils/window.py - Window management helpers (SKLauncher auto-click, focus, etc.)
"""
import time
import pyautogui
import pygetwindow as gw
from core import logger


def find_and_activate(title_keyword: str, wait_seconds: int = 30):
    """Wait up to wait_seconds for a window whose title contains title_keyword, then activate it."""
    log = logger.get()
    log.info(f"Waiting for window: '{title_keyword}' (up to {wait_seconds}s)...")
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        matches = [w for w in gw.getAllWindows() if title_keyword.lower() in w.title.lower()]
        if matches:
            win = matches[0]
            log.info(f"Found: '{win.title}'")
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.8)
            except Exception as e:
                log.warning(f"Activate failed: {e}")
            return win
        time.sleep(1)
    log.warning(f"Window '{title_keyword}' not found after {wait_seconds}s.")
    return None


def click_launcher_play(config: dict) -> bool:
    """
    Find the SKLauncher window and click the blue Play button.
    Uses configurable pixel offsets from config.yaml.
    """
    log = logger.get()
    launcher_name = config.get("launcher_name", "SKLauncher")
    wait_sec = config.get("launcher_wait_seconds", 30)
    x_off = config.get("launcher_play_btn_x_offset", 140)
    y_off = config.get("launcher_play_btn_y_from_bottom", 65)

    win = find_and_activate(launcher_name, wait_seconds=wait_sec)
    if win is None:
        return False

    time.sleep(2)  # let launcher finish internal loading

    try:
        # Dismiss any error popup first
        pyautogui.press("enter")
        time.sleep(0.5)

        click_x = win.left + x_off
        click_y = win.top + win.height - y_off
        log.info(f"Clicking Play at ({click_x}, {click_y})")
        pyautogui.moveTo(click_x, click_y, duration=0.5)
        pyautogui.click()
        return True
    except Exception as e:
        log.error(f"Play button click failed: {e}")
        pyautogui.press("enter")
        return False