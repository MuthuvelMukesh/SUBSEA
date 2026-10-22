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
  W0: "W0 (Normal / Safe): Ambient background conditions, all channels within baseline thresholds.",
  W1: "W1 (Watch): Subtle acoustic, mechanical, or kinematic anomaly observed; advance monitoring.",
  W2: "W2 (Advisory): Multi-sensor corroborated anomalous trend with potential cable corridor interaction.",
  W3: "W3 (Urgent): Imminent cable hazard, physical strike, or high-speed critical boundary intrusion.",
  WX: "WX (Data Quality / Degraded): Stale, missing, or contradictory telemetry; safety fail-safe state.",
  QUALITY_GOOD: "Good Quality: Valid packets, current timestamps, and corroborating channel readings.",
  QUALITY_DEGRADED: "Degraded Quality: Increased sensor noise, partial channel dropouts, or clock skew.",
  QUALITY_STALE: "Stale Quality: Telemetry age exceeded max freshness threshold without new frames.",
  QUALITY_MISSING: "Missing Quality: Hardware channel completely disconnected or omitted.",
  QUALITY_INVALID: "Invalid Quality: Out-of-bounds telemetry values or malformed frame CRC.",
  QUALITY_CONTRADICTORY: "Contradictory Quality: Incompatible simultaneous readings between redundant channels.",
};

export function renderBadge(state) {
  const s = (state || "T0").toUpperCase();
  return `<span class="state-badge ${s}" title="${TOOLTIPS[s] || s}">${s}</span>`;
}

export function renderWarningBadge(state, label = "") {
  const s = (state || "W0").toUpperCase();
  const text = label ? `${s}: ${label}` : s;
  return `<span class="state-badge ${s}" title="${TOOLTIPS[s] || s}">${text}</span>`;
}

export function renderProvenanceBadge(source) {
  const src = (source || "SIMULATED").toUpperCase();
  const cls = src === "PHYSICAL" ? "physical" : "simulated";
  return `<span class="provenance-badge ${cls}" title="Data Provenance: ${src}">${src}</span>`;
}

export function renderQualityBadge(quality) {
  const q = (quality || "GOOD").toUpperCase();
  const key = `QUALITY_${q}`;
  const tip = TOOLTIPS[key] || `Data Quality: ${q}`;
  return `<span class="quality-pill ${q.toLowerCase()}" title="${tip}">${q}</span>`;
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
