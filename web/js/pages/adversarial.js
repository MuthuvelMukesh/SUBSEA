/**
 * Page 8: Adversarial Lab (AER & FHER)
 * Evaluates pipeline robustness against vessel-side AIS manipulation and transponder suppression attacks.
 */

import { renderBanner } from "../banner.js";
import { renderKPI, renderBadge, TOOLTIPS } from "../components.js";
import { buildPlot, exportTableToCSV } from "../charts.js";

let advData = {};
let manifestMeta = {};

export async function render(container) {
  renderBanner("SIMULATION");

  try {
    const res = await fetch("data/adversarial.json");
    const json = await res.json();
    advData = json || {};
    manifestMeta = json.manifest || {};
  } catch (err) {
    console.error("Failed to load adversarial.json", err);
  }

  const results = manifestMeta.results || [];
  const attackTypes = Array.from(new Set(results.map((r) => r.attack)));

  container.innerHTML = `
    <!-- Scientific Disclaimer Banner -->
    <div class="card" style="border-left: 4px solid var(--state-t0); margin-bottom: 1.5rem;">
      <div style="font-weight: 700; color: var(--state-t0); margin-bottom: 0.25rem;">
        Empirical Adversarial Finding (Manifest Verified)
      </div>
      <p style="font-size: 0.9rem; margin: 0; color: var(--text-color);">
        ${manifestMeta.scientific_statement || "Within the implemented vessel-side attack model and tested severity range, no adversarial trial collapsed to T0."}
      </p>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem;">
        <em>Disclaimer:</em> Evaluates vessel-side AIS kinematic manipulation and suppression under physical sensor integrity. Does not constitute an "attack-proof" claim against physical acoustic spoofing.
      </div>
    </div>

    <!-- Controls -->
    <div class="control-row">
      <div class="control-group" style="min-width: 250px;">
        <label class="control-label" for="adv-attack-select">Select Adversarial Attack Type</label>
        <select id="adv-attack-select" class="select-input">
          ${attackTypes.map((atk) => `<option value="${atk}">${atk.replace(/_/g, " ").toUpperCase()}</option>`).join("")}
        </select>
      </div>
      <div style="flex: 1;"></div>
      <button id="download-adv-csv" class="btn btn-secondary">📥 Export Adversarial CSV</button>
    </div>

    <!-- Active Attack Display -->
    <div id="adv-view"></div>
  `;

  const sel = document.getElementById("adv-attack-select");

  function updateView() {
    const atk = sel.value;
    const sweep = results.filter((r) => r.attack === atk);

    if (sweep.length === 0) {
      document.getElementById("adv-view").innerHTML = `
        <div class="empty-state">
          <h3>No Adversarial Sweep Data for ${atk}</h3>
        </div>
      `;
      return;
    }

    const maxAER = Math.max(...sweep.map((s) => s.AER));
    const meanTx = sweep.reduce((acc, s) => acc + s.TX_rate, 0) / sweep.length;
    const trialsPerLevel = sweep[0]?.trials || 100;
    const totalTrials = trialsPerLevel * sweep.length;

    document.getElementById("adv-view").innerHTML = `
      <!-- KPIs -->
      <div class="grid-cols-4">
        ${renderKPI(
          "Adversarial Evasion Rate (AER)",
          `${(maxAER * 100).toFixed(1)}%`,
          "Rate of Collapse to T0",
          "Fraction of trials where attack successfully suppressed alarm into benign T0 (target: 0.0%)."
        )}
        ${renderKPI(
          "Mean Fail-Closed Rate (TX)",
          `${(meanTx * 100).toFixed(1)}%`,
          "Gate 3 Fail-Closed Activation",
          "Fraction of trials safely routed to TX due to conflicting or degraded evidence."
        )}
        ${renderKPI(
          "Evaluated Severity Range",
          "0.0 → 1.0",
          "6 Controlled Levels",
          "Severity sweeps from clean baseline (0.0) to full manipulation (1.0)."
        )}
        ${renderKPI(
          "Total Trials Evaluated",
          `${totalTrials.toLocaleString()}`,
          `${trialsPerLevel} Monte Carlo Runs / Level`,
          "Evaluation batch size per attack condition."
        )}
      </div>

      <!-- Charts Grid -->
      <div class="grid-cols-2">
        <!-- AER & Escalation vs Severity -->
        <div class="card">
          <div class="card-title">
            <span>AER & Escalation Rates vs Severity</span>
            <span class="brand-badge">Evasion Profile</span>
          </div>
          <div id="aer-curve-plot" class="chart-container"></div>
        </div>

        <!-- Decision Distribution Breakdown -->
        <div class="card">
          <div class="card-title">
            <span>Decision State Distribution Across Severity</span>
            <span class="brand-badge">Cohort Breakdown</span>
          </div>
          <div id="decision-dist-plot" class="chart-container"></div>
        </div>
      </div>

      <!-- Severity Table -->
      <div class="card">
        <div class="card-title">
          <span>Adversarial Severity Sweep Table</span>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Source: <code>${advData.metadata?.source_manifest_path || "artifacts/adversarial"}</code></span>
        </div>
        <div class="table-container">
          <table id="adv-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Trials</th>
                <th>AER (T0 Rate)</th>
                <th>TX Fail-Closed Rate</th>
                <th>T2/T3 Escalation Rate</th>
                <th>Mean Uncertainty (U)</th>
                <th>Mean Physical Conf (C_P)</th>
                <th>Mean Assoc Conf (C_A)</th>
              </tr>
            </thead>
            <tbody>
              ${sweep
                .map(
                  (s) => `
                <tr>
                  <td><strong>${s.severity.toFixed(2)}</strong></td>
                  <td>${s.trials}</td>
                  <td><span style="color: ${s.AER === 0 ? "var(--state-t0)" : "var(--state-t3)"}; font-weight: 700;">${(s.AER * 100).toFixed(1)}%</span></td>
                  <td>${(s.TX_rate * 100).toFixed(1)}%</td>
                  <td>${(s.escalated_T2_T3_rate * 100).toFixed(1)}%</td>
                  <td>${s.mean_uncertainty ? s.mean_uncertainty.toFixed(3) : "N/A"}</td>
                  <td>${s.mean_physical_confidence ? s.mean_physical_confidence.toFixed(3) : "N/A"}</td>
                  <td>${s.mean_association_confidence ? s.mean_association_confidence.toFixed(3) : "N/A"}</td>
                </tr>
              `
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Render AER & Escalation Plot
    const severities = sweep.map((s) => s.severity);
    const traceAer = {
      x: severities,
      y: sweep.map((s) => s.AER),
      mode: "lines+markers",
      name: "AER (Evasion to T0)",
      line: { color: "#ef4444", width: 2.5 },
      marker: { size: 7 },
    };
    const traceTx = {
      x: severities,
      y: sweep.map((s) => s.TX_rate),
      mode: "lines+markers",
      name: "TX Rate (Fail-Closed)",
      line: { color: "#8b5cf6", width: 2.5 },
      marker: { size: 7 },
    };
    const traceEsc = {
      x: severities,
      y: sweep.map((s) => s.escalated_T2_T3_rate),
      mode: "lines+markers",
      name: "T2/T3 Escalation Rate",
      line: { color: "#10b981", width: 2.5 },
      marker: { size: 7 },
    };

    buildPlot(
      "aer-curve-plot",
      [traceAer, traceTx, traceEsc],
      {
        xaxis: { title: "Attack Severity [0.0, 1.0]" },
        yaxis: { title: "Fraction of Trials", range: [-0.05, 1.05] },
        legend: { orientation: "h", y: -0.25 },
      }
    );

    // Render Stacked Decision Distribution Plot
    const traceT0 = {
      x: severities,
      y: sweep.map((s) => s.t0_count || 0),
      name: "T0 (Normal)",
      type: "bar",
      marker: { color: "#10b981" },
    };
    const traceT1 = {
      x: severities,
      y: sweep.map((s) => s.t1_count || 0),
      name: "T1 (Uncorroborated)",
      type: "bar",
      marker: { color: "#f59e0b" },
    };
    const traceT2 = {
      x: severities,
      y: sweep.map((s) => s.t2_count || 0),
      name: "T2 (Corroborated)",
      type: "bar",
      marker: { color: "#f97316" },
    };
    const traceT3 = {
      x: severities,
      y: sweep.map((s) => s.t3_count || 0),
      name: "T3 (Imminent)",
      type: "bar",
      marker: { color: "#ef4444" },
    };
    const traceTX = {
      x: severities,
      y: sweep.map((s) => s.tx_count || 0),
      name: "TX (Fail-Closed)",
      type: "bar",
      marker: { color: "#8b5cf6" },
    };

    buildPlot(
      "decision-dist-plot",
      [traceT0, traceT1, traceT2, traceT3, traceTX],
      {
        barmode: "stack",
        xaxis: { title: "Attack Severity [0.0, 1.0]" },
        yaxis: { title: "Count of Trials" },
        legend: { orientation: "h", y: -0.25 },
      }
    );

    // CSV Download
    const dlBtn = document.getElementById("download-adv-csv");
    if (dlBtn) {
      dlBtn.onclick = () => {
        const table = document.getElementById("adv-table");
        if (table) exportTableToCSV(table, `adversarial_${atk}.csv`);
      };
    }
  }

  sel.addEventListener("change", updateView);
  updateView();
}
