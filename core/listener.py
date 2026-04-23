"""
core/listener.py - Clap detection engine.
Uses a SINGLE persistent PyAudio stream shared for the whole session.
Implements adaptive ambient noise flooring to auto-calibrate the trigger threshold.
"""
import pyaudio
import struct
import math
import time
from collections import deque
from core import logger

FORMAT  = pyaudio.paInt16
CHANNELS = 1

_config  = {}
_pa      = None
_stream  = None
_ambient = deque([2.0] * 30, maxlen=30)


def setup(config: dict):
    global _config, _pa, _stream
    _config = config
    _pa = pyaudio.PyAudio()
    _stream = _pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=config.get("sample_rate", 44100),
        input=True,
        frames_per_buffer=config.get("chunk_size", 1024),
    )
    logger.get().info("Audio stream opened.")


def teardown():
    global _stream, _pa
    if _stream:
        try:
            _stream.stop_stream()
            _stream.close()
        except Exception:
            pass
    if _pa:
        try:
            _pa.terminate()
        except Exception:
            pass
    logger.get().info("Audio stream closed.")


def pause():
    if _stream and _stream.is_active():
        _stream.stop_stream()


def resume():
    if _stream and not _stream.is_active():
        _stream.start_stream()


def _rms(data: bytes) -> float:
    count = len(data) // 2
    shorts = struct.unpack(f"{count}h", data)
    mean_sq = sum((s / 32768.0) ** 2 for s in shorts) / count
    return math.sqrt(mean_sq) * 1000


def _threshold() -> float:
    avg = sum(_ambient) / len(_ambient)
    return max(
        _config.get("min_threshold", 5),
        avg * _config.get("spike_multiplier", 4.0),
    )


def _read_chunk() -> float:
    chunk = _config.get("chunk_size", 1024)
    try:
        data = _stream.read(chunk, exception_on_overflow=False)
    except OSError:
        return 0.0
    rms = _rms(data)
    if rms < _threshold():
        _ambient.append(rms)
    return rms


def wait_for_clap() -> bool:
    """Block until a single loud sound (clap) is detected. Returns True."""
    while True:
        rms = _read_chunk()
        thr = _threshold()
        if rms > 1.5:
            print(
                f"  Level: {rms:5.1f}  Floor: {sum(_ambient)/len(_ambient):4.1f}  Trigger: {thr:5.1f}\r",
                end="",
                flush=True,
            )
        if rms > thr:
            return True


def listen_for_second_clap(window: float = None) -> bool:
    """
    After the first clap, listen for a second within the given time window.
    Returns True if a second clap is detected.
    """
    window = window or _config.get("double_clap_window", 0.80)
    gap    = _config.get("clap_gap_seconds", 0.30)
    start  = time.time()
    last   = 0.0

    while time.time() - start < window:
        rms = _read_chunk()
        now = time.time()
        if rms > _threshold() and (now - last) > gap:
            last = now
            return True
    return False