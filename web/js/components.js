/**
 * Shared UI Components and Helpers
 */

export const TOOLTIPS = {
  CP: "Physical Confidence (C_P): Signal energy and spectral disturbance intensity score in [0.0, 1.0].",
  CA: "Association Confidence (C_A): Kinematic spatial, temporal, and behavioural correlation with AIS track in [0.0, 1.0].",
  R: "Reliability (R): Sensor operational health and telemetry packet availability score in [0.0, 1.0].",
  U: "Uncertainty (U): Composite epistemic uncertainty score reflecting missing channels, noise, or conflict in [0.0, 1.0].",
  T0: "T0 (Normal / Safe): Healthy sensor in unperturbed ambient background.",
  T1: "T1 (Uncorroborated Disturbance): Physical disturbance detected without corroborating AIS vessel presence.",
  T2: "T2 (Corroborated Alert): Strong physical disturbance with confirmed vessel spatial-temporal proximity.",
  T3: "T3 (Imminent Risk): High-confidence corroborated disturbance under low uncertainty threshold.",
  TX: "TX (Fail-Closed Degraded Alert): Sensor hardware, optical link, or backhaul failure requiring operator inspection.",
};

export function renderBadge(state) {
  const s = (state || "T0").toUpperCase();
  return `<span class="state-badge ${s}" title="${TOOLTIPS[s] || s}">${s}</span>`;
}

export function renderKPI(label, value, sub = "", tooltip = "") {
  const tooltipHtml = tooltip ? ` <span class="tooltip-trigger">ⓘ<span class="tooltip-box">${tooltip}</span></span>` : "";
  return `
    <div class="card kpi-card">
      <div class="kpi-label">${label}${tooltipHtml}</div>
      <div class="kpi-value">${value}</div>
      ${sub ? `<div class="kpi-sub">${sub}</div>` : ""}
    </div>
  `;
}
