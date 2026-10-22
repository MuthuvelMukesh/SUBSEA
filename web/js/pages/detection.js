/**
 * Module 1: Detection (Primary Operational Dashboard & Landing Page)
 *
 * Focuses strictly on:
 * 1. Physical hardware connection status (Web Serial / ESP32).
 * 2. Current validated sensor readings from actual physical prototype.
 * 3. Primary detection state (T0, T1, T2, T3, TX) preserving existing definitions.
 * 4. Most recent detection evidence (C_P, C_A, R, U gate metrics).
 * 5. Data quality, freshness, and ingestion error handling.
 * 6. Timestamped detection event audit history.
 *
 * Scientific Provenance:
 * Physical sensor channels are marked [PHYSICAL].
 * Channels not present on physical hardware are explicitly labeled unavailable.
 */

import { renderBanner } from "../banner.js";
import {
  renderKPI,
  renderBadge,
  renderProvenanceBadge,
  renderQualityBadge,
  TOOLTIPS,
} from "../components.js";
import { buildPlot, exportTableToCSV } from "../charts.js";
import { isSerialSupported, HardwareSerialController } from "../hardware_serial.js";
import {
  TelemetryBuffer,
  validateSensorPacket,
  validateAckPacket,
  PipelineBridgeClient,
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
let lastPacketTimestamp = null;
let freshnessInterval = null;

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

let activeEventFilter = "ALL";
let eventSearchTerm = "";

export async function render(container) {
  renderBanner("HIL_SIMULATED_ACCEL");

  const serialSupported = isSerialSupported();

  container.innerHTML = `
    <!-- Top System Architecture & Physical Hardware Header -->
    <div class="card" style="border-left: 4px solid var(--accent); background: var(--bg-card); padding: 1.25rem 1.5rem;">
      <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 1rem;">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <span id="hardware-live-dot" class="pulse-dot" style="background-color: var(--text-muted);" title="Hardware Link Status"></span>
          <div>
            <div style="font-size: 0.72rem; text-transform: uppercase; font-weight: 700; color: var(--text-muted); letter-spacing: 0.05em;">
              AbyssLink Operational Monitoring — Module 1
            </div>
            <div style="font-size: 1.25rem; font-weight: 800; color: var(--text-main); margin-top: 0.1rem; display: flex; align-items: center; gap: 0.6rem;">
              <span>Subsea Disturbance Detection Dashboard</span>
              <span id="detection-mode-badge" class="brand-badge" style="background: var(--bg-subtle); color: var(--text-muted);">
                AWAITING PHYSICAL HARDWARE
              </span>
            </div>
          </div>
        </div>

        <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
          <a href="#/early-warning" class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.45rem 0.85rem;">
            ⚡ Go to Early Warning ➔
          </a>
          <a href="#/research" class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.45rem 0.85rem;">
            🔬 Research & Validation ➔
          </a>
        </div>
      </div>

      <!-- Provenance Notice -->
      <div style="margin-top: 0.85rem; padding: 0.6rem 0.9rem; border-radius: 6px; font-size: 0.82rem; line-height: 1.4; background: rgba(56, 189, 248, 0.08); border-left: 3px solid var(--accent); color: var(--text-main);">
        <strong>📡 Physical-First Ingestion Contract:</strong> Real physical sensors stream from the ESP32 via USB Web Serial (115,200 baud). Sensor channels not physically present on the benchtop prototype (DAS distributed acoustics, subsea fiber strain) are strictly excluded in physical-only operation and never fabricated.
      </div>
    </div>

    <!-- Section 1: Physical Hardware Connection & Serial Link Controls -->
    <div class="card" style="border-color: rgba(56, 189, 248, 0.4);">
      <div class="card-title">
        <span style="display: flex; align-items: center; gap: 0.5rem;">
          <span>🔌 Physical ESP32 Hardware Link (Web Serial)</span>
          <span id="serial-status-badge" class="brand-badge" style="background: var(--bg-hover); color: var(--text-muted);">
            DISCONNECTED
          </span>
        </span>
        <span id="sample-freshness-badge" style="font-size: 0.78rem; font-family: var(--font-mono); color: var(--text-muted);">
          Freshness: No samples yet
        </span>
      </div>

      <!-- Browser support warning if Web Serial unavailable -->
      ${
        !serialSupported
          ? `
        <div style="padding: 0.6rem 0.9rem; border-radius: 6px; background: rgba(239, 68, 68, 0.12); border-left: 3px solid var(--state-t3); font-size: 0.82rem; color: var(--text-main);">
          <strong>⚠️ Web Serial API Not Supported:</strong> Your current browser does not support the Web Serial API. Please open this dashboard in Google Chrome or Microsoft Edge to connect to the physical ESP32 hardware prototype.
        </div>
        `
          : ""
      }

      <!-- Hardware Action Controls Row -->
      <div style="display: flex; flex-wrap: wrap; gap: 0.65rem; align-items: center; margin-top: 0.5rem;">
        <div style="display: flex; align-items: center; gap: 0.35rem;">
          <label for="select-serial-baud" style="font-size: 0.78rem; font-weight: 700; color: var(--text-muted);">Baud:</label>
          <select id="select-serial-baud" style="padding: 0.4rem 0.65rem; background: var(--bg-card); color: var(--text-color); border: 1px solid var(--border-color); border-radius: 6px; font-size: 0.82rem; font-weight: 700; font-family: var(--font-mono);">
            <option value="115200" selected>115,200 (AbyssLink Default)</option>
            <option value="9600">9,600 (Standard Arduino)</option>
            <option value="57600">57,600</option>
            <option value="74880">74,880 (ESP32 Bootloader)</option>
            <option value="38400">38,400</option>
            <option value="19200">19,200</option>
            <option value="230400">230,400</option>
            <option value="921600">921,600</option>
          </select>
        </div>

        <button id="btn-serial-connect" class="btn btn-primary" ${!serialSupported ? "disabled" : ""}>
          🔌 Connect ESP32
        </button>
        <button id="btn-serial-disconnect" class="btn btn-secondary" disabled>
          Disconnect
        </button>
        <button id="btn-serial-reset-esp" class="btn btn-secondary" disabled title="Send hardware RTS reset pulse to reboot ESP32">
          🔄 Reboot ESP32
        </button>

        <div style="width: 1px; height: 22px; background: var(--border-color); margin: 0 0.2rem;"></div>

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

      <!-- Actionable Baud Rate Mismatch & Troubleshooting Banner -->
      <div id="baud-mismatch-banner" style="display: none; margin-top: 0.75rem; padding: 0.75rem 1rem; border-radius: 6px; background: rgba(239, 68, 68, 0.12); border: 1px solid #ef4444; color: var(--text-main); font-size: 0.82rem; line-height: 1.45;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.6rem;">
          <div>
            <strong style="color: #ef4444;">⚠️ Baud Rate Mismatch / Framing Noise Detected:</strong>
            <div id="baud-mismatch-text" style="color: var(--text-main); margin-top: 0.15rem;">
              The serial port is receiving corrupt replacement bytes (\ufffd). Your ESP32 is likely running at 9600 baud instead of 115200.
            </div>
          </div>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <button id="btn-auto-switch-baud" class="btn btn-primary" style="font-size: 0.78rem; padding: 0.35rem 0.75rem;">
              ⚡ Switch to 9600 Baud & Reconnect
            </button>
            <button id="btn-mismatch-reboot" class="btn btn-secondary" style="font-size: 0.78rem; padding: 0.35rem 0.75rem;">
              🔄 Reboot ESP32 (RTS)
            </button>
          </div>
        </div>
      </div>

      <!-- Hardware Link Statistics -->
      <div style="display: flex; flex-wrap: wrap; gap: 1.5rem; margin-top: 0.75rem; padding: 0.6rem 1rem; background: var(--bg-subtle); border-radius: 6px; font-size: 0.82rem;">
        <div><strong>Baud Rate:</strong> <span id="stat-baud-rate" style="font-family: var(--font-mono); font-weight: 700;">115,200</span></div>
        <div><strong>Packets Received:</strong> <span id="stat-pkt-count" style="font-family: var(--font-mono); font-weight: 700;">0</span></div>
        <div><strong>Ingestion Rate:</strong> <span id="stat-pkt-rate" style="font-family: var(--font-mono);">0.0 Hz</span></div>
        <div><strong>Malformed Frames:</strong> <span id="stat-malformed-count" style="font-family: var(--font-mono);">0</span></div>
        <div><strong>Last Packet:</strong> <span id="stat-last-pkt" style="font-family: var(--font-mono); color: var(--text-muted);">Never</span></div>
      </div>
    </div>

    <!-- Section 2: Real-Time Detection State & Continuous Evidence -->
    <div class="grid-cols-2">
      <!-- Card A: Primary Detection Classification (T0-TX) -->
      <div class="card" style="border-left: 4px solid var(--state-t0); background: var(--bg-card);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">
            Subsea Disturbance Detection Pipeline
          </div>
          <span id="pipeline-status-badge" class="brand-badge" style="background: var(--bg-subtle); color: var(--text-muted); font-size: 0.72rem;">
            Checking Pipeline Bridge...
          </span>
        </div>

        <div style="display: flex; align-items: baseline; gap: 0.75rem; margin: 0.6rem 0 0.2rem 0;">
          <div id="detection-state-badge" style="font-size: 1.6rem; font-weight: 800; font-family: var(--font-mono); color: var(--state-t0);">
            T0: NOMINAL
          </div>
          <div id="detection-confidence-sub" style="font-size: 0.9rem; font-weight: 600; color: var(--text-muted);">
            Physical Confidence: --
          </div>
        </div>

        <div id="detection-rationale-text" style="font-size: 0.85rem; color: var(--text-main); margin-bottom: 0.6rem; min-height: 2.2rem; line-height: 1.4;">
          Awaiting live hardware frames or HIL decision records.
        </div>

        <div style="padding-top: 0.5rem; border-top: 1px solid var(--border-color); font-size: 0.78rem; color: var(--text-muted);">
          <strong>State Hierarchy:</strong> T0=Safe Ambient, T1=Uncorrelated Event, T2=Corroborated Alert, T3=Imminent Risk, TX=Link/Sensor Fault.
        </div>
      </div>

      <!-- Card B: Continuous Multimodal Evidence (C_P, C_A, R, U) -->
      <div class="card" style="border-left: 4px solid var(--accent); background: var(--bg-card);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">
            Continuous Fusion Gate Metrics
          </div>
          <span id="detection-quality-badge">
            ${renderQualityBadge("GOOD")}
          </span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin: 0.75rem 0;">
          <div style="text-align: center; padding: 0.5rem 0.25rem; background: var(--bg-subtle); border-radius: 6px;">
            <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700;" title="${TOOLTIPS.CP}">C_P (Physical)</div>
            <div id="metric-cp" style="font-size: 1.15rem; font-weight: 800; font-family: var(--font-mono); color: var(--accent); margin-top: 0.15rem;">--</div>
          </div>
          <div style="text-align: center; padding: 0.5rem 0.25rem; background: var(--bg-subtle); border-radius: 6px;">
            <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700;" title="${TOOLTIPS.CA}">C_A (Assoc)</div>
            <div id="metric-ca" style="font-size: 1.15rem; font-weight: 800; font-family: var(--font-mono); color: var(--state-t1); margin-top: 0.15rem;">--</div>
          </div>
          <div style="text-align: center; padding: 0.5rem 0.25rem; background: var(--bg-subtle); border-radius: 6px;">
            <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700;" title="${TOOLTIPS.R}">R (Reliability)</div>
            <div id="metric-r" style="font-size: 1.15rem; font-weight: 800; font-family: var(--font-mono); color: var(--state-t0); margin-top: 0.15rem;">--</div>
          </div>
          <div style="text-align: center; padding: 0.5rem 0.25rem; background: var(--bg-subtle); border-radius: 6px;">
            <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700;" title="${TOOLTIPS.U}">U (Uncertainty)</div>
            <div id="metric-u" style="font-size: 1.15rem; font-weight: 800; font-family: var(--font-mono); color: var(--state-tx); margin-top: 0.15rem;">--</div>
          </div>
        </div>

        <div style="padding-top: 0.5rem; border-top: 1px solid var(--border-color); font-size: 0.78rem; color: var(--text-muted);">
          Gated evidence bounds in [0.0, 1.0]. Generated mathematically by Subsea fusion inference.
        </div>
      </div>
    </div>

    <!-- Section 3: Physical Telemetry Sensor Channels (Genuine Available Inputs) -->
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 0.5rem;">
      <h3 style="font-size: 1rem; font-weight: 700; color: var(--text-main); margin: 0;">
        Physical Prototype Telemetry Channels (ESP32 Live Stream)
      </h3>
      <span style="font-size: 0.8rem; color: var(--text-muted);">
        Verified Channel Provenance: [PHYSICAL HARDWARE]
      </span>
    </div>

    <div class="grid-cols-4">
      <!-- Channel 1: Optical Laser Link LDR -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700;">OPTICAL LINK (GPIO 34)</span>
          ${renderProvenanceBadge("PHYSICAL")}
        </div>
        <div id="disp-ldr-badge" style="margin: 0.35rem 0;">
          <span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">STANDBY</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-main);">
          LDR Digital Flag: <strong id="disp-ldr-val">--</strong>
        </div>
        <div id="disp-ldr-desc" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          0 = Laser received, 1 = Beam broken
        </div>
      </div>

      <!-- Channel 2: Piezo Vibration Sensor -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700;">PIEZO VIBRATION (GPIO 27)</span>
          ${renderProvenanceBadge("PHYSICAL")}
        </div>
        <div id="disp-vib-badge" style="margin: 0.35rem 0;">
          <span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">STANDBY</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-main);">
          Vibration Flag: <strong id="disp-vib-val">--</strong>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          0 = Quiet background, 1 = Shock detected
        </div>
      </div>

      <!-- Channel 3: HC-SR04 Proximity Sensor -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700;">ULTRASONIC (GPIO 5/18)</span>
          ${renderProvenanceBadge("PHYSICAL")}
        </div>
        <div id="disp-dist-val" style="font-size: 1.3rem; font-weight: 800; margin: 0.25rem 0; font-family: var(--font-mono);">
          -- cm
        </div>
        <div id="disp-dist-zone" style="font-size: 0.8rem;">
          <span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">NO ECHO</span>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          Measured distance in air (80ms sample interval)
        </div>
      </div>

      <!-- Channel 4: Actuator & Alert Feedback -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700;">ACTUATOR STATUS</span>
          ${renderProvenanceBadge("PHYSICAL")}
        </div>
        <div style="display: flex; gap: 0.4rem; margin: 0.35rem 0;">
          <span id="disp-laser-pill" class="brand-badge" style="font-size: 0.7rem;">LASER: --</span>
          <span id="disp-buzzer-pill" class="brand-badge" style="font-size: 0.7rem;">BUZZER: --</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-main);">
          Alert Code: <strong id="disp-alert-val">--</strong>
        </div>
        <div id="disp-tx-status" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          Transmission: Inactive
        </div>
      </div>
    </div>

    <!-- Section 4: Secondary Replay Controls & Decision Stream Chart -->
    <div class="card">
      <div class="card-title">
        <span>Detection Timeline & Multimodal Evidence Stream</span>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <label for="detection-file-input" class="btn btn-secondary" style="cursor: pointer; font-size: 0.75rem; padding: 0.25rem 0.6rem; margin: 0;">
            📁 Load decisions.jsonl
          </label>
          <input type="file" id="detection-file-input" accept=".jsonl,.json" style="display: none;">
          <button id="btn-toggle-poll" class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.6rem;">
            ▶ Start Server Polling (2s)
          </button>
        </div>
      </div>
      <div id="detection-timeline-plot" class="chart-container" style="height: 320px;"></div>
    </div>

    <!-- Section 5: Bounded Detection Audit Event History -->
    <div class="card" style="margin-top: 0.5rem;">
      <div class="card-title">
        <span>Physical Hardware & Detection Event Audit Log</span>
        <span style="font-size: 0.75rem; color: var(--text-muted);">Chronological Ingestion Audit Trail</span>
      </div>

      <!-- Filter Bar -->
      <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 0.75rem; margin-top: 0.25rem;">
        <div id="detection-filter-pills" style="display: flex; flex-wrap: wrap; gap: 0.35rem;">
          <button class="filter-pill active" data-filter="ALL">ALL</button>
          <button class="filter-pill" data-filter="OPTICAL">OPTICAL</button>
          <button class="filter-pill" data-filter="SEISMIC">SEISMIC</button>
          <button class="filter-pill" data-filter="RADAR">RADAR</button>
          <button class="filter-pill" data-filter="SERIAL">SERIAL</button>
          <button class="filter-pill" data-filter="SYSTEM">SYSTEM</button>
        </div>

        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <input type="text" id="detection-search-input" placeholder="Search event logs..." class="text-input" style="font-size: 0.78rem; padding: 0.25rem 0.55rem; width: 180px; border-radius: 4px;">
          <button id="btn-clear-detection-events" class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.55rem;">Clear Log</button>
        </div>
      </div>

      <div class="table-container" style="max-height: 240px; overflow-y: auto; margin-top: 0.5rem;">
        <table id="detection-events-table">
          <thead>
            <tr>
              <th style="width: 120px;">Timestamp</th>
              <th style="width: 120px;">Subsystem</th>
              <th>Event Description</th>
            </tr>
          </thead>
          <tbody id="detection-events-tbody">
            <tr>
              <td colspan="3" style="text-align: center; color: var(--text-muted);">No hardware detection events logged yet. Connect ESP32 above to begin stream.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Initialize Hardware Controller
  initHardwareSerial(container);

  // Check Pipeline Bridge
  checkPipelineBridge();

  // Setup Drag & Drop and File Loaders
  setupFileHandlers();

  // Setup Server Polling
  setupPolling();

  // Setup Freshness Timer
  startFreshnessMonitor();

  // Setup Event Filtering
  setupEventFiltering();

  // Render initial blank / standby plot
  renderDetectionTimelinePlot();

  // Load existing decisions if available
  fetch("hil/decisions.jsonl")
    .then((r) => (r.ok ? r.text() : null))
    .then((text) => {
      if (text && loadedDecisions.length === 0) {
        parseAndDisplayDecisions(text, "Default Decision Log");
      }
    })
    .catch(() => {});
}

/**
 * Checks if Python Subsea pipeline bridge endpoint (/api/status) is reachable.
 */
async function checkPipelineBridge() {
  const badge = document.getElementById("pipeline-status-badge");
  const isHealthy = await pipelineBridge.checkHealth();
  if (badge) {
    if (isHealthy) {
      badge.textContent = "🟢 Python Pipeline Online";
      badge.style.color = "var(--state-t0)";
      telemetryBuffer.addEvent("SYSTEM", "Connected to Python Subsea inference backend.", "safe");
    } else {
      badge.textContent = "🟡 Static Web Mode";
      badge.style.color = "var(--state-t1)";
    }
  }
}

/**
 * Initializes the Web Serial Controller for Detection page.
 */
function initHardwareSerial(container) {
  const connectBtn = document.getElementById("btn-serial-connect");
  const disconnectBtn = document.getElementById("btn-serial-disconnect");
  const startTxBtn = document.getElementById("btn-serial-start-tx");
  const stopTxBtn = document.getElementById("btn-serial-stop-tx");
  const exportRawBtn = document.getElementById("btn-export-raw-jsonl");
  const clearEventsBtn = document.getElementById("btn-clear-detection-events");
  const baudSelect = document.getElementById("select-serial-baud");
  const resetEspBtn = document.getElementById("btn-serial-reset-esp");
  const mismatchRebootBtn = document.getElementById("btn-mismatch-reboot");
  const autoSwitchBaudBtn = document.getElementById("btn-auto-switch-baud");
  const baudMismatchBanner = document.getElementById("baud-mismatch-banner");
  const baudMismatchText = document.getElementById("baud-mismatch-text");

  // Restore saved baud preference if present
  if (baudSelect) {
    const savedBaud = localStorage.getItem("abysslink_serial_baud");
    if (savedBaud) baudSelect.value = savedBaud;
    baudSelect.addEventListener("change", (e) => {
      localStorage.setItem("abysslink_serial_baud", e.target.value);
    });
  }

  serialController = new HardwareSerialController({
    onPacket: handleIncomingSensorPacket,
    onAck: handleIncomingAckPacket,
    onStateChange: handleSerialStateChange,
    onLog: (lvl, msg) => {
      telemetryBuffer.addEvent("SERIAL", msg, lvl);
      renderDetectionEventLog();
    },
    onBaudMismatch: ({ currentBaud, suggestedBaud, sample }) => {
      if (baudMismatchBanner && baudMismatchText) {
        baudMismatchText.innerHTML = `Connected at <strong>${currentBaud} baud</strong>, but receiving framing noise (<code>${sample}</code>). Your ESP32 is likely running at <strong>${suggestedBaud} baud</strong>.`;
        if (autoSwitchBaudBtn) {
          autoSwitchBaudBtn.textContent = `⚡ Switch to ${suggestedBaud} Baud & Reconnect`;
          autoSwitchBaudBtn.dataset.targetBaud = String(suggestedBaud);
        }
        baudMismatchBanner.style.display = "block";
      }
    },
  });

  if (connectBtn) {
    connectBtn.addEventListener("click", async () => {
      try {
        const baud = parseInt(baudSelect?.value || "115200", 10);
        if (baudMismatchBanner) baudMismatchBanner.style.display = "none";
        await serialController.connect({ baudRate: baud });
      } catch (_) {}
    });
  }

  if (disconnectBtn) {
    disconnectBtn.addEventListener("click", async () => {
      if (baudMismatchBanner) baudMismatchBanner.style.display = "none";
      await serialController.disconnect();
    });
  }

  const handleRebootClick = async () => {
    if (serialController) {
      await serialController.resetEsp();
    }
  };
  if (resetEspBtn) resetEspBtn.addEventListener("click", handleRebootClick);
  if (mismatchRebootBtn) mismatchRebootBtn.addEventListener("click", handleRebootClick);

  if (autoSwitchBaudBtn) {
    autoSwitchBaudBtn.addEventListener("click", async () => {
      const targetBaud = parseInt(autoSwitchBaudBtn.dataset.targetBaud || "9600", 10);
      if (baudSelect) baudSelect.value = String(targetBaud);
      localStorage.setItem("abysslink_serial_baud", String(targetBaud));
      if (baudMismatchBanner) baudMismatchBanner.style.display = "none";

      telemetryBuffer.addEvent("SERIAL", `Auto-switching baud rate from ${serialController.currentBaudRate} to ${targetBaud}...`, "warning");
      await serialController.disconnect();
      setTimeout(async () => {
        try {
          await serialController.connect({ baudRate: targetBaud });
        } catch (_) {}
      }, 250);
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
      renderDetectionEventLog();
    });
  }
}

/**
 * Handles Web Serial connection state changes on Detection page.
 */
function handleSerialStateChange(state, detail) {
  const badge = document.getElementById("serial-status-badge");
  const dot = document.getElementById("hardware-live-dot");
  const modeBadge = document.getElementById("detection-mode-badge");
  const connectBtn = document.getElementById("btn-serial-connect");
  const disconnectBtn = document.getElementById("btn-serial-disconnect");
  const startTxBtn = document.getElementById("btn-serial-start-tx");
  const stopTxBtn = document.getElementById("btn-serial-stop-tx");
  const resetEspBtn = document.getElementById("btn-serial-reset-esp");
  const baudStatEl = document.getElementById("stat-baud-rate");
  const baudMismatchBanner = document.getElementById("baud-mismatch-banner");

  if (baudStatEl && serialController) {
    baudStatEl.textContent = serialController.currentBaudRate.toLocaleString();
  }

  if (badge) {
    badge.textContent = state;
    if (state === "CONNECTED") {
      badge.style.color = "var(--state-t0)";
      badge.style.background = "rgba(16, 185, 129, 0.15)";
      if (dot) {
        dot.className = "pulse-dot live";
      }
      if (modeBadge) {
        modeBadge.textContent = "🟢 PHYSICAL HARDWARE ACTIVE";
        modeBadge.style.color = "var(--state-t0)";
        modeBadge.style.background = "rgba(16, 185, 129, 0.15)";
      }
    } else if (state === "CONNECTING") {
      badge.style.color = "var(--state-t1)";
      badge.style.background = "rgba(245, 158, 11, 0.15)";
      if (dot) dot.className = "pulse-dot warning";
    } else if (state === "ERROR") {
      badge.style.color = "var(--state-t3)";
      badge.style.background = "rgba(239, 68, 68, 0.15)";
      if (dot) dot.className = "pulse-dot urgent";
    } else {
      badge.style.color = "var(--text-muted)";
      badge.style.background = "var(--bg-hover)";
      if (dot) {
        dot.className = "pulse-dot";
        dot.style.backgroundColor = "var(--text-muted)";
      }
      if (modeBadge) {
        modeBadge.textContent = "AWAITING PHYSICAL HARDWARE";
        modeBadge.style.color = "var(--text-muted)";
        modeBadge.style.background = "var(--bg-subtle)";
      }
      if (baudMismatchBanner) {
        baudMismatchBanner.style.display = "none";
      }
    }
  }

  if (connectBtn) connectBtn.disabled = state === "CONNECTED" || state === "CONNECTING";
  if (disconnectBtn) disconnectBtn.disabled = state !== "CONNECTED";
  if (resetEspBtn) resetEspBtn.disabled = state !== "CONNECTED";
  if (startTxBtn) startTxBtn.disabled = state !== "CONNECTED" || isTransmissionActive;
  if (stopTxBtn) stopTxBtn.disabled = state !== "CONNECTED" || !isTransmissionActive;
}

/**
 * Handles incoming sensor packet from physical ESP32.
 */
async function handleIncomingSensorPacket(rawObj, rawLine) {
  const packet = validateSensorPacket(rawObj);
  if (!packet) {
    telemetryBuffer.addEvent("SERIAL", "Malformed sensor frame rejected.", "warning");
    return;
  }

  lastPacketTimestamp = Date.now();

  // 1. Buffer raw packet
  telemetryBuffer.addRawPacket(packet, rawLine);

  // 2. Detect transitions
  detectHardwareTransitions(lastTelemetry, packet);
  lastTelemetry = { ...packet };
  isTransmissionActive = packet.transmission;

  // 3. Update hardware sensor cards
  updatePhysicalCards(packet);

  // 4. Update Stats bar
  updateStatsBar();

  // 5. Route to backend pipeline bridge
  const pipelineResult = await pipelineBridge.processPacket(packet);
  if (pipelineResult) {
    loadedDecisions.push(pipelineResult);
    updateDetectionDecision(pipelineResult);
    renderDetectionTimelinePlot();
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
  renderDetectionEventLog();
}

/**
 * Detects hardware sensor state transitions and records to audit log.
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

  renderDetectionEventLog();
}

/**
 * Updates the 4 physical telemetry cards.
 */
function updatePhysicalCards(pkt) {
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
 * Updates the live Detection classification and C_P, C_A, R, U cards.
 */
function updateDetectionDecision(res) {
  const decBadge = document.getElementById("detection-state-badge");
  const confSub = document.getElementById("detection-confidence-sub");
  const ratText = document.getElementById("detection-rationale-text");

  const cpEl = document.getElementById("metric-cp");
  const caEl = document.getElementById("metric-ca");
  const rEl = document.getElementById("metric-r");
  const uEl = document.getElementById("metric-u");

  if (decBadge) {
    decBadge.innerHTML = renderBadge(res.decision);
    decBadge.style.fontSize = "1.6rem";
    decBadge.style.fontWeight = "800";
  }
  if (confSub) {
    confSub.textContent = `Physical Confidence: ${((res.physical_confidence || 0) * 100).toFixed(0)}%`;
  }
  if (ratText) {
    ratText.textContent = res.rationale || "Evaluated by Subsea evidence fusion engine.";
  }

  if (cpEl) cpEl.textContent = res.physical_confidence !== undefined ? res.physical_confidence.toFixed(3) : "--";
  if (caEl) caEl.textContent = res.association_confidence !== undefined ? res.association_confidence.toFixed(3) : "--";
  if (rEl) rEl.textContent = res.reliability !== undefined ? res.reliability.toFixed(3) : "--";
  if (uEl) uEl.textContent = res.uncertainty !== undefined ? res.uncertainty.toFixed(3) : "--";
}

/**
 * Updates stats in the serial link bar.
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
 * Monitors data freshness every second.
 */
function startFreshnessMonitor() {
  if (freshnessInterval) clearInterval(freshnessInterval);
  freshnessInterval = setInterval(() => {
    const badge = document.getElementById("sample-freshness-badge");
    if (!badge) return;

    if (!lastPacketTimestamp) {
      badge.textContent = "Freshness: No samples yet";
      badge.style.color = "var(--text-muted)";
      return;
    }

    const elapsedMs = Date.now() - lastPacketTimestamp;
    const elapsedSec = (elapsedMs / 1000).toFixed(1);

    if (elapsedMs < 1000) {
      badge.textContent = `🟢 Live (<1s ago)`;
      badge.style.color = "var(--state-t0)";
    } else if (elapsedMs < 3000) {
      badge.textContent = `🟡 Delay: ${elapsedSec}s`;
      badge.style.color = "var(--state-t1)";
    } else {
      badge.textContent = `⚠️ Stale (${elapsedSec}s ago)`;
      badge.style.color = "var(--state-t3)";
    }
  }, 1000);
}

/**
 * Sets up event log filtering and text search.
 */
function setupEventFiltering() {
  const pills = document.querySelectorAll("#detection-filter-pills .filter-pill");
  pills.forEach((pill) => {
    pill.onclick = () => {
      pills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      activeEventFilter = pill.dataset.filter || "ALL";
      renderDetectionEventLog();
    };
  });

  const searchInput = document.getElementById("detection-search-input");
  if (searchInput) {
    searchInput.oninput = (e) => {
      eventSearchTerm = e.target.value.toLowerCase().trim();
      renderDetectionEventLog();
    };
  }
}

/**
 * Renders the chronological detection audit log.
 */
function renderDetectionEventLog() {
  const tbody = document.getElementById("detection-events-tbody");
  if (!tbody) return;

  let filtered = telemetryBuffer.events;

  if (activeEventFilter !== "ALL") {
    filtered = filtered.filter((ev) => ev.category === activeEventFilter);
  }

  if (eventSearchTerm) {
    filtered = filtered.filter(
      (ev) =>
        ev.message.toLowerCase().includes(eventSearchTerm) ||
        ev.category.toLowerCase().includes(eventSearchTerm) ||
        ev.timestamp.toLowerCase().includes(eventSearchTerm)
    );
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No matching detection events found.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered
    .map((ev) => {
      let color = "var(--text-main)";
      if (ev.level === "danger") color = "var(--state-t3)";
      if (ev.level === "warning") color = "var(--state-t1)";
      if (ev.level === "safe") color = "var(--state-t0)";

      return `
      <tr>
        <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">${ev.timestamp}</td>
        <td><span class="brand-badge" style="font-size: 0.72rem;">${ev.category}</span></td>
        <td style="color: ${color}; font-size: 0.85rem;">${ev.message}</td>
      </tr>
    `;
    })
    .join("");
}

/**
 * Renders the Detection State & Evidence timeline plot.
 */
function renderDetectionTimelinePlot() {
  const plotEl = document.getElementById("detection-timeline-plot");
  if (!plotEl) return;

  const records = loadedDecisions.slice(-60);
  const times = records.map((d) => d.timestamp);
  const decisions = records.map((d) => d.decision);
  const cp = records.map((d) => d.physical_confidence || 0);
  const ca = records.map((d) => d.association_confidence || 0);
  const r = records.map((d) => d.reliability || 0);
  const u = records.map((d) => d.uncertainty || 0);

  const stateColors = {
    T0: "#10b981",
    T1: "#f59e0b",
    T2: "#f97316",
    T3: "#ef4444",
    TX: "#8b5cf6",
  };

  const traceState = {
    x: times,
    y: decisions,
    mode: "lines+markers",
    name: "Detection State",
    line: { shape: "hv", color: "#64748b", width: 2 },
    marker: {
      size: 7,
      color: decisions.map((d) => stateColors[d] || "#3b82f6"),
    },
    yaxis: "y2",
  };

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
    line: { color: "#fbbf24", width: 1.5, dash: "dot" },
  };

  const traceR = {
    x: times,
    y: r,
    name: "R (Reliability)",
    line: { color: "#34d399", width: 1.5 },
  };

  const traceU = {
    x: times,
    y: u,
    name: "U (Uncertainty)",
    line: { color: "#c084fc", width: 1.5, dash: "dash" },
  };

  buildPlot("detection-timeline-plot", [traceCp, traceCa, traceR, traceU, traceState], {
    xaxis: { title: "Time (s)" },
    yaxis: { title: "Metric [0.0, 1.0]", range: [-0.05, 1.05] },
    yaxis2: {
      title: "Decision State",
      overlaying: "y",
      side: "right",
      categoryorder: "array",
      categoryarray: ["T0", "T1", "T2", "T3", "TX"],
    },
    legend: { orientation: "h", y: -0.25, font: { size: 10 } },
    margin: { l: 50, r: 60, t: 30, b: 50 },
  });
}

function setupFileHandlers() {
  const fileInput = document.getElementById("detection-file-input");
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        const file = e.target.files[0];
        const reader = new FileReader();
        reader.onload = (evt) => {
          parseAndDisplayDecisions(evt.target.result, file.name);
          telemetryBuffer.addEvent("SYSTEM", `Loaded decision log file: ${file.name}`, "info");
          renderDetectionEventLog();
        };
        reader.readAsText(file);
      }
    });
  }
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

  if (records.length === 0) return;

  loadedDecisions = records;
  currentRunMeta = { source: sourceName, count: records.length };
  const latest = records[records.length - 1];
  updateDetectionDecision(latest);
  renderDetectionTimelinePlot();
}

function setupPolling() {
  const pollBtn = document.getElementById("btn-toggle-poll");
  if (!pollBtn) return;

  async function pollLatest() {
    try {
      const ptrResp = await fetch("hil/latest.json?t=" + Date.now());
      if (!ptrResp.ok) return;
      const ptr = await ptrResp.json();

      const decResp = await fetch("hil/decisions.jsonl?t=" + Date.now());
      if (decResp.ok) {
        const text = await decResp.text();
        parseAndDisplayDecisions(text, ptr.run_id || "Live Polled Run");
      }
    } catch (e) {
      console.warn("Polling error:", e);
    }
  }

  pollBtn.addEventListener("click", () => {
    isPollingActive = !isPollingActive;
    if (isPollingActive) {
      pollBtn.textContent = "⏸ Pause Polling";
      pollBtn.classList.remove("btn-secondary");
      pollBtn.classList.add("btn-primary");
      pollLatest();
      pollInterval = setInterval(pollLatest, 2000);
    } else {
      pollBtn.textContent = "▶ Start Server Polling (2s)";
      pollBtn.classList.remove("btn-primary");
      pollBtn.classList.add("btn-secondary");
      clearInterval(pollInterval);
      pollInterval = null;
    }
  });
}

/**
 * Clean lifecycle teardown when navigating away from Detection page.
 */
export function cleanup() {
  if (freshnessInterval) {
    clearInterval(freshnessInterval);
    freshnessInterval = null;
  }
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
    isPollingActive = false;
  }
}
