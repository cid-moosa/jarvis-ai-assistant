"""
utils/window.py
===============
Window manager for Jarvis.

Key responsibilities:
  - Focus a window by title without disturbing others
  - Tile/position windows to avoid overlap
  - Run the SKLauncher boot sequence (Enter -> Play click) on the correct window
  - Launch apps via hotkeys or Start menu with overlap-safe ordering
"""
import time
import ctypes
import pyautogui
import pygetwindow as gw
from core import logger

# Windows API constants for reliable foreground focus
SW_RESTORE = 9
SPI_GETWORKAREA = 48


def _screen_size():
    """Return (width, height) of the primary monitor work area (excludes taskbar)."""
    try:
        import ctypes
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        return rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        return pyautogui.size()


def find_window(title_keyword: str):
    """Return first window whose title contains title_keyword (case-insensitive), or None."""
    kw = title_keyword.lower()
    matches = [w for w in gw.getAllWindows()
               if kw in w.title.lower() and w.width > 0]
    return matches[0] if matches else None


def wait_for_window(title_keyword: str, timeout: int = 30):
    """Block until a matching window appears. Returns window or None on timeout."""
    log = logger.get()
    log.info(f"Waiting for window '{title_keyword}' (up to {timeout}s)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        win = find_window(title_keyword)
        if win:
            log.info(f"Found window: '{win.title}'")
            return win
        time.sleep(0.5)
    log.warning(f"Timed out waiting for '{title_keyword}'")
    return None


def force_focus(win) -> bool:
    """
    Forcefully bring a window to the foreground using Win32 API.
    pygetwindow's activate() can silently fail when another app owns focus.
    """
    if win is None:
        return False
    try:
        if win.isMinimized:
            win.restore()
            time.sleep(0.3)
        # Use Win32 SetForegroundWindow for guaranteed focus
        hwnd = win._hWnd
        ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        return True
    except Exception as e:
        logger.get().warning(f"force_focus failed: {e}")
        try:
            win.activate()
            time.sleep(0.4)
        except Exception:
            pass
        return False


def tile_side_by_side(left_keyword: str, right_keyword: str):
    """
    Position two windows side-by-side filling the work area.
    left_keyword goes on the left half, right_keyword on the right half.
    """
    log = logger.get()
    sw, sh = _screen_size()
    half = sw // 2

    for keyword, x, w in [(left_keyword, 0, half), (right_keyword, half, half)]:
        win = find_window(keyword)
        if win:
            try:
                if win.isMinimized:
                    win.restore()
                win.moveTo(x, 0)
                win.resizeTo(w, sh)
                log.info(f"Tiled '{keyword}' -> x={x} w={w} h={sh}")
            except Exception as e:
                log.warning(f"Tile failed for '{keyword}': {e}")


def move_to_center(keyword: str, width_pct: float = 0.6, height_pct: float = 0.85):
    """Centre a window and set it to width_pct / height_pct of screen size."""
    sw, sh = _screen_size()
    win = find_window(keyword)
    if win:
        try:
            w = int(sw * width_pct)
            h = int(sh * height_pct)
            x = (sw - w) // 2
            y = (sh - h) // 2
            if win.isMinimized:
                win.restore()
            win.moveTo(x, y)
            win.resizeTo(w, h)
        except Exception as e:
            logger.get().warning(f"Centre failed for '{keyword}': {e}")


def run_launcher_sequence(config: dict) -> bool:
    """
    Full SKLauncher boot sequence:
      1. Wait for the launcher window to appear
      2. Force-focus it (prevents Discord overlap stealing focus)
      3. Press Enter to dismiss any error/update popup
      4. Click the Play button at the configured offsets

    Returns True if Play was clicked successfully.
    """
    log = logger.get()
    launcher_name  = config.get("launcher_name",               "SKLauncher")
    wait_sec       = config.get("launcher_wait_seconds",        30)
    x_off          = config.get("launcher_play_btn_x_offset",   140)
    y_off          = config.get("launcher_play_btn_y_from_bottom", 65)

    # Step 1: Wait for launcher window
    win = wait_for_window(launcher_name, timeout=wait_sec)
    if win is None:
        log.error("SKLauncher window never appeared.")
        return False

    # Step 2: Let internal loading finish, then force focus
    log.info("Launcher found — waiting for it to fully load...")
    time.sleep(2.5)
    force_focus(win)
    log.info("Launcher focused.")

    # Step 3: Dismiss error/update popup (Enter)
    pyautogui.press("enter")
    time.sleep(0.6)

    # Step 4: Re-focus (Enter may have shifted focus to popup dialog)
    force_focus(win)

    # Step 5: Click Play button
    try:
        # Refresh window geometry after any resize
        win = find_window(launcher_name) or win
        click_x = win.left + x_off
        click_y = win.top + win.height - y_off
        log.info(f"Clicking Play at ({click_x}, {click_y})")
        pyautogui.moveTo(click_x, click_y, duration=0.4)
        pyautogui.click()
        return True
    except Exception as e:
        log.error(f"Play button click failed: {e}")
        return False