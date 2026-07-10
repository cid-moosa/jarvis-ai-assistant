# Jarvis v2.0 — Hybrid Local AI Voice & Text Assistant

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-windows-lightgrey.svg)

Jarvis is a hybrid AI voice and text assistant running as a local Windows daemon, featuring a sci-fi glassmorphic WebUI, RapidFuzz-based local skill routing, and a Gemini LLM fallback engine.

---

## Features

- **Double-Clap Trigger**: Hands-free voice activation using adaptive ambient noise floor detection.
- **Sci-Fi WebUI & Console**: Beautiful glassmorphic dashboard built with real-time canvas animations, system stats monitor, and command console.
- **Hybrid Skill Pipeline**: High-speed local intent classifier (RapidFuzz) for calculator, media controls, notes, system info, weather, and camera, with automatic Gemini/LLM fallback for conversational queries.
- **Dual TTS Mode**: Premium Microsoft Edge TTS cloud voices with local SAPI5 offline fallback.
- **OpenCV Vision Fallback**: Heuristic environment analysis (brightness & edge-density) if Gemini API key is unavailable.
- **Windows Defender Mitigation**: Local data (memory, logs, conversations) are saved to `%APPDATA%\Jarvis` instead of the project directory to prevent file lock issues caused by Controlled Folder Access.

---

## Tech Stack

- **Backend**: Python 3.12, Flask, Flask-Sock (WebSocket), PyAudio, SpeechRecognition, `edge-tts`, `pyttsx3`, `rapidfuzz`, `google-generativeai`, OpenCV, `psutil`.
- **Frontend**: HTML5, Vanilla CSS3 (Glassmorphism), Vanilla JavaScript (Canvas visualizer).

---

## Quickstart

### Prerequisites
- Python 3.12+ installed on Windows.
- A microphone and webcam (optional, for camera skills).
- A Gemini API Key (for conversational fallback).

### Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/cid-moosa/jarvis-ai-assistant.git
   cd jarvis-ai-assistant
   ```

2. **Set up a virtual environment**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration**:
   - Customize identity, microphone volume, clap detection, and weather city in [config.yaml](file:///c:/Users/CIDMOOSA/Documents/gemini%20cli/config.yaml).
   - Enter your Gemini API key in the WebUI Settings modal or set the environment variable:
     ```cmd
     set GEMINI_API_KEY=your_gemini_api_key_here
     ```

### Running Jarvis

Run the startup batch script:
```cmd
run_jarvis.bat
```
Or run directly:
```bash
python main.py
```
This will start the local daemon and automatically open the interactive WebUI at `http://127.0.0.1:5000`.

---

## License

This project is licensed under the MIT License.

---

## Author

Created by [cid-moosa](https://github.com/cid-moosa).
