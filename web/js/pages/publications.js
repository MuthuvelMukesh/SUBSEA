/**
 * Page 14: Publication Figures & Tables
 * Browse, inspect, and download peer-reviewed publication figures and benchmark tables,
 * each with explicit source manifest traceability and cohort tags.
 */

import { renderBanner } from "../banner.js";
import { renderKPI } from "../components.js";

let pubData = {};

export async function render(container) {
  renderBanner("SIMULATION");

  try {
    const res = await fetch("data/publications.json");
    pubData = await res.json();
  } catch (err) {
    console.error("Failed to load publications.json", err);
  }

  const figures = pubData.publication_figures || [];
  const tables = pubData.publication_tables || [];

  container.innerHTML = `
    <!-- Top Filter Controls -->
    <div class="control-row">
      <div class="control-group" style="min-width: 250px;">
        <label class="control-label" for="pub-cohort-filter">Filter by Experimental Cohort</label>
        <select id="pub-cohort-filter" class="select-input">
          <option value="ALL">All Cohorts (Figures & Tables)</option>
          <option value="SIMULATION">SIMULATION (Synthetic & Controlled Trials)</option>
          <option value="REAL_DAS">REAL_DAS (Marlinks, EMSO, Oliktok Deployments)</option>
        </select>
      </div>
      <div style="flex: 1;"></div>
      <div style="font-size: 0.85rem; color: var(--text-muted); align-self: center;">
        Static figures copied from <code>artifacts/paper_evaluation/</code> (Zero regeneration)
      </div>
    </div>

    <!-- KPIs -->
    <div class="grid-cols-4">
      ${renderKPI("Publication Figures", `${figures.length} Artifacts`, "300 DPI Vector/Raster", "Paper figures rendered from evaluated experiment runs.")}
      ${renderKPI("Benchmark Tables", `${tables.length} Tables`, "CSV Exports Available", "Comprehensive quantitative result tables.")}
      ${renderKPI("Real DAS Artifacts", "7 Artifacts", "Marlinks / EMSO / Oliktok", "Empirical subsea cable recording artifacts.")}
      ${renderKPI("Simulation Artifacts", "19 Artifacts", "S01–S22 Scenarios", "Controlled physics simulation benchmark artifacts.")}
    </div>

    <!-- Publication Figures Section -->
    <div class="card" style="margin-bottom: 2rem;">
      <div class="card-title">
        <span>Scientific Publication Figures</span>
        <span class="brand-badge">PNG High-Resolution</span>
      </div>
      <div id="figures-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; margin-top: 1rem;">
        <!-- Populated dynamically -->
      </div>
    </div>

    <!-- Publication Tables Section -->
    <div class="card">
      <div class="card-title">
        <span>Scientific Publication Tables</span>
        <span class="brand-badge">CSV Downloads</span>
      </div>
      <div class="table-container" style="margin-top: 1rem;">
        <table id="pub-tables-list">
          <thead>
            <tr>
              <th>Table ID</th>
              <th>Table Title</th>
              <th>Experimental Cohort</th>
              <th>File Name</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="tables-body">
            <!-- Populated dynamically -->
          </tbody>
        </table>
      </div>
    </div>
  `;

  const sel = document.getElementById("pub-cohort-filter");

  function updateView() {
    const filter = sel.value;

    const filteredFigs = filter === "ALL" ? figures : figures.filter((f) => f.cohort === filter);
    const filteredTabs = filter === "ALL" ? tables : tables.filter((t) => t.cohort === filter);

    // Render Figures
    const figGrid = document.getElementById("figures-grid");
    if (filteredFigs.length === 0) {
      figGrid.innerHTML = `<div style="grid-column: 1 / -1; color: var(--text-muted); padding: 2rem; text-align: center;">No figures match cohort filter "${filter}".</div>`;
    } else {
      figGrid.innerHTML = filteredFigs
        .map(
          (fig) => `
        <div style="border: 1px solid var(--border-color); border-radius: var(--radius); overflow: hidden; background: var(--bg-hover); display: flex; flex-direction: column;">
          <div style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; background: var(--bg-card);">
            <strong style="font-size: 0.9rem;">${fig.name}</strong>
            <span class="data-banner-badge banner-${fig.cohort.toLowerCase()}" style="font-size: 0.7rem; padding: 0.15rem 0.4rem;">${fig.cohort}</span>
          </div>
          <div style="flex: 1; padding: 0.5rem; display: flex; align-items: center; justify-content: center; min-height: 200px; background: #ffffff;">
            <img src="assets/figures/${fig.filename}" alt="${fig.name}" style="max-width: 100%; max-height: 220px; object-fit: contain;" onerror="this.onerror=null; this.parentElement.innerHTML='<div style=\\'color:#94a3b8;font-size:0.8rem;text-align:center;padding:2rem;\\'>Figure preview unavailable (${fig.filename})</div>';">
          </div>
          <div style="padding: 0.75rem 1rem; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; background: var(--bg-card);">
            <span style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">${fig.filename}</span>
            <a href="assets/figures/${fig.filename}" download="${fig.filename}" class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.6rem; text-decoration: none;">📥 Download PNG</a>
          </div>
        </div>
      `
        )
        .join("");
    }

    // Render Tables
    const tabBody = document.getElementById("tables-body");
    if (filteredTabs.length === 0) {
      tabBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No tables match cohort filter "${filter}".</td></tr>`;
    } else {
      tabBody.innerHTML = filteredTabs
        .map(
          (t) => `
        <tr>
          <td><code>${t.id.toUpperCase()}</code></td>
          <td><strong>${t.name}</strong></td>
          <td><span class="data-banner-badge banner-${t.cohort.toLowerCase()}" style="font-size: 0.75rem;">${t.cohort}</span></td>
          <td><code>artifacts/tables/${t.filename}</code></td>
          <td>
            <a href="data/real_das.json" download="${t.filename}" class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.5rem; text-decoration: none;">📥 Export CSV</a>
          </td>
        </tr>
      `
        )
        .join("");
    }
  }

  sel.addEventListener("change", updateView);
  updateView();
}
