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
import {
  renderKPI,
  renderBadge,
  renderWarningBadge,
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
  BENCHTOP_DISCLAIMERS,
} from "../hardware_adapter.js";

// Benchmark Evaluation Scorecard Data from artifacts/digital_twin/evaluation_report.md
const BENCHMARK_EVAL_SCORECARD = [
  {
    scenario: "1. Normal Operation",
    behavior: "Zero False Alarms",
    metric: "False Positive Rate",
    value: "0.0%",
    status: "PASS",
    details: "100 frames evaluated. Clean W0 baseline maintained with zero alarm leakage."
  },
  {
    scenario: "2. Approaching Vessel",
    behavior: "Advance Watch (W1->W2)",
    metric: "W1 Latency / W2 Latency",
    value: "6.0s / 6.6s",
    status: "PASS",
    details: "Watch triggered at 60m route perimeter, advisory escalated on sustained approach before corridor intrusion."
  },
  {
    scenario: "3. Low-Level Vibration",
    behavior: "Detect Subtle Anomaly",
    metric: "Latency to W1/W2",
    value: "0.3s",
    status: "PASS",
    details: "Subtle vibration anomaly detected at 0.3s without false escalation to W3 strike."
  },
  {
    scenario: "4. Increasing Disturbance",
    behavior: "Escalation to Urgent (W3)",
    metric: "W3 Latency",
    value: "1.5s",
    status: "PASS",
    details: "Clean progressive escalation tracking ramped strain and acoustic RMS."
  },
  {
    scenario: "5. Severe Disturbance",
    behavior: "Rapid Strike Warning (W3)",
    metric: "Immediate W3 Latency",
    value: "1.5s",
    status: "PASS",
    details: "Immediate multi-sensor corroboration triggers urgent alarm in 1.5s."
  },
  {
    scenario: "6. Sensor Degradation",
    behavior: "Fail-Safe Trip to WX",
    metric: "WX Trigger Latency",
    value: "10.2s",
    status: "PASS",
    details: "Stale and missing telemetry safely trips WX rather than masking faults as nominal."
  },
  {
    scenario: "7. Disturbance Recovery",
    behavior: "Return to Normal (W0)",
    metric: "De-escalation Latency",
    value: "20.1s",
    status: "PASS",
    details: "Exponential decay followed by staged de-escalation back to baseline."
  }
];

const SCENARIO_METADATA = {
  normal_operation: {
    title: "1. Normal Operating Conditions",
    states: "W0 (Normal Baseline)",
    duration: "30.0s (100 frames)",
    desc: "Evaluates ambient seafloor baseline with undisturbed acoustic signals, zero vessel encroachment, and nominal cable strain. Target: 0.0% false alarm rate.",
    badgeClass: "W0",
  },
  approaching_vessel: {
    title: "2. Approaching Simulated Vessel",
    states: "W0 ➔ W1 ➔ W2 ➔ W3",
    duration: "30.0s (100 frames)",
    desc: "Vessel navigates across subsea cable route. Crosses 60m threshold at t=6.0s (triggers W1 Watch), sustains approach into W2 Advisory, and enters 15m danger corridor.",
    badgeClass: "W2",
  },
  low_level_vibration: {
    title: "3. Low-Level Vibration Anomaly",
    states: "W0 ➔ W1 ➔ W2",
    duration: "18.0s (60 frames)",
    desc: "Simulates subtle acoustic and mechanical vibration anomaly without vessel presence. Rapidly detected at t=0.3s without spuriously escalating to W3 strike alarm.",
    badgeClass: "W1",
  },
  increasing_disturbance: {
    title: "4. Increasing Disturbance",
    states: "W2 ➔ W3",
    duration: "15.0s (50 frames)",
    desc: "Monitors ramping acoustic RMS and escalating mechanical strain tension, triggering clean W2 Advisory to W3 Urgent strike transition in 1.5s.",
    badgeClass: "W3",
  },
  severe_disturbance: {
    title: "5. Severe Cable Disturbance",
    states: "W3 (Urgent Strike)",
    duration: "15.0s (50 frames)",
    desc: "Direct multi-sensor impact: immediate DAS acoustic surge, heavy mechanical strain (>250 με), and vessel corridor entry triggering instant W3 alert in 1.5s.",
    badgeClass: "W3",
  },
  sensor_degradation: {
    title: "6. Sensor Degradation & Fail-Safe",
    states: "W0 ➔ WX (Fail-Safe)",
    duration: "21.0s (70 frames)",
    desc: "Simulates hardware telemetry packet dropouts, stale timestamps, and contradictory sensor data. Safely trips to fail-safe state WX at t=10.2s without masking faults.",
    badgeClass: "WX",
  },
  recovery: {
    title: "7. Disturbance Recovery",
    states: "W3 ➔ W2 ➔ W1 ➔ W0",
    duration: "30.0s (100 frames)",
    desc: "Evaluates post-strike exponential disturbance decay. Follows verified hysteresis logic to de-escalate back to nominal W0 baseline within 20.1s.",
    badgeClass: "W0",
  },
};

// Event log filter state & stepping lock
let activeEventFilter = "ALL";
let eventSearchTerm = "";
let isSteppingInProgress = false;

// Session singletons
let serialController = null;
const telemetryBuffer = new TelemetryBuffer(5000);
const pipelineBridge = new PipelineBridgeClient("");

let pollInterval = null;
let isPollingActive = false;
let loadedDecisions = [];
let currentRunMeta = null;
let isTransmissionActive = false;

// Digital Twin & Early Warning State
let currentOperatingMode = "HYBRID_DEMO"; // "HYBRID_DEMO" or "PHYSICAL_ONLY"
let activeTwinScenario = "approaching_vessel";
let twinSimTimer = null;
let twinPreloadedScenarios = null;
let currentTwinStepIndex = 0;
let currentTwinData = {
  elapsed_s: 0.0,
  phase: "STANDBY",
  warning_state: "W0",
  warning_confidence: 0.95,
  warning_explanation: "Nominal conditions: all monitored channels within normal parameters.",
  triggering_indicators: [],
  data_quality: "GOOD",
  vibration_rms: 0.08,
  vessel_distance_m: 80.0,
  vessel_x: 80.0,
  vessel_y: -40.0,
  vessel_speed: 3.5,
  cable_strain: 10.0,
  temperature: 4.0,
  cable_health: 0.98,
  disturbance_state: "T0",
  history: [],
};

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

  // Load preloaded digital twin scenarios in background if not already loaded
  if (!twinPreloadedScenarios) {
    try {
      const resp = await fetch("data/digital_twin_scenarios.json");
      if (resp.ok) {
        twinPreloadedScenarios = await resp.json();
      }
    } catch (_) {}
  }

  container.innerHTML = `
    <!-- Top Mandatory Scientific Notice -->
    <div class="card" style="border-left: 4px solid var(--state-t1); margin-bottom: 1rem;">
      <div style="font-weight: 700; color: var(--state-t1); margin-bottom: 0.25rem;">
        Hardware-in-the-Loop & Digital Twin Scientific Integrity Notice
      </div>
      <p style="font-size: 0.9rem; margin: 0; color: var(--text-color); line-height: 1.5;">
        <strong>The accelerometer is simulated; this validates integration and decision logic under real timing and link faults, not subsea sensing physics.</strong>
      </p>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.25rem;">
        <div>📡 <strong>Physical ESP32:</strong> USB serial telemetry (115,200 baud, 300 ms packet interval).</div>
        <div>🌐 <strong>Digital Twin:</strong> Mathematical benchmark models for DAS acoustics, vessel proximity, temperature, and cable strain.</div>
        <div>⚖️ <strong>Provenance Separation:</strong> Physical and simulated data carry immutable source provenance tags and are never mixed silently.</div>
      </div>
    </div>

    <!-- Operating Mode Selector & Prominent Warning Banner -->
    <div class="card" style="margin-bottom: 1rem; border-color: rgba(56, 189, 248, 0.4); padding: 1rem 1.25rem;">
      <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 1rem;">
        <div>
          <div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">
            Operating Mode
          </div>
          <div style="font-size: 1.15rem; font-weight: 700; color: var(--text-color); margin-top: 0.2rem;">
            Current Mode: <span id="current-mode-label" style="color: var(--brand-blue);">${currentOperatingMode === "HYBRID_DEMO" ? "🌐 HYBRID DIGITAL TWIN" : "🔒 PHYSICAL-ONLY"}</span>
          </div>
        </div>

        <div style="display: flex; gap: 0.5rem;">
          <button id="btn-mode-hybrid" class="btn ${currentOperatingMode === "HYBRID_DEMO" ? "btn-primary" : "btn-secondary"}" style="font-size: 0.85rem;">
            🌐 Hybrid Digital Twin Mode
          </button>
          <button id="btn-mode-physical" class="btn ${currentOperatingMode === "PHYSICAL_ONLY" ? "btn-primary" : "btn-secondary"}" style="font-size: 0.85rem;">
            🔒 Physical-Only Mode
          </button>
        </div>
      </div>

      <!-- Prominent Warning Banner based on active mode -->
      <div id="mode-provenance-banner" style="margin-top: 0.75rem; padding: 0.6rem 0.9rem; border-radius: var(--radius); font-size: 0.85rem; line-height: 1.4; ${
        currentOperatingMode === "HYBRID_DEMO"
          ? "background: rgba(234, 179, 8, 0.12); border-left: 4px solid var(--state-t2); color: var(--text-color);"
          : "background: rgba(56, 189, 248, 0.12); border-left: 4px solid var(--brand-blue); color: var(--text-color);"
      }">
        ${
          currentOperatingMode === "HYBRID_DEMO"
            ? "<strong>⚠️ SIMULATED DATA ACTIVE:</strong> Digital Twin software channels (DAS acoustics, vessel kinematics, cable strain, benthic temperature) are synthesized. These benchmark channels are explicitly labeled and do not represent physical seabed measurements."
            : "<strong>🔒 PHYSICAL-ONLY MODE:</strong> Simulated channels are completely isolated and excluded. Decisions use only verified physical ESP32 telemetry, or report disconnected status."
        }
      </div>
    </div>

    <!-- Digital Twin Scenario Runner Card -->
    <div class="card" style="margin-bottom: 1.5rem; border-color: rgba(168, 85, 247, 0.4);">
      <div class="card-title">
        <span style="display: flex; align-items: center; gap: 0.5rem;">
          <span id="sim-status-dot" class="pulse-dot" style="background-color: var(--text-muted);" title="Simulation Engine Status"></span>
          <span>🧪 Digital Twin Simulation & Scenario Controls</span>
          <span id="twin-phase-badge" class="brand-badge" style="background: rgba(168, 85, 247, 0.2); color: #c084fc;">
            PHASE: STANDBY
          </span>
        </span>
        <span id="twin-time-badge" class="brand-badge" style="background: var(--bg-hover); color: var(--text-muted); font-family: var(--font-mono);">
          t = 0.0s
        </span>
      </div>

      <!-- Scenario Dropdown & Simulation Buttons -->
      <div style="display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin-top: 0.75rem;">
        <label style="font-size: 0.85rem; font-weight: 600; color: var(--text-muted);" for="select-twin-scenario">
          Scenario:
        </label>
        <select id="select-twin-scenario" style="padding: 0.45rem 0.8rem; background: var(--bg-card); color: var(--text-color); border: 1px solid var(--border-color); border-radius: var(--radius); font-size: 0.85rem; font-weight: 600;">
          <option value="normal_operation" ${activeTwinScenario === "normal_operation" ? "selected" : ""}>1. Normal Operating Conditions (W0)</option>
          <option value="approaching_vessel" ${activeTwinScenario === "approaching_vessel" ? "selected" : ""}>2. Approaching Simulated Vessel (W1 -> W2 -> W3)</option>
          <option value="low_level_vibration" ${activeTwinScenario === "low_level_vibration" ? "selected" : ""}>3. Low-Level Vibration Anomaly (W1 -> W2)</option>
          <option value="increasing_disturbance" ${activeTwinScenario === "increasing_disturbance" ? "selected" : ""}>4. Increasing Disturbance (W2 -> W3)</option>
          <option value="severe_disturbance" ${activeTwinScenario === "severe_disturbance" ? "selected" : ""}>5. Severe Cable Disturbance (W3 Urgent)</option>
          <option value="sensor_degradation" ${activeTwinScenario === "sensor_degradation" ? "selected" : ""}>6. Sensor Degradation & Fail-Safe (WX)</option>
          <option value="recovery" ${activeTwinScenario === "recovery" ? "selected" : ""}>7. Disturbance Recovery (W3 -> W0)</option>
        </select>

        <button id="btn-twin-run" class="btn btn-primary" style="font-size: 0.85rem;">
          ▶ Run Simulation
        </button>
        <button id="btn-twin-step" class="btn btn-secondary" style="font-size: 0.85rem;">
          ⏭ Step Frame (0.3s)
        </button>
        <button id="btn-twin-reset" class="btn btn-secondary" style="font-size: 0.85rem;">
          🔄 Reset to Baseline
        </button>

        <div style="flex: 1;"></div>

        <button id="btn-run-all-eval" class="btn btn-secondary" style="font-size: 0.85rem;">
          📊 View Scenario Evaluation Report
        </button>
      </div>

      <!-- Active Scenario Synopsis Box -->
      <div id="scenario-synopsis-box" style="margin-top: 0.75rem; padding: 0.75rem 1rem; background: var(--bg-subtle); border: 1px solid var(--border-color); border-radius: var(--radius);">
        <!-- Populated dynamically by updateScenarioSynopsis() -->
      </div>
    </div>

    <!-- Dual Inference KPI Cards: Early Warning vs Disturbance Classification -->
    <div class="grid-cols-2" style="margin-bottom: 1.5rem;">
      <!-- Left Card: Independent Early Warning State (W0-WX) -->
      <div class="card" style="border-left: 4px solid var(--brand-blue); background: var(--bg-card);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">
            Multi-Sensor Early Warning Engine
          </div>
          <span id="early-warning-quality-badge">
            ${renderQualityBadge(currentTwinData.data_quality)}
          </span>
        </div>

        <div style="display: flex; align-items: baseline; gap: 0.75rem; margin: 0.6rem 0 0.3rem 0;">
          <div id="early-warning-state-badge" style="font-size: 1.5rem; font-weight: 800; font-family: var(--font-mono); color: var(--state-t0);">
            W0: NORMAL
          </div>
          <div id="early-warning-confidence" style="font-size: 0.95rem; font-weight: 600; color: var(--text-muted);">
            Confidence: 95%
          </div>
        </div>

        <div id="early-warning-explanation" style="font-size: 0.85rem; color: var(--text-color); margin-bottom: 0.6rem; min-height: 2.2rem; line-height: 1.4;">
          Nominal conditions: all monitored channels within normal parameters.
        </div>

        <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;">
          Triggering Indicators:
        </div>
        <div id="early-warning-indicators" style="display: flex; flex-wrap: wrap; gap: 0.35rem; min-height: 1.5rem;">
          <span class="brand-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">None (Ambient Baseline)</span>
        </div>
      </div>

      <!-- Right Card: Pipeline Disturbance Classification (T0-TX) -->
      <div class="card" style="border-left: 4px solid var(--state-t2); background: var(--bg-card);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">
            Subsea Disturbance Pipeline Classification
          </div>
          <span id="pipeline-status-badge" class="brand-badge" style="background: var(--bg-card); color: var(--text-muted); font-size: 0.75rem;">
            Checking Python Pipeline...
          </span>
        </div>

        <div style="display: flex; align-items: baseline; gap: 0.75rem; margin: 0.6rem 0 0.3rem 0;">
          <div id="pipeline-decision-badge" style="font-size: 1.5rem; font-weight: 800; font-family: var(--font-mono); color: var(--state-t0);">
            T0: NOMINAL
          </div>
          <div id="pipeline-gate-metrics" style="font-size: 0.85rem; color: var(--text-muted); font-family: var(--font-mono);">
            C_P: 0.12 | C_A: 0.10 | R: 0.95 | U: 0.08
          </div>
        </div>

        <div id="pipeline-rationale-text" style="font-size: 0.85rem; color: var(--text-color); margin-bottom: 0.6rem; min-height: 2.2rem; line-height: 1.4;">
          Safe ambient conditions. No acoustic signature or physical cable strike detected.
        </div>

        <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; margin-bottom: 0.25rem;">
          Classification Semantics:
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted);">
          Independent decision logic (T0=Nominal, T1=Uncorrelated, T2=Corroborated, T3=Severe Strike, TX=Fault).
        </div>
      </div>
    </div>

    <!-- Direct ESP32 USB Serial Hardware Control Card -->
    <div class="card" style="margin-bottom: 1.5rem; border-color: rgba(56, 189, 248, 0.4);">
      <div class="card-title">
        <span style="display: flex; align-items: center; gap: 0.5rem;">
          <span>🔌 Direct ESP32 Physical Prototype Link (Web Serial)</span>
          <span id="serial-status-badge" class="brand-badge" style="background: var(--bg-hover); color: var(--text-muted);">
            DISCONNECTED
          </span>
        </span>
        <span style="font-size: 0.8rem; color: var(--text-muted);">
          Optional Physical Acquisition
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

    <!-- Section Heading: Physical vs Digital Twin Channels -->
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.75rem;">
      <h3 style="font-size: 1rem; font-weight: 700; color: var(--text-color); margin: 0;">
        Physical Telemetry & Digital Twin Sensor Stream
      </h3>
      <span style="font-size: 0.8rem; color: var(--text-muted);">
        Immutable Data Provenance: [PHYSICAL] vs [SIMULATED]
      </span>
    </div>

    <!-- Multi-Sensor Telemetry Grid (8 Channels: 4 Physical + 4 Simulated) -->
    <div class="grid-cols-4" style="margin-bottom: 1.5rem;">
      <!-- Sensor Card 1: Optical Link LDR (Physical) -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">OPTICAL LINK</span>
          ${renderProvenanceBadge("PHYSICAL")}
        </div>
        <div id="disp-ldr-badge" style="margin: 0.4rem 0;">
          <span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">STANDBY</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-color);">
          Digital Flag: <strong id="disp-ldr-val">--</strong>
        </div>
        <div id="disp-ldr-desc" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          ESP32 laser photodiode
        </div>
      </div>

      <!-- Sensor Card 2: Piezo Vibration (Physical) -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">PIEZO VIBRATION</span>
          ${renderProvenanceBadge("PHYSICAL")}
        </div>
        <div id="disp-vib-badge" style="margin: 0.4rem 0;">
          <span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">STANDBY</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-color);">
          Vibration Flag: <strong id="disp-vib-val">--</strong>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          Hardware digital vibration switch
        </div>
      </div>

      <!-- Sensor Card 3: Ultrasonic Distance (Physical) -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">HC-SR04 PROXIMITY</span>
          ${renderProvenanceBadge("PHYSICAL")}
        </div>
        <div id="disp-dist-val" style="font-size: 1.3rem; font-weight: 700; margin: 0.3rem 0; font-family: var(--font-mono);">
          -- cm
        </div>
        <div id="disp-dist-zone" style="font-size: 0.8rem;">
          <span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">NO ECHO</span>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          Benchtop ultrasonic in air
        </div>
      </div>

      <!-- Sensor Card 4: Actuator & Buzzer (Physical) -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">ACTUATORS</span>
          ${renderProvenanceBadge("PHYSICAL")}
        </div>
        <div style="display: flex; gap: 0.4rem; margin: 0.4rem 0;">
          <span id="disp-laser-pill" class="brand-badge" style="font-size: 0.7rem;">LASER: --</span>
          <span id="disp-buzzer-pill" class="brand-badge" style="font-size: 0.7rem;">BUZZER: --</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-color);">
          Alert Code: <strong id="disp-alert-val">--</strong>
        </div>
        <div id="disp-tx-status" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          Transmission: Inactive
        </div>
      </div>

      <!-- Sensor Card 5: Virtual DAS Acoustic RMS (Simulated) -->
      <div class="card" style="border-top: 2px solid #eab308;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">DAS ACOUSTIC RMS</span>
          ${renderProvenanceBadge("SIMULATED")}
        </div>
        <div id="disp-das-rms" style="font-size: 1.3rem; font-weight: 700; margin: 0.3rem 0; font-family: var(--font-mono); color: var(--text-color);">
          0.08 units
        </div>
        <div id="disp-das-badge" style="font-size: 0.8rem;">
          <span class="state-badge T0" style="font-size: 0.75rem;">QUIET AMBIENT</span>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          Spectral acoustic band model
        </div>
      </div>

      <!-- Sensor Card 6: Virtual Vessel Proximity (Simulated) -->
      <div class="card" style="border-top: 2px solid #eab308;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">VESSEL PROXIMITY</span>
          ${renderProvenanceBadge("SIMULATED")}
        </div>
        <div id="disp-vessel-dist" style="font-size: 1.3rem; font-weight: 700; margin: 0.3rem 0; font-family: var(--font-mono); color: var(--text-color);">
          80.0 m
        </div>
        <div id="disp-vessel-speed" style="font-size: 0.85rem; color: var(--text-color);">
          Speed: <strong>3.5 m/s</strong> (Heading: 180°)
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          Kinematic trajectory to route
        </div>
      </div>

      <!-- Sensor Card 7: Cable Mechanical Strain (Simulated) -->
      <div class="card" style="border-top: 2px solid #eab308;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">MECHANICAL STRAIN</span>
          ${renderProvenanceBadge("SIMULATED")}
        </div>
        <div id="disp-cable-strain" style="font-size: 1.3rem; font-weight: 700; margin: 0.3rem 0; font-family: var(--font-mono); color: var(--text-color);">
          10.0 με
        </div>
        <div id="disp-strain-badge" style="font-size: 0.8rem;">
          <span class="state-badge T0" style="font-size: 0.75rem;">NORMAL TENSION</span>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          Optical fiber strain gauge
        </div>
      </div>

      <!-- Sensor Card 8: Seafloor Temp & Health Index (Simulated) -->
      <div class="card" style="border-top: 2px solid #eab308;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">BENTHIC TEMP & HEALTH</span>
          ${renderProvenanceBadge("SIMULATED")}
        </div>
        <div id="disp-cable-temp" style="font-size: 1.3rem; font-weight: 700; margin: 0.3rem 0; font-family: var(--font-mono); color: var(--text-color);">
          4.00 °C
        </div>
        <div id="disp-health-index" style="font-size: 0.85rem; color: var(--text-color);">
          Condition Index: <strong id="disp-health-val">0.98</strong>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
          DTS thermal trend & integrity
        </div>
      </div>
    </div>

    <!-- Live Digital Twin Visualizations: Cable Route Map & Signal Trends -->
    <div class="grid-cols-2" style="margin-bottom: 1.5rem;">
      <!-- Plot 1: Virtual Cable Route & Vessel Kinematics Map -->
      <div class="card">
        <div class="card-title">
          <span>Virtual Cable Route & Simulated Vessel Kinematics</span>
          <span class="brand-badge" style="background: rgba(234, 179, 8, 0.15); color: var(--state-t2);">SIMULATED MAP</span>
        </div>
        <div id="twin-map-plot" class="chart-container" style="height: 320px;"></div>
      </div>

      <!-- Plot 2: Multi-Sensor Telemetry & Early Warning Signal Trends -->
      <div class="card">
        <div class="card-title">
          <span>Multi-Sensor Waveforms & Early Warning State Trace</span>
          <span class="brand-badge">W0-W3 Evolution</span>
        </div>
        <div id="twin-trends-plot" class="chart-container" style="height: 320px;"></div>
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
        Generate offline mock runs with: <code>python scripts/run_abysslink_demo.py --scenario approaching_vessel</code>
      </div>
    </div>

    <!-- Active Inference View Container -->
    <div id="hil-content-view">
      <div class="empty-state">
        <h3>Awaiting Hardware Connection or HIL Log</h3>
        <p>Connect your ESP32 device via USB Serial above, start live server polling, or run a digital twin scenario.</p>
      </div>
    </div>

    <!-- Bounded Hardware Event Log Card (Filterable & Searchable) -->
    <div class="card" style="margin-top: 1.5rem;">
      <div class="card-title">
        <span>Hardware & Digital Twin Event Audit Log</span>
        <span style="font-size: 0.75rem; color: var(--text-muted);">Real-time Chronological Audit Trail</span>
      </div>

      <!-- Event Filter Bar & Search Input -->
      <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 0.75rem; margin-top: 0.25rem;">
        <div id="event-filter-pills" style="display: flex; flex-wrap: wrap; gap: 0.35rem;">
          <button class="filter-pill active" data-filter="ALL">ALL</button>
          <button class="filter-pill" data-filter="EARLY_WARN">EARLY_WARN</button>
          <button class="filter-pill" data-filter="OPTICAL">OPTICAL</button>
          <button class="filter-pill" data-filter="SEISMIC">SEISMIC</button>
          <button class="filter-pill" data-filter="RADAR">RADAR</button>
          <button class="filter-pill" data-filter="SERIAL">SERIAL</button>
          <button class="filter-pill" data-filter="MODE">MODE</button>
        </div>

        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <input type="text" id="event-search-input" placeholder="Search event logs..." class="text-input" style="font-size: 0.78rem; padding: 0.25rem 0.55rem; width: 180px; border-radius: 4px;">
          <button id="btn-clear-events" class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.55rem;">Clear Log</button>
        </div>
      </div>

      <div class="table-container" style="max-height: 240px; overflow-y: auto; margin-top: 0.5rem;">
        <table id="hil-events-table">
          <thead>
            <tr>
              <th style="width: 120px;">Timestamp</th>
              <th style="width: 120px;">Subsystem</th>
              <th>Event Description</th>
            </tr>
          </thead>
          <tbody id="hil-events-tbody">
            <tr>
              <td colspan="3" style="text-align: center; color: var(--text-muted);">No events logged yet. Connect hardware or run digital twin to begin.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Benchmark Evaluation Modal Container -->
    <div id="eval-modal-container"></div>
  `;

  // Initialize Hardware Serial Controller
  initHardwareSerial(container);

  // Initialize Digital Twin UI and Handlers
  initDigitalTwinUI(container);

  // Check Python Pipeline Bridge
  checkPipelineBridge();

  // Setup Drag & Drop and File Loaders
  setupFileHandlers();

  // Setup Server Polling
  setupPolling();

  // Initial plot render
  renderDigitalTwinPlots();

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
 * Renders the bounded event audit log with category filtering and text search.
 */
function renderEventLog() {
  const tbody = document.getElementById("hil-events-tbody");
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
    tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No matching events found.</td></tr>`;
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

function setupEventFiltering() {
  const pills = document.querySelectorAll("#event-filter-pills .filter-pill");
  pills.forEach((pill) => {
    pill.onclick = () => {
      pills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      activeEventFilter = pill.dataset.filter || "ALL";
      renderEventLog();
    };
  });

  const searchInput = document.getElementById("event-search-input");
  if (searchInput) {
    searchInput.oninput = (e) => {
      eventSearchTerm = e.target.value.toLowerCase().trim();
      renderEventLog();
    };
  }
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

/**
 * Initializes Digital Twin UI controls, mode switching, and scenario runners.
 */
function initDigitalTwinUI(container) {
  const btnHybrid = document.getElementById("btn-mode-hybrid");
  const btnPhysical = document.getElementById("btn-mode-physical");
  const modeLabel = document.getElementById("current-mode-label");
  const modeBanner = document.getElementById("mode-provenance-banner");

  const scenSelect = document.getElementById("select-twin-scenario");
  const btnRun = document.getElementById("btn-twin-run");
  const btnStep = document.getElementById("btn-twin-step");
  const btnReset = document.getElementById("btn-twin-reset");
  const btnEval = document.getElementById("btn-run-all-eval");

  function setMode(newMode) {
    currentOperatingMode = newMode;
    if (btnHybrid && btnPhysical) {
      if (newMode === "HYBRID_DEMO") {
        btnHybrid.className = "btn btn-primary";
        btnPhysical.className = "btn btn-secondary";
        if (modeLabel) {
          modeLabel.textContent = "🌐 HYBRID DIGITAL TWIN";
          modeLabel.style.color = "var(--state-t2)";
        }
        if (modeBanner) {
          modeBanner.style.background = "rgba(234, 179, 8, 0.12)";
          modeBanner.style.borderLeft = "4px solid var(--state-t2)";
          modeBanner.innerHTML = "<strong>⚠️ SIMULATED DATA ACTIVE:</strong> Digital Twin software channels (DAS acoustics, vessel kinematics, cable strain, benthic temperature) are synthesized. These benchmark channels are explicitly labeled and do not represent physical seabed measurements.";
        }
      } else {
        btnHybrid.className = "btn btn-secondary";
        btnPhysical.className = "btn btn-primary";
        if (modeLabel) {
          modeLabel.textContent = "🔒 PHYSICAL-ONLY";
          modeLabel.style.color = "var(--brand-blue)";
        }
        if (modeBanner) {
          modeBanner.style.background = "rgba(56, 189, 248, 0.12)";
          modeBanner.style.borderLeft = "4px solid var(--brand-blue)";
          modeBanner.innerHTML = "<strong>🔒 PHYSICAL-ONLY MODE:</strong> Simulated channels are completely isolated and excluded. Decisions use only verified physical ESP32 telemetry, or report disconnected status.";
        }
      }
    }
    telemetryBuffer.addEvent("MODE", `Operating mode switched to ${newMode}.`, "info");
    renderEventLog();
    pipelineBridge.setDigitalTwinScenario(activeTwinScenario, currentOperatingMode);
    stepDigitalTwinSimulation(0.0);
  }

  if (btnHybrid) btnHybrid.onclick = () => setMode("HYBRID_DEMO");
  if (btnPhysical) btnPhysical.onclick = () => setMode("PHYSICAL_ONLY");

  if (scenSelect) {
    scenSelect.onchange = (e) => {
      activeTwinScenario = e.target.value;
      currentTwinStepIndex = 0;
      currentTwinData.history = [];
      telemetryBuffer.addEvent("SCENARIO", `Configured scenario: ${activeTwinScenario}`, "info");
      renderEventLog();
      updateScenarioSynopsis(activeTwinScenario);
      pipelineBridge.setDigitalTwinScenario(activeTwinScenario, currentOperatingMode);
      stepDigitalTwinSimulation(0.0);
    };
  }

  if (btnRun) {
    btnRun.onclick = () => {
      const simStatusDot = document.getElementById("sim-status-dot");
      if (twinSimTimer) {
        clearInterval(twinSimTimer);
        twinSimTimer = null;
        btnRun.innerHTML = "▶ Run Simulation";
        btnRun.className = "btn btn-primary";
        if (simStatusDot) {
          simStatusDot.className = "pulse-dot";
          simStatusDot.style.backgroundColor = "var(--text-muted)";
        }
      } else {
        btnRun.innerHTML = "⏸ Pause Simulation";
        btnRun.className = "btn btn-secondary";
        if (simStatusDot) {
          simStatusDot.className = "pulse-dot live";
        }
        stepDigitalTwinSimulation(0.3);
        twinSimTimer = setInterval(() => stepDigitalTwinSimulation(0.3), 300);
      }
    };
  }

  if (btnStep) {
    btnStep.onclick = async () => {
      if (isSteppingInProgress) return;
      isSteppingInProgress = true;
      btnStep.disabled = true;

      try {
        if (twinSimTimer) {
          clearInterval(twinSimTimer);
          twinSimTimer = null;
          if (btnRun) {
            btnRun.innerHTML = "▶ Run Simulation";
            btnRun.className = "btn btn-primary";
          }
          const simStatusDot = document.getElementById("sim-status-dot");
          if (simStatusDot) {
            simStatusDot.className = "pulse-dot";
            simStatusDot.style.backgroundColor = "var(--text-muted)";
          }
        }
        await stepDigitalTwinSimulation(0.3);
      } finally {
        setTimeout(() => {
          isSteppingInProgress = false;
          if (btnStep) btnStep.disabled = false;
        }, 120);
      }
    };
  }

  if (btnReset) {
    btnReset.onclick = () => {
      if (twinSimTimer) {
        clearInterval(twinSimTimer);
        twinSimTimer = null;
        if (btnRun) {
          btnRun.innerHTML = "▶ Run Simulation";
          btnRun.className = "btn btn-primary";
        }
        const simStatusDot = document.getElementById("sim-status-dot");
        if (simStatusDot) {
          simStatusDot.className = "pulse-dot";
          simStatusDot.style.backgroundColor = "var(--text-muted)";
        }
      }
      currentTwinStepIndex = 0;
      currentTwinData.history = [];
      pipelineBridge.setDigitalTwinScenario(activeTwinScenario, currentOperatingMode);
      telemetryBuffer.addEvent("TWIN", `Simulation reset to t=0s (${activeTwinScenario}).`, "info");
      renderEventLog();
      updateScenarioSynopsis(activeTwinScenario);
      stepDigitalTwinSimulation(0.0);
    };
  }

  if (btnEval) {
    btnEval.onclick = () => {
      openEvaluationModal();
    };
  }

  // Initial scenario synopsis and event filtering setup
  updateScenarioSynopsis(activeTwinScenario);
  setupEventFiltering();
}

/**
 * Steps the digital twin simulation by dt seconds and refreshes UI.
 */
async function stepDigitalTwinSimulation(dt = 0.3) {
  let stepRecord = null;

  // Try live backend step first if bridge is healthy
  if (pipelineBridge.isOnline) {
    const liveStep = await pipelineBridge.stepDigitalTwin(dt);
    if (liveStep && liveStep.frame) {
      stepRecord = {
        elapsed_s: liveStep.elapsed_s,
        phase: liveStep.phase,
        summary: liveStep.frame.summary,
        readings: liveStep.frame.readings,
        early_warning: liveStep.early_warning,
        disturbance_classification: liveStep.disturbance_classification,
      };
    }
  }

  // Fallback to pre-exported static scenario trace if offline
  if (!stepRecord && twinPreloadedScenarios && twinPreloadedScenarios[activeTwinScenario]) {
    const scenSteps = twinPreloadedScenarios[activeTwinScenario].steps;
    if (scenSteps && scenSteps.length > 0) {
      if (dt > 0) {
        currentTwinStepIndex = (currentTwinStepIndex + 1) % scenSteps.length;
      }
      stepRecord = scenSteps[currentTwinStepIndex];
    }
  }

  if (!stepRecord) return;

  const prevWarning = currentTwinData.warning_state;
  const isHybrid = currentOperatingMode === "HYBRID_DEMO";

  // In Physical-Only mode, isolate simulated values
  if (!isHybrid) {
    currentTwinData.warning_state = "WX";
    currentTwinData.warning_confidence = 0.0;
    currentTwinData.warning_explanation = "Physical hardware disconnected: no physical channels available (simulated channels isolated).";
    currentTwinData.data_quality = "MISSING";
    currentTwinData.triggering_indicators = [];
    currentTwinData.disturbance_state = "TX";
  } else {
    currentTwinData.warning_state = stepRecord.early_warning.state || "W0";
    currentTwinData.warning_confidence = stepRecord.early_warning.confidence || 0.95;
    currentTwinData.warning_explanation = stepRecord.early_warning.explanation || "Nominal conditions.";
    currentTwinData.data_quality = stepRecord.early_warning.data_quality || "GOOD";
    currentTwinData.triggering_indicators = stepRecord.early_warning.triggering_indicators || [];
    currentTwinData.disturbance_state = stepRecord.disturbance_classification || "T0";
  }

  currentTwinData.elapsed_s = stepRecord.elapsed_s;
  currentTwinData.phase = stepRecord.phase;

  const sum = stepRecord.summary || {};
  currentTwinData.vibration_rms = sum.vibration_rms !== undefined ? sum.vibration_rms : 0.08;
  currentTwinData.vessel_distance_m = sum.distance_m !== undefined ? sum.distance_m : 80.0;
  currentTwinData.cable_strain = sum.strain_microstrain !== undefined ? sum.strain_microstrain : 10.0;
  currentTwinData.temperature = sum.temperature_c !== undefined ? sum.temperature_c : 4.0;
  currentTwinData.cable_health = sum.condition_index !== undefined ? sum.condition_index : 0.98;

  // Approximate vessel positions
  currentTwinData.vessel_x = currentTwinData.vessel_distance_m;
  currentTwinData.vessel_y = (currentTwinData.elapsed_s * 1.5) - 30.0;

  // Detect state change and log event
  if (prevWarning !== currentTwinData.warning_state) {
    let lvl = "info";
    if (currentTwinData.warning_state === "W3") lvl = "danger";
    else if (currentTwinData.warning_state === "W2") lvl = "warning";
    else if (currentTwinData.warning_state === "W1") lvl = "info";
    else if (currentTwinData.warning_state === "W0") lvl = "safe";

    telemetryBuffer.addEvent(
      "EARLY_WARN",
      `State transition: ${prevWarning} ➔ ${currentTwinData.warning_state} (${currentTwinData.warning_explanation})`,
      lvl
    );
    renderEventLog();
  }

  // Update Badges & Headers
  const phaseBadge = document.getElementById("twin-phase-badge");
  const timeBadge = document.getElementById("twin-time-badge");
  if (phaseBadge) phaseBadge.textContent = `PHASE: ${currentTwinData.phase}`;
  if (timeBadge) timeBadge.textContent = `t = ${currentTwinData.elapsed_s.toFixed(1)}s`;

  // Update Early Warning KPI Card
  const warnBadge = document.getElementById("early-warning-state-badge");
  const warnConf = document.getElementById("early-warning-confidence");
  const warnExp = document.getElementById("early-warning-explanation");
  const warnQual = document.getElementById("early-warning-quality-badge");
  const warnInd = document.getElementById("early-warning-indicators");

  if (warnBadge) {
    warnBadge.innerHTML = renderWarningBadge(currentTwinData.warning_state, getWarningStateName(currentTwinData.warning_state));
  }
  if (warnConf) {
    warnConf.textContent = `Confidence: ${(currentTwinData.warning_confidence * 100).toFixed(0)}%`;
  }
  if (warnExp) {
    warnExp.textContent = currentTwinData.warning_explanation;
  }
  if (warnQual) {
    warnQual.innerHTML = renderQualityBadge(currentTwinData.data_quality);
  }
  if (warnInd) {
    if (currentTwinData.triggering_indicators.length === 0) {
      warnInd.innerHTML = `<span class="brand-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">None (Ambient Baseline)</span>`;
    } else {
      warnInd.innerHTML = currentTwinData.triggering_indicators
        .map((ind) => `<span class="brand-badge" style="background: rgba(234, 179, 8, 0.2); color: var(--state-t2); font-size: 0.75rem;">${ind}</span>`)
        .join("");
    }
  }

  // Update Disturbance Pipeline Card
  const pipeBadge = document.getElementById("pipeline-decision-badge");
  const pipeRationale = document.getElementById("pipeline-rationale-text");
  if (pipeBadge) {
    pipeBadge.textContent = `${currentTwinData.disturbance_state}: ${getDisturbanceStateName(currentTwinData.disturbance_state)}`;
    pipeBadge.style.color = getDisturbanceStateColor(currentTwinData.disturbance_state);
  }
  if (pipeRationale) {
    if (currentTwinData.disturbance_state === "T3") {
      pipeRationale.textContent = "CRITICAL DISTURBANCE: Corroborated cable strike / dragging anchor event.";
    } else if (currentTwinData.disturbance_state === "T2") {
      pipeRationale.textContent = "Elevated acoustic signature with corroborated vessel interaction zone.";
    } else if (currentTwinData.disturbance_state === "T1") {
      pipeRationale.textContent = "Uncorrelated physical disturbance detected on cable corridor.";
    } else if (currentTwinData.disturbance_state === "TX") {
      pipeRationale.textContent = "High uncertainty or missing sensor data: fail-closed safety state.";
    } else {
      pipeRationale.textContent = "Safe ambient conditions. No acoustic signature or physical cable strike detected.";
    }
  }

  // Update Simulated Telemetry Cards
  const dasRmsEl = document.getElementById("disp-das-rms");
  const dasBadgeEl = document.getElementById("disp-das-badge");
  const vesselDistEl = document.getElementById("disp-vessel-dist");
  const vesselSpeedEl = document.getElementById("disp-vessel-speed");
  const strainEl = document.getElementById("disp-cable-strain");
  const strainBadgeEl = document.getElementById("disp-strain-badge");
  const tempEl = document.getElementById("disp-cable-temp");
  const healthEl = document.getElementById("disp-health-val");

  if (!isHybrid) {
    if (dasRmsEl) dasRmsEl.textContent = "ISOLATED";
    if (dasBadgeEl) dasBadgeEl.innerHTML = `<span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">PHYSICAL ONLY</span>`;
    if (vesselDistEl) vesselDistEl.textContent = "ISOLATED";
    if (vesselSpeedEl) vesselSpeedEl.innerHTML = "Simulated channels disabled";
    if (strainEl) strainEl.textContent = "ISOLATED";
    if (strainBadgeEl) strainBadgeEl.innerHTML = `<span class="state-badge" style="background: var(--bg-hover); color: var(--text-muted); font-size: 0.75rem;">PHYSICAL ONLY</span>`;
    if (tempEl) tempEl.textContent = "ISOLATED";
    if (healthEl) healthEl.textContent = "--";
  } else {
    if (dasRmsEl) dasRmsEl.textContent = `${currentTwinData.vibration_rms.toFixed(2)} units`;
    if (dasBadgeEl) {
      if (currentTwinData.vibration_rms >= 1.0) {
        dasBadgeEl.innerHTML = `<span class="state-badge T3" style="font-size: 0.75rem;">SEVERE ACOUSTIC RMS</span>`;
      } else if (currentTwinData.vibration_rms >= 0.25) {
        dasBadgeEl.innerHTML = `<span class="state-badge T2" style="font-size: 0.75rem;">ELEVATED DAS RMS</span>`;
      } else {
        dasBadgeEl.innerHTML = `<span class="state-badge T0" style="font-size: 0.75rem;">QUIET AMBIENT</span>`;
      }
    }

    if (vesselDistEl) vesselDistEl.textContent = `${currentTwinData.vessel_distance_m.toFixed(1)} m`;
    if (vesselSpeedEl) {
      vesselSpeedEl.innerHTML = `Speed: <strong>${currentTwinData.vessel_speed.toFixed(1)} m/s</strong> (Route Proximity)`;
    }

    if (strainEl) strainEl.textContent = `${currentTwinData.cable_strain.toFixed(1)} με`;
    if (strainBadgeEl) {
      if (currentTwinData.cable_strain >= 250.0) {
        strainBadgeEl.innerHTML = `<span class="state-badge T3" style="font-size: 0.75rem;">CRITICAL MECHANICAL TENSION</span>`;
      } else if (currentTwinData.cable_strain >= 40.0) {
        strainBadgeEl.innerHTML = `<span class="state-badge T2" style="font-size: 0.75rem;">ELEVATED STRAIN</span>`;
      } else {
        strainBadgeEl.innerHTML = `<span class="state-badge T0" style="font-size: 0.75rem;">NORMAL TENSION</span>`;
      }
    }

    if (tempEl) tempEl.textContent = `${currentTwinData.temperature.toFixed(2)} °C`;
    if (healthEl) healthEl.textContent = currentTwinData.cable_health.toFixed(3);
  }

  // Record into history buffer for charts
  currentTwinData.history.push({
    t: currentTwinData.elapsed_s,
    rms: currentTwinData.vibration_rms,
    dist: currentTwinData.vessel_distance_m,
    strain: currentTwinData.cable_strain,
    temp: currentTwinData.temperature,
    vx: currentTwinData.vessel_x,
    vy: currentTwinData.vessel_y,
    state: currentTwinData.warning_state,
    stateNum: warningStateToNumber(currentTwinData.warning_state),
  });

  if (currentTwinData.history.length > 80) {
    currentTwinData.history.shift();
  }

  renderDigitalTwinPlots();
}

function getWarningStateName(state) {
  if (state === "W0") return "NORMAL";
  if (state === "W1") return "WATCH";
  if (state === "W2") return "ADVISORY";
  if (state === "W3") return "URGENT";
  return "UNKNOWN / DATA QUALITY";
}

function getWarningStateColor(state) {
  if (state === "W0") return "var(--state-t0)";
  if (state === "W1") return "var(--state-t1)";
  if (state === "W2") return "var(--state-t2)";
  if (state === "W3") return "var(--state-t3)";
  return "var(--state-tx)";
}

function getDisturbanceStateName(state) {
  if (state === "T0") return "NOMINAL";
  if (state === "T1") return "UNCORRELATED";
  if (state === "T2") return "CORROBORATED";
  if (state === "T3") return "SEVERE STRIKE";
  return "HIGH UNCERTAINTY / FAULT";
}

function getDisturbanceStateColor(state) {
  if (state === "T0") return "var(--state-t0)";
  if (state === "T1") return "var(--state-t1)";
  if (state === "T2") return "var(--state-t2)";
  if (state === "T3") return "var(--state-t3)";
  return "var(--state-tx)";
}

function warningStateToNumber(state) {
  if (state === "W0") return 0;
  if (state === "W1") return 1;
  if (state === "W2") return 2;
  if (state === "W3") return 3;
  return -0.5; // WX
}

/**
 * Renders the 2D Cable Route Map and Multi-Sensor Early Warning Trend Plot.
 */
function renderDigitalTwinPlots() {
  const mapEl = document.getElementById("twin-map-plot");
  const trendEl = document.getElementById("twin-trends-plot");
  if (!mapEl || !trendEl) return;

  const hist = currentTwinData.history;
  const isHybrid = currentOperatingMode === "HYBRID_DEMO";

  // --- PLOT 1: 2D Cable Route & Vessel Kinematics Map ---
  const cableLineX = [0, 0];
  const cableLineY = [-100, 100];

  const watchCorridorLeftX = [-60, -60];
  const watchCorridorRightX = [60, 60];
  const urgentCorridorLeftX = [-15, -15];
  const urgentCorridorRightX = [15, 15];
  const corridorY = [-100, 100];

  const traceCable = {
    x: cableLineX,
    y: cableLineY,
    mode: "lines",
    name: "Subsea Cable Route (X=0)",
    line: { color: "#38bdf8", width: 4 },
  };

  const traceWatchLeft = {
    x: watchCorridorLeftX,
    y: corridorY,
    mode: "lines",
    name: "Watch Corridor (60m)",
    line: { color: "#fbbf24", width: 1.5, dash: "dash" },
  };
  const traceWatchRight = {
    x: watchCorridorRightX,
    y: corridorY,
    mode: "lines",
    showlegend: false,
    line: { color: "#fbbf24", width: 1.5, dash: "dash" },
  };

  const traceUrgentLeft = {
    x: urgentCorridorLeftX,
    y: corridorY,
    mode: "lines",
    name: "Urgent Corridor (15m)",
    line: { color: "#ef4444", width: 1.5, dash: "dot" },
  };
  const traceUrgentRight = {
    x: urgentCorridorRightX,
    y: corridorY,
    mode: "lines",
    showlegend: false,
    line: { color: "#ef4444", width: 1.5, dash: "dot" },
  };

  const trailX = hist.map((h) => h.vx);
  const trailY = hist.map((h) => h.vy);
  const traceTrail = {
    x: trailX,
    y: trailY,
    mode: "lines",
    name: "Vessel Trajectory Trail",
    line: { color: "#94a3b8", width: 2 },
  };

  const currVx = isHybrid ? [currentTwinData.vessel_x] : [];
  const currVy = isHybrid ? [currentTwinData.vessel_y] : [];
  const traceVessel = {
    x: currVx,
    y: currVy,
    mode: "markers+text",
    name: "Simulated Vessel",
    text: isHybrid ? [`Vessel (${currentTwinData.vessel_distance_m.toFixed(1)}m)`] : [],
    textposition: "top center",
    marker: {
      size: 14,
      symbol: "triangle-up",
      color: currentTwinData.warning_state === "W3" ? "#ef4444" : currentTwinData.warning_state === "W2" ? "#f59e0b" : "#38bdf8",
      line: { color: "#ffffff", width: 1.5 },
    },
  };

  buildPlot("twin-map-plot", [traceCable, traceWatchLeft, traceWatchRight, traceUrgentLeft, traceUrgentRight, traceTrail, traceVessel], {
    xaxis: { title: "Cross-Track Distance X (meters)", range: [-90, 90] },
    yaxis: { title: "Along-Track Position Y (meters)", range: [-90, 90] },
    legend: { orientation: "h", y: -0.22, font: { size: 10 } },
    margin: { l: 50, r: 20, t: 20, b: 50 },
  });

  // --- PLOT 2: Multi-Sensor Early Warning Signals & State Trace ---
  const times = hist.map((h) => h.t);
  const rmsVals = hist.map((h) => h.rms);
  const strainVals = hist.map((h) => h.strain);
  const distVals = hist.map((h) => h.dist);
  const stateNums = hist.map((h) => h.stateNum);

  const traceRms = {
    x: times,
    y: rmsVals,
    name: "DAS Acoustic RMS",
    line: { color: "#f59e0b", width: 2 },
  };

  const traceStrain = {
    x: times,
    y: strainVals.map((s) => s * 0.01), // scaled to fit 0-5 axis
    name: "Cable Strain (x0.01 με)",
    line: { color: "#ec4899", width: 2 },
  };

  const traceDist = {
    x: times,
    y: distVals.map((d) => d * 0.05), // scaled to fit 0-5 axis
    name: "Vessel Dist (x0.05 m)",
    line: { color: "#38bdf8", width: 1.5, dash: "dot" },
  };

  const traceStateStep = {
    x: times,
    y: stateNums,
    name: "Warning State (W0-W3)",
    mode: "lines+markers",
    line: { shape: "hv", color: "#a855f7", width: 3 },
    marker: { size: 6, color: "#c084fc" },
  };

  buildPlot("twin-trends-plot", [traceRms, traceStrain, traceDist, traceStateStep], {
    xaxis: { title: "Elapsed Time (seconds)" },
    yaxis: {
      title: "Warning State / Signal Values",
      tickvals: [-0.5, 0, 1, 2, 3],
      ticktext: ["WX", "W0", "W1", "W2", "W3"],
      range: [-1.0, 3.8],
    },
    shapes: [
      {
        type: "line",
        xref: "paper",
        x0: 0,
        x1: 1,
        y0: 0.25,
        y1: 0.25,
        line: { color: "rgba(245, 158, 11, 0.4)", width: 1, dash: "dash" },
      },
      {
        type: "line",
        xref: "paper",
        x0: 0,
        x1: 1,
        y0: 1.0,
        y1: 1.0,
        line: { color: "rgba(239, 68, 68, 0.4)", width: 1, dash: "dot" },
      },
    ],
    annotations: [
      {
        xref: "paper",
        x: 0.98,
        y: 0.25,
        xanchor: "right",
        yanchor: "bottom",
        text: "Advisory Threshold (0.25)",
        showarrow: false,
        font: { size: 9, color: "#f59e0b" },
      },
      {
        xref: "paper",
        x: 0.98,
        y: 1.0,
        xanchor: "right",
        yanchor: "bottom",
        text: "Strike Threshold (1.00)",
        showarrow: false,
        font: { size: 9, color: "#ef4444" },
      },
    ],
    legend: { orientation: "h", y: -0.22, font: { size: 10 } },
    margin: { l: 50, r: 20, t: 20, b: 50 },
  });
}

/**
 * Updates the synopsis card with the selected scenario's purpose and expected progression.
 */
function updateScenarioSynopsis(scenarioKey) {
  const meta = SCENARIO_METADATA[scenarioKey] || SCENARIO_METADATA.normal_operation;
  const synopsisEl = document.getElementById("scenario-synopsis-box");
  if (!synopsisEl) return;
  synopsisEl.innerHTML = `
    <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 0.5rem; margin-bottom: 0.35rem;">
      <div style="font-weight: 700; font-size: 0.9rem; color: var(--text-main);">
        ${meta.title}
      </div>
      <div style="display: flex; gap: 0.5rem; align-items: center; font-size: 0.75rem;">
        <span style="color: var(--text-muted);">Expected Progression:</span>
        <span class="state-badge ${meta.badgeClass}" style="font-size: 0.75rem;">${meta.states}</span>
        <span class="brand-badge" style="font-family: var(--font-mono); font-size: 0.7rem;">${meta.duration}</span>
      </div>
    </div>
    <div style="font-size: 0.82rem; color: var(--text-muted); line-height: 1.4;">
      ${meta.desc}
    </div>
  `;
}

/**
 * Opens the interactive digital twin scenario evaluation modal report.
 */
function openEvaluationModal() {
  const container = document.getElementById("eval-modal-container");
  if (!container) return;

  const rowsHtml = BENCHMARK_EVAL_SCORECARD.map((item) => `
    <tr>
      <td style="font-weight: 600; color: var(--text-main); font-size: 0.85rem;">${item.scenario}</td>
      <td style="font-size: 0.82rem; color: var(--text-muted);">${item.behavior}</td>
      <td style="font-size: 0.82rem; font-family: var(--font-mono);">${item.metric}</td>
      <td style="font-weight: 700; font-family: var(--font-mono); color: var(--accent);">${item.value}</td>
      <td><span class="brand-badge" style="background: rgba(16, 185, 129, 0.15); color: var(--state-t0); font-weight: 700;">${item.status}</span></td>
      <td style="font-size: 0.78rem; color: var(--text-muted); max-width: 240px; white-space: normal;">${item.details}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <div class="modal-overlay" id="eval-modal-overlay">
      <div class="modal-card">
        <div class="modal-header">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 1.1rem; font-weight: 700; color: var(--text-main);">
              📊 Digital Twin Benchmark Evaluation Report
            </span>
            <span class="brand-badge" style="background: rgba(16, 185, 129, 0.15); color: var(--state-t0);">
              ALL 7 PASS
            </span>
          </div>
          <button id="btn-close-eval-modal" class="btn btn-secondary" style="padding: 0.2rem 0.5rem; font-size: 0.8rem;">✕ Close</button>
        </div>
        <div class="modal-body">
          <div class="card" style="border-left: 4px solid var(--state-t1); margin-bottom: 0.5rem;">
            <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-main);">
              Scientific Integrity Notice (Offline Seed 42 Benchmark)
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem; line-height: 1.4;">
              All evaluated channels are synthesized by benchmark models. Performance metrics reflect early warning algorithm convergence, false alarm rejection, and fail-safe trip speeds.
            </div>
          </div>

          <div class="table-container">
            <table class="data-table" id="eval-modal-table">
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Target Behavior</th>
                  <th>Evaluated Metric</th>
                  <th>Value</th>
                  <th>Status</th>
                  <th>Detailed Finding</th>
                </tr>
              </thead>
              <tbody>
                ${rowsHtml}
              </tbody>
            </table>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin-top: 0.5rem;">
            <div class="card" style="padding: 0.75rem;">
              <div style="font-size: 0.72rem; color: var(--text-muted);">False Alarm Rate</div>
              <div style="font-size: 1.25rem; font-weight: 700; color: var(--state-t0); font-family: var(--font-mono);">0.0%</div>
              <div style="font-size: 0.7rem; color: var(--text-dim);">Zero alarm leakage on baseline</div>
            </div>
            <div class="card" style="padding: 0.75rem;">
              <div style="font-size: 0.72rem; color: var(--text-muted);">Watch Latency</div>
              <div style="font-size: 1.25rem; font-weight: 700; color: var(--accent); font-family: var(--font-mono);">6.0s</div>
              <div style="font-size: 0.7rem; color: var(--text-dim);">Triggered at 60m perimeter</div>
            </div>
            <div class="card" style="padding: 0.75rem;">
              <div style="font-size: 0.72rem; color: var(--text-muted);">Severe Strike Trigger</div>
              <div style="font-size: 1.25rem; font-weight: 700; color: var(--state-t3); font-family: var(--font-mono);">1.5s</div>
              <div style="font-size: 0.7rem; color: var(--text-dim);">Corroborated alert trigger</div>
            </div>
            <div class="card" style="padding: 0.75rem;">
              <div style="font-size: 0.72rem; color: var(--text-muted);">Fail-Safe Trip Speed</div>
              <div style="font-size: 1.25rem; font-weight: 700; color: var(--state-tx); font-family: var(--font-mono);">10.2s</div>
              <div style="font-size: 0.7rem; color: var(--text-dim);">Safe trip to WX state</div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button id="btn-export-eval-csv" class="btn btn-secondary" style="font-size: 0.8rem;">
            📥 Export Scorecard (CSV)
          </button>
          <button id="btn-export-eval-json" class="btn btn-secondary" style="font-size: 0.8rem;">
            📥 Export Report (JSON)
          </button>
          <button id="btn-close-eval-modal-bottom" class="btn btn-primary" style="font-size: 0.8rem;">
            Done
          </button>
        </div>
      </div>
    </div>
  `;

  const overlay = document.getElementById("eval-modal-overlay");
  const closeTop = document.getElementById("btn-close-eval-modal");
  const closeBottom = document.getElementById("btn-close-eval-modal-bottom");
  const exportCsv = document.getElementById("btn-export-eval-csv");
  const exportJson = document.getElementById("btn-export-eval-json");

  const closeFn = () => closeEvaluationModal();
  if (closeTop) closeTop.onclick = closeFn;
  if (closeBottom) closeBottom.onclick = closeFn;
  if (overlay) {
    overlay.onclick = (e) => {
      if (e.target === overlay) closeFn();
    };
  }

  if (exportCsv) {
    exportCsv.onclick = () => {
      const table = document.getElementById("eval-modal-table");
      if (table) exportTableToCSV(table, "digital_twin_evaluation_scorecard.csv");
    };
  }

  if (exportJson) {
    exportJson.onclick = () => {
      const blob = new Blob([JSON.stringify(BENCHMARK_EVAL_SCORECARD, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "digital_twin_evaluation_scorecard.json";
      a.click();
      URL.revokeObjectURL(url);
    };
  }
}

/**
 * Closes and removes the evaluation modal.
 */
function closeEvaluationModal() {
  const container = document.getElementById("eval-modal-container");
  if (container) container.innerHTML = "";
}

/**
 * Clean lifecycle teardown for HIL page when navigating away.
 */
export function cleanup() {
  if (twinSimTimer) {
    clearInterval(twinSimTimer);
    twinSimTimer = null;
  }
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
    isPollingActive = false;
  }
  closeEvaluationModal();
}

