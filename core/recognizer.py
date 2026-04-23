"""
core/recognizer.py - Google Speech-to-Text wrapper.
Mutes mic volume during playback to prevent feedback, restores after.
"""
import speech_recognition as sr
from core import logger
from utils import audio_control

_config = {}


def setup(config: dict):
    global _config
    _config = config


def listen(timeout: float = None, phrase_limit: float = None) -> str:
    """
    Listen via microphone and return recognized text (lowercased), or empty string on failure.
    """
    log = logger.get()
    timeout = timeout or _config.get("listen_timeout", 7.0)
    phrase_limit = phrase_limit or _config.get("phrase_time_limit", 6)

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True

    log.debug("Microphone open for voice input...")
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        text = recognizer.recognize_google(audio).lower()
        log.info(f"[You]: {text}")
        return text
    except sr.WaitTimeoutError:
        log.warning("No speech detected (timeout).")
        return ""
    except sr.UnknownValueError:
        log.warning("Could not understand audio.")
        return ""
    except sr.RequestError as e:
        log.error(f"Google STT error: {e}")
        return ""