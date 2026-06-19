/**
 * JARVIS WebUI — main.js
 * WebSocket state machine + Canvas core animator + Console manager
 * Handles: WS connection/reconnect, state transitions, command submission,
 *          LLM streaming, settings API calls, snapshot refresh.
 */

"use strict";

// ── State machine ────────────────────────────────────────────────────────────

const State = Object.freeze({
  IDLE:       "IDLE",
  LISTENING:  "LISTENING",
  PROCESSING: "PROCESSING",
  SPEAKING:   "SPEAKING",
});

let _currentState = State.IDLE;
let _animFrame    = null;

// Session stats
let _commandCount = 0;
let _llmCount     = 0;
let _sessionStart = Date.now();

// ── Clock ─────────────────────────────────────────────────────────────────────

function tickClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2,"0");
  const m = String(now.getMinutes()).padStart(2,"0");
  const s = String(now.getSeconds()).padStart(2,"0");
  document.getElementById("clock").textContent = `${h}:${m}:${s}`;
}
setInterval(tickClock, 1000);
tickClock();

// ── Uptime ticker ─────────────────────────────────────────────────────────────

function updateUptime() {
  const elapsed = Math.floor((Date.now() - _sessionStart) / 1000);
  const mm = String(Math.floor(elapsed / 60)).padStart(2,"0");
  const ss = String(elapsed % 60).padStart(2,"0");
  const el = document.getElementById("stat-uptime");
  if (el) el.textContent = `${mm}:${ss}`;
}
setInterval(updateUptime, 1000);

// ── State transition ─────────────────────────────────────────────────────────

function setState(state, speakText = "") {
  _currentState = state;

  const badge  = document.getElementById("state-badge");
  const label  = document.getElementById("core-label");
  const cLabel = document.getElementById("core-label");

  const MAP = {
    [State.IDLE]:       { text: "STANDBY",    cls: "",           badge: "IDLE" },
    [State.LISTENING]:  { text: "LISTENING",  cls: "listening",  badge: "LISTENING" },
    [State.PROCESSING]: { text: "PROCESSING", cls: "processing", badge: "PROCESSING" },
    [State.SPEAKING]:   { text: "SPEAKING",   cls: "speaking",   badge: "SPEAKING" },
  };

  const cfg = MAP[state] || MAP[State.IDLE];

  if (badge) {
    badge.textContent = cfg.badge;
    badge.className   = `state-badge ${cfg.cls}`;
  }
  if (cLabel) {
    cLabel.textContent = speakText && state === State.SPEAKING
      ? speakText.slice(0, 28) + (speakText.length > 28 ? "…" : "")
      : cfg.text;
  }
}

// ── Canvas Core Renderer ─────────────────────────────────────────────────────

const canvas  = document.getElementById("core-canvas");
const ctx     = canvas ? canvas.getContext("2d") : null;
let   _phi    = 0;   // rotation phase
let   _pulse  = 0;   // pulse phase

const PALETTE = {
  idle:       { ring: "#00c8ff", arc: "#0077aa",  core: "#003355", glow: "rgba(0,200,255,0.35)" },
  listening:  { ring: "#00ff9d", arc: "#00aa6a",  core: "#003322", glow: "rgba(0,255,157,0.40)" },
  processing: { ring: "#a78bfa", arc: "#7c3aed",  core: "#1a0040", glow: "rgba(124,58,237,0.45)" },
  speaking:   { ring: "#f59e0b", arc: "#b45309",  core: "#2a1500", glow: "rgba(245,158,11,0.40)" },
};

function stateKey() {
  return _currentState.toLowerCase() in PALETTE
    ? _currentState.toLowerCase()
    : "idle";
}

function lerp(a, b, t) { return a + (b - a) * t; }

function drawCore(ts) {
  if (!ctx) return;
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;
  const pal = PALETTE[stateKey()];
  const t   = ts * 0.001;

  _phi   += 0.012;
  _pulse  = Math.sin(t * 2.0) * 0.5 + 0.5;

  ctx.clearRect(0, 0, W, H);

  // Outer glow aura
  const auraR = 150 + _pulse * 8;
  const aura  = ctx.createRadialGradient(cx, cy, 60, cx, cy, auraR);
  aura.addColorStop(0, pal.glow.replace("0.35","0.18").replace("0.40","0.20").replace("0.45","0.22").replace("0.40","0.18"));
  aura.addColorStop(1, "transparent");
  ctx.fillStyle = aura;
  ctx.beginPath();
  ctx.arc(cx, cy, auraR, 0, Math.PI * 2);
  ctx.fill();

  // Rings (static + spinning arcs)
  const rings = _currentState === State.PROCESSING
    ? [
        { r: 130, lw: 1.5, alpha: 0.25, dash: [4,8],   spin: 1 },
        { r: 110, lw: 2.5, alpha: 0.50, dash: [12,6],  spin: -1.4 },
        { r:  90, lw: 1.5, alpha: 0.35, dash: [3,10],  spin: 1.8 },
        { r:  70, lw: 3.0, alpha: 0.65, dash: [20,8],  spin: -0.9 },
      ]
    : _currentState === State.LISTENING
    ? [
        { r: 132 + _pulse * 10, lw: 2, alpha: 0.30 + _pulse * 0.3, dash: [],       spin: 0.3 },
        { r: 108,               lw: 2, alpha: 0.55,                 dash: [8,6],    spin: -0.5 },
        { r:  82,               lw: 3, alpha: 0.70 + _pulse * 0.3,  dash: [],       spin: 0.2 },
      ]
    : _currentState === State.SPEAKING
    ? [
        { r: 128 + Math.sin(t * 8) * 8, lw: 2,   alpha: 0.45, dash: [],      spin: 0.2 },
        { r: 100 + Math.sin(t * 6) * 6, lw: 2.5, alpha: 0.55, dash: [6,4],   spin: -0.3 },
        { r:  76 + Math.sin(t * 10) * 4,lw: 3,   alpha: 0.65, dash: [],      spin: 0.15 },
      ]
    : [
        { r: 130, lw: 1,   alpha: 0.20, dash: [6,12], spin: 0.15 },
        { r: 106, lw: 1.5, alpha: 0.30, dash: [],     spin: -0.1 },
        { r:  80, lw: 2,   alpha: 0.45, dash: [],     spin: 0.08 },
      ];

  rings.forEach(ring => {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(_phi * ring.spin);
    ctx.strokeStyle = pal.ring;
    ctx.globalAlpha = ring.alpha;
    ctx.lineWidth   = ring.lw;
    if (ring.dash.length) ctx.setLineDash(ring.dash);
    ctx.beginPath();
    ctx.arc(0, 0, ring.r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
  });

  // Hex core background
  ctx.save();
  ctx.globalAlpha = 0.8;
  const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 48);
  coreGrad.addColorStop(0, pal.core);
  coreGrad.addColorStop(1, "rgba(0,0,0,0.6)");
  ctx.fillStyle = coreGrad;
  _hexPath(ctx, cx, cy, 48, _phi * 0.5);
  ctx.fill();
  ctx.strokeStyle = pal.arc;
  ctx.lineWidth = 1.5;
  ctx.globalAlpha = 0.6;
  ctx.stroke();
  ctx.restore();

  // Inner spinning arc accent
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-_phi * 2);
  ctx.globalAlpha = 0.8;
  ctx.strokeStyle = pal.arc;
  ctx.lineWidth   = 3;
  ctx.beginPath();
  ctx.arc(0, 0, 55, 0, Math.PI * 1.2);
  ctx.stroke();
  ctx.restore();

  // Center dot
  const dotGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 14);
  dotGrad.addColorStop(0, "#ffffff");
  dotGrad.addColorStop(0.4, pal.ring);
  dotGrad.addColorStop(1, "transparent");
  ctx.globalAlpha = 0.9;
  ctx.fillStyle = dotGrad;
  ctx.beginPath();
  ctx.arc(cx, cy, 14, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;

  // Waveform bars during SPEAKING
  if (_currentState === State.SPEAKING) {
    const bars = 16;
    for (let i = 0; i < bars; i++) {
      const angle  = (i / bars) * Math.PI * 2;
      const barH   = 12 + Math.abs(Math.sin(t * 8 + i * 0.8)) * 22;
      const x1 = cx + Math.cos(angle) * 60;
      const y1 = cy + Math.sin(angle) * 60;
      const x2 = cx + Math.cos(angle) * (60 + barH);
      const y2 = cy + Math.sin(angle) * (60 + barH);
      ctx.globalAlpha = 0.65;
      ctx.strokeStyle = pal.ring;
      ctx.lineWidth   = 2.5;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  _animFrame = requestAnimationFrame(drawCore);
}

function _hexPath(ctx, cx, cy, r, rot) {
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const a = rot + (i / 6) * Math.PI * 2;
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath();
}

if (ctx) _animFrame = requestAnimationFrame(drawCore);

// ── Console Manager ──────────────────────────────────────────────────────────

const consoleOutput = document.getElementById("console-output");
let _llmBuffer = "";
let _llmEntry  = null;

function ts() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}:${String(now.getSeconds()).padStart(2,"0")}`;
}

function appendLog(type, text, badge = "") {
  if (!consoleOutput) return;
  const entry = document.createElement("div");
  entry.className = `log-entry ${type}`;

  const tsEl = document.createElement("span");
  tsEl.className = "log-ts";
  tsEl.textContent = ts();

  const textEl = document.createElement("span");
  textEl.className = "log-text";
  if (badge) {
    const b = document.createElement("span");
    b.className = `mode-badge ${badge}`;
    b.textContent = badge.replace("mode-","").toUpperCase();
    textEl.appendChild(b);
  }
  textEl.appendChild(document.createTextNode(text));

  entry.appendChild(tsEl);
  entry.appendChild(textEl);
  consoleOutput.appendChild(entry);
  consoleOutput.scrollTop = consoleOutput.scrollHeight;
  return entry;
}

function appendSystem(text) { appendLog("system", text); }

function startLLMStream() {
  _llmBuffer = "";
  _llmEntry  = appendLog("llm", "");
}

function appendLLMChunk(chunk) {
  if (!_llmEntry) startLLMStream();
  _llmBuffer += chunk;
  const textEl = _llmEntry.querySelector(".log-text");
  if (textEl) textEl.textContent = _llmBuffer;
  consoleOutput.scrollTop = consoleOutput.scrollHeight;

  // Show toast
  const toast = document.getElementById("llm-toast");
  if (toast) {
    toast.style.display = "block";
    toast.textContent   = _llmBuffer.slice(-120);
  }
}

function endLLMStream() {
  _llmEntry = null;
  _llmBuffer = "";
  const toast = document.getElementById("llm-toast");
  if (toast) setTimeout(() => { toast.style.display = "none"; }, 2000);
}

// ── WebSocket ────────────────────────────────────────────────────────────────

let _ws = null;
let _reconnectDelay = 1000;

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  _ws = new WebSocket(`${proto}://${location.host}/ws`);

  _ws.onopen = () => {
    _reconnectDelay = 1000;
    const pill = document.getElementById("pill-ws");
    if (pill) pill.classList.add("active");
    appendSystem("WebSocket connected.");
    loadStatus();
  };

  _ws.onclose = () => {
    const pill = document.getElementById("pill-ws");
    if (pill) { pill.classList.remove("active"); pill.classList.add("error"); }
    appendSystem("Connection lost. Reconnecting...");
    setTimeout(connectWS, _reconnectDelay);
    _reconnectDelay = Math.min(_reconnectDelay * 2, 16000);
  };

  _ws.onerror = () => {};

  _ws.onmessage = (ev) => {
    let data;
    try { data = JSON.parse(ev.data); } catch { return; }
    handleServerEvent(data);
  };
}

function handleServerEvent(data) {
  // State transition
  if (data.state) {
    const s = data.state.toUpperCase();
    setState(s, data.text || "");

    if (s === State.SPEAKING && data.text) {
      appendLog("assistant", data.text);
    }
    if (s === State.IDLE) {
      endLLMStream();
    }
  }

  // Events
  switch (data.event) {
    case "user_input":
      appendLog("user", data.text, data.mode === "VOICE" ? "mode-voice" : "mode-text");
      _commandCount++;
      document.getElementById("stat-commands").textContent = _commandCount;
      break;

    case "stt_result":
      appendLog("stt", data.text);
      break;

    case "llm_chunk":
      if (!_llmEntry) {
        _llmCount++;
        document.getElementById("stat-llm").textContent = _llmCount;
        startLLMStream();
      }
      appendLLMChunk(data.text);
      break;

    case "snapshot_ready":
      refreshSnapshot(data.url);
      if (data.caption) {
        document.getElementById("snapshot-caption").textContent = data.caption;
        appendLog("system", "📷 Vision: " + data.caption);
      }
      break;
  }
}

// ── Command submission ───────────────────────────────────────────────────────

async function sendCommand(text) {
  if (!text.trim()) return;
  appendLog("user", text, "mode-text");
  _commandCount++;
  document.getElementById("stat-commands").textContent = _commandCount;

  try {
    const res = await fetch("/api/command", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ command: text }),
    });
    if (!res.ok) {
      const err = await res.json();
      appendSystem(`Error: ${err.error || res.statusText}`);
    }
  } catch (e) {
    appendSystem(`Network error: ${e.message}`);
  }
}

// ── Input bar events ─────────────────────────────────────────────────────────

const cmdInput = document.getElementById("command-input");
const btnSend  = document.getElementById("btn-send");

if (cmdInput) {
  cmdInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const val = cmdInput.value.trim();
      cmdInput.value = "";
      if (val) sendCommand(val);
    }
  });
}

if (btnSend) {
  btnSend.addEventListener("click", () => {
    const val = cmdInput ? cmdInput.value.trim() : "";
    if (cmdInput) cmdInput.value = "";
    if (val) sendCommand(val);
  });
}

// Clear console
const btnClear = document.getElementById("btn-clear");
if (btnClear) {
  btnClear.addEventListener("click", () => {
    if (consoleOutput) consoleOutput.innerHTML = "";
    appendSystem("Console cleared.");
  });
}

// Export log
const btnExport = document.getElementById("btn-export");
if (btnExport) {
  btnExport.addEventListener("click", () => {
    const entries = Array.from(document.querySelectorAll(".log-entry")).map(e => {
      const ts   = e.querySelector(".log-ts")?.textContent || "";
      const text = e.querySelector(".log-text")?.textContent || "";
      return `[${ts}] ${text}`;
    });
    const blob = new Blob([entries.join("\n")], { type: "text/plain" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = `jarvis_session_${Date.now()}.txt`; a.click();
    URL.revokeObjectURL(url);
  });
}

// Snapshot button
const btnSnap = document.getElementById("btn-snapshot");
if (btnSnap) {
  btnSnap.addEventListener("click", () => {
    sendCommand("take a snapshot");
  });
}

// ── Settings Modal ───────────────────────────────────────────────────────────

const modalBackdrop = document.getElementById("modal-backdrop");
const btnSettings   = document.getElementById("btn-settings");
const btnClose      = document.getElementById("modal-close");

if (btnSettings) btnSettings.addEventListener("click", () => { if (modalBackdrop) modalBackdrop.style.display = "flex"; });
if (btnClose)    btnClose.addEventListener("click",    () => { if (modalBackdrop) modalBackdrop.style.display = "none"; });
if (modalBackdrop) {
  modalBackdrop.addEventListener("click", (e) => {
    if (e.target === modalBackdrop) modalBackdrop.style.display = "none";
  });
}

function showFeedback(elId, msg) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = msg;
  el.classList.add("visible");
  setTimeout(() => el.classList.remove("visible"), 3000);
}

async function postSettings(url, body) {
  const res = await fetch(url, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  });
  return res.ok;
}

// Save API key
const btnSaveKey = document.getElementById("btn-save-key");
if (btnSaveKey) {
  btnSaveKey.addEventListener("click", async () => {
    const provider = document.getElementById("key-provider")?.value || "gemini";
    const key      = document.getElementById("key-input")?.value?.trim();
    if (!key) { showFeedback("key-feedback", "⚠ Key cannot be empty"); return; }
    const ok = await postSettings("/api/settings/key", { provider, key });
    showFeedback("key-feedback", ok ? "✓ Key saved" : "✗ Save failed");
    if (ok) {
      document.getElementById("key-input").value = "";
      const pill = document.getElementById("pill-llm");
      if (pill) pill.classList.add("active");
    }
  });
}

// Save voice
const btnSaveVoice = document.getElementById("btn-save-voice");
if (btnSaveVoice) {
  btnSaveVoice.addEventListener("click", async () => {
    const voice = document.getElementById("voice-select")?.value;
    const ok = await postSettings("/api/settings/config", { voice });
    showFeedback("voice-feedback", ok ? "✓ Voice updated" : "✗ Failed");
  });
}

// Save city
const btnSaveCity = document.getElementById("btn-save-city");
if (btnSaveCity) {
  btnSaveCity.addEventListener("click", async () => {
    const city = document.getElementById("city-input")?.value?.trim();
    if (!city) return;
    const ok = await postSettings("/api/settings/config", { weather_city: city });
    showFeedback("city-feedback", ok ? "✓ City saved" : "✗ Failed");
  });
}

// Save LLM model
const btnSaveModel = document.getElementById("btn-save-model");
if (btnSaveModel) {
  btnSaveModel.addEventListener("click", async () => {
    const model = document.getElementById("llm-model")?.value;
    const ok = await postSettings("/api/settings/config", { llm_model: model });
    showFeedback("model-feedback", ok ? "✓ Model updated" : "✗ Failed");
  });
}

// ── Status loader (skills) ────────────────────────────────────────────────────

async function loadStatus() {
  try {
    const res  = await fetch("/api/status");
    const data = await res.json();
    const chips = document.getElementById("skill-chips");
    if (chips && data.skills) {
      chips.innerHTML = "";
      data.skills.forEach(sk => {
        const c = document.createElement("div");
        c.className = "skill-chip";
        c.textContent = sk.name.toUpperCase();
        c.title = sk.description;
        chips.appendChild(c);
      });
    }
    // Indicate LLM pill if key exists
    // (We do not expose the key, server just checks)
    if (data.state) setState(data.state);
    appendSystem(`Loaded ${(data.skills || []).length} skills.`);
  } catch (e) {
    appendSystem("Could not load status.");
  }
}

// ── Snapshot refresh ─────────────────────────────────────────────────────────

function refreshSnapshot(url) {
  const img         = document.getElementById("snapshot-img");
  const placeholder = document.getElementById("snapshot-placeholder");
  if (img && placeholder) {
    img.src = url + "?t=" + Date.now();
    img.style.display = "block";
    placeholder.style.display = "none";
  }
}

async function checkSnapshot() {
  try {
    const res  = await fetch("/api/snapshot");
    const data = await res.json();
    if (data.available) refreshSnapshot(data.url);
  } catch {}
}
checkSnapshot();

// ── Boot ─────────────────────────────────────────────────────────────────────

appendSystem("Jarvis Web Interface v2.0 — Hybrid AI Mode");
appendSystem("Use double-clap for voice commands, or type below.");
appendSystem("Open ⚙ Settings to configure your Gemini API key.");
connectWS();
