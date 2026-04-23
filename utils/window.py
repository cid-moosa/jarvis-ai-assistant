"""
utils/window.py
===============
Window manager for Jarvis.

Fixes vs previous version:
  - _safe_rect(hwnd): uses ctypes.GetWindowRect for FRESH coordinates every call.
    Never uses win.left/win.top/etc. from a possibly-stale pygetwindow object.
  - _find_blue_button: uses pyautogui.screenshot(region=...) which goes through
    GDI correctly — no invalid window handle (error 1400).
  - run_launcher_sequence: waits for launcher to be STABLE (present for 2 checks)
    before proceeding, then waits a longer boot time (5s) for full UI load.
  - All Win32 calls wrapped with IsWindow() guard before use.
"""
import time
import ctypes
import ctypes.wintypes
import os
import threading
import pyautogui
import pygetwindow as gw
from core import logger

# ── Speed config ───────────────────────────────────────────────────────────────
pyautogui.MINIMUM_DURATION = 0
pyautogui.MINIMUM_SLEEP    = 0
pyautogui.PAUSE            = 0.04

SW_RESTORE       = 9
SPI_GETWORKAREA  = 48

_user32 = ctypes.windll.user32


# ── Win32 helpers ──────────────────────────────────────────────────────────────

def _is_valid_hwnd(hwnd: int) -> bool:
    """Return True if hwnd is still a live window."""
    return bool(_user32.IsWindow(hwnd))


def _safe_rect(hwnd: int):
    """
    Get (left, top, right, bottom) screen coordinates for hwnd via GetWindowRect.
    Always fresh — never stale pygetwindow cached values.
    Returns None if hwnd is invalid.
    """
    if not _is_valid_hwnd(hwnd):
        return None
    rect = ctypes.wintypes.RECT()
    if _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return rect.left, rect.top, rect.right, rect.bottom
    return None


def _work_area():
    try:
        rect = ctypes.wintypes.RECT()
        _user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
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


def wait_for_window(keyword: str, timeout: int = 40):
    """
    Poll until a window matching keyword appears AND has been stable
    for 2 consecutive 0.5s checks (avoids grabbing the window too early
    when the handle is still being registered by the OS).
    """
    log = logger.get()
    log.info(f"Waiting for '{keyword}' (up to {timeout}s)...")
    deadline  = time.time() + timeout
    stable    = 0

    while time.time() < deadline:
        w = find_window(keyword)
        if w and _is_valid_hwnd(w._hWnd):
            stable += 1
            if stable >= 2:
                log.info(f"Window stable: '{w.title}'")
                return w
        else:
            stable = 0
        time.sleep(0.5)

    log.warning(f"Timed out waiting for '{keyword}'")
    return None


# ── Focus ──────────────────────────────────────────────────────────────────────

def force_focus(win) -> bool:
    """Bring window to foreground using Win32. Guards against stale handles."""
    if win is None:
        return False
    hwnd = win._hWnd
    if not _is_valid_hwnd(hwnd):
        logger.get().warning("force_focus: stale HWND — refreshing window...")
        win = find_window(win.title.split()[0])
        if win is None:
            return False
        hwnd = win._hWnd

    try:
        _user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.15)
        _user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        return True
    except Exception as e:
        logger.get().warning(f"force_focus Win32 error: {e}")
        return False


# ── Blue button finder ─────────────────────────────────────────────────────────

def _find_blue_button(win, x_off: int, y_off: int, scan_rows: int = 140) -> tuple:
    """
    Scan the bottom-left region of the launcher for the blue Start button.
    Uses pyautogui.screenshot(region=...) — safe, no HWND involved.

    Returns (screen_x, screen_y) of button centre, or falls back to offsets.
    """
    log = logger.get()

    # Get FRESH window rect via GetWindowRect (not cached pygetwindow values)
    r = _safe_rect(win._hWnd)
    if r is None:
        log.warning("Button scan: invalid HWND — using offset fallback.")
        return win.left + x_off, win.top + win.height - y_off

    wl, wt, wr, wb = r
    win_w = wr - wl
    win_h = wb - wt

    # Scan region: bottom `scan_rows` pixels, left 55% of window
    scan_left   = wl
    scan_top    = wb - scan_rows
    scan_width  = int(win_w * 0.55)
    scan_height = scan_rows

    try:
        img = pyautogui.screenshot(region=(scan_left, scan_top, scan_width, scan_height))
        pixels = img.load()
        w, h   = img.size

        blue_xs, blue_ys = [], []
        for y in range(h):
            for x in range(w):
                r_px, g_px, b_px = pixels[x, y][:3]
                # Blue button: clearly blue, not white/grey/black
                if b_px > 140 and r_px < 130 and (b_px - r_px) > 50 and (b_px - g_px) > 20:
                    blue_xs.append(x)
                    blue_ys.append(y)

        if len(blue_xs) > 60:
            cx = scan_left + int(sum(blue_xs) / len(blue_xs))
            cy = scan_top  + int(sum(blue_ys) / len(blue_ys))
            log.info(f"Blue button found: ({cx}, {cy}) from {len(blue_xs)} px")
            return cx, cy
        else:
            log.info(f"Blue scan: {len(blue_xs)} px (< 60) — using offset fallback")
            return wl + x_off, wb - y_off

    except Exception as e:
        log.warning(f"Blue scan error: {e} — using offset fallback")
        return wl + x_off, wb - y_off


# ── Main launcher sequence ─────────────────────────────────────────────────────

def run_launcher_sequence(config: dict) -> bool:
    """
    Full SKLauncher boot sequence:
      1.  Wait for window to appear AND be stable (2 consecutive valid-handle checks)
      2.  Wait 5s for the launcher UI + any auto-update check to fully load
      3.  Force-focus via Win32
      4.  Press Enter to dismiss any error/update popup
      5.  Wait 0.8s — the popup closes, launcher redraws
      6.  Force-focus again (popup dialog eats focus)
      7.  Pixel-scan for blue Start button; click instantly (duration=0)
      8.  Verify game started (up to 3 retries)
    """
    log = logger.get()
    launcher_name = config.get("launcher_name",                  "SKLauncher")
    wait_sec      = config.get("launcher_wait_seconds",           40)
    x_off         = config.get("launcher_play_btn_x_offset",      140)
    y_off         = config.get("launcher_play_btn_y_from_bottom", 65)

    # ── 1. Wait for stable window ──
    win = wait_for_window(launcher_name, timeout=wait_sec)
    if win is None:
        log.error("SKLauncher never appeared.")
        return False

    # ── 2. Wait for full UI load (splash + update check) ──
    log.info("Launcher appeared — waiting 5s for full UI load...")
    time.sleep(5)

    # ── 3. Force focus ──
    win = find_window(launcher_name) or win
    force_focus(win)
    time.sleep(0.3)

    # ── 4. Dismiss error/update popup ──
    log.info("Sending Enter to dismiss popup...")
    pyautogui.press("enter")
    time.sleep(0.8)    # wait for popup to close + launcher to redraw

    # ── 5. Re-focus after popup closed ──
    win = find_window(launcher_name) or win
    force_focus(win)
    time.sleep(0.4)

    # ── 6. Find + click Start button (3 retries) ──
    import psutil
    for attempt in range(1, 4):
        # Always refresh window object to get valid handle
        fresh = find_window(launcher_name)
        if fresh:
            win = fresh

        cx, cy = _find_blue_button(win, x_off, y_off)
        log.info(f"Attempt {attempt}: clicking Start at ({cx}, {cy})")

        force_focus(win)
        time.sleep(0.1)
        pyautogui.moveTo(cx, cy, duration=0)
        pyautogui.click()
        time.sleep(0.5)

        # ── Verify: did the game start? ──
        mc = any(p.name().lower() in ("javaw.exe", "minecraft.exe")
                 for p in psutil.process_iter(["name"]))
        launcher_gone = find_window(launcher_name) is None

        if mc or launcher_gone:
            log.info("Game launch confirmed!")
            return True

        if attempt < 3:
            log.warning(f"Attempt {attempt} didn't start game — retrying in 1.5s...")
            time.sleep(1.5)

    log.error("All 3 click attempts failed.")
    return False


# ── Layout helpers ─────────────────────────────────────────────────────────────

def tile_side_by_side(left_keyword: str, right_keyword: str):
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

def watch_and_terminate_when_game_starts(check_interval: float = 4.0, stable_checks: int = 3):
    """
    Daemon thread: watches for javaw.exe. When Minecraft is confirmed stable
    (running for stable_checks consecutive polls), Jarvis terminates via os._exit(0)
    to free all resources for the game.
    """
    log = logger.get()

    def _watcher():
        import psutil
        stable = 0
        log.info("Game watcher running...")
        while True:
            time.sleep(check_interval)
            try:
                running = any(
                    p.name().lower() in ("javaw.exe", "minecraft.exe")
                    for p in psutil.process_iter(["name"])
                )
            except Exception:
                running = False

            if running:
                stable += 1
                log.info(f"Minecraft stable check {stable}/{stable_checks}")
                if stable >= stable_checks:
                    log.info("Minecraft confirmed — Jarvis terminating.")
                    time.sleep(0.5)
                    os._exit(0)
            else:
                stable = 0

    t = threading.Thread(target=_watcher, daemon=True, name="GameWatcher")
    t.start()
    log.info("Game watcher active.")