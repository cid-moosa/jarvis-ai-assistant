"""
core/server.py
==============
Flask + Flask-Sock web server running as a background daemon thread.
Serves the WebUI and provides API endpoints for command submission,
API key registration, and real-time WebSocket state streaming.

Broadcast architecture (fan-out via per-client queues):
  broadcast(payload) -> pushes to every connected client's individual queue
  websocket_handler  -> each client drains its own queue and sends JSON
"""
import json
import os
import queue
import threading
import time
import asyncio
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sock import Sock
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List
from core.enhancer import PromptEnhancer

# ── App setup ─────────────────────────────────────────────────────────────────

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_web_dir  = os.path.join(_base_dir, "web")

app = Flask(
    __name__,
    template_folder=os.path.join(_web_dir, "templates"),
    static_folder=os.path.join(_web_dir, "static"),
    static_url_path="/static",
)
sock = Sock(app)

# ── Shared state ──────────────────────────────────────────────────────────────

# Each connected client gets its own queue; broadcast() fans out to all of them.
_client_queues: dict = {}   # ws_id -> queue.Queue
_clients_lock  = threading.Lock()
_config: dict  = {}
_current_state: str = "IDLE"
_id_counter    = 0


def _new_client_id() -> int:
    global _id_counter
    with _clients_lock:
        _id_counter += 1
        return _id_counter


def setup(config: dict):
    global _config
    _config = config


def broadcast(payload: dict):
    """
    Fan-out a JSON payload to every active WebSocket client (thread-safe).
    Also tracks current state for new-client initial sync.
    """
    global _current_state
    if "state" in payload:
        _current_state = payload["state"]
    with _clients_lock:
        for q in _client_queues.values():
            q.put_nowait(payload)


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@sock.route("/ws")
def websocket_handler(ws):
    """
    Each client gets its own queue. The handler:
      1. Drains the queue and sends to this client.
      2. Also reads any messages from the client (direct WS command entry).
    """
    cid = _new_client_id()
    my_queue: queue.Queue = queue.Queue()

    with _clients_lock:
        _client_queues[cid] = my_queue

    # Send initial state immediately on connect
    try:
        ws.send(json.dumps({"state": _current_state}))
    except Exception:
        pass

    try:
        while True:
            # ── Receive from client (non-blocking) ──
            try:
                msg = ws.receive(timeout=0.04)
                if msg:
                    try:
                        data = json.loads(msg)
                        if data.get("type") == "command":
                            _enqueue_command(data.get("text", ""), "TEXT")
                    except Exception:
                        pass
            except Exception:
                pass  # receive timeout is normal

            # ── Send queued payloads to this client ──
            drained = 0
            while drained < 20:   # drain up to 20 at a time per tick
                try:
                    payload = my_queue.get_nowait()
                    ws.send(json.dumps(payload))
                    drained += 1
                except queue.Empty:
                    break
                except Exception:
                    # Client disconnected mid-send
                    return

    except Exception:
        pass
    finally:
        with _clients_lock:
            _client_queues.pop(cid, None)


# ── HTTP Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", config=_config)


@app.route("/static/img/<path:filename>")
def static_img(filename):
    img_dir = os.path.join(_web_dir, "static", "img")
    os.makedirs(img_dir, exist_ok=True)
    return send_from_directory(img_dir, filename)


@app.route("/api/command", methods=["POST"])
def api_command():
    """Accept a typed command from the WebUI text box."""
    data = request.get_json(silent=True) or {}
    command = (data.get("command") or "").strip()
    if not command:
        return jsonify({"error": "empty command"}), 400
    _enqueue_command(command, "TEXT")
    broadcast({"event": "user_input", "text": command, "mode": "TEXT"})
    return jsonify({"status": "queued", "command": command})


@app.route("/api/settings/key", methods=["POST"])
def api_settings_key():
    """Save an API key for a given provider into memory.json."""
    data = request.get_json(silent=True) or {}
    provider = (data.get("provider") or "gemini").strip().lower()
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "key must not be empty"}), 400
    try:
        from core import memory
        memory.set_api_key(provider, key)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": "saved", "provider": provider})


@app.route("/api/settings/config", methods=["POST"])
def api_settings_config():
    """Update a runtime config key (voice, weather_city, etc.)."""
    data = request.get_json(silent=True) or {}
    allowed = {"voice", "weather_city", "llm_model", "web_open_browser"}
    updated = {}
    for k, v in data.items():
        if k in allowed:
            _config[k] = v
            updated[k] = v
    return jsonify({"status": "updated", "keys": updated})


@app.route("/api/status", methods=["GET"])
def api_status():
    """Return current Jarvis state and loaded skill list."""
    from core import intent as _intent
    skills = [{"name": s.name, "description": s.description} for s in _intent._registry]
    return jsonify({
        "state": _current_state,
        "skills": skills,
        "config": {k: v for k, v in _config.items() if "key" not in k.lower()},
    })


@app.route("/api/snapshot", methods=["GET"])
def api_snapshot():
    """Return the latest camera snapshot metadata if available."""
    img_path = os.path.join(_web_dir, "static", "img", "snapshot.jpg")
    if os.path.exists(img_path):
        mtime = os.path.getmtime(img_path)
        return jsonify({"available": True, "url": "/static/img/snapshot.jpg", "mtime": mtime})
    return jsonify({"available": False})


# ── Command queue bridge ───────────────────────────────────────────────────────

def _enqueue_command(command: str, mode: str):
    """Put a command into the engine text-worker queue."""
    try:
        from core import engine
        engine.get_command_queue().put((command, mode))
    except Exception:
        pass


def _stats_daemon():
    """Periodically fetches CPU, RAM, disk, and network stats, and broadcasts to WebUI."""
    import psutil
    import time
    
    # Initialize CPU measurement
    try:
        psutil.cpu_percent(interval=None)
    except Exception:
        pass
        
    last_net = None
    try:
        last_net = psutil.net_io_counters()
    except Exception:
        pass
        
    last_time = time.time()
    
    while True:
        time.sleep(1.0)
        try:
            # CPU
            try:
                cpu = psutil.cpu_percent(interval=None)
            except Exception:
                cpu = 0.0
            
            # RAM
            try:
                vm = psutil.virtual_memory()
                ram = vm.percent
            except Exception:
                ram = 0.0
            
            # Disk
            try:
                disk = psutil.disk_usage("/").percent
            except Exception:
                try:
                    # Fallback for Windows drives
                    disk = psutil.disk_usage(os.getcwd()[:3]).percent
                except Exception:
                    disk = 0.0
                    
            # Network speeds
            net_in = 0.0
            net_out = 0.0
            try:
                now_net = psutil.net_io_counters()
                now_time = time.time()
                if last_net is not None:
                    dt = max(now_time - last_time, 0.1)
                    bytes_sent = now_net.bytes_sent - last_net.bytes_sent
                    bytes_recv = now_net.bytes_recv - last_net.bytes_recv
                    net_out = round((bytes_sent / 1024) / dt, 1)
                    net_in = round((bytes_recv / 1024) / dt, 1)
                last_net = now_net
                last_time = now_time
            except Exception:
                pass
            
            # Broadcast to all clients
            broadcast({
                "event": "sys_stats",
                "cpu": cpu,
                "ram": ram,
                "disk": disk,
                "net_in": net_in,
                "net_out": net_out
            })
        except Exception:
            pass
class EnhanceRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    detail_level: str = Field("detailed", pattern="^(detailed|concise)$")
    tone: str = Field("professional")
    use_llm: bool = Field(True)
    api_key: Optional[str] = Field(None)
    archetype: str = Field("general", pattern="^(general|developer_agent|tui_assistant)$")
    include_rules: Optional[List[str]] = Field(default=None)
    tools_list: Optional[List[str]] = Field(default=None)

# Initialize PromptEnhancer
enhancer = PromptEnhancer()

@app.route("/api/enhance", methods=["POST"])
def api_enhance():
    """Accept raw prompt and options, returning optimized prompt."""
    data = request.get_json(silent=True) or {}
    try:
        req = EnhanceRequest(**data)
    except ValidationError as err:
        return jsonify({"error": err.errors()}), 422

    # Instantiate or load key
    if req.api_key:
        active_enhancer = PromptEnhancer(api_key=req.api_key)
    else:
        active_enhancer = PromptEnhancer()

    # Run the coroutine synchronously in an event loop
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(active_enhancer.enhance(
            prompt=req.prompt,
            detail_level=req.detail_level,
            tone=req.tone,
            use_llm=req.use_llm,
            archetype=req.archetype,
            include_rules=req.include_rules,
            tools_list=req.tools_list
        ))
    finally:
        loop.close()

    return jsonify(result)


# ── Server daemon startup ──────────────────────────────────────────────────────

def start(config: dict):
    """Start the Flask server in a background daemon thread."""
    setup(config)
    host = config.get("web_host", "127.0.0.1")
    port = int(config.get("web_port", 5000))
    open_browser = config.get("web_open_browser", True)

    def _run():
        import logging as _logging
        _logging.getLogger("werkzeug").setLevel(_logging.ERROR)
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)

    t = threading.Thread(target=_run, daemon=True, name="WebServer")
    t.start()

    # Start stats daemon
    ts = threading.Thread(target=_stats_daemon, daemon=True, name="StatsDaemon")
    ts.start()

    # Give the server a moment to bind to the port
    time.sleep(1.2)

    if open_browser:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}")

    from core import logger as log_mod
    try:
        log = log_mod.get()
        log.info(f"Web UI running at http://{host}:{port}")
    except Exception:
        print(f"[Jarvis] Web UI at http://{host}:{port}")