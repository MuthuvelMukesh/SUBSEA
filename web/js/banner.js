/**
 * Data-Kind Banner Component for Subsea Web App
 * Guarantees strict cohort separation and clear scientific provenance.
 */

const BANNERS = {
  SIMULATION: {
    className: "simulation",
    badge: "SIMULATION",
    title: "Controlled Simulation Benchmark",
    description: "Evaluates multi-modal evidence fusion under 22 controlled synthetic scenarios. Synthetic results do not constitute operational seabed truth.",
  },
  REAL_DAS: {
    className: "real-das",
    badge: "REAL_DAS",
    title: "Real Submarine Fiber DAS Deployments",
    description: "Evaluates empirical datasets (Marlinks, EMSO Western Ionian, Dryad Oliktok). Decoupled from vessel ground truth where unlabelled.",
  },
  HIL_SIMULATED_ACCEL: {
    className: "hil",
    badge: "HIL_SIMULATED_ACCEL",
    title: "Hardware-in-the-Loop AbyssLink Bridge",
    description: "Live ESP32 serial telemetry. Accelerometer data is synthesized from binary vibration flags and does not represent subsea acoustic physics.",
  },
};

export function renderBanner(dataKind = "SIMULATION", containerId = "data-banner") {
  const container = document.getElementById(containerId);
  if (!container) return;

  const info = BANNERS[dataKind] || BANNERS.SIMULATION;

  container.innerHTML = `
    <div class="cohort-banner ${info.className}" role="alert">
      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <span class="cohort-badge">${info.badge}</span>
        <span><strong>${info.title}:</strong> ${info.description}</span>
      </div>
      <div style="font-size: 0.75rem; opacity: 0.8; white-space: nowrap;">
        Verified Cohort
      </div>
    </div>
  `;
}
