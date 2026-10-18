/**
 * Page 7: Hypotheses & Evidence Audit
 * Evaluates candidate hypotheses from Hypothesis enum and displays evidence audit trails.
 */

import { renderBanner } from "../banner.js";
import { renderKPI, renderBadge, TOOLTIPS } from "../components.js";
import { buildPlot, exportTableToCSV } from "../charts.js";

let hypothesesMeta = {};
let runsData = {};

export async function render(container) {
  renderBanner("SIMULATION");

  try {
    const [hypRes, runsRes] = await Promise.all([
      fetch("data/hypotheses.json"),
      fetch("data/scenario_runs.json"),
    ]);
    const hypJson = await hypRes.json();
    const runsJson = await runsRes.json();
    hypothesesMeta = hypJson.definitions || {};
    runsData = runsJson.runs || {};
  } catch (err) {
    console.error("Failed to load hypotheses data", err);
  }

  const sids = Object.keys(runsData);

  container.innerHTML = `
    <!-- Scenario Selection Controls -->
    <div class="control-row">
      <div class="control-group" style="min-width: 250px;">
        <label class="control-label" for="hypo-scenario-select">Select Scenario for Evidence Audit</label>
        <select id="hypo-scenario-select" class="select-input">
          ${sids.map((id) => `<option value="${id}">${id} Hypothesis Audit</option>`).join("")}
        </select>
      </div>
      <div style="flex: 1;"></div>
      <button id="download-hypo-csv" class="btn btn-secondary">📥 Export Audit CSV</button>
    </div>

    <!-- Active Audit View -->
    <div id="hypo-view"></div>
  `;

  const sel = document.getElementById("hypo-scenario-select");

  function updateView() {
    const sid = sel.value;
    const run = runsData[sid]?.ais_spoofing?.["0.0"]?.result;

    if (!run) {
      document.getElementById("hypo-view").innerHTML = `
        <div class="empty-state">
          <h3>No Hypothesis Audit Data Available for ${sid}</h3>
        </div>
      `;
      return;
    }

    const scores = run.hypothesis_scores || {};
    const audit = run.audit || {};
    const unc = audit.uncertainty_components || {};
    const health = audit.health || {};
    const assoc = audit.association_components || {};

    document.getElementById("hypo-view").innerHTML = `
      <!-- KPIs -->
      <div class="grid-cols-4">
        ${renderKPI(
          "Evaluated State",
          renderBadge(run.decision),
          `Pipeline Output`,
          TOOLTIPS[run.decision] || ""
        )}
        ${renderKPI(
          "Top Candidate Hypothesis",
          getTopHypothesis(scores),
          "Maximum Evidence Score",
          "Hypothesis receiving highest weighted multimodal support."
        )}
        ${renderKPI(
          "Sensor Health Status",
          health.health !== undefined ? `${(health.health * 100).toFixed(0)}%` : "N/A",
          health.stale ? "⚠️ Stale Telemetry" : "Healthy Link",
          "Sensor operational status from health diagnostics."
        )}
        ${renderKPI(
          "Kinematic Association",
          assoc.spatial !== undefined ? `${(assoc.spatial * 100).toFixed(0)}% Spatial` : "N/A",
          assoc.temporal !== undefined ? `${(assoc.temporal * 100).toFixed(0)}% Temporal` : "",
          "Association confidence components."
        )}
      </div>

      <!-- Chart & Evidence Breakdown -->
      <div class="grid-cols-2">
        <!-- Hypothesis Scores Chart -->
        <div class="card">
          <div class="card-title">
            <span>Hypothesis Confidence Scores</span>
            <span class="brand-badge">subsea.models.Hypothesis</span>
          </div>
          <div id="hypo-score-plot" class="chart-container"></div>
        </div>

        <!-- Evidence Audit Card -->
        <div class="card">
          <div class="card-title">
            <span>Evidence Audit & Corroboration</span>
            <span class="brand-badge">Audit Trail</span>
          </div>

          <div style="margin-top: 1rem; display: flex; flex-direction: column; gap: 1rem;">
            <div>
              <div style="font-size: 0.85rem; font-weight: 600; color: var(--state-t0); margin-bottom: 0.25rem;">
                ✔ Positive Corroborating Evidence:
              </div>
              <ul style="padding-left: 1.25rem; font-size: 0.85rem; margin: 0; color: var(--text-color);">
                ${
                  run.positive_evidence && run.positive_evidence.length > 0
                    ? run.positive_evidence.map((e) => `<li>${e}</li>`).join("")
                    : "<li style='color: var(--text-muted);'>None recorded</li>"
                }
              </ul>
            </div>

            <div>
              <div style="font-size: 0.85rem; font-weight: 600; color: var(--state-t3); margin-bottom: 0.25rem;">
                ✖ Counter Evidence:
              </div>
              <ul style="padding-left: 1.25rem; font-size: 0.85rem; margin: 0; color: var(--text-color);">
                ${
                  run.counter_evidence && run.counter_evidence.length > 0
                    ? run.counter_evidence.map((e) => `<li>${e}</li>`).join("")
                    : "<li style='color: var(--text-muted);'>None recorded</li>"
                }
              </ul>
            </div>

            <div>
              <div style="font-size: 0.85rem; font-weight: 600; color: var(--state-t1); margin-bottom: 0.25rem;">
                ⚠️ Missing Corroboration:
              </div>
              <ul style="padding-left: 1.25rem; font-size: 0.85rem; margin: 0; color: var(--text-color);">
                ${
                  run.missing_corroboration && run.missing_corroboration.length > 0
                    ? run.missing_corroboration.map((e) => `<li>${e}</li>`).join("")
                    : "<li style='color: var(--text-muted);'>None recorded</li>"
                }
              </ul>
            </div>

            <div style="background: var(--bg-hover); padding: 0.75rem; border-radius: var(--radius);">
              <div style="font-size: 0.8rem; font-weight: 600; margin-bottom: 0.25rem;">Pipeline Rationale:</div>
              <div style="font-family: monospace; font-size: 0.8rem; color: var(--primary);">
                ${run.rationale ? run.rationale.join(" | ") : "N/A"}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Audit Breakdown Table -->
      <div class="card">
        <div class="card-title">
          <span>Hypothesis Definitions and Audit Table</span>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Real Enum: <code>subsea.models.Hypothesis</code></span>
        </div>
        <div class="table-container">
          <table id="hypo-audit-table">
            <thead>
              <tr>
                <th>Hypothesis Enum Key</th>
                <th>Score [0-1]</th>
                <th>Scientific Definition</th>
                <th>Physical Support</th>
              </tr>
            </thead>
            <tbody>
              ${Object.entries(scores)
                .map(([k, score]) => {
                  const def = hypothesesMeta[k] || "No description available.";
                  return `
                    <tr>
                      <td><code>${k}</code></td>
                      <td><strong>${score.toFixed(4)}</strong></td>
                      <td>${def}</td>
                      <td>${score > 0.5 ? '<span style="color: var(--state-t0);">Supported</span>' : '<span style="color: var(--text-muted);">Uncorroborated</span>'}</td>
                    </tr>
                  `;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Hypothesis Scores Plot
    const hypoNames = Object.keys(scores).map((k) => k.replace(/_/g, " "));
    const hypoVals = Object.values(scores);

    const trace = {
      x: hypoVals,
      y: hypoNames,
      type: "bar",
      orientation: "h",
      marker: {
        color: hypoVals.map((v) => (v >= 0.5 ? "#38bdf8" : "#94a3b8")),
      },
    };

    buildPlot(
      "hypo-score-plot",
      [trace],
      {
        xaxis: { title: "Evidence Score [0.0, 1.0]", range: [0, 1.05] },
        yaxis: { automargin: true },
        margin: { l: 180, r: 20, t: 30, b: 50 },
      }
    );

    // CSV Download
    const dlBtn = document.getElementById("download-hypo-csv");
    if (dlBtn) {
      dlBtn.onclick = () => {
        const table = document.getElementById("hypo-audit-table");
        if (table) exportTableToCSV(table, `hypotheses_audit_${sid}.csv`);
      };
    }
  }

  function getTopHypothesis(scores) {
    let topKey = "None";
    let maxVal = -1;
    for (const [k, v] of Object.entries(scores)) {
      if (v > maxVal) {
        maxVal = v;
        topKey = k;
      }
    }
    return topKey.replace(/_/g, " ");
  }

  sel.addEventListener("change", updateView);
  updateView();
}
