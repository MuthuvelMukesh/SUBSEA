/**
 * Page 2: Scenario Explorer (S01–S22)
 */

import { renderBanner } from "../banner.js";
import { renderBadge, renderKPI, TOOLTIPS } from "../components.js";
import { buildPlot } from "../charts.js";

let catalog = [];
let allRuns = {};

export async function render(container) {
  renderBanner("SIMULATION");

  try {
    const [scRes, runsRes] = await Promise.all([
      fetch("data/scenarios.json"),
      fetch("data/scenario_runs.json"),
    ]);
    const scData = await scRes.json();
    const runsData = await runsRes.json();
    catalog = scData.scenarios || [];
    allRuns = runsData.runs || {};
  } catch (err) {
    console.error("Failed to load scenario data", err);
  }

  container.innerHTML = `
    <!-- Scenario Selection Controls -->
    <div class="control-row">
      <div class="control-group" style="flex: 1; min-width: 250px;">
        <label class="control-label" for="scenario-select">Scenario Identifier</label>
        <select id="scenario-select" class="select-input">
          ${catalog.map((s) => `<option value="${s.scenario_id}">${s.scenario_id}: ${s.description}</option>`).join("")}
        </select>
      </div>

      <div class="control-group" style="width: 200px;">
        <label class="control-label" for="attack-select">Adversarial Attack</label>
        <select id="attack-select" class="select-input">
          <option value="none">none (Clean)</option>
          <option value="ais_spoofing">ais_spoofing</option>
          <option value="transponder_suppression">transponder_suppression</option>
          <option value="timestamp_manipulation">timestamp_manipulation</option>
          <option value="spatial_manipulation">spatial_manipulation</option>
          <option value="combined_evasion">combined_evasion</option>
        </select>
      </div>

      <div class="control-group" style="width: 140px;">
        <label class="control-label" for="severity-select">Attack Severity</label>
        <select id="severity-select" class="select-input">
          <option value="0.0">0.0 (Baseline)</option>
          <option value="0.25">0.25</option>
          <option value="0.5">0.50</option>
          <option value="0.75">0.75</option>
          <option value="1.0">1.00 (Max)</option>
        </select>
      </div>
    </div>

    <!-- Active Run Result Display -->
    <div id="scenario-result-view"></div>
  `;

  const scSelect = document.getElementById("scenario-select");
  const atkSelect = document.getElementById("attack-select");
  const sevSelect = document.getElementById("severity-select");

  function updateView() {
    const sid = scSelect.value;
    const atk = atkSelect.value;
    const sev = atk === "none" ? "0.0" : sevSelect.value;

    sevSelect.disabled = atk === "none";

    const scMeta = catalog.find((s) => s.scenario_id === sid) || {};
    const runInfo = allRuns[sid]?.[atk]?.[sev] || allRuns[sid]?.["none"]?.["0.0"];

    if (!runInfo) {
      document.getElementById("scenario-result-view").innerHTML = `
        <div class="empty-state">
          <h3>Run Data Unavailable</h3>
          <p>No precomputed run found for ${sid} / ${atk} / ${sev}</p>
        </div>
      `;
      return;
    }

    const res = runInfo.result;
    const v = runInfo.vessel;

    document.getElementById("scenario-result-view").innerHTML = `
      <!-- KPI Cards -->
      <div class="grid-cols-4">
        ${renderKPI("Decision State", renderBadge(res.decision), "Gate Output", TOOLTIPS[res.decision])}
        ${renderKPI("Physical Confidence (C_P)", res.physical_confidence.toFixed(3), "Sensor Vibration Energy", TOOLTIPS.CP)}
        ${renderKPI("Association Confidence (C_A)", res.association_confidence.toFixed(3), "Kinematic Spatial-Temporal", TOOLTIPS.CA)}
        ${renderKPI("Reliability (R) / Uncertainty (U)", `${res.reliability.toFixed(2)} / ${res.uncertainty.toFixed(2)}`, "Health & Epistemic Uncertainty", "R = Sensor availability/health, U = Uncertainty.")}
      </div>

      <!-- Two-Column Layout: Details & Hypothesis Chart -->
      <div class="grid-cols-2">
        <!-- Ground Truth & Kinematics Card -->
        <div class="card">
          <div class="card-title">
            <span>Scenario Ground Truth & Vessel Telemetry</span>
            <span class="brand-badge">${sid}</span>
          </div>

          <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">
            <strong>Description:</strong> ${scMeta.description}
          </div>

          <div class="table-container">
            <table class="data-table">
              <tbody>
                <tr>
                  <td><strong>Vessel Present</strong></td>
                  <td>${scMeta.vessel_present ? "✓ Yes" : "✗ No (Ambient/No Vessel)"}</td>
                  <td><strong>Disturbance Present</strong></td>
                  <td>${scMeta.disturbance_present ? "✓ Yes (High Strain/Energy)" : "✗ No (Normal Background)"}</td>
                </tr>
                <tr>
                  <td><strong>Environmental Event</strong></td>
                  <td>${scMeta.environmental_event ? "✓ Active (Storm/Seismic)" : "✗ None"}</td>
                  <td><strong>Sensor Failure Flag</strong></td>
                  <td>${scMeta.sensor_failure ? "✓ Degraded Hardware" : "✗ Healthy"}</td>
                </tr>
                <tr>
                  <td><strong>Packet Loss Ratio</strong></td>
                  <td>${(scMeta.packet_loss * 100).toFixed(0)}%</td>
                  <td><strong>Adversarial Evasion</strong></td>
                  <td>${scMeta.spoofing ? "✓ Active Spoofing/Manipulation" : "✗ None"}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="card-title" style="margin-top: 0.75rem;">
            <span>AIS Vessel Kinematics (Observed)</span>
          </div>

          ${
            v
              ? `
            <div class="table-container">
              <table class="data-table">
                <tbody>
                  <tr>
                    <td><strong>Vessel ID</strong></td>
                    <td><code>${v.vessel_id}</code></td>
                    <td><strong>Reported (AIS Active)</strong></td>
                    <td>${v.reported ? "✓ Reported" : "✗ Suppressed / Silent"}</td>
                  </tr>
                  <tr>
                    <td><strong>2D Position (Metric)</strong></td>
                    <td><code>(${v.position[0].toFixed(1)} m, ${v.position[1].toFixed(1)} m)</code></td>
                    <td><strong>Distance to Cable</strong></td>
                    <td><strong>${v.distance_to_cable_m.toFixed(1)} m</strong></td>
                  </tr>
                  <tr>
                    <td><strong>Speed Over Ground</strong></td>
                    <td>${v.speed.toFixed(1)} m/s</td>
                    <td><strong>Heading</strong></td>
                    <td>${v.heading.toFixed(0)}°</td>
                  </tr>
                </tbody>
              </table>
            </div>
          `
              : `<div style="font-size: 0.85rem; color: var(--text-muted); padding: 0.5rem 0;">No vessel associated with this scenario (vessel is None).</div>`
          }
        </div>

        <!-- Hypotheses Scores & Rationale -->
        <div class="card">
          <div class="card-title">
            <span>Competing Hypotheses Scores & Rationale</span>
          </div>

          <div id="hypotheses-bar-chart" class="chart-container" style="min-height: 240px;"></div>

          <div style="font-size: 0.85rem; margin-top: 0.5rem;">
            <strong>Decision Rationale:</strong>
            <ul style="padding-left: 1.25rem; color: var(--text-muted); margin-top: 0.25rem;">
              ${res.rationale.map((r) => `<li>${r}</li>`).join("")}
            </ul>
          </div>

          ${
            res.missing_corroboration.length > 0
              ? `
            <div style="font-size: 0.85rem; margin-top: 0.5rem;">
              <strong style="color: var(--state-t1);">Missing Corroboration:</strong>
              <span style="color: var(--text-muted);">${res.missing_corroboration.join(", ")}</span>
            </div>
          `
              : ""
          }
        </div>
      </div>
    `;

    // Render Hypotheses Plotly Bar Chart
    const hScores = res.hypothesis_scores;
    const hLabels = [
      "Vessel Disturbance",
      "Environmental",
      "Non-Vessel Mech",
      "Sensor Fault",
    ];
    const hKeys = [
      "vessel_associated_disturbance",
      "environmental_disturbance",
      "non_vessel_mechanical_disturbance",
      "sensor_system_fault",
    ];
    const hValues = hKeys.map((k) => hScores[k] || 0.0);

    const barTrace = {
      x: hValues,
      y: hLabels,
      type: "bar",
      orientation: "h",
      marker: {
        color: ["#f97316", "#3b82f6", "#10b981", "#8b5cf6"],
      },
      text: hValues.map((v) => v.toFixed(3)),
      textposition: "auto",
    };

    buildPlot("hypotheses-bar-chart", [barTrace], {
      margin: { l: 150, r: 20, t: 20, b: 30 },
      xaxis: { title: "Posterior Probability Score", range: [0, 1.05] },
      yaxis: { automargin: true },
    });
  }

  scSelect.addEventListener("change", updateView);
  atkSelect.addEventListener("change", updateView);
  sevSelect.addEventListener("change", updateView);

  updateView();
}
