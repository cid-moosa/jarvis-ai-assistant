"""
core/voice.py - Non-blocking Edge TTS speaker.
Runs TTS in a background thread so the main loop never freezes.
"""
import asyncio
import os
import uuid
import tempfile
import threading
import pygame
from core import logger

pygame.mixer.init()
_channel = pygame.mixer.Channel(0)
_lock = threading.Lock()
_config = {}


def setup(config: dict):
    global _config
    _config = config


async def _async_speak(text: str, voice: str):
    import edge_tts
    tmp = os.path.join(tempfile.gettempdir(), f"jarvis_tts_{uuid.uuid4().hex}.mp3")
    try:
        comm = edge_tts.Communicate(text, voice)
        await comm.save(tmp)
        with _lock:
            sound = pygame.mixer.Sound(tmp)
            _channel.play(sound)
            while _channel.get_busy():
                pygame.time.Clock().tick(10)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _speak_thread(text: str, voice: str):
    asyncio.run(_async_speak(text, voice))


def speak(text: str, blocking: bool = False):
    """Speak text via Edge TTS. Non-blocking by default."""
    log = logger.get()
    log.info(f"[Jarvis]: {text}")
    voice = _config.get("voice", "en-US-ChristopherNeural")
    t = threading.Thread(target=_speak_thread, args=(text, voice), daemon=True)
    t.start()
    if blocking:
        t.join()


def wait_done():
    """Block until the current TTS utterance finishes."""
    while _channel.get_busy():
        pygame.time.Clock().tick(10)