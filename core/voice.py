"""
core/voice.py
=============
TTS speaker with two backends:
  1. Edge TTS (en-US-ChristopherNeural) — online, best quality
  2. pyttsx3 (Windows SAPI5) — 100% offline fallback

speak() is BLOCKING by default now — this is critical for the launch sequence
so announcements actually complete before the automation starts running.
Use blocking=False only for non-critical background messages.
"""
import asyncio
import os
import uuid
import tempfile
import threading
import pygame
from core import logger

pygame.mixer.init()
_channel  = pygame.mixer.Channel(0)
_lock     = threading.Lock()
_config   = {}
_sapi_engine = None   # pyttsx3 engine, initialised lazily


def setup(config: dict):
    global _config
    _config = config


# ── pyttsx3 offline TTS (fallback) ────────────────────────────────────────────

def _get_sapi():
    global _sapi_engine
    if _sapi_engine is None:
        try:
            import pyttsx3
            _sapi_engine = pyttsx3.init()
            _sapi_engine.setProperty("rate", 185)
        except Exception as e:
            logger.get().warning(f"pyttsx3 init failed: {e}")
    return _sapi_engine


def _sapi_speak(text: str):
    eng = _get_sapi()
    if eng:
        try:
            eng.say(text)
            eng.runAndWait()
        except Exception as e:
            logger.get().error(f"SAPI speak failed: {e}")


# ── Edge TTS (online, preferred) ──────────────────────────────────────────────

async def _async_speak(text: str, voice_name: str):
    import edge_tts
    tmp = os.path.join(tempfile.gettempdir(), f"jarvis_{uuid.uuid4().hex}.mp3")
    try:
        comm = edge_tts.Communicate(text, voice_name)
        await comm.save(tmp)
        with _lock:
            sound = pygame.mixer.Sound(tmp)
            _channel.play(sound)
            while _channel.get_busy():
                pygame.time.Clock().tick(10)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _edge_speak(text: str, voice_name: str):
    try:
        asyncio.run(_async_speak(text, voice_name))
    except Exception as e:
        logger.get().warning(f"Edge TTS failed ({e}) — falling back to SAPI.")
        _sapi_speak(text)


# ── Public API ─────────────────────────────────────────────────────────────────

def speak(text: str, blocking: bool = True):
    """
    Speak text aloud.

    blocking=True  (default): caller waits until speech finishes.
                              Use this for all launch-sequence announcements.
    blocking=False:           fire-and-forget background thread.
                              Use only for non-critical status messages.
    """
    log = logger.get()
    log.info(f"[Jarvis]: {text}")
    voice_name = _config.get("voice", "en-US-ChristopherNeural")

    t = threading.Thread(target=_edge_speak, args=(text, voice_name), daemon=True)
    t.start()
    if blocking:
        t.join()


def wait_done():
    """Block until any playing TTS audio finishes."""
    while _channel.get_busy():
        pygame.time.Clock().tick(10)