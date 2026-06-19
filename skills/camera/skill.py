"""
skills/camera/skill.py
======================
OpenCV Computer Vision Skill.
Triggers on: "what do you see", "camera access", "take a snapshot",
             "look around", "describe the room", "snapshot".

On trigger:
  1. Opens cv2.VideoCapture(0) with graceful fallback on failure.
  2. Captures a single frame and saves to web/static/img/snapshot.jpg.
  3. If a Gemini API key with vision support is configured, sends the
     image to gemini-1.5-flash for a natural language room description.
  4. If no API key, runs basic OpenCV stats (edge density, brightness)
     and reports a heuristic summary.
  5. Broadcasts snapshot_ready event to all WebSocket clients so the UI
     displays the image inline.

All cv2 / camera errors degrade gracefully without crashing.
"""
import os
import base64
import threading
from core import voice, intent, logger, memory


# ── Path helpers ───────────────────────────────────────────────────────────────

def _snapshot_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    img_dir = os.path.join(base, "web", "static", "img")
    os.makedirs(img_dir, exist_ok=True)
    return os.path.join(img_dir, "snapshot.jpg")


# ── Vision analysis ────────────────────────────────────────────────────────────

def _analyse_with_gemini(img_path: str, config: dict) -> str:
    """Send captured image to Gemini vision API for description. Returns summary string."""
    api_key = memory.get_api_key("gemini")
    if not api_key:
        return None  # Signal caller to use OpenCV fallback

    model_name = config.get("llm_model", "gemini-1.5-flash")
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            import google.generativeai as genai
            from google.generativeai import types as genai_types
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)

        with open(img_path, "rb") as f:
            image_bytes = f.read()

        image_part = genai_types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg"
        )
        prompt = (
            "You are Jarvis, an AI assistant with camera access. "
            "Describe what you see in this room snapshot in 2-3 natural spoken sentences. "
            "Be concise and direct. Do not use markdown."
        )
        response = model.generate_content([prompt, image_part])
        return response.text.strip()
    except Exception as e:
        logger.get().error(f"Camera: Gemini vision error: {e}")
        return None


def _analyse_opencv(img_path: str) -> str:
    """Heuristic analysis using OpenCV edge density and brightness."""
    try:
        import cv2
        import numpy as np
        img = cv2.imread(img_path)
        if img is None:
            return "I could read the frame but could not analyse it."

        gray       = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        edges      = cv2.Canny(gray, 50, 150)
        edge_pct   = float(np.count_nonzero(edges)) / edges.size * 100

        if brightness < 40:
            light = "very dark environment"
        elif brightness < 100:
            light = "dimly lit environment"
        elif brightness < 180:
            light = "moderately lit environment"
        else:
            light = "bright environment"

        if edge_pct < 2:
            detail = "with very few distinct objects"
        elif edge_pct < 6:
            detail = "with some objects or surfaces"
        elif edge_pct < 12:
            detail = "with a number of distinct objects"
        else:
            detail = "with a complex arrangement of objects"

        return (
            f"I can see a {light} {detail}. "
            f"The average brightness is {brightness:.0f} out of 255, "
            f"and the scene has about {edge_pct:.1f} percent edge coverage. "
            f"For a detailed description, configure a Gemini API key in the settings."
        )
    except Exception as e:
        return f"OpenCV analysis failed: {e}"


# ── Snapshot capture ───────────────────────────────────────────────────────────

def _capture_and_analyse(config: dict):
    log = logger.get()
    try:
        import cv2
    except ImportError:
        voice.speak("OpenCV is not installed. Run pip install opencv-python to enable camera support.")
        return

    snap_path = _snapshot_path()
    cap = None

    try:
        log.info("Camera: opening cv2.VideoCapture(0)")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            voice.speak("I could not access the webcam. It may be in use or disconnected.")
            log.warning("Camera: cv2.VideoCapture(0) failed to open.")
            return

        # Warm-up frames
        for _ in range(3):
            cap.read()

        ret, frame = cap.read()
        if not ret or frame is None:
            voice.speak("The camera opened but did not return a valid frame.")
            log.warning("Camera: frame capture returned None.")
            return

        cv2.imwrite(snap_path, frame)
        log.info(f"Camera: snapshot saved to {snap_path}")
        voice.speak("Snapshot captured. Analysing the scene.", blocking=False)

        # Try Gemini vision first, fall back to OpenCV heuristic
        description = _analyse_with_gemini(snap_path, config)
        if description is None:
            description = _analyse_opencv(snap_path)

        log.info(f"Camera: description = {description}")
        voice.speak(description)

        # Push snapshot event to WebSocket
        try:
            from core import server as srv
            srv.broadcast({
                "event":   "snapshot_ready",
                "url":     "/static/img/snapshot.jpg",
                "caption": description[:200],
            })
        except Exception:
            pass

    except Exception as e:
        log.error(f"Camera skill error: {e}")
        voice.speak(f"Camera error: {e}. Please check your webcam connection.")
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        log.info("Camera: VideoCapture released.")


# ── Main handler ───────────────────────────────────────────────────────────────

def handle(cmd: str, config: dict):
    log = logger.get()
    log.info(f"Camera skill triggered: '{cmd}'")
    voice.speak("Accessing camera.", blocking=False)
    # Run capture in a thread so it does not block the engine
    t = threading.Thread(
        target=_capture_and_analyse,
        args=(config,),
        daemon=True,
        name="CameraCapture",
    )
    t.start()


# ── Skill registration ─────────────────────────────────────────────────────────

SKILL = intent.Skill(
    name        = "camera",
    handler     = handle,
    description = "OpenCV webcam snapshot + Gemini vision description. Displays in WebUI.",
    keywords    = ["see", "camera", "snapshot", "photo", "picture", "look", "room", "describe", "vision"],
    patterns    = [
        intent.IntentPattern("what do you see",    92),
        intent.IntentPattern("camera access",      90),
        intent.IntentPattern("take a snapshot",    95),
        intent.IntentPattern("take a photo",       92),
        intent.IntentPattern("take a picture",     92),
        intent.IntentPattern("look around",        88),
        intent.IntentPattern("describe the room",  90),
        intent.IntentPattern("snapshot",           82),
        intent.IntentPattern("what is in the room",88),
        intent.IntentPattern("show me what you see",90),
    ],
)
