"""
core/engine.py
==============
Hybrid async event loop for Jarvis.

Runs two concurrent worker threads:
  1. VOICE LOOP  — original PyAudio double-clap -> STT -> intent -> skill/LLM
  2. TEXT WORKER — drains _command_queue filled by the web server's POST endpoint

Both threads call _process_command() so behaviour is identical regardless
of input source. All original PyAudio / double-clap / SAPI5 / RapidFuzz
logic is 100% preserved.
"""
import time
import queue
import threading
from core import listener, voice, recognizer, intent, memory, logger

# Shared queue: core/server.py puts (command_str, "TEXT") here
_command_queue: queue.Queue = queue.Queue()


def get_command_queue() -> queue.Queue:
    """Expose queue so server.py can push text commands."""
    return _command_queue


# ── Shared command processor ───────────────────────────────────────────────────

def _process_command(command: str, mode: str, config: dict):
    """
    Unified command handler called by both the voice loop and the text worker.
    mode: "VOICE" | "TEXT"
    """
    from core import logger as log_mod, server as srv
    log = log_mod.get()

    if not command:
        return

    # Push PROCESSING state to WebUI
    try:
        srv.broadcast({"state": "PROCESSING"})
    except Exception:
        pass

    # Classify with local RapidFuzz pipeline
    skill, score, matched = intent.classify(command)
    log.debug(f"Intent: skill={skill.name if skill else 'none'}, score={score}, matched='{matched}', mode={mode}")

    if skill:
        memory.set("last_command", command)
        memory.set("last_skill", skill.name)
        try:
            skill.handler(command, config)
            # Log the exchange (skill handled it — response text is implied by TTS)
            from core import logger as log_mod2
            log_mod2.log_exchange(mode, command, f"[{skill.name} skill executed]")
        except Exception as e:
            log.error(f"Skill '{skill.name}' raised: {e}")
            response = "Something went wrong with that command."
            voice.speak(response)
            from core import logger as log_mod2
            log_mod2.log_exchange(mode, command, response)
    else:
        log.info(f"No local skill matched '{command}' (score={score}) — routing to LLM.")
        # Push LLM thinking state
        try:
            srv.broadcast({"state": "PROCESSING", "hint": "llm"})
        except Exception:
            pass
        response = intent.llm_fallback(command, config)
        voice.speak(response)
        from core import logger as log_mod2
        log_mod2.log_exchange(mode, command, response)


# ── Text worker thread ─────────────────────────────────────────────────────────

def _text_worker(config: dict, stop_event: threading.Event):
    """Drain _command_queue and process typed commands from the WebUI."""
    log = logger.get()
    log.info("Text input worker started.")
    while not stop_event.is_set():
        try:
            cmd, mode = _command_queue.get(timeout=0.5)
            _process_command(cmd, mode, config)
        except queue.Empty:
            continue
        except Exception as e:
            log.error(f"Text worker error: {e}")


# ── Voice loop thread ──────────────────────────────────────────────────────────

def _voice_loop(config: dict, stop_event: threading.Event):
    """
    Original double-clap -> STT -> intent pipeline — runs in its own thread.
    All PyAudio / listener / recognizer logic is unchanged.
    """
    from core import server as srv
    log = logger.get()
    name = config.get("name", "Jarvis")

    try:
        listener.setup(config)
    except Exception as e:
        log.error(f"Microphone init failed: {e}. Voice loop disabled — use text input.")
        voice.speak("Microphone unavailable. Use the web interface to type commands.")
        return

    log.info(f"{name} voice loop active. Double-clap to give a command.")

    try:
        while not stop_event.is_set():
            # --- Wait for first clap ---
            try:
                listener.wait_for_clap()
            except Exception as e:
                log.error(f"Clap detection error: {e}")
                time.sleep(1)
                continue

            # --- Wait for second clap ---
            try:
                if not listener.listen_for_second_clap():
                    continue
            except Exception as e:
                log.error(f"Second-clap detection error: {e}")
                continue

            print()  # clear level-meter line
            log.info("Double clap! Listening for command...")

            # Push LISTENING state to WebUI
            try:
                srv.broadcast({"state": "LISTENING"})
            except Exception:
                pass

            # --- Pause audio stream while using mic for STT ---
            listener.pause()

            voice.speak("Yes?", blocking=True)

            try:
                command = recognizer.listen()
            except Exception as e:
                log.error(f"STT error: {e}")
                command = ""

            if not command:
                voice.speak("I didn't catch that.")
                # Push IDLE
                try:
                    srv.broadcast({"state": "IDLE"})
                except Exception:
                    pass
                listener.resume()
                continue

            # Log what was heard to WebUI console
            try:
                srv.broadcast({"event": "stt_result", "text": command})
            except Exception:
                pass

            _process_command(command, "VOICE", config)
            listener.resume()

    except Exception as e:
        log.error(f"Voice loop fatal error: {e}")
    finally:
        try:
            listener.teardown()
        except Exception:
            pass
        log.info("Voice loop terminated.")


# ── Public entry point ─────────────────────────────────────────────────────────

def run(config: dict):
    """
    Start both the voice loop thread and the text worker thread.
    Blocks until KeyboardInterrupt.
    """
    from utils import audio_control
    log = logger.get()
    name = config.get("name", "Jarvis")

    # Restore mic on exit
    try:
        orig_vol = audio_control.get_volume()
        audio_control.set_volume(config.get("mic_volume", 0.50))
    except Exception as e:
        log.warning(f"Audio volume control unavailable: {e}")
        orig_vol = None

    voice.speak(f"{name} online. Double clap anytime, or use the web interface.", blocking=False)

    stop_event = threading.Event()

    # Start text worker
    tw = threading.Thread(target=_text_worker, args=(config, stop_event), daemon=True, name="TextWorker")
    tw.start()

    # Start voice loop
    vl = threading.Thread(target=_voice_loop, args=(config, stop_event), daemon=True, name="VoiceLoop")
    vl.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
        log.info("Shutting down...")
    finally:
        stop_event.set()
        tw.join(timeout=2)
        vl.join(timeout=2)
        if orig_vol is not None:
            try:
                audio_control.set_volume(orig_vol)
            except Exception:
                pass
        log.info("Session ended.")
