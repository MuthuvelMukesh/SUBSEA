/**
 * Page 5: Evidence & Uncertainty Timeline
 * Displays sliding-window evolution of C_P, C_A, R, U, and discrete Decision States.
 */

import { renderBanner } from "../banner.js";
import { renderKPI, renderBadge, TOOLTIPS } from "../components.js";
import { buildPlot, exportTableToCSV } from "../charts.js";

let timelinesData = {};
let metadata = null;

const STATE_COLORS = {
  T0: "#10b981", // green
  T1: "#f59e0b", // amber
  T2: "#f97316", // orange
  T3: "#ef4444", // red
  TX: "#8b5cf6", // purple
};

export async function render(container) {
  try {
    const res = await fetch("data/timelines.json");
    const json = await res.json();
    metadata = json.metadata || {};
    timelinesData = json.timelines || {};
    renderBanner(metadata.data_kind || "SIMULATION");
  } catch (err) {
    console.error("Failed to load timelines.json", err);
    renderBanner("SIMULATION");
  }

  const sids = Object.keys(timelinesData);

  container.innerHTML = `
    <!-- Controls -->
    <div class="control-row">
      <div class="control-group" style="min-width: 250px;">
        <label class="control-label" for="timeline-scenario-select">Select Scenario Timeline</label>
        <select id="timeline-scenario-select" class="select-input">
          ${sids.map((id) => `<option value="${id}">${id} Evidence Dynamics</option>`).join("")}
        </select>
      </div>
      <div style="flex: 1;"></div>
      <button id="download-timeline-csv" class="btn btn-secondary">📥 Export Timeline CSV</button>
    </div>

    <!-- Active Timeline Container -->
    <div id="timeline-view"></div>
  `;

  const sel = document.getElementById("timeline-scenario-select");

  function updateView() {
    const sid = sel.value;
    const tl = timelinesData[sid];

    if (!tl || !tl.timestamps || tl.timestamps.length === 0) {
      document.getElementById("timeline-view").innerHTML = `
        <div class="empty-state">
          <h3>No Timeline Data Available for ${sid}</h3>
          <p>Generate pipeline runs with: <code>python scripts/export_web_data.py</code></p>
        </div>
      `;
      return;
    }

    const lastDecision = tl.decisions[tl.decisions.length - 1] || "T0";
    const maxCp = Math.max(...tl.physical_confidence);
    const meanR = tl.reliability.reduce((a, b) => a + b, 0) / tl.reliability.length;
    const meanU = tl.uncertainty.reduce((a, b) => a + b, 0) / tl.uncertainty.length;

    document.getElementById("timeline-view").innerHTML = `
      <!-- Timeline KPIs -->
      <div class="grid-cols-4">
        ${renderKPI(
          "Final Decision State",
          renderBadge(lastDecision),
          `At t = ${tl.timestamps[tl.timestamps.length - 1]}s`,
          TOOLTIPS[lastDecision] || "Final decision state at end of evaluation window."
        )}
        ${renderKPI(
          "Peak Physical Confidence (C_P)",
          maxCp.toFixed(3),
          "Threshold: 0.55",
          TOOLTIPS.CP
        )}
        ${renderKPI(
          "Mean Sensor Reliability (R)",
          meanR.toFixed(3),
          "Gate 1 Fail Threshold: 0.35",
          TOOLTIPS.R
        )}
        ${renderKPI(
          "Mean Epistemic Uncertainty (U)",
          meanU.toFixed(3),
          "Gate 3 Fail-Closed Threshold: 0.65",
          TOOLTIPS.U
        )}
      </div>

      <!-- Charts Grid -->
      <div class="grid-cols-2">
        <!-- Continuous Evidence Multi-Trace Plot -->
        <div class="card">
          <div class="card-title">
            <span>Continuous Evidence Traces (C_P, C_A, R, U)</span>
            <span class="brand-badge">Sliding Window</span>
          </div>
          <div id="evidence-plot" class="chart-container"></div>
        </div>

        <!-- Discrete Decision State Sequence -->
        <div class="card">
          <div class="card-title">
            <span>Decision State Sequence Over Time</span>
            <span class="brand-badge">Gate Engine Output</span>
          </div>
          <div id="decision-seq-plot" class="chart-container"></div>
        </div>
      </div>

      <!-- Tabular Log -->
      <div class="card">
        <div class="card-title">
          <span>Sliding-Window Pipeline Decision Table</span>
          <span style="font-size: 0.8rem; color: var(--text-muted);">
            Window: ${tl.window_size} samples (1.28s) | Step: ${tl.step_size} samples (0.32s)
          </span>
        </div>
        <div class="table-container">
          <table id="timeline-table">
            <thead>
              <tr>
                <th>Step #</th>
                <th>Window End (s)</th>
                <th>Physical Conf (C_P)</th>
                <th>Assoc Conf (C_A)</th>
                <th>Reliability (R)</th>
                <th>Uncertainty (U)</th>
                <th>Pipeline Decision</th>
              </tr>
            </thead>
            <tbody>
              ${tl.timestamps
                .map(
                  (t, idx) => `
                <tr>
                  <td>${idx + 1}</td>
                  <td><strong>${t.toFixed(3)}</strong></td>
                  <td>${tl.physical_confidence[idx].toFixed(4)}</td>
                  <td>${tl.association_confidence[idx].toFixed(4)}</td>
                  <td>${tl.reliability[idx].toFixed(4)}</td>
                  <td>${tl.uncertainty[idx].toFixed(4)}</td>
                  <td>${renderBadge(tl.decisions[idx])}</td>
                </tr>
              `
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Render Evidence Plot
    const traceCp = {
      x: tl.timestamps,
      y: tl.physical_confidence,
      mode: "lines+markers",
      name: "C_P (Physical)",
      line: { color: "#38bdf8", width: 2.5 },
      marker: { size: 5 },
    };
    const traceCa = {
      x: tl.timestamps,
      y: tl.association_confidence,
      mode: "lines+markers",
      name: "C_A (Association)",
      line: { color: "#fbbf24", width: 2.5 },
      marker: { size: 5 },
    };
    const traceR = {
      x: tl.timestamps,
      y: tl.reliability,
      mode: "lines+markers",
      name: "R (Reliability)",
      line: { color: "#34d399", width: 2.5 },
      marker: { size: 5 },
    };
    const traceU = {
      x: tl.timestamps,
      y: tl.uncertainty,
      mode: "lines+markers",
      name: "U (Uncertainty)",
      line: { color: "#c084fc", width: 2.5, dash: "dot" },
      marker: { size: 5 },
    };

    buildPlot(
      "evidence-plot",
      [traceCp, traceCa, traceR, traceU],
      {
        xaxis: { title: "Timestamp (s)" },
        yaxis: { title: "Evidence Metric [0.0, 1.0]", range: [-0.05, 1.05] },
        legend: { orientation: "h", y: -0.25 },
      }
    );

    // Render Decision Sequence Plot
    const stateOrder = ["T0", "T1", "T2", "T3", "TX"];
    const yVals = tl.decisions.map((d) => stateOrder.indexOf(d));
    const colors = tl.decisions.map((d) => STATE_COLORS[d] || "#3b82f6");

    const traceSeq = {
      x: tl.timestamps,
      y: tl.decisions,
      mode: "lines+markers",
      name: "Decision State",
      line: { shape: "hv", color: "#64748b", width: 2 },
      marker: {
        size: 10,
        color: colors,
        line: { color: "#ffffff", width: 1.5 },
      },
    };

    buildPlot(
      "decision-seq-plot",
      [traceSeq],
      {
        xaxis: { title: "Timestamp (s)" },
        yaxis: {
          title: "Decision State",
          categoryorder: "array",
          categoryarray: stateOrder,
        },
        margin: { l: 60, r: 20, t: 40, b: 50 },
      }
    );

    // CSV Download
    const dlBtn = document.getElementById("download-timeline-csv");
    if (dlBtn) {
      dlBtn.onclick = () => {
        const table = document.getElementById("timeline-table");
        if (table) exportTableToCSV(table, `timeline_${sid}.csv`);
      };
    }
  }

  sel.addEventListener("change", updateView);
  updateView();
}
