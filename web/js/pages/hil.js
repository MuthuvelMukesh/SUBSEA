/**
 * Page 12: Live Hardware-in-the-Loop (HIL) & Direct ESP32 Dashboard
 * Visualizes real-time ESP32 serial telemetry via Web Serial API,
 * routes packets to the Subsea Python research pipeline, and supports
 * file-based replay/polling.
 *
 * Data Kind: HIL_SIMULATED_ACCEL
 * (Validates integration, timing, and link faults; accelerometer is simulated).
 */

import { renderBanner } from "../banner.js";
import { renderKPI, renderBadge, TOOLTIPS } from "../components.js";
import { buildPlot, exportTableToCSV } from "../charts.js";
import { isSerialSupported, HardwareSerialController } from "../hardware_serial.js";
import {
  TelemetryBuffer,
  validateSensorPacket,
  validateAckPacket,
  PipelineBridgeClient,
  BENCHTOP_DISCLAIMERS,
} from "../hardware_adapter.js";

// Session singletons
let serialController = null;
const telemetryBuffer = new TelemetryBuffer(5000);
const pipelineBridge = new PipelineBridgeClient("");

let pollInterval = null;
let isPollingActive = false;
let loadedDecisions = [];
let currentRunMeta = null;
let isTransmissionActive = false;
let lastTelemetry = {
  ldr: null,
  vibration: null,
  distance_cm: null,
  distance_valid: false,
  laser: "OFF",
  buzzer: "OFF",
  alert: "SAFE",
  transmission: false,
};

export async function render(container) {
  renderBanner("HIL_SIMULATED_ACCEL");

  const serialSupported = isSerialSupported();

  container.innerHTML = `
    <!-- Top Mandatory Scientific Notice -->
    <div class="card" style="border-left: 4px solid var(--state-t1); margin-bottom: 1rem;">
      <div style="font-weight: 700; color: var(--state-t1); margin-bottom: 0.25rem;">
        Hardware-in-the-Loop Scientific Integrity Notice
      </div>
      <p style="font-size: 0.9rem; margin: 0; color: var(--text-color); line-height: 1.5;">
        <strong>The accelerometer is simulated; this validates integration and decision logic under real timing and link faults, not subsea sensing physics.</strong>
      </p>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.25rem;">
        <div>📡 <strong>Optical/Serial:</strong> ESP32 AbyssLink hardware telemetry (115,200 baud, 300 ms packet interval).</div>
        <div>📏 <strong>Proximity:</strong> ${BENCHTOP_DISCLAIMERS.ultrasonic}</div>
        <div>⚡ <strong>Vibration:</strong> ${BENCHTOP_DISCLAIMERS.vibration}</div>
      </div>
    </div>

    <!-- Browser Compatibility Warning (if Web Serial not supported) -->
    ${
      !serialSupported
        ? `
      <div class="card" style="border-left: 4px solid var(--state-t2); margin-bottom: 1rem; background: var(--bg-hover);">
        <div style="font-weight: 700; color: var(--state-t2);">⚠️ Web Serial API Unsupported in this Browser</div>
        <p style="font-size: 0.85rem; margin: 0.25rem 0 0 0; color: var(--text-color);">
          Direct USB Serial communication requires a desktop Chromium browser (Google Chrome, Microsoft Edge, or Opera).
          File-based replay and server-side polling remain fully operational.
        </p>
      </div>
    `
        : ""
    }

    <!-- Direct ESP32 USB Serial Hardware Control Card -->
    <div class="card" style="margin-bottom: 1.5rem; border-color: rgba(56, 189, 248, 0.4);">
      <div class="card-title">
        <span style="display: flex; align-items: center; gap: 0.5rem;">
          <span>🔌 Direct ESP32 Hardware Link (Web Serial API)</span>
          <span id="serial-status-badge" class="brand-badge" style="background: var(--bg-hover); color: var(--text-muted);">
            DISCONNECTED
          </span>
        </span>
        <span id="pipeline-status-badge" class="brand-badge" style="background: var(--bg-card); color: var(--text-muted);">
          Checking Python Pipeline...
        </span>
      </div>

      <!-- Action Buttons Row -->
      <div style="display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin-top: 0.75rem;">
        <button id="btn-serial-connect" class="btn btn-primary" ${!serialSupported ? "disabled" : ""}>
          🔌 Connect ESP32 (115200 Baud)
        </button>
        <button id="btn-serial-disconnect" class="btn btn-secondary" disabled>
          Disconnect
        </button>

        <div style="width: 1px; height: 24px; background: var(--border-color); margin: 0 0.25rem;"></div>

        <button id="btn-serial-start-tx" class="btn btn-secondary" disabled>
          ▶ Start Laser Transmission
        </button>
        <button id="btn-serial-stop-tx" class="btn btn-secondary" disabled>
          ⏹ Stop Laser Transmission
        </button>

        <div style="flex: 1;"></div>

        <button id="btn-export-raw-jsonl" class="btn btn-secondary">
          📥 Export Raw Telemetry (JSONL)
        </button>
      </div>

      <!-- Live Link Stats Banner -->
      <div style="display: flex; flex-wrap: wrap; gap: 1.5rem; margin-top: 1rem; padding: 0.6rem 1rem; background: var(--bg-hover); border-radius: var(--radius); font-size: 0.85rem;">
        <div><strong>Baud:</strong> <span style="font-family: var(--font-mono);">115200</span></div>
        <div><strong>Packets Received:</strong> <span id="stat-pkt-count" style="font-family: var(--font-mono); font-weight: 700;">0</span></div>
        <div><strong>Update Rate:</strong> <span id="stat-pkt-rate" style="font-family: var(--font-mono);">0.0 Hz</span></div>
        <div><strong>Malformed Frames:</strong> <span id="stat-malformed-count" style="font-family: var(--font-mono);">0</span></div>
        <div><strong>Last Packet:</strong> <span id="stat-last-pkt" style="font-family: var(--font-mono); color: var(--text-muted);">Never</span></div>
      </div>
    </div>

    <!-- Live ESP32 Sensor Telemetry Grid -->
    <div class="grid-cols-4" style="margin-bottom: 1.5rem;">
      <!-- Sensor Card 1: Optical Link LDR -->
      <div class="card">
        <div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">
          Optical Path (LDR)
        </div>
        <div id="disp-ldr-badge" style="margin: 0.5rem 0;">
          <span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted);">STANDBY</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-color);">
          Digital Flag: <strong id="disp-ldr-val">--</strong>
        </div>
        <div id="disp-ldr-desc" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
          Waiting for serial packet...
        </div>
      </div>

      <!-- Sensor Card 2: Seismic / Vibration -->
      <div class="card">
        <div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">
          Seismic / Vibration
        </div>
        <div id="disp-vib-badge" style="margin: 0.5rem 0;">
          <span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted);">STANDBY</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-color);">
          Vibration Flag: <strong id="disp-vib-val">--</strong>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
          MPU6050 digital vibration switch
        </div>
      </div>

      <!-- Sensor Card 3: Ultrasonic Distance -->
      <div class="card">
        <div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">
          Proximity (HC-SR04)
        </div>
        <div id="disp-dist-val" style="font-size: 1.4rem; font-weight: 700; margin: 0.4rem 0; font-family: var(--font-mono);">
          -- cm
        </div>
        <div id="disp-dist-zone" style="font-size: 0.85rem;">
          <span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted);">NO ECHO</span>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
          Benchtop air measurement
        </div>
      </div>

      <!-- Sensor Card 4: Actuator Status -->
      <div class="card">
        <div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">
          Actuator & Alert State
        </div>
        <div style="display: flex; gap: 0.5rem; margin: 0.5rem 0;">
          <span id="disp-laser-pill" class="brand-badge" style="font-size: 0.75rem;">LASER: --</span>
          <span id="disp-buzzer-pill" class="brand-badge" style="font-size: 0.75rem;">BUZZER: --</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-color);">
          Alert Code: <strong id="disp-alert-val">--</strong>
        </div>
        <div id="disp-tx-status" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
          Transmission: Inactive
        </div>
      </div>
    </div>

    <!-- Secondary Controls Row (Replay & Server Polling) -->
    <div class="control-row" style="margin-bottom: 1.5rem;">
      <div style="display: flex; gap: 0.75rem; align-items: center;">
        <button id="toggle-poll-btn" class="btn btn-secondary">▶ Start Server Polling (2s)</button>
        <span id="poll-indicator" class="brand-badge" style="background: var(--bg-card); color: var(--text-muted);">
          ⚪ Polling Inactive
        </span>
      </div>

      <div style="flex: 1;"></div>

      <div style="display: flex; gap: 0.75rem; align-items: center;">
        <label for="hil-file-input" class="btn btn-secondary" style="cursor: pointer; margin: 0;">
          📁 Load decisions.jsonl
        </label>
        <input type="file" id="hil-file-input" accept=".jsonl,.json" style="display: none;">
        <button id="download-hil-csv" class="btn btn-secondary">📥 Export Decisions CSV</button>
      </div>
    </div>

    <!-- Drag & Drop Zone -->
    <div id="drop-zone" style="border: 2px dashed var(--border-color); border-radius: var(--radius); padding: 1.25rem; text-align: center; margin-bottom: 1.5rem; transition: all 0.2s ease; background: var(--bg-hover);">
      <div style="font-size: 0.9rem; font-weight: 600; color: var(--text-color);">
        Drag & Drop <code>decisions.jsonl</code> here or load via file picker
      </div>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
        Generate offline mock runs with: <code>python scripts/run_abysslink_hil.py --mock --seed 42</code>
      </div>
    </div>

    <!-- Active Inference View Container -->
    <div id="hil-content-view">
      <div class="empty-state">
        <h3>Awaiting Hardware Connection or HIL Log</h3>
        <p>Connect your ESP32 device via USB Serial above, start live server polling, or load a recorded run.</p>
      </div>
    </div>

    <!-- Bounded Hardware Event Log Card (Last 50 Events) -->
    <div class="card" style="margin-top: 1.5rem;">
      <div class="card-title">
        <span>Hardware & Serial Event Audit Log</span>
        <button id="btn-clear-events" class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.2rem 0.5rem;">Clear Log</button>
      </div>
      <div class="table-container" style="max-height: 220px; overflow-y: auto;">
        <table id="hil-events-table">
          <thead>
            <tr>
              <th style="width: 120px;">Timestamp</th>
              <th style="width: 110px;">Subsystem</th>
              <th>Event Description</th>
            </tr>
          </thead>
          <tbody id="hil-events-tbody">
            <tr>
              <td colspan="3" style="text-align: center; color: var(--text-muted);">No events logged yet. Connect hardware or load a log to begin.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Initialize Hardware Serial Controller
  initHardwareSerial(container);

  // Check Python Pipeline Bridge
  checkPipelineBridge();

  // Setup Drag & Drop and File Loaders
  setupFileHandlers();

  // Setup Server Polling
  setupPolling();

  // Load existing decisions.jsonl if available initially
  fetch("hil/decisions.jsonl")
    .then((r) => (r.ok ? r.text() : null))
    .then((text) => {
      if (text && loadedDecisions.length === 0) {
        parseAndDisplayDecisions(text, "Default HIL Run");
      }
    })
    .catch(() => {});
}

/**
 * Checks if the Python Subsea pipeline server endpoint (/api/status) is reachable.
 */
async function checkPipelineBridge() {
  const badge = document.getElementById("pipeline-status-badge");
  const isHealthy = await pipelineBridge.checkHealth();
  if (badge) {
    if (isHealthy) {
      badge.textContent = "🟢 Real Python Pipeline Bridge Online";
      badge.style.color = "var(--state-t0)";
      telemetryBuffer.addEvent("SYSTEM", "Connected to Python Subsea inference backend.", "safe");
    } else {
      badge.textContent = "🟡 Static Web Mode (Raw Telemetry)";
      badge.style.color = "var(--state-t1)";
    }
  }
}

/**
 * Initializes the Web Serial Controller and hooks UI buttons.
 */
function initHardwareSerial(container) {
  const connectBtn = document.getElementById("btn-serial-connect");
  const disconnectBtn = document.getElementById("btn-serial-disconnect");
  const startTxBtn = document.getElementById("btn-serial-start-tx");
  const stopTxBtn = document.getElementById("btn-serial-stop-tx");
  const exportRawBtn = document.getElementById("btn-export-raw-jsonl");
  const clearEventsBtn = document.getElementById("btn-clear-events");

  serialController = new HardwareSerialController({
    onPacket: handleIncomingSensorPacket,
    onAck: handleIncomingAckPacket,
    onStateChange: handleSerialStateChange,
    onLog: (lvl, msg) => {
      telemetryBuffer.addEvent("SERIAL", msg, lvl);
      renderEventLog();
    },
    onRawLine: (line) => {
      // Optional debug line
    },
  });

  if (connectBtn) {
    connectBtn.addEventListener("click", async () => {
      try {
        await serialController.connect({ baudRate: 115200 });
      } catch (_) {
        // Handled in controller
      }
    });
  }

  if (disconnectBtn) {
    disconnectBtn.addEventListener("click", async () => {
      await serialController.disconnect();
    });
  }

  if (startTxBtn) {
    startTxBtn.addEventListener("click", async () => {
      try {
        await serialController.sendCommand("START_TRANSMISSION");
        telemetryBuffer.addEvent("OPTICAL", "Sent START_TRANSMISSION command to ESP32.", "info");
      } catch (e) {
        telemetryBuffer.addEvent("SERIAL", `Command error: ${e.message}`, "danger");
      }
    });
  }

  if (stopTxBtn) {
    stopTxBtn.addEventListener("click", async () => {
      try {
        await serialController.sendCommand("STOP_TRANSMISSION");
        telemetryBuffer.addEvent("OPTICAL", "Sent STOP_TRANSMISSION command to ESP32.", "info");
      } catch (e) {
        telemetryBuffer.addEvent("SERIAL", `Command error: ${e.message}`, "danger");
      }
    });
  }

  if (exportRawBtn) {
    exportRawBtn.addEventListener("click", () => {
      const exported = telemetryBuffer.exportRawJSONL();
      if (!exported) {
        alert("No raw hardware telemetry packets recorded yet to export.");
      }
    });
  }

  if (clearEventsBtn) {
    clearEventsBtn.addEventListener("click", () => {
      telemetryBuffer.events = [];
      renderEventLog();
    });
  }
}

/**
 * Handles Web Serial connection state changes.
 */
function handleSerialStateChange(state, detail) {
  const badge = document.getElementById("serial-status-badge");
  const connectBtn = document.getElementById("btn-serial-connect");
  const disconnectBtn = document.getElementById("btn-serial-disconnect");
  const startTxBtn = document.getElementById("btn-serial-start-tx");
  const stopTxBtn = document.getElementById("btn-serial-stop-tx");

  if (badge) {
    badge.textContent = state;
    if (state === "CONNECTED") {
      badge.style.color = "var(--state-t0)";
      badge.style.background = "rgba(16, 185, 129, 0.15)";
    } else if (state === "CONNECTING") {
      badge.style.color = "var(--state-t1)";
      badge.style.background = "rgba(245, 158, 11, 0.15)";
    } else if (state === "ERROR") {
      badge.style.color = "var(--state-t3)";
      badge.style.background = "rgba(239, 68, 68, 0.15)";
    } else {
      badge.style.color = "var(--text-muted)";
      badge.style.background = "var(--bg-hover)";
    }
  }

  if (connectBtn) connectBtn.disabled = state === "CONNECTED" || state === "CONNECTING";
  if (disconnectBtn) disconnectBtn.disabled = state !== "CONNECTED";

  if (startTxBtn) startTxBtn.disabled = state !== "CONNECTED" || isTransmissionActive;
  if (stopTxBtn) stopTxBtn.disabled = state !== "CONNECTED" || !isTransmissionActive;
}

/**
 * Handles incoming sensor telemetry packet from Web Serial.
 */
async function handleIncomingSensorPacket(rawObj, rawLine) {
  const packet = validateSensorPacket(rawObj);
  if (!packet) {
    telemetryBuffer.addEvent("SERIAL", "Malformed sensor frame rejected.", "warning");
    return;
  }

  // 1. Buffer raw packet
  telemetryBuffer.addRawPacket(packet, rawLine);

  // 2. Detect transitions
  detectHardwareTransitions(lastTelemetry, packet);
  lastTelemetry = { ...packet };
  isTransmissionActive = packet.transmission;

  // 3. Update Hardware Display Cards
  updateHardwareCards(packet);

  // 4. Update Stats Bar
  updateStatsBar();

  // 5. Route to Python Pipeline Bridge if backend server is available
  const pipelineResult = await pipelineBridge.processPacket(packet);
  if (pipelineResult) {
    // Pipeline returned real decision result
    loadedDecisions.push(pipelineResult);
    currentRunMeta = { source: "Live ESP32 USB Link", count: loadedDecisions.length };
    updateDashboard();
  } else {
    // Server is offline (static mode): render hardware cards and telemetry
    if (loadedDecisions.length === 0) {
      renderRawHardwareSummary(packet);
    }
  }
}

/**
 * Handles incoming ACK packet from ESP32.
 */
function handleIncomingAckPacket(rawObj) {
  const ack = validateAckPacket(rawObj);
  if (!ack) return;

  isTransmissionActive = ack.transmission;
  const startTxBtn = document.getElementById("btn-serial-start-tx");
  const stopTxBtn = document.getElementById("btn-serial-stop-tx");
  if (startTxBtn) startTxBtn.disabled = isTransmissionActive;
  if (stopTxBtn) stopTxBtn.disabled = !isTransmissionActive;

  if (ack.success) {
    telemetryBuffer.addEvent("OPTICAL", `ESP32 ACK: ${ack.command} confirmed (Transmission=${ack.transmission}).`, "safe");
  } else {
    telemetryBuffer.addEvent("OPTICAL", `ESP32 NACK: ${ack.command} rejected.`, "danger");
  }
  renderEventLog();
}

/**
 * Detects sensor state changes and logs them into the bounded event log.
 */
function detectHardwareTransitions(prev, curr) {
  if (prev.transmission !== null && prev.transmission !== curr.transmission) {
    telemetryBuffer.addEvent(
      "OPTICAL",
      curr.transmission ? "Laser transmission active." : "Laser transmission stopped.",
      curr.transmission ? "safe" : "info"
    );
  }

  if (curr.transmission) {
    if (prev.ldr !== null && prev.ldr !== curr.ldr) {
      if (curr.ldr === 1) {
        telemetryBuffer.addEvent("OPTICAL", "⚠️ Optical beam interrupted! Photodiode signal lost.", "danger");
      } else if (curr.ldr === 0) {
        telemetryBuffer.addEvent("OPTICAL", "✔ Optical laser link restored to receiver.", "safe");
      }
    }
  }

  if (prev.vibration !== null && prev.vibration !== curr.vibration) {
    if (curr.vibration === 1) {
      telemetryBuffer.addEvent("SEISMIC", "⚡ Cable vibration detected by sensor switch!", "danger");
    } else if (curr.vibration === 0) {
      telemetryBuffer.addEvent("SEISMIC", "Seismic sensor returned to quiet baseline.", "safe");
    }
  }

  if (prev.alert !== curr.alert) {
    if (curr.alert === "CRITICAL_PROXIMITY") {
      telemetryBuffer.addEvent("RADAR", `CRITICAL: Proximity intrusion at ${curr.distance_cm} cm!`, "danger");
    } else if (curr.alert === "PROXIMITY_DANGER") {
      telemetryBuffer.addEvent("RADAR", `DANGER: Obstacle in danger zone (${curr.distance_cm} cm).`, "danger");
    } else if (curr.alert === "PROXIMITY_WARNING") {
      telemetryBuffer.addEvent("RADAR", `WARNING: Obstacle approaching (${curr.distance_cm} cm).`, "warning");
    }
  }

  renderEventLog();
}

/**
 * Updates the 4 hardware sensor cards with latest telemetry.
 */
function updateHardwareCards(pkt) {
  // 1. LDR Card
  const ldrBadge = document.getElementById("disp-ldr-badge");
  const ldrVal = document.getElementById("disp-ldr-val");
  const ldrDesc = document.getElementById("disp-ldr-desc");

  if (ldrVal) ldrVal.textContent = pkt.ldr !== null ? pkt.ldr : "Unavailable";
  if (ldrBadge && ldrDesc) {
    if (!pkt.transmission) {
      ldrBadge.innerHTML = `<span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted);">STANDBY (LASER OFF)</span>`;
      ldrDesc.textContent = "Laser disarmed. Ready to transmit.";
    } else if (pkt.ldr === 0) {
      ldrBadge.innerHTML = `<span class="state-badge T0">✔ SIGNAL NOMINAL</span>`;
      ldrDesc.textContent = "Laser photodiode receiving optical beam.";
    } else {
      ldrBadge.innerHTML = `<span class="state-badge T3">⚠️ BEAM INTERRUPTED</span>`;
      ldrDesc.textContent = "Optical path broken or photodiode misaligned.";
    }
  }

  // 2. Vibration Card
  const vibBadge = document.getElementById("disp-vib-badge");
  const vibVal = document.getElementById("disp-vib-val");
  if (vibVal) vibVal.textContent = pkt.vibration !== null ? pkt.vibration : "Unavailable";
  if (vibBadge) {
    if (pkt.vibration === 1) {
      vibBadge.innerHTML = `<span class="state-badge T3">⚡ VIBRATION (FLAG 1)</span>`;
    } else {
      vibBadge.innerHTML = `<span class="state-badge T0">QUIET (FLAG 0)</span>`;
    }
  }

  // 3. Distance Card
  const distVal = document.getElementById("disp-dist-val");
  const distZone = document.getElementById("disp-dist-zone");
  if (distVal) {
    distVal.textContent = pkt.distance_valid && pkt.distance_cm !== null ? `${pkt.distance_cm.toFixed(1)} cm` : "-- cm";
  }
  if (distZone) {
    if (!pkt.distance_valid || pkt.distance_cm === null) {
      distZone.innerHTML = `<span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted);">NO ECHO / OUT OF RANGE</span>`;
    } else if (pkt.distance_cm <= 5.0) {
      distZone.innerHTML = `<span class="state-badge T3">CRITICAL (≤ 5 cm)</span>`;
    } else if (pkt.distance_cm <= 50.0) {
      distZone.innerHTML = `<span class="state-badge T2">DANGER (6-50 cm)</span>`;
    } else if (pkt.distance_cm <= 80.0) {
      distZone.innerHTML = `<span class="state-badge T1">WARNING (51-80 cm)</span>`;
    } else {
      distZone.innerHTML = `<span class="state-badge T0">SAFE (> 80 cm)</span>`;
    }
  }

  // 4. Actuators Card
  const laserPill = document.getElementById("disp-laser-pill");
  const buzzerPill = document.getElementById("disp-buzzer-pill");
  const alertVal = document.getElementById("disp-alert-val");
  const txStatus = document.getElementById("disp-tx-status");

  if (laserPill) {
    laserPill.textContent = `LASER: ${pkt.laser}`;
    laserPill.style.color = pkt.laser === "ON" ? "var(--state-t0)" : "var(--text-muted)";
  }
  if (buzzerPill) {
    buzzerPill.textContent = `BUZZER: ${pkt.buzzer}`;
    buzzerPill.style.color = pkt.buzzer === "ON" ? "var(--state-t3)" : "var(--text-muted)";
  }
  if (alertVal) alertVal.textContent = pkt.alert;
  if (txStatus) {
    txStatus.textContent = pkt.transmission ? "Transmission: Active" : "Transmission: Inactive";
  }
}

/**
 * Updates stats in the serial link banner.
 */
function updateStatsBar() {
  if (!serialController) return;
  const stats = serialController.getStats();

  const pktCountEl = document.getElementById("stat-pkt-count");
  const rateEl = document.getElementById("stat-pkt-rate");
  const malformedEl = document.getElementById("stat-malformed-count");
  const lastPktEl = document.getElementById("stat-last-pkt");

  if (pktCountEl) pktCountEl.textContent = stats.receivedCount.toString();
  if (rateEl) rateEl.textContent = `${stats.updateRateHz} Hz`;
  if (malformedEl) malformedEl.textContent = stats.malformedCount.toString();
  if (lastPktEl && stats.lastTimestamp) {
    const d = new Date(stats.lastTimestamp);
    lastPktEl.textContent = d.toTimeString().split(" ")[0];
  }
}

/**
 * Renders the bounded event audit log.
 */
function renderEventLog() {
  const tbody = document.getElementById("hil-events-tbody");
  if (!tbody) return;

  if (telemetryBuffer.events.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No events logged yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = telemetryBuffer.events
    .map((ev) => {
      let color = "var(--text-color)";
      if (ev.level === "danger") color = "var(--state-t3)";
      if (ev.level === "warning") color = "var(--state-t1)";
      if (ev.level === "safe") color = "var(--state-t0)";

      return `
      <tr>
        <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">${ev.timestamp}</td>
        <td><span class="brand-badge" style="font-size: 0.75rem;">${ev.category}</span></td>
        <td style="color: ${color}; font-size: 0.85rem;">${ev.message}</td>
      </tr>
    `;
    })
    .join("");
}

/**
 * Renders raw hardware summary when Python inference server is offline.
 */
function renderRawHardwareSummary(pkt) {
  const view = document.getElementById("hil-content-view");
  if (!view) return;

  view.innerHTML = `
    <div class="card" style="border-left: 4px solid var(--state-t1);">
      <div class="card-title">
        <span>Hardware Telemetry Active (Client-Only Mode)</span>
        <span class="brand-badge">Raw Sensor Stream</span>
      </div>
      <p style="font-size: 0.9rem; color: var(--text-color); margin: 0.25rem 0 0.75rem 0;">
        Serial packets are streaming directly from the ESP32 to the browser via Web Serial.
        To enable real-time subsea multimodal evidence fusion inference ($C_P, C_A, R, U$),
        run the unified local server:
      </p>
      <pre style="background: var(--bg-hover); padding: 0.75rem; border-radius: var(--radius); display: inline-block; font-family: var(--font-mono);">python scripts/serve_web.py --port 8000</pre>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem;">
        Buffered packets: <strong>${telemetryBuffer.rawPackets.length}</strong>. You can export the raw telemetry at any time using <strong>Export Raw Telemetry (JSONL)</strong> above.
      </div>
    </div>
  `;
}

/**
 * Standard dashboard updater for decision records (from Python server or loaded file).
 */
function updateDashboard() {
  if (loadedDecisions.length === 0) return;

  const latest = loadedDecisions[loadedDecisions.length - 1];
  const first = loadedDecisions[0];
  const duration = (latest.timestamp - first.timestamp).toFixed(1);

  // Compute decision counts
  const counts = { T0: 0, T1: 0, T2: 0, T3: 0, TX: 0 };
  for (const d of loadedDecisions) {
    if (counts[d.decision] !== undefined) {
      counts[d.decision]++;
    }
  }

  const view = document.getElementById("hil-content-view");
  if (!view) return;

  view.innerHTML = `
    <!-- KPIs -->
    <div class="grid-cols-4">
      ${renderKPI(
        "Current State",
        renderBadge(latest.decision),
        `Packet #${latest.sequence} at t=${latest.timestamp.toFixed(1)}s`,
        TOOLTIPS[latest.decision] || ""
      )}
      ${renderKPI(
        "Pipeline Optical Link",
        latest.transmission ? "CONNECTED" : "LINK FAULT",
        latest.ldr_flag ? "⚠️ Optical Degraded" : "Nominal Optical Path",
        "ESP32 hardware link and photodiode transmission indicator."
      )}
      ${renderKPI(
        "Vibration & Proximity",
        latest.vibration_flag ? "VIBRATING (FLAG 1)" : "QUIET (FLAG 0)",
        latest.vessel_distance_m !== null ? `Distance: ${latest.vessel_distance_m} m` : "Distance: Unavailable",
        "Simulated 50 Hz accelerometer + ultrasonic distance mapped to vessel observation."
      )}
      ${renderKPI(
        "Pipeline Decisions",
        `${loadedDecisions.length}`,
        `Duration: ${duration} s (${(loadedDecisions.length / Math.max(1, parseFloat(duration))).toFixed(1)} Hz)`,
        "Total telemetry frames evaluated by the real Subsea pipeline."
      )}
    </div>

    <!-- Live Charts Grid -->
    <div class="grid-cols-2">
      <!-- Decision State Timeline -->
      <div class="card">
        <div class="card-title">
          <span>Decision State Evolution (T0, T1, T2, T3, TX)</span>
          <span class="brand-badge">${currentRunMeta?.source || "HIL Session"}</span>
        </div>
        <div id="hil-state-plot" class="chart-container"></div>
      </div>

      <!-- Evidence & Confidence Traces -->
      <div class="card">
        <div class="card-title">
          <span>Continuous Multimodal Evidence (C_P, C_A, R, U)</span>
          <span class="brand-badge">Gate Metrics</span>
        </div>
        <div id="hil-evidence-plot" class="chart-container"></div>
      </div>
    </div>

    <!-- Decision Breakdown & Event Log Grid -->
    <div class="grid-cols-2" style="margin-top: 1.5rem;">
      <!-- Decision State Distribution -->
      <div class="card">
        <div class="card-title">
          <span>Decision State Distribution</span>
          <span class="brand-badge">${loadedDecisions.length} Packets</span>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Decision State</th>
                <th>Packet Count</th>
                <th>Distribution (%)</th>
                <th>Target Semantics</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>${renderBadge("T0")}</td>
                <td><strong>${counts.T0}</strong></td>
                <td>${((counts.T0 / loadedDecisions.length) * 100).toFixed(1)}%</td>
                <td>Safe background unperturbed</td>
              </tr>
              <tr>
                <td>${renderBadge("T1")}</td>
                <td><strong>${counts.T1}</strong></td>
                <td>${((counts.T1 / loadedDecisions.length) * 100).toFixed(1)}%</td>
                <td>Uncorroborated physical disturbance</td>
              </tr>
              <tr>
                <td>${renderBadge("T2")}</td>
                <td><strong>${counts.T2}</strong></td>
                <td>${((counts.T2 / loadedDecisions.length) * 100).toFixed(1)}%</td>
                <td>Corroborated alert with vessel contact</td>
              </tr>
              <tr>
                <td>${renderBadge("T3")}</td>
                <td><strong>${counts.T3}</strong></td>
                <td>${((counts.T3 / loadedDecisions.length) * 100).toFixed(1)}%</td>
                <td>High-confidence imminent risk</td>
              </tr>
              <tr>
                <td>${renderBadge("TX")}</td>
                <td><strong>${counts.TX}</strong></td>
                <td>${((counts.TX / loadedDecisions.length) * 100).toFixed(1)}%</td>
                <td>Fail-closed / link fault alert</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Latest Decisions Stream Table -->
      <div class="card">
        <div class="card-title">
          <span>Recent Telemetry Decisions Stream</span>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Last 10 Frames</span>
        </div>
        <div class="table-container">
          <table id="hil-recent-table">
            <thead>
              <tr>
                <th>Pkt #</th>
                <th>Timestamp</th>
                <th>C_P</th>
                <th>C_A</th>
                <th>R</th>
                <th>U</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              ${loadedDecisions
                .slice(-10)
                .reverse()
                .map(
                  (d) => `
                <tr>
                  <td><code>#${d.sequence}</code></td>
                  <td>${d.timestamp.toFixed(2)}s</td>
                  <td>${d.physical_confidence !== undefined ? d.physical_confidence.toFixed(3) : "N/A"}</td>
                  <td>${d.association_confidence !== undefined ? d.association_confidence.toFixed(3) : "N/A"}</td>
                  <td>${d.reliability !== undefined ? d.reliability.toFixed(3) : "N/A"}</td>
                  <td>${d.uncertainty !== undefined ? d.uncertainty.toFixed(3) : "N/A"}</td>
                  <td>${renderBadge(d.decision)}</td>
                </tr>
              `
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  renderCharts();

  const dlBtn = document.getElementById("download-hil-csv");
  if (dlBtn) {
    dlBtn.onclick = () => {
      const table = document.getElementById("hil-recent-table");
      if (table) exportTableToCSV(table, "hil_decisions_stream.csv");
    };
  }
}

function renderCharts() {
  const times = loadedDecisions.map((d) => d.timestamp);
  const decisions = loadedDecisions.map((d) => d.decision);
  const cp = loadedDecisions.map((d) => d.physical_confidence || 0);
  const ca = loadedDecisions.map((d) => d.association_confidence || 0);
  const r = loadedDecisions.map((d) => d.reliability || 0);
  const u = loadedDecisions.map((d) => d.uncertainty || 0);

  const stateColors = {
    T0: "#10b981",
    T1: "#f59e0b",
    T2: "#f97316",
    T3: "#ef4444",
    TX: "#8b5cf6",
  };

  // Plot 1: Decision States
  const traceState = {
    x: times,
    y: decisions,
    mode: "lines+markers",
    name: "Decision State",
    line: { shape: "hv", color: "#64748b", width: 2 },
    marker: {
      size: 7,
      color: decisions.map((d) => stateColors[d] || "#3b82f6"),
    },
  };
  buildPlot("hil-state-plot", [traceState], {
    xaxis: { title: "Time (s)" },
    yaxis: {
      title: "Decision State",
      categoryorder: "array",
      categoryarray: ["T0", "T1", "T2", "T3", "TX"],
    },
    margin: { l: 60, r: 20, t: 30, b: 50 },
  });

  // Plot 2: Evidence Traces
  const traceCp = {
    x: times,
    y: cp,
    name: "C_P (Physical)",
    line: { color: "#38bdf8", width: 2 },
  };
  const traceCa = {
    x: times,
    y: ca,
    name: "C_A (Assoc)",
    line: { color: "#fbbf24", width: 2 },
  };
  const traceR = {
    x: times,
    y: r,
    name: "R (Reliability)",
    line: { color: "#34d399", width: 2 },
  };
  const traceU = {
    x: times,
    y: u,
    name: "U (Uncertainty)",
    line: { color: "#c084fc", width: 2, dash: "dot" },
  };
  buildPlot("hil-evidence-plot", [traceCp, traceCa, traceR, traceU], {
    xaxis: { title: "Time (s)" },
    yaxis: { title: "Metric [0.0, 1.0]", range: [-0.05, 1.05] },
    legend: { orientation: "h", y: -0.25 },
    margin: { l: 50, r: 20, t: 30, b: 50 },
  });
}

function setupFileHandlers() {
  const fileInput = document.getElementById("hil-file-input");
  const dropZone = document.getElementById("drop-zone");

  if (dropZone) {
    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropZone.style.borderColor = "var(--primary)";
      dropZone.style.background = "rgba(56, 189, 248, 0.1)";
    });
    dropZone.addEventListener("dragleave", () => {
      dropZone.style.borderColor = "var(--border-color)";
      dropZone.style.background = "var(--bg-hover)";
    });
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.style.borderColor = "var(--border-color)";
      dropZone.style.background = "var(--bg-hover)";
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFileLoad(e.dataTransfer.files[0]);
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFileLoad(e.target.files[0]);
      }
    });
  }
}

function handleFileLoad(file) {
  const reader = new FileReader();
  reader.onload = (evt) => {
    parseAndDisplayDecisions(evt.target.result, file.name);
    telemetryBuffer.addEvent("SYSTEM", `Loaded decision log file: ${file.name}`, "info");
    renderEventLog();
  };
  reader.readAsText(file);
}

function parseAndDisplayDecisions(content, sourceName = "Loaded File") {
  const lines = content.split("\n");
  const records = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const obj = JSON.parse(trimmed);
      if (obj.sequence !== undefined && obj.decision !== undefined) {
        records.push(obj);
      }
    } catch (_) {}
  }

  if (records.length === 0) {
    const view = document.getElementById("hil-content-view");
    if (view) {
      view.innerHTML = `
        <div class="empty-state">
          <h3>Failed to Parse Valid Decision Records</h3>
          <p>Please ensure file contains valid JSONL decision lines.</p>
        </div>
      `;
    }
    return;
  }

  loadedDecisions = records;
  currentRunMeta = { source: sourceName, count: records.length };
  updateDashboard();
}

function setupPolling() {
  const pollBtn = document.getElementById("toggle-poll-btn");
  if (!pollBtn) return;

  async function pollLatest() {
    try {
      const ptrResp = await fetch("hil/latest.json?t=" + Date.now());
      if (!ptrResp.ok) return;
      const ptr = await ptrResp.json();

      const decResp = await fetch("hil/decisions.jsonl?t=" + Date.now());
      if (decResp.ok) {
        const text = await decResp.text();
        parseAndDisplayDecisions(text, ptr.run_id || "Live HIL Run");
      }
    } catch (e) {
      console.warn("Polling error:", e);
    }
  }

  pollBtn.addEventListener("click", () => {
    isPollingActive = !isPollingActive;
    const ind = document.getElementById("poll-indicator");
    if (isPollingActive) {
      pollBtn.textContent = "⏸ Pause Polling";
      pollBtn.classList.remove("btn-secondary");
      pollBtn.classList.add("btn-primary");
      if (ind) {
        ind.innerHTML = "🟢 Live Streaming (2s)";
        ind.style.color = "var(--state-t0)";
      }
      pollLatest();
      pollInterval = setInterval(pollLatest, 2000);
    } else {
      pollBtn.textContent = "▶ Start Server Polling (2s)";
      pollBtn.classList.remove("btn-primary");
      pollBtn.classList.add("btn-secondary");
      if (ind) {
        ind.innerHTML = "⚪ Polling Inactive";
        ind.style.color = "var(--text-muted)";
      }
      clearInterval(pollInterval);
      pollInterval = null;
    }
  });
}
