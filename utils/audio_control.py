"""
utils/audio_control.py - Mic volume management via pycaw (Windows only).
"""
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from core import logger


def _get_control():
    try:
        devices = AudioUtilities.GetMicrophone()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception as e:
        logger.get().warning(f"Mic volume control unavailable: {e}")
        return None


def get_volume() -> float:
    vol = _get_control()
    return vol.GetMasterVolumeLevelScalar() if vol else 1.0


def set_volume(level: float):
    vol = _get_control()
    if vol:
        vol.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level)), None)