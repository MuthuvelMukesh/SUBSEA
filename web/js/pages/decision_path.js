/**
 * Page 6: Decision Path Explainer
 * Visualizes the 5-stage sequential decision gating logic of decide() from subsea.decision.
 */

import { renderBanner } from "../banner.js";
import { renderKPI, renderBadge, TOOLTIPS } from "../components.js";

let gatesData = [];
let runsData = {};
let configData = {};

export async function render(container) {
  renderBanner("SIMULATION");

  try {
    const [gatesRes, runsRes, cfgRes] = await Promise.all([
      fetch("data/decision_paths.json"),
      fetch("data/scenario_runs.json"),
      fetch("data/config.json"),
    ]);
    const gatesJson = await gatesRes.json();
    const runsJson = await runsRes.json();
    const cfgJson = await cfgRes.json();

    gatesData = gatesJson.gates || [];
    runsData = runsJson.runs || {};
    configData = cfgJson.effective_thresholds || {
      tx_reliability: 0.35,
      physical: 0.55,
      tx_uncertainty: 0.65,
      association: 0.60,
      t3: 0.85,
      t3_uncertainty: 0.35,
    };
  } catch (err) {
    console.error("Failed to load decision path data", err);
  }

  const sids = Object.keys(runsData);

  container.innerHTML = `
    <!-- Scenario Selection and Mode Switcher -->
    <div class="control-row">
      <div class="control-group" style="min-width: 250px;">
        <label class="control-label" for="path-scenario-select">Select Scenario to Trace</label>
        <select id="path-scenario-select" class="select-input">
          ${sids.map((id) => `<option value="${id}">${id} Ground-Truth Decision Path</option>`).join("")}
        </select>
      </div>
      <div style="flex: 1;"></div>
      <div style="font-size: 0.85rem; color: var(--text-muted); align-self: center;">
        Source: <code>subsea.decision.decide()</code> & <code>config/system.yaml</code>
      </div>
    </div>

    <div class="grid-cols-2">
      <!-- Left Column: Sequential Gating Pipeline -->
      <div>
        <div class="card">
          <div class="card-title">
            <span>Sequential Decision Gating Hierarchy</span>
            <span class="brand-badge">Deterministic Engine</span>
          </div>
          <div id="gate-flow-container" style="display: flex; flex-direction: column; gap: 1rem; margin-top: 1rem;">
            <!-- Rendered by updateView -->
          </div>
        </div>
      </div>

      <!-- Right Column: Exploratory Sandbox & Firing Summary -->
      <div>
        <!-- Evaluated Decision Summary Card -->
        <div class="card" style="margin-bottom: 1.5rem;">
          <div class="card-title">
            <span>Evaluation Result & Active Gate</span>
            <span id="active-scenario-badge" class="brand-badge">S01</span>
          </div>
          <div id="evaluation-summary"></div>
        </div>

        <!-- Interactive What-If Exploratory Sandbox -->
        <div class="card">
          <div class="card-title">
            <span>Exploratory Sandbox (What-If Analysis)</span>
            <span style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Simulated Input</span>
          </div>
          <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1.25rem;">
            Adjust sliders to simulate hypothetical telemetry inputs. Labelled <strong>Exploratory</strong>: does not alter precomputed baseline manifests.
          </p>

          <div style="display: flex; flex-direction: column; gap: 1rem;">
            <div>
              <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;">
                <span title="${TOOLTIPS.R}">Sensor Reliability (R)</span>
                <strong id="val-r">1.00</strong>
              </div>
              <input type="range" id="slider-r" min="0" max="1" step="0.01" value="1.00" style="width: 100%;">
            </div>

            <div>
              <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;">
                <span title="${TOOLTIPS.CP}">Physical Confidence (C_P)</span>
                <strong id="val-cp">0.01</strong>
              </div>
              <input type="range" id="slider-cp" min="0" max="1" step="0.01" value="0.01" style="width: 100%;">
            </div>

            <div>
              <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;">
                <span title="${TOOLTIPS.U}">Epistemic Uncertainty (U)</span>
                <strong id="val-u">0.38</strong>
              </div>
              <input type="range" id="slider-u" min="0" max="1" step="0.01" value="0.38" style="width: 100%;">
            </div>

            <div>
              <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;">
                <span title="${TOOLTIPS.CA}">Association Confidence (C_A)</span>
                <strong id="val-ca">0.00</strong>
              </div>
              <input type="range" id="slider-ca" min="0" max="1" step="0.01" value="0.00" style="width: 100%;">
            </div>

            <div style="padding: 1rem; border-radius: var(--radius); background: var(--bg-hover); margin-top: 0.5rem;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600;">Sandbox Simulated Decision:</span>
                <span id="sandbox-decision-badge"></span>
              </div>
              <div id="sandbox-gate-reason" style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem;"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Function to simulate decide() logic
  function evaluateDecide(cp, ca, r, u) {
    const txRel = configData.tx_reliability ?? 0.35;
    const thPhys = configData.physical ?? 0.55;
    const txUnc = configData.tx_uncertainty ?? 0.65;
    const thAssoc = configData.association ?? 0.60;
    const thT3 = configData.t3 ?? 0.85;
    const thT3Unc = configData.t3_uncertainty ?? 0.35;

    // Gate 1: Reliability
    if (r <= txRel) {
      return {
        gate: 1,
        decision: "TX",
        reason: `Gate 1 Triggered: Reliability R (${r.toFixed(3)}) <= ${txRel}. Hardware / comms failure fail-closed alert.`,
      };
    }
    // Gate 2: Physical Confidence
    if (cp < thPhys) {
      return {
        gate: 2,
        decision: "T0",
        reason: `Gate 2 Triggered: Physical Confidence C_P (${cp.toFixed(3)}) < ${thPhys}. Ambient background unperturbed.`,
      };
    }
    // Gate 3: Uncertainty
    if (u >= txUnc) {
      return {
        gate: 3,
        decision: "TX",
        reason: `Gate 3 Triggered: Epistemic Uncertainty U (${u.toFixed(3)}) >= ${txUnc}. High conflict / missing data fail-closed alert.`,
      };
    }
    // Gate 4: Association
    if (ca < thAssoc) {
      return {
        gate: 4,
        decision: "T1",
        reason: `Gate 4 Triggered: Association Confidence C_A (${ca.toFixed(3)}) < ${thAssoc}. Uncorroborated physical disturbance.`,
      };
    }
    // Gate 5: Escalation
    const score = (cp + ca) / 2.0; // surrogate score for escalation check
    if (score >= thT3 && u < thT3Unc) {
      return {
        gate: 5,
        decision: "T3",
        reason: `Gate 5 Triggered: High confidence score (${score.toFixed(3)} >= ${thT3}) and low uncertainty U (${u.toFixed(3)} < ${thT3Unc}). Escalate to T3 Imminent Risk.`,
      };
    } else {
      return {
        gate: 5,
        decision: "T2",
        reason: `Gate 5 Triggered: Strong physical and vessel corroboration, nominal escalation. Corroborated Alert T2.`,
      };
    }
  }

  // Render Gate Cards
  function renderGateCards(activeGate) {
    const container = document.getElementById("gate-flow-container");
    if (!container) return;

    container.innerHTML = gatesData
      .map((g) => {
        const isActive = g.gate === activeGate;
        const borderColor = isActive ? "var(--state-t2)" : "var(--border-color)";
        const bgColor = isActive ? "rgba(249, 115, 22, 0.08)" : "var(--bg-card)";
        const statusIcon = isActive ? "👉 <strong>FIRED HERE</strong>" : "Passed (Next Gate)";

        return `
          <div style="border: 2px solid ${borderColor}; background: ${bgColor}; border-radius: var(--radius); padding: 1rem; transition: all 0.2s ease;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <span style="font-weight: 700; font-size: 0.95rem;">Gate ${g.gate}: ${g.name}</span>
              <span style="font-size: 0.8rem; ${isActive ? "color: var(--state-t2); font-weight: bold;" : "color: var(--text-muted);"}">${statusIcon}</span>
            </div>
            <div style="font-family: monospace; font-size: 0.85rem; color: var(--primary); margin-bottom: 0.4rem;">
              Rule: IF ${g.condition} THEN ${renderBadge(g.target_decision.slice(0, 2))}
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); line-height: 1.4;">
              ${g.explanation}
            </div>
          </div>
        `;
      })
      .join("");
  }

  const sel = document.getElementById("path-scenario-select");

  function updateScenarioView() {
    const sid = sel.value;
    document.getElementById("active-scenario-badge").textContent = sid;

    const run = runsData[sid]?.ais_spoofing?.["0.0"]?.result;
    if (!run) return;

    const cp = run.physical_confidence;
    const ca = run.association_confidence;
    const r = run.reliability;
    const u = run.uncertainty;

    const evalResult = evaluateDecide(cp, ca, r, u);

    // Sync sliders to scenario values
    document.getElementById("slider-cp").value = cp;
    document.getElementById("slider-ca").value = ca;
    document.getElementById("slider-r").value = r;
    document.getElementById("slider-u").value = u;
    document.getElementById("val-cp").textContent = cp.toFixed(3);
    document.getElementById("val-ca").textContent = ca.toFixed(3);
    document.getElementById("val-r").textContent = r.toFixed(3);
    document.getElementById("val-u").textContent = u.toFixed(3);

    // Update summary
    document.getElementById("evaluation-summary").innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
        <div>
          <span style="font-size: 0.85rem; color: var(--text-muted);">Real Pipeline Decision:</span>
          <div style="margin-top: 0.25rem;">${renderBadge(run.decision)}</div>
        </div>
        <div style="text-align: right;">
          <span style="font-size: 0.85rem; color: var(--text-muted);">Deciding Gate:</span>
          <div style="font-weight: 700; color: var(--state-t2); font-size: 1.1rem;">Gate ${evalResult.gate}</div>
        </div>
      </div>
      <div style="padding: 0.75rem; background: var(--bg-hover); border-radius: var(--radius); font-size: 0.85rem; line-height: 1.4;">
        ${evalResult.reason}
      </div>
    `;

    renderGateCards(evalResult.gate);
    updateSandbox();
  }

  function updateSandbox() {
    const cp = parseFloat(document.getElementById("slider-cp").value);
    const ca = parseFloat(document.getElementById("slider-ca").value);
    const r = parseFloat(document.getElementById("slider-r").value);
    const u = parseFloat(document.getElementById("slider-u").value);

    document.getElementById("val-cp").textContent = cp.toFixed(2);
    document.getElementById("val-ca").textContent = ca.toFixed(2);
    document.getElementById("val-r").textContent = r.toFixed(2);
    document.getElementById("val-u").textContent = u.toFixed(2);

    const sbResult = evaluateDecide(cp, ca, r, u);
    document.getElementById("sandbox-decision-badge").innerHTML = renderBadge(sbResult.decision);
    document.getElementById("sandbox-gate-reason").textContent = sbResult.reason;
  }

  ["slider-cp", "slider-ca", "slider-r", "slider-u"].forEach((id) => {
    document.getElementById(id).addEventListener("input", () => {
      updateSandbox();
      const cp = parseFloat(document.getElementById("slider-cp").value);
      const ca = parseFloat(document.getElementById("slider-ca").value);
      const r = parseFloat(document.getElementById("slider-r").value);
      const u = parseFloat(document.getElementById("slider-u").value);
      const sbResult = evaluateDecide(cp, ca, r, u);
      renderGateCards(sbResult.gate);
    });
  });

  sel.addEventListener("change", updateScenarioView);
  updateScenarioView();
}
