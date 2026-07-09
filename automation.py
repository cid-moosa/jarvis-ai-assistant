import pyaudio
import struct
import math
import pyautogui
import time
import asyncio
import edge_tts
import pygame
import os
import uuid
import tempfile
import speech_recognition as sr
import subprocess
import webbrowser
import pygetwindow as gw
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# --- Configuration ---
MIN_THRESHOLD = 5
SPIKE_MULTIPLIER = 4.0
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

# Global state for auto-leveling
ambient_noise_history = [2.0] * 30

def get_dynamic_threshold():
    avg_ambient = sum(ambient_noise_history) / len(ambient_noise_history)
    return max(MIN_THRESHOLD, avg_ambient * SPIKE_MULTIPLIER)

# --- Audio Control ---
def get_mic_volume_control():
    try:
        devices = AudioUtilities.GetMicrophone()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except: return None

def set_mic_volume(level):
    vol = get_mic_volume_control()
    if vol: vol.SetMasterVolumeLevelScalar(level, None)

def get_current_mic_volume():
    vol = get_mic_volume_control()
    return vol.GetMasterVolumeLevelScalar() if vol else 1.0

# --- Speech ---
pygame.mixer.init()
voice_channel = pygame.mixer.Channel(0)

async def _async_speak(text):
    temp_file = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4().hex}.mp3")
    try:
        comm = edge_tts.Communicate(text, "en-US-ChristopherNeural")
        await comm.save(temp_file)
        sound = pygame.mixer.Sound(temp_file)
        voice_channel.play(sound)
        while voice_channel.get_busy(): pygame.time.Clock().tick(10)
    finally:
        if os.path.exists(temp_file):
            try: os.remove(temp_file)
            except: pass

def speak(text):
    print(f"Assistant: {text}")
    asyncio.run(_async_speak(text))

# --- Detection Logic ---
def get_rms(block):
    count = len(block) / 2
    shorts = struct.unpack("%dh" % count, block)
    sum_squares = sum((s * (1.0/32768.0))**2 for s in shorts)
    rms = math.sqrt(sum_squares / count) * 1000
    dynamic_t = get_dynamic_threshold()
    if rms < dynamic_t:
        ambient_noise_history.append(rms)
        if len(ambient_noise_history) > 30: ambient_noise_history.pop(0)
    if rms > 1.5: 
        print(f"Level: {rms:.1f} (Floor: {sum(ambient_noise_history)/len(ambient_noise_history):.1f} | Trigger: {dynamic_t:.1f})", end="\r")
    return rms

def listen_for_claps(count_needed, timeout=2.0):
    claps = 0
    start = time.time()
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    last_clap = 0
    while time.time() - start < timeout:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = get_rms(data)
            if rms > get_dynamic_threshold() and (time.time() - last_clap) > 0.3:
                claps += 1
                last_clap = time.time()
                print(f"\n[!] Clap {claps}/{count_needed}")
                if claps >= count_needed:
                    stream.stop_stream(); stream.close(); p.terminate()
                    return True
        except: break
    stream.stop_stream(); stream.close(); p.terminate()
    return False

def listen_for_voice(prompt_msg, timeout=5.0):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print(f"\n[Voice Mode] {prompt_msg}...")
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=4)
            return recognizer.recognize_google(audio).lower()
        except: return ""

# --- Launcher Automation Helper ---
def click_launcher_play_button():
    """Waits for SKLauncher window to appear, then clicks the blue Play button."""
    print("Waiting for SKLauncher window to appear (up to 30s)...")
    start_wait = time.time()
    win = None
    
    while time.time() - start_wait < 30:
        skl_windows = [w for w in gw.getWindowsWithTitle('SKLauncher')]
        if skl_windows:
            win = skl_windows[0]
            break
        time.sleep(1)
    
    if win:
        try:
            print(f"Launcher found: {win.title}. Finalizing boot...")
            time.sleep(2) # Final small buffer for internal loading
            
            # Programmatic Alt+Tab
            win.activate()
            if win.isMinimized: win.restore()
            time.sleep(1)
            
            # 1. Close Error Popup (Enter)
            pyautogui.press('enter')
            time.sleep(0.5)
            
            # 2. Click Blue Play Button
            click_x = win.left + 140
            click_y = win.top + win.height - 65
            print(f"Clicking play button at {click_x}, {click_y}...")
            pyautogui.moveTo(click_x, click_y, duration=0.5)
            pyautogui.click()
            return True
        except Exception as e:
            print(f"Error clicking button: {e}")
            pyautogui.press('enter')
    else:
        print("Launcher window never appeared.")
    return False

def execute_task(command):
    print(f"Executing Task: {command}")
    
    if "minecraft folder" in command:
        speak("Opening Minecraft folder.")
        os.startfile(os.path.expandvars(r"%appdata%\.minecraft"))

    elif "mod folder" in command or "mods folder" in command:
        speak("Opening mods folder.")
        os.startfile(os.path.expandvars(r"%appdata%\.minecraft\mods"))

    elif "youtube" in command:
        speak("Opening YouTube.")
        webbrowser.open("https://www.youtube.com")
        
    elif "discord" in command:
        speak("Opening Discord.")
        pyautogui.press('win'); time.sleep(0.5)
        pyautogui.write('discord'); pyautogui.press('enter')
        
    elif "minecraft" in command:
        speak("Launching Minecraft.")
        pyautogui.hotkey('win', 'd'); time.sleep(0.5)
        pyautogui.press('win'); time.sleep(0.5)
        pyautogui.write('skl'); pyautogui.press('enter')
        click_launcher_play_button()
        speak("Game starting.")
            
    elif "i am free" in command:
        speak("Welcome sir. Setting up your session.")
        pyautogui.hotkey('win', 'd'); time.sleep(1)
        # Discord
        pyautogui.press('win'); time.sleep(0.5); pyautogui.write('discord'); pyautogui.press('enter')
        time.sleep(2)
        # Minecraft
        pyautogui.press('win'); time.sleep(0.5); pyautogui.write('skl'); pyautogui.press('enter')
        click_launcher_play_button()
        speak("Setup complete.")

    elif "terminate" in command:
        speak("Terminating. Goodbye.")
        os._exit(0)

    elif "rickroll" in command:
        speak("Executing surprise.")
        pyautogui.hotkey('win', 'r'); time.sleep(0.5)
        pyautogui.write('https://www.youtube.com/watch?v=dQw4w9WgXcQ'); pyautogui.press('enter')
    else:
        speak("Command not recognized.")

def main():
    orig_vol = get_current_mic_volume()
    set_mic_volume(0.50)
    print("\n--- ASSISTANT READY ---")
    print("Action: Double-clap to give a command.")
    
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    try:
        last_clap = 0
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = get_rms(data)
            
            if rms > get_dynamic_threshold() and (time.time() - last_clap) > 0.4:
                last_clap = time.time()
                
                # Double clap trigger
                if listen_for_claps(1, timeout=0.8):
                    stream.stop_stream()
                    print("\n[Listening...]")
                    cmd = listen_for_voice("Speak your command", timeout=7.0)
                    if cmd:
                        execute_task(cmd)
                    stream.start_stream()
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        set_mic_volume(orig_vol)
        if 'stream' in locals(): stream.close()
        p.terminate()

if __name__ == "__main__":
    main()
