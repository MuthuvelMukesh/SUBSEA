/**
 * Hash-Based Router for Subsea Standalone Web App
 */

const ROUTES = {
  "overview": { title: "1. Overview & Architecture", module: "./pages/overview.js" },
  "scenarios": { title: "2. Scenario Explorer (S01–S22)", module: "./pages/scenarios.js" },
  "signals": { title: "3. Signals & Spectrum", module: "./pages/signals.js" },
  "geometry": { title: "4. Geometry & Kinematics", module: "./pages/geometry.js" },
  "timeline": { title: "5. Evidence & Uncertainty Timeline", module: "./pages/timeline.js" },
  "decision-path": { title: "6. Decision Path Explainer", module: "./pages/decision_path.js" },
  "hypotheses": { title: "7. Hypotheses & Evidence Audit", module: "./pages/hypotheses.js" },
  "adversarial": { title: "8. Adversarial Lab (AER & FHER)", module: "./pages/adversarial.js" },
  "baselines": { title: "9. Baselines & Ablation Studies", module: "./pages/baselines.js" },
  "robustness": { title: "10. Robustness & Calibration", module: "./pages/robustness.js" },
  "real-das": { title: "11. Real Submarine DAS Deployments", module: "./pages/real_das.js" },
  "hil": { title: "12. Live Hardware-in-the-Loop (HIL)", module: "./pages/hil.js" },
  "provenance": { title: "13. In-Browser Provenance Verification", module: "./pages/provenance.js" },
  "publications": { title: "14. Publication Figures & Tables", module: "./pages/publications.js" },
};

let activePageModule = null;

export async function navigateTo(routeKey) {
  const cleanRoute = (routeKey || "overview").replace(/^#\/?/, "");
  const route = ROUTES[cleanRoute] || ROUTES["overview"];

  // Tear down timers or listeners from previous page if defined
  if (activePageModule && typeof activePageModule.cleanup === "function") {
    try {
      activePageModule.cleanup();
    } catch (e) {
      console.warn("Error during page cleanup:", e);
    }
  }

  // Update active state in sidebar nav
  document.querySelectorAll(".nav-item").forEach((link) => {
    const href = link.getAttribute("href") || "";
    if (href.replace(/^#\/?/, "") === cleanRoute) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });

  // Update header title
  const titleEl = document.getElementById("page-title");
  if (titleEl) {
    titleEl.textContent = route.title;
  }

  const contentEl = document.getElementById("main-content");
  if (!contentEl) return;

  contentEl.innerHTML = `<div style="padding: 2rem; color: var(--text-muted);">Loading ${route.title}...</div>`;

  try {
    const pageMod = await import(route.module);
    activePageModule = pageMod;
    contentEl.innerHTML = "";
    await pageMod.render(contentEl);
  } catch (err) {
    console.error(`Failed to load page: ${route.module}`, err);
    contentEl.innerHTML = `
      <div class="card" style="border-color: var(--state-t3);">
        <h3 style="color: var(--state-t3);">Error Loading View</h3>
        <p>${err.message}</p>
      </div>
    `;
  }
}

export function initRouter() {
  window.addEventListener("hashchange", () => {
    const hash = window.location.hash || "#/overview";
    navigateTo(hash);
  });

  const initial = window.location.hash || "#/overview";
  navigateTo(initial);
}
