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

const _particles = [];
const MAX_PARTICLES = 110;

function initParticles() {
  if (!canvas) return;
  _particles.length = 0;
  for (let i = 0; i < MAX_PARTICLES; i++) {
    // Generate particles uniformly on a 3D sphere shell
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos((Math.random() * 2) - 1);
    const radius = 60 + Math.random() * 40; // Shell thickness
    
    _particles.push({
      x: Math.sin(phi) * Math.cos(theta) * radius,
      y: Math.sin(phi) * Math.sin(theta) * radius,
      z: Math.cos(phi) * radius,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      vz: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 1.5 + 0.8,
      alpha: Math.random() * 0.5 + 0.35,
      phase: Math.random() * Math.PI * 2,
      baseRadius: radius
    });
  }
}

function drawParticles(cx, cy, pal, t) {
  if (_particles.length === 0) initParticles();

  // 1. Calculate 3D rotations based on time to spin the whole sphere
  const rotSpeedY = t * 0.15;
  const rotSpeedX = Math.sin(t * 0.08) * 0.25;

  const cosY = Math.cos(rotSpeedY), sinY = Math.sin(rotSpeedY);
  const cosX = Math.cos(rotSpeedX), sinX = Math.sin(rotSpeedX);

  const projected = [];

  _particles.forEach((p, idx) => {
    let px = p.x;
    let py = p.y;
    let pz = p.z;

    // Update coordinates based on current state
    if (_currentState === State.PROCESSING) {
      // In PROCESSING, spiral the particles inward toward the core (radius -> 0)
      const currentRadius = Math.sqrt(px * px + py * py + pz * pz);
      if (currentRadius < 8) {
        // Respawn at outer edge of sphere shell
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos((Math.random() * 2) - 1);
        const radius = 100 + Math.random() * 30;
        p.x = Math.sin(phi) * Math.cos(theta) * radius;
        p.y = Math.sin(phi) * Math.sin(theta) * radius;
        p.z = Math.cos(phi) * radius;
      } else {
        // Drag inward and add rotation velocity
        const dragFactor = 0.94;
        p.x *= dragFactor;
        p.y *= dragFactor;
        p.z *= dragFactor;
        // Small orbital swirl
        const swirlSpeed = 0.05;
        const tempX = p.x;
        p.x = tempX * Math.cos(swirlSpeed) - p.y * Math.sin(swirlSpeed);
        p.y = tempX * Math.sin(swirlSpeed) + p.y * Math.cos(swirlSpeed);
      }
    } else if (_currentState === State.SPEAKING) {
      // In SPEAKING, animate like a disrupted, wiggling atom (orbiting shells wiggling violently)
      const orbitIndex = idx % 3;
      const orbitAngle = t * 7.5 + p.phase;
      // Vibrating atomic radius
      const baseR = p.baseRadius * (0.80 + Math.sin(t * 22) * 0.12);
      
      let tx = 0, ty = 0, tz = 0;
      if (orbitIndex === 0) {
        // Horizontal loop
        tx = Math.cos(orbitAngle) * baseR;
        ty = Math.sin(orbitAngle) * baseR * 0.25;
        tz = Math.sin(orbitAngle) * baseR * 0.95;
      } else if (orbitIndex === 1) {
        // Vertical loop
        tx = Math.sin(orbitAngle) * baseR * 0.25;
        ty = Math.cos(orbitAngle) * baseR;
        tz = Math.sin(orbitAngle) * baseR * 0.95;
      } else {
        // Tilted diagonal loop
        tx = Math.cos(orbitAngle) * baseR * 0.65;
        ty = Math.sin(orbitAngle) * baseR * 0.65;
        tz = Math.cos(orbitAngle) * baseR * 0.65;
      }

      // Add high-frequency atomic wiggles / vibrations
      const wiggleAmt = 15 + Math.sin(t * 35 + idx) * 9;
      p.x = tx + (Math.random() - 0.5) * wiggleAmt;
      p.y = ty + (Math.random() - 0.5) * wiggleAmt;
      p.z = tz + (Math.random() - 0.5) * wiggleAmt;
    } else if (_currentState === State.LISTENING) {
      // In LISTENING, vibrate particles rapidly in and out based on the audio pulse
      const baseR = p.baseRadius;
      const pulseAmp = Math.sin(t * 28 + p.phase) * (4 + _pulse * 12);
      const targetR = baseR + pulseAmp;
      
      const currentR = Math.sqrt(px * px + py * py + pz * pz) || 1;
      const factor = targetR / currentR;
      p.x *= factor;
      p.y *= factor;
      p.z *= factor;
      
      // Slow orbital drift
      const drift = 0.004;
      const tempX = p.x;
      p.x = tempX * Math.cos(drift) - p.y * Math.sin(drift);
      p.y = tempX * Math.sin(drift) + p.y * Math.cos(drift);
    } else {
      // IDLE: Slow breathing pulse + gentle 3D drift
      const baseR = p.baseRadius;
      const breathingAmp = Math.sin(t * 2.2 + p.phase) * 6;
      const targetR = baseR + breathingAmp;
      
      const currentR = Math.sqrt(px * px + py * py + pz * pz) || 1;
      const factor = targetR / currentR;
      p.x *= factor;
      p.y *= factor;
      p.z *= factor;

      // Slow orbital drift
      const drift = 0.003;
      const tempX = p.x;
      p.x = tempX * Math.cos(drift) - p.y * Math.sin(drift);
      p.y = tempX * Math.sin(drift) + p.y * Math.cos(drift);
    }

    // 2. Rotate around Y axis
    let rx = px * cosY - pz * sinY;
    let rz = px * sinY + pz * cosY;

    // 3. Rotate around X axis
    let ry = py * cosX - rz * sinX;
    let rz2 = py * sinX + rz * cosX;

    // 4. Perspective Projection mapping to 2D
    const fov = 190;
    const scale = fov / (fov + rz2);
    const screenX = cx + rx * scale;
    const screenY = cy + ry * scale;

    projected.push({
      x: screenX,
      y: screenY,
      z: rz2,
      r: p.r * scale,
      alpha: p.alpha * (scale * 0.8)
    });
  });

  // 5. Draw Plexus Web Links
  // Loop through pairs and draw lines between close points
  ctx.save();
  ctx.lineWidth = 0.6;
  const linkDist = 45;
  for (let i = 0; i < projected.length; i++) {
    const p1 = projected[i];
    for (let j = i + 1; j < projected.length; j++) {
      const p2 = projected[j];
      const dx = p1.x - p2.x;
      const dy = p1.y - p2.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < linkDist) {
        // Opacity drops linearly as distance increases
        const opacity = (1.0 - (dist / linkDist)) * 0.18;
        ctx.strokeStyle = pal.ring;
        ctx.globalAlpha = opacity * p1.alpha;
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
      }
    }
  }
  ctx.restore();

  // 6. Draw Projected Particles
  projected.forEach(p => {
    ctx.save();
    ctx.globalAlpha = p.alpha;
    ctx.fillStyle = pal.ring;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  });
}

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

  // 1. Background Plexus Particles (3D shell/plexus)
  drawParticles(cx, cy, pal, t);

  // 2. Glowing outer aura
  const auraR = 145 + _pulse * 6;
  const aura  = ctx.createRadialGradient(cx, cy, 40, cx, cy, auraR);
  aura.addColorStop(0, pal.glow.replace("0.35","0.12").replace("0.40","0.15").replace("0.45","0.18").replace("0.40","0.12"));
  aura.addColorStop(1, "transparent");
  ctx.fillStyle = aura;
  ctx.beginPath();
  ctx.arc(cx, cy, auraR, 0, Math.PI * 2);
  ctx.fill();

  // 3. Rippling Core Glows (breathing pulse)
  const rippleCount = 3;
  for (let i = 0; i < rippleCount; i++) {
    const scale = ((t * 0.4 + i / rippleCount) % 1.0);
    const radius = 38 + scale * 45;
    const opacity = (1.0 - scale) * 0.35;
    ctx.save();
    ctx.globalAlpha = opacity;
    const ripGrad = ctx.createRadialGradient(cx, cy, 10, cx, cy, radius);
    ripGrad.addColorStop(0, pal.ring);
    ripGrad.addColorStop(1, "transparent");
    ctx.fillStyle = ripGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // 4. (Removed Beating Hex Core)

  // 5. Center pulsing dot
  const dotGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 10);
  dotGrad.addColorStop(0, "#ffffff");
  dotGrad.addColorStop(0.5, pal.ring);
  dotGrad.addColorStop(1, "transparent");
  ctx.globalAlpha = 0.95;
  ctx.fillStyle = dotGrad;
  ctx.beginPath();
  ctx.arc(cx, cy, 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1.0;

  _animFrame = requestAnimationFrame(drawCore);
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

function typeWriteText(element, text, speed = 15, onComplete = null) {
  let idx = 0;
  element.textContent = "";
  function type() {
    if (idx < text.length) {
      element.textContent += text.charAt(idx);
      idx++;
      setTimeout(type, speed);
      if (consoleOutput) consoleOutput.scrollTop = consoleOutput.scrollHeight;
    } else {
      if (onComplete) onComplete();
    }
  }
  type();
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

  entry.appendChild(tsEl);
  entry.appendChild(textEl);
  consoleOutput.appendChild(entry);

  if (type === "assistant" && text) {
    typeWriteText(textEl, text);
  } else {
    textEl.appendChild(document.createTextNode(text));
  }

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

function updateSystemStats(data) {
  const cpuVal = document.getElementById("monitor-cpu-val");
  const cpuBar = document.getElementById("monitor-cpu-bar");
  const ramVal = document.getElementById("monitor-ram-val");
  const ramBar = document.getElementById("monitor-ram-bar");
  const diskVal = document.getElementById("monitor-disk-val");
  const diskBar = document.getElementById("monitor-disk-bar");
  const netIn = document.getElementById("monitor-net-in");
  const netOut = document.getElementById("monitor-net-out");

  if (cpuVal && cpuBar) {
    cpuVal.textContent = `${Math.round(data.cpu)}%`;
    cpuBar.style.width = `${data.cpu}%`;
    _setMeterColor(cpuBar, data.cpu);
  }
  if (ramVal && ramBar) {
    ramVal.textContent = `${Math.round(data.ram)}%`;
    ramBar.style.width = `${data.ram}%`;
    _setMeterColor(ramBar, data.ram);
  }
  if (diskVal && diskBar) {
    diskVal.textContent = `${Math.round(data.disk)}%`;
    diskBar.style.width = `${data.disk}%`;
    _setMeterColor(diskBar, data.disk);
  }
  if (netIn) netIn.textContent = `${data.net_in.toFixed(1)} KB/s`;
  if (netOut) netOut.textContent = `${data.net_out.toFixed(1)} KB/s`;
}

function _setMeterColor(bar, val) {
  if (val > 85) {
    bar.style.background = "linear-gradient(90deg, #ef4444, #f87171)";
    bar.style.boxShadow = "0 0 8px rgba(239,68,68,0.6)";
  } else if (val > 65) {
    bar.style.background = "linear-gradient(90deg, #f59e0b, #fbbf24)";
    bar.style.boxShadow = "0 0 8px rgba(245,158,11,0.5)";
  } else {
    bar.style.background = "linear-gradient(90deg, #0077aa, #00c8ff)";
    bar.style.boxShadow = "0 0 8px rgba(0,200,255,0.5)";
  }
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
    case "sys_stats":
      updateSystemStats(data);
      break;

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

// Boot Loader sequence
window.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("boot-overlay");
  const bar = document.getElementById("boot-bar");
  const txt = document.getElementById("boot-text");
  if (!overlay || !bar || !txt) return;

  const logs = [
    "INIT SYSTEM CORE DIAGNOSTICS...",
    "ESTABLISHING SECURE MEMORY VAULT...",
    "LOADING DYNAMIC INTENT DICTIONARIES...",
    "CALIBRATING PYAUDIO CLAP SENSITIVITY...",
    "REGISTERING SAPI5 / EDGE-TTS DUAL VOICES...",
    "SYNCING WEBSOCKET BROADCAST PORTS...",
    "SYSTEM STATUS: ONLINE. INTERFACES SECURED."
  ];

  let progress = 0;

  function bootTick() {
    progress += Math.floor(Math.random() * 12) + 6;
    if (progress >= 100) progress = 100;
    bar.style.width = `${progress}%`;

    const idx = Math.floor((progress / 100) * (logs.length - 1));
    txt.textContent = logs[idx];

    if (progress < 100) {
      setTimeout(bootTick, 100 + Math.random() * 150);
    } else {
      setTimeout(() => {
        overlay.classList.add("hidden");
        // Fade in panels sequentially
        const panels = document.querySelectorAll(".panel, .topbar");
        panels.forEach((p, idx) => {
          setTimeout(() => {
            p.style.opacity = 1;
            p.style.transform = "translateY(0)";
          }, idx * 120);
        });
      }, 600);
    }
  }

  // Pre-boot setup: prepare fade-in styles on panels
  const panels = document.querySelectorAll(".panel, .topbar");
  panels.forEach(p => {
    p.style.opacity = 0;
    p.style.transform = "translateY(15px)";
    p.style.transition = "opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1), transform 0.8s cubic-bezier(0.16, 1, 0.3, 1)";
  });

  setTimeout(bootTick, 400);
});

appendSystem("Jarvis Web Interface v2.0 — Hybrid AI Mode");
appendSystem("Use double-clap for voice commands, or type below.");
appendSystem("Open ⚙ Settings to configure your Gemini API key.");
connectWS();
