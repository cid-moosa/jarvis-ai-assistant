"""
core/engine.py
==============
Main async event loop for Jarvis.
Orchestrates: clap detection -> STT -> intent -> skill dispatch -> TTS.
"""
import time
from core import listener, voice, recognizer, intent, memory, logger
from utils import audio_control


def run(config: dict):
    log = logger.get()
    name = config.get("name", "Jarvis")

    # Restore mic on exit
    orig_vol = audio_control.get_volume()
    audio_control.set_volume(config.get("mic_volume", 0.50))

    listener.setup(config)
    log.info(f"{name} is online. Double-clap to give a command.")
    voice.speak(f"{name} online. Double clap anytime.", blocking=False)

    try:
        while True:
            # --- Wait for first clap ---
            listener.wait_for_clap()

            # --- Wait for second clap ---
            if not listener.listen_for_second_clap():
                continue

            print()  # clear level-meter line
            log.info("Double clap! Listening for command...")

            # --- Pause audio stream while using mic for STT ---
            listener.pause()

            voice.speak("Yes?", blocking=True)
            command = recognizer.listen()

            if not command:
                voice.speak("I didn't catch that.")
                listener.resume()
                continue

            # --- Classify intent locally ---
            skill, score, matched = intent.classify(command)
            log.debug(f"Intent: skill={skill.name if skill else 'none'}, score={score}, matched='{matched}'")

            if skill:
                memory.set("last_command", command)
                memory.set("last_skill", skill.name)
                try:
                    skill.handler(command, config)
                except Exception as e:
                    log.error(f"Skill '{skill.name}' raised: {e}")
                    voice.speak("Something went wrong with that command.")
            else:
                log.warning(f"No skill matched '{command}' (best score < 60)")
                voice.speak("I don't know how to do that yet. Say 'help' for a list of commands.")

            listener.resume()

    except KeyboardInterrupt:
        print()
        log.info("Shutting down...")
    finally:
        listener.teardown()
        audio_control.set_volume(orig_vol)
        log.info("Mic volume restored. Session ended.")