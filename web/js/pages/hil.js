/**
 * Page 12: Live Hardware-in-the-Loop (HIL) Dashboard
 * Visualizes real-time and replay telemetry from the AbyssLink ESP32 bridge.
 * Data Kind: HIL_SIMULATED_ACCEL (Simulated accelerometer; validates timing & link faults).
 */

import { renderBanner } from "../banner.js";
import { renderKPI, renderBadge, TOOLTIPS } from "../components.js";
import { buildPlot, exportTableToCSV } from "../charts.js";

let pollInterval = null;
let isPollingActive = false;
let loadedDecisions = [];
let lastSeenSequence = -1;
let currentRunMeta = null;

export async function render(container) {
  renderBanner("HIL_SIMULATED_ACCEL");

  container.innerHTML = `
    <!-- Top Mandatory Scientific Notice -->
    <div class="card" style="border-left: 4px solid var(--state-t1); margin-bottom: 1.5rem;">
      <div style="font-weight: 700; color: var(--state-t1); margin-bottom: 0.25rem;">
        Hardware-in-the-Loop Scientific Integrity Notice
      </div>
      <p style="font-size: 0.9rem; margin: 0; color: var(--text-color);">
        <strong>The accelerometer is simulated; this validates integration and decision logic under real timing and link faults, not subsea sensing physics.</strong>
      </p>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem;">
        ESP32 AbyssLink optical & serial protocol telemetry (115,200 baud, 300 ms packet interval) coupled with synthesized MPU6050 vibration profiles.
      </div>
    </div>

    <!-- Controls Row -->
    <div class="control-row">
      <div style="display: flex; gap: 0.75rem; align-items: center;">
        <button id="toggle-poll-btn" class="btn btn-primary">▶ Start Live Polling (2s)</button>
        <span id="poll-indicator" class="brand-badge" style="background: var(--bg-card); color: var(--text-muted);">
          ⚪ Standby
        </span>
      </div>

      <div style="flex: 1;"></div>

      <div style="display: flex; gap: 0.75rem; align-items: center;">
        <label for="hil-file-input" class="btn btn-secondary" style="cursor: pointer; margin: 0;">
          📁 Load decisions.jsonl
        </label>
        <input type="file" id="hil-file-input" accept=".jsonl,.json" style="display: none;">
        <button id="download-hil-csv" class="btn btn-secondary">📥 Export HIL CSV</button>
      </div>
    </div>

    <!-- Drag & Drop Zone -->
    <div id="drop-zone" style="border: 2px dashed var(--border-color); border-radius: var(--radius); padding: 1.5rem; text-align: center; margin-bottom: 1.5rem; transition: all 0.2s ease; background: var(--bg-hover);">
      <div style="font-size: 0.95rem; font-weight: 600; color: var(--text-color);">
        Drag & Drop <code>decisions.jsonl</code> here or load using the file picker
      </div>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
        Generate mock HIL logs using: <code>python scripts/run_abysslink_hil.py --mock --seed 42</code>
      </div>
    </div>

    <!-- Active View Container -->
    <div id="hil-content-view">
      <div class="empty-state">
        <h3>No Active HIL Session Loaded</h3>
        <p>Start live polling or execute the mock bridge runner:</p>
        <pre style="background: var(--bg-hover); padding: 0.75rem; border-radius: var(--radius); display: inline-block;">python scripts/run_abysslink_hil.py --mock --seed 42</pre>
      </div>
    </div>
  `;

  const pollBtn = document.getElementById("toggle-poll-btn");
  const fileInput = document.getElementById("hil-file-input");
  const dropZone = document.getElementById("drop-zone");

  // Setup Drag and Drop
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

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileLoad(e.target.files[0]);
    }
  });

  function handleFileLoad(file) {
    const reader = new FileReader();
    reader.onload = (evt) => {
      parseAndDisplayDecisions(evt.target.result, file.name);
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
      } catch (e) {
        // Skip malformed line
      }
    }

    if (records.length === 0) {
      document.getElementById("hil-content-view").innerHTML = `
        <div class="empty-state">
          <h3>Failed to Parse Valid Decision Records</h3>
          <p>Please ensure file contains valid JSONL decision lines.</p>
        </div>
      `;
      return;
    }

    loadedDecisions = records;
    currentRunMeta = { source: sourceName, count: records.length };
    updateDashboard();
  }

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
          "Optical & Link Status",
          latest.transmission ? "CONNECTED" : "LINK FAULT",
          latest.ldr_flag ? "⚠️ Optical Degraded" : "Nominal Optical Path",
          "ESP32 hardware link and photodiode transmission indicator."
        )}
        ${renderKPI(
          "Vibration Hardware Flag",
          latest.vibration_flag ? "VIBRATING (FLAG 1)" : "QUIET (FLAG 0)",
          `Simulated Accel | Alert: ${latest.alert || "N/A"}`,
          "ESP32 hardware digital vibration switch flag."
        )}
        ${renderKPI(
          "Packets Processed",
          `${loadedDecisions.length}`,
          `Duration: ${duration} s (${(loadedDecisions.length / Math.max(1, parseFloat(duration))).toFixed(1)} Hz)`,
          "Total telemetry frames decoded and evaluated."
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
                    <td>${d.physical_confidence.toFixed(3)}</td>
                    <td>${d.association_confidence.toFixed(3)}</td>
                    <td>${d.reliability.toFixed(3)}</td>
                    <td>${d.uncertainty.toFixed(3)}</td>
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
    const cp = loadedDecisions.map((d) => d.physical_confidence);
    const ca = loadedDecisions.map((d) => d.association_confidence);
    const r = loadedDecisions.map((d) => d.reliability);
    const u = loadedDecisions.map((d) => d.uncertainty);

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

  // Polling logic for live stream
  async function pollLatest() {
    try {
      // 1. Fetch latest.json pointer
      const ptrResp = await fetch("hil/latest.json?t=" + Date.now());
      if (!ptrResp.ok) return;
      const ptr = await ptrResp.json();

      // 2. Fetch decisions file (try relative hil/decisions.jsonl)
      const decResp = await fetch("hil/decisions.jsonl?t=" + Date.now());
      if (decResp.ok) {
        const text = await decResp.text();
        parseAndDisplayDecisions(text, ptr.run_id || "Live HIL Run");
      }
    } catch (e) {
      console.warn("Polling error:", e);
    }
  }

  function togglePolling() {
    isPollingActive = !isPollingActive;
    const ind = document.getElementById("poll-indicator");
    if (isPollingActive) {
      pollBtn.textContent = "⏸ Pause Polling";
      pollBtn.classList.remove("btn-primary");
      pollBtn.classList.add("btn-secondary");
      if (ind) {
        ind.innerHTML = "🟢 Live Streaming (2s)";
        ind.style.color = "var(--state-t0)";
      }
      pollLatest();
      pollInterval = setInterval(pollLatest, 2000);
    } else {
      pollBtn.textContent = "▶ Start Live Polling (2s)";
      pollBtn.classList.remove("btn-secondary");
      pollBtn.classList.add("btn-primary");
      if (ind) {
        ind.innerHTML = "🟡 Paused";
        ind.style.color = "var(--state-t1)";
      }
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  pollBtn.addEventListener("click", togglePolling);

  // Auto-load available decisions.jsonl initially if present
  fetch("hil/decisions.jsonl")
    .then((r) => (r.ok ? r.text() : null))
    .then((text) => {
      if (text) {
        parseAndDisplayDecisions(text, "Default HIL Run");
      }
    })
    .catch(() => {});
}
