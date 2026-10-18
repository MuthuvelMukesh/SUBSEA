/**
 * Page 4: Geometry & Kinematics
 */

import { renderBanner } from "../banner.js";
import { renderKPI } from "../components.js";
import { buildPlot } from "../charts.js";

let geoData = {};

export async function render(container) {
  renderBanner("SIMULATION");

  try {
    const res = await fetch("data/geometry.json");
    const json = await res.json();
    geoData = json.geometries || {};
  } catch (err) {
    console.error("Failed to load geometry.json", err);
  }

  const sids = Object.keys(geoData);

  container.innerHTML = `
    <!-- Controls -->
    <div class="control-row">
      <div class="control-group" style="min-width: 250px;">
        <label class="control-label" for="geo-scenario-select">Select Scenario Trajectory</label>
        <select id="geo-scenario-select" class="select-input">
          ${sids.map((id) => `<option value="${id}">${id} Kinematics & Cable Interaction</option>`).join("")}
        </select>
      </div>
      <div style="flex: 1;"></div>
      <span style="font-size: 0.8rem; color: var(--text-muted);">Coordinate Frame: Local Metric Cartesian (Meters)</span>
    </div>

    <!-- Active Geometry Display Container -->
    <div id="geometry-view"></div>
  `;

  const sel = document.getElementById("geo-scenario-select");

  function updateView() {
    const sid = sel.value;
    const g = geoData[sid];

    if (!g) {
      document.getElementById("geometry-view").innerHTML = `
        <div class="empty-state">
          <h3>No Geometry Data Available for ${sid}</h3>
        </div>
      `;
      return;
    }

    const hasVessel = g.vessel_current_position !== null;

    document.getElementById("geometry-view").innerHTML = `
      <!-- Kinematic KPIs -->
      <div class="grid-cols-4">
        ${renderKPI(
          "Closest Point of Approach",
          g.closest_point_of_approach_m !== null ? `${g.closest_point_of_approach_m.toFixed(1)} m` : "N/A",
          g.closest_point_timestamp !== null ? `At t=${g.closest_point_timestamp.toFixed(1)}s` : "No vessel",
          "Minimum Euclidean distance from vessel trajectory to cable polyline."
        )}
        ${renderKPI(
          "Interaction Dwell Time",
          `${g.dwell_time_within_10m_s.toFixed(1)} s`,
          "Within 10m Corridor",
          "Total elapsed duration spent within the 10-meter physical interaction radius."
        )}
        ${renderKPI(
          "Cable Crossing Detected",
          g.crossing_detected ? "YES (Crossed)" : "NO (Non-Crossing)",
          "Vector Intersection",
          "Oriented line segment intersection between trajectory and cable polyline."
        )}
        ${renderKPI(
          "Speed & Heading",
          hasVessel ? `${g.speed.toFixed(1)} m/s (${g.heading.toFixed(0)}°)` : "N/A",
          hasVessel ? (g.reported ? "AIS Transponder Active" : "Transponder Suppressed") : "No vessel present",
          "Instantaneous vessel kinematics."
        )}
      </div>

      <!-- Spatial Map and Distance Evolution Grid -->
      <div class="grid-cols-2">
        <!-- 2D Spatial Map -->
        <div class="card">
          <div class="card-title">
            <span>2D Metric Spatial Map (Cable & Vessel Track)</span>
            <span class="brand-badge">Meters</span>
          </div>
          <div id="spatial-map-plot" class="chart-container"></div>
        </div>

        <!-- Distance to Cable over Time -->
        <div class="card">
          <div class="card-title">
            <span>Euclidean Distance to Cable vs Time</span>
          </div>
          <div id="distance-time-plot" class="chart-container"></div>
        </div>
      </div>

      <!-- Scientific Disclaimer Card -->
      <div class="card">
        <div class="card-title">
          <span>Kinematic Representation Note</span>
        </div>
        <p style="font-size: 0.85rem; color: var(--text-muted);">
          To avoid unverified geographical assumptions, all spatial tracking operates strictly within local metric Cartesian coordinates <code>(x, y)</code> in meters, where the subsea telecommunication cable lies along the polyline <code>[(0, 0) -> (100, 0)]</code>.
          The 10-meter shaded corridor defines the acoustic/elastodynamic interaction radius. No synthetic latitude or longitude coordinates are fabricated.
        </p>
      </div>
    `;

    // 1. Render 2D Spatial Map
    const cableX = g.cable_polyline.map((p) => p[0]);
    const cableY = g.cable_polyline.map((p) => p[1]);

    const traceCable = {
      x: cableX,
      y: cableY,
      name: "Subsea Cable Polyline",
      mode: "lines+markers",
      line: { color: "#3b82f6", width: 4 },
      marker: { size: 6, color: "#1d4ed8" },
    };

    // 10m Interaction Corridor Lines
    const traceCorridorUpper = {
      x: [0, 100],
      y: [10, 10],
      name: "+10m Interaction Boundary",
      mode: "lines",
      line: { color: "rgba(245, 158, 11, 0.4)", dash: "dash", width: 1 },
      showlegend: false,
    };
    const traceCorridorLower = {
      x: [0, 100],
      y: [-10, -10],
      name: "-10m Interaction Boundary",
      mode: "lines",
      line: { color: "rgba(245, 158, 11, 0.4)", dash: "dash", width: 1 },
      showlegend: false,
    };

    const tracesMap = [traceCable, traceCorridorUpper, traceCorridorLower];

    if (hasVessel && g.vessel_trajectory.length > 0) {
      const vX = g.vessel_trajectory.map((p) => p[0]);
      const vY = g.vessel_trajectory.map((p) => p[1]);

      const traceTraj = {
        x: vX,
        y: vY,
        name: "Vessel Approach Track",
        mode: "lines+markers",
        line: { color: "#f97316", width: 2, dash: "dot" },
        marker: { size: 5, color: "#f97316" },
      };

      const traceVesselCurrent = {
        x: [g.vessel_current_position[0]],
        y: [g.vessel_current_position[1]],
        name: "Vessel Position",
        mode: "markers",
        marker: { size: 12, color: "#ef4444", symbol: "triangle-up" },
      };

      tracesMap.push(traceTraj, traceVesselCurrent);
    }

    buildPlot("spatial-map-plot", tracesMap, {
      xaxis: { title: "X Coordinate (meters)", range: [-10, 110] },
      yaxis: { title: "Y Coordinate (meters)", range: [-40, 40], scaleanchor: "x", scaleratio: 1 },
    });

    // 2. Render Distance vs Time Plot
    if (hasVessel && g.vessel_trajectory.length > 0) {
      const dists = g.vessel_trajectory.map((p) => Math.hypot(p[0] - Math.max(0, Math.min(100, p[0])), p[1]));
      const traceDist = {
        x: g.trajectory_timestamps,
        y: dists,
        name: "Vessel-to-Cable Distance",
        mode: "lines+markers",
        line: { color: "#10b981", width: 2 },
      };
      const trace10m = {
        x: [g.trajectory_timestamps[0], g.trajectory_timestamps[g.trajectory_timestamps.length - 1]],
        y: [10, 10],
        name: "10m Interaction Radius",
        mode: "lines",
        line: { color: "#ef4444", dash: "dash" },
      };

      buildPlot("distance-time-plot", [traceDist, trace10m], {
        xaxis: { title: "Time (seconds)" },
        yaxis: { title: "Distance to Cable (meters)", range: [0, Math.max(25, ...dists) + 5] },
      });
    } else {
      document.getElementById("distance-time-plot").innerHTML = `
        <div class="empty-state" style="padding: 2rem;">
          <p>No vessel trajectory associated with this scenario.</p>
        </div>
      `;
    }
  }

  sel.addEventListener("change", updateView);
  updateView();
}
