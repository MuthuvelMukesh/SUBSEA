/**
 * Page 1: Overview & Architecture
 */

import { renderBanner } from "../banner.js";
import { renderBadge, renderWarningBadge, renderKPI, TOOLTIPS } from "../components.js";

export async function render(container) {
  renderBanner("SIMULATION");

  let data = null;
  try {
    const res = await fetch("data/overview.json");
    data = await res.json();
  } catch (err) {
    console.error("Failed to load overview.json", err);
  }

  const kpis = data?.kpis || {
    scenarios_count: 22,
    real_datasets_count: 3,
    total_simulation_trials: 2200,
    oliktok_eval_duration_days: 27.6,
    adversarial_error_rate_aer: 0.0,
  };

  container.innerHTML = `
    <!-- Live Operational Status & Quick Navigation -->
    <div class="card" style="border-left: 4px solid var(--state-t0); background: var(--bg-card); padding: 1.25rem 1.5rem;">
      <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 1rem;">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <span class="pulse-dot live"></span>
          <div>
            <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: var(--text-muted); letter-spacing: 0.05em;">
              AbyssLink Monitoring Infrastructure
            </div>
            <div style="font-size: 1.2rem; font-weight: 800; color: var(--text-main); margin-top: 0.1rem; display: flex; align-items: center; gap: 0.6rem;">
              <span>Operational Early Warning & Digital Twin System</span>
              <span class="brand-badge" style="background: rgba(16, 185, 129, 0.15); color: var(--state-t0); font-size: 0.75rem;">HEALTHY</span>
            </div>
          </div>
        </div>

        <div style="display: flex; gap: 0.75rem; align-items: center;">
          <a href="#/hil" class="btn btn-primary" style="font-size: 0.85rem; padding: 0.5rem 1rem;">
            ⚡ Open Live HIL & Digital Twin Dashboard ➔
          </a>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border-color);">
        <div>
          <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">Active Operating Mode</div>
          <div style="font-size: 0.95rem; font-weight: 700; color: var(--text-main); margin-top: 0.2rem;">
            🌐 Hybrid Digital Twin
          </div>
          <div style="font-size: 0.75rem; color: var(--text-dim);">Software benchmark channels enabled</div>
        </div>

        <div>
          <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">Early Warning State</div>
          <div style="margin-top: 0.2rem;">
            ${renderWarningBadge("W0", "NORMAL")}
          </div>
          <div style="font-size: 0.75rem; color: var(--text-dim);">Advance acoustic/kinematic watch</div>
        </div>

        <div>
          <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">Disturbance Decision</div>
          <div style="margin-top: 0.2rem;">
            ${renderBadge("T0")} <span style="font-size: 0.85rem; font-weight: 600; color: var(--state-t0);">NOMINAL</span>
          </div>
          <div style="font-size: 0.75rem; color: var(--text-dim);">Decoupled multimodal fusion gate</div>
        </div>

        <div>
          <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">Hardware Link Status</div>
          <div style="font-size: 0.95rem; font-weight: 700; color: var(--text-muted); margin-top: 0.2rem;">
            🔌 Web Serial Ready
          </div>
          <div style="font-size: 0.75rem; color: var(--text-dim);">115200 Baud / 300ms packet interval</div>
        </div>
      </div>
    </div>

    <!-- Top KPI Grid -->
    <div class="grid-cols-4">
      ${renderKPI("Controlled Scenarios", kpis.scenarios_count, "S01–S22 Verified Matrix", "22 distinct operational and adversarial benchmark scenarios.")}
      ${renderKPI("Real Deployments", kpis.real_datasets_count, "Marlinks, EMSO, Oliktok", "Real submarine fiber DAS datasets across North Sea, Mediterranean, and Arctic.")}
      ${renderKPI("Simulation Trials", kpis.total_simulation_trials.toLocaleString(), "100 Trials / Scenario (Seed 42)", "Full Monte Carlo reproducible trial count.")}
      ${renderKPI("Arctic Continuous DAS", `${kpis.oliktok_eval_duration_days} Days`, "215 Hours, 183 Channels", "Continuous shallow Arctic seafloor deployment.")}
    </div>

    <!-- Framework Purpose Card -->
    <div class="card">
      <div class="card-title">
        <span>Framework Objective & Provenance Boundaries</span>
        <span class="brand-badge">IEEE Reference System</span>
      </div>
      <p style="color: var(--text-muted); font-size: 0.9rem;">
        An uncertainty-aware multimodal evidence fusion framework for vessel-associated subsea cable disturbance assessment under adversarial uncertainty.
        The system decouples physical sensor disturbance detection from vessel attribution, avoiding false alarms during innocent cable crossings, environmental storms, and intentional vessel AIS evasions.
      </p>
      <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 0.5rem;">
        <span class="cohort-badge" style="background: var(--cohort-sim-bg); color: var(--cohort-sim);">Simulation: 22 Scenarios (N=2,200)</span>
        <span class="cohort-badge" style="background: var(--cohort-real-bg); color: var(--cohort-real);">Real DAS: 3 Continents (27.6 Days)</span>
        <span class="cohort-badge" style="background: var(--cohort-hil-bg); color: var(--cohort-hil);">HIL: ESP32 AbyssLink (115200 Baud)</span>
      </div>
    </div>

    <!-- Decision State Hierarchy -->
    <div class="card">
      <div class="card-title">
        <span>Decoupled Decision Hierarchy (T0, T1, T2, T3, TX)</span>
      </div>
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>State</th>
              <th>Operational Meaning</th>
              <th>Trigger Conditions</th>
              <th>Action Implication</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>${renderBadge("T0")}</td>
              <td><strong>Safe / Ambient Baseline</strong></td>
              <td><code>C_P < 0.55</code> on healthy sensor (R > 0.35)</td>
              <td>No disturbance; normal background monitoring.</td>
            </tr>
            <tr>
              <td>${renderBadge("T1")}</td>
              <td><strong>Uncorroborated Disturbance</strong></td>
              <td><code>C_P >= 0.55</code> AND <code>C_A < 0.60</code></td>
              <td>Physical event detected (e.g. biological, mechanical) without AIS vessel corroboration.</td>
            </tr>
            <tr>
              <td>${renderBadge("T2")}</td>
              <td><strong>Corroborated Interaction Alert</strong></td>
              <td><code>Score >= 0.65</code> with vessel corroboration (C_A >= 0.60)</td>
              <td>Verified proximity between vessel and cable disturbance; advisory dispatch.</td>
            </tr>
            <tr>
              <td>${renderBadge("T3")}</td>
              <td><strong>Imminent High-Confidence Risk</strong></td>
              <td><code>Score >= 0.85</code> AND <code>U < 0.35</code></td>
              <td>High physical disturbance directly aligned with vessel track under low uncertainty; emergency alert.</td>
            </tr>
            <tr>
              <td>${renderBadge("TX")}</td>
              <td><strong>Fail-Closed Degraded Sensor Alert</strong></td>
              <td><code>R <= 0.35</code> OR <code>U >= 0.65</code> (when C_P >= 0.55)</td>
              <td>Sensor hardware dropouts, optical link break, or conflicting evidence; operator inspection.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Three Cohorts Detail -->
    <div class="grid-cols-2">
      <div class="card">
        <div class="card-title">
          <span>Three Independent Validation Cohorts</span>
        </div>
        <ul style="padding-left: 1.25rem; font-size: 0.85rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 0.6rem;">
          <li><strong>Cohort 1 (Controlled Simulation):</strong> Validates theoretical fusion, hypothesis scoring, and adversarial robustness across 2,200 trials.</li>
          <li><strong>Cohort 2 (Real Submarine DAS):</strong> Evaluates empirical robustness on real seabed fiber cables: Marlinks ($\rho = 0.948$), EMSO noise floor ($\text{CV} = 0.0008$), and Oliktok ($0.0\%$ T2/T3 escalations over 27.6 days).</li>
          <li><strong>Cohort 3 (Hardware-in-the-Loop):</strong> Validates real-time serial protocol decoding, streaming adaptation, and optical link fault handling from AbyssLink ESP32 hardware.</li>
        </ul>
      </div>

      <div class="card">
        <div class="card-title">
          <span>Strict Scientific Disclaimers</span>
        </div>
        <ul style="padding-left: 1.25rem; font-size: 0.85rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 0.6rem;">
          <li><strong>No Causal Ground Truth:</strong> Sensor measurements reflect strain/vibration intensity, not metallurgical cable damage.</li>
          <li><strong>Unlabelled Ocean Datasets:</strong> Unlabelled DAS datasets (Oliktok) validate physical detector ambient stability and false-alarm avoidance, not vessel classification.</li>
          <li><strong>Cohort Separation:</strong> Simulation and real DAS datasets are strictly segregated; metrics are never cross-pooled.</li>
          <li><strong>Synthetic Accelerometer in HIL:</strong> HIL accelerometer observations are synthesized from binary vibration flags.</li>
        </ul>
      </div>
    </div>
  `;
}
