"""
utils/window.py
===============
Window manager for Jarvis — fast, reliable, overlap-safe.

Key design decisions:
  - pyautogui MINIMUM_DURATION = 0: mouse moves are INSTANT (no animation delay)
  - Blue button finder: scans the launcher window for the actual blue Start button
    by pixel color — does NOT rely on fixed offsets that break on different resolutions
  - Win32 SetForegroundWindow: guarantees focus, unlike pygetwindow activate()
  - Popup detector: waits for the error popup specifically before pressing Enter
  - Game process watcher: terminates Jarvis once javaw.exe is confirmed stable
"""
import time
import ctypes
import ctypes.wintypes
import os
import threading
import pyautogui
import pygetwindow as gw
from core import logger

# ── Speed config ──────────────────────────────────────────────────────────────
# Remove all mouse animation delays globally — instant movement
pyautogui.MINIMUM_DURATION  = 0
pyautogui.MINIMUM_SLEEP     = 0
pyautogui.PAUSE             = 0.05   # tiny safety pause between calls

SW_RESTORE       = 9
SPI_GETWORKAREA  = 48


# ── Screen helpers ─────────────────────────────────────────────────────────────

def _work_area():
    """Return (width, height) of primary monitor minus taskbar."""
    try:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        return rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        return pyautogui.size()


# ── Window finders ─────────────────────────────────────────────────────────────

def find_window(keyword: str):
    """Return first visible window whose title contains keyword, or None."""
    kw = keyword.lower()
    return next(
        (w for w in gw.getAllWindows() if kw in w.title.lower() and w.width > 0),
        None
    )


def wait_for_window(keyword: str, timeout: int = 30):
    """Poll until a window matching keyword appears. Returns window or None."""
    log = logger.get()
    log.info(f"Waiting for window '{keyword}' (up to {timeout}s)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        w = find_window(keyword)
        if w:
            log.info(f"Found: '{w.title}'")
            return w
        time.sleep(0.4)
    log.warning(f"Timed out waiting for '{keyword}'")
    return None


# ── Focus ──────────────────────────────────────────────────────────────────────

def force_focus(win) -> bool:
    """
    Guarantee a window is in the foreground using Win32.
    pygetwindow.activate() silently fails when another app holds focus lock.
    """
    if win is None:
        return False
    try:
        hwnd = win._hWnd
        if win.isMinimized:
            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.2)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.25)
        return True
    except Exception as e:
        logger.get().warning(f"force_focus: {e}")
        try:
            win.activate()
            time.sleep(0.2)
        except Exception:
            pass
        return False


# ── Blue button finder ─────────────────────────────────────────────────────────

def _find_blue_button(win, scan_rows: int = 120) -> tuple:
    """
    Scan the bottom-left region of the launcher window for the blue Start button.

    SKLauncher's Start button is a distinct blue: R < 100, G < 170, B > 160.
    We scan the bottom `scan_rows` pixels of the window, left half only.

    Returns (click_x, click_y) of the button centre, or (None, None) if not found.
    """
    log = logger.get()
    try:
        from PIL import ImageGrab
        # Capture just the bottom-left region of the launcher
        left   = win.left
        top    = max(win.top, win.top + win.height - scan_rows)
        right  = win.left + win.width // 2   # left half only
        bottom = win.top + win.height

        img = ImageGrab.grab(bbox=(left, top, right, bottom))
        pixels = img.load()
        w, h   = img.size

        blue_xs, blue_ys = [], []
        for y in range(h):
            for x in range(w):
                r, g, b = pixels[x, y][:3]
                # Blue button heuristic: clearly blue, not white/grey
                if b > 150 and r < 120 and b - r > 60 and b - g > 30:
                    blue_xs.append(x)
                    blue_ys.append(y)

        if len(blue_xs) > 40:   # enough blue pixels to be a button, not a border
            cx = left + int(sum(blue_xs) / len(blue_xs))
            cy = top  + int(sum(blue_ys) / len(blue_ys))
            log.info(f"Blue button found at ({cx}, {cy}) from {len(blue_xs)} px")
            return cx, cy
        else:
            log.warning(f"Blue button scan: only {len(blue_xs)} blue pixels — falling back to offset")
            return None, None
    except Exception as e:
        log.warning(f"Blue button scan error: {e}")
        return None, None


# ── Launcher sequence ──────────────────────────────────────────────────────────

def run_launcher_sequence(config: dict) -> bool:
    """
    Full SKLauncher start sequence. Steps:
      1. Wait for the launcher window to appear
      2. Force-focus it exclusively
      3. Wait briefly for internal loading (splash/update check)
      4. Press Enter to dismiss any error/update popup
      5. Re-focus (popup may have shifted focus away)
      6. Find the blue Start button by pixel scan, click it instantly
      7. Verify the click landed on something blue (retry up to 3x)

    Returns True once the click was executed.
    """
    log = logger.get()
    launcher_name = config.get("launcher_name", "SKLauncher")
    wait_sec      = config.get("launcher_wait_seconds", 30)
    x_off         = config.get("launcher_play_btn_x_offset", 140)
    y_off         = config.get("launcher_play_btn_y_from_bottom", 65)

    # ── 1. Wait for window ──
    win = wait_for_window(launcher_name, timeout=wait_sec)
    if win is None:
        log.error("SKLauncher never appeared.")
        return False

    # ── 2. Wait for launcher to load its UI fully ──
    log.info("Launcher appeared — waiting for UI to load...")
    time.sleep(3)

    # ── 3. Force focus before any keypress ──
    win = find_window(launcher_name) or win   # refresh geometry
    force_focus(win)

    # ── 4. Dismiss error/update popup with Enter ──
    log.info("Pressing Enter to dismiss popup (if any)...")
    pyautogui.press("enter")
    time.sleep(0.5)

    # ── 5. Re-focus (popup dialog may have eaten the focus) ──
    win = find_window(launcher_name) or win
    force_focus(win)
    time.sleep(0.3)

    # ── 6. Find + click the blue Start button (up to 3 retries) ──
    for attempt in range(1, 4):
        win = find_window(launcher_name) or win

        # Try pixel-scan first (most reliable)
        cx, cy = _find_blue_button(win)

        if cx is None:
            # Fallback: use config offsets
            cx = win.left + x_off
            cy = win.top + win.height - y_off
            log.info(f"Attempt {attempt}: fallback offset click at ({cx}, {cy})")
        else:
            log.info(f"Attempt {attempt}: pixel-scan click at ({cx}, {cy})")

        # Instant mouse move + click (duration=0)
        pyautogui.moveTo(cx, cy, duration=0)
        pyautogui.click()
        time.sleep(0.4)

        # Verify: check if the launcher window is still present
        # If game started launching, launcher might close or minimise
        post_win = find_window(launcher_name)
        if post_win is None:
            log.info("Launcher closed after click — game is launching!")
            return True

        # If launcher still open, check if Minecraft process appeared
        import psutil
        mc_running = any(
            p.name().lower() in ("javaw.exe", "minecraft.exe")
            for p in psutil.process_iter(["name"])
        )
        if mc_running:
            log.info("Minecraft process detected — launch confirmed!")
            return True

        if attempt < 3:
            log.warning(f"Click attempt {attempt} did not start game. Retrying in 1s...")
            force_focus(win)
            time.sleep(1)

    log.error("All click attempts failed.")
    return False


# ── Window layout helpers ──────────────────────────────────────────────────────

def tile_side_by_side(left_keyword: str, right_keyword: str):
    """Position two windows side-by-side with zero overlap."""
    log = logger.get()
    sw, sh = _work_area()
    half = sw // 2
    for keyword, x, w in [(left_keyword, 0, half), (right_keyword, half, half)]:
        win = find_window(keyword)
        if win:
            try:
                if win.isMinimized:
                    win.restore()
                win.moveTo(x, 0)
                win.resizeTo(w, sh)
                log.info(f"Tiled '{keyword}' -> x={x} w={w}")
            except Exception as e:
                log.warning(f"Tile '{keyword}': {e}")


# ── Game watcher / self-terminate ─────────────────────────────────────────────

def watch_and_terminate_when_game_starts(check_interval: float = 3.0, stable_checks: int = 3):
    """
    Start a background daemon thread that monitors for javaw.exe.
    Once Minecraft is confirmed running (stable for stable_checks * check_interval seconds),
    Jarvis calls os._exit(0) to free all PC resources for the game.
    """
    log = logger.get()

    def _watcher():
        import psutil
        stable = 0
        log.info("Game watcher started — will self-terminate when Minecraft is stable.")
        while True:
            time.sleep(check_interval)
            running = any(
                p.name().lower() in ("javaw.exe", "minecraft.exe")
                for p in psutil.process_iter(["name"])
            )
            if running:
                stable += 1
                log.info(f"Minecraft running ({stable}/{stable_checks} stability checks)...")
                if stable >= stable_checks:
                    log.info("Minecraft confirmed stable — Jarvis terminating to free resources.")
                    time.sleep(1)
                    os._exit(0)
            else:
                stable = 0   # reset if process disappears (crash / user quit before stable)

    t = threading.Thread(target=_watcher, daemon=True, name="GameWatcher")
    t.start()
    logger.get().info("Game watcher active.")