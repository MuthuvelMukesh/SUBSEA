/**
 * Page 3: Signals & Spectrum
 */

import { renderBanner } from "../banner.js";
import { renderKPI } from "../components.js";
import { buildPlot, exportTableToCSV } from "../charts.js";

let signalsData = {};

export async function render(container) {
  renderBanner("SIMULATION");

  try {
    const res = await fetch("data/signals.json");
    const json = await res.json();
    signalsData = json.waveforms || {};
  } catch (err) {
    console.error("Failed to load signals.json", err);
  }

  const sids = Object.keys(signalsData);

  container.innerHTML = `
    <!-- Scenario Selection Controls -->
    <div class="control-row">
      <div class="control-group" style="min-width: 250px;">
        <label class="control-label" for="signal-scenario-select">Select Scenario Waveform</label>
        <select id="signal-scenario-select" class="select-input">
          ${sids.map((id) => `<option value="${id}">${id} Acceleration Waveform</option>`).join("")}
        </select>
      </div>
      <div style="flex: 1;"></div>
      <button id="download-signals-btn" class="btn btn-secondary">📥 Export Spectral CSV</button>
    </div>

    <!-- Active Waveform Display Container -->
    <div id="signals-view"></div>
  `;

  const sel = document.getElementById("signal-scenario-select");

  function updateView() {
    const sid = sel.value;
    const wf = signalsData[sid];

    if (!wf) {
      document.getElementById("signals-view").innerHTML = `
        <div class="empty-state">
          <h3>No Signal Data Available for ${sid}</h3>
        </div>
      `;
      return;
    }

    const feat = wf.spectral_features || {};

    document.getElementById("signals-view").innerHTML = `
      <!-- Top KPIs -->
      <div class="grid-cols-4">
        ${renderKPI("Sampling Rate", `${wf.sampling_rate_hz} Hz`, "50 Samples / Second", "Standard MPU6050 acquisition sampling frequency.")}
        ${renderKPI("Dominant Frequency", `${feat.dominant_frequency ? feat.dominant_frequency.toFixed(1) : 0.0} Hz`, "FFT Spectral Peak", "Frequency bin carrying maximum spectral energy.")}
        ${renderKPI("RMS Acceleration", `${feat.rms ? feat.rms.toFixed(3) : 0.0} g`, "Root Mean Square", "Baseline ~1.0g; Disturbed >= 1.8g.")}
        ${renderKPI("Packet Loss", `${wf.packet_loss_count} / ${wf.sample_count}`, `${((wf.packet_loss_count / wf.sample_count) * 100).toFixed(1)}% dropped`, "Number of dropped sensor packets in window.")}
      </div>

      <!-- Plot 1: Triaxial Waveforms -->
      <div class="card">
        <div class="card-title">
          <span>Triaxial Acceleration Waveforms (ax, ay, az) with Packet Drops</span>
          <span class="brand-badge">${sid}</span>
        </div>
        <div id="waveform-plot" class="chart-container"></div>
      </div>

      <!-- Grid: Magnitude and FFT Spectrum -->
      <div class="grid-cols-2">
        <div class="card">
          <div class="card-title">
            <span>Acceleration Magnitude √(ax² + ay² + az²)</span>
          </div>
          <div id="magnitude-plot" class="chart-container"></div>
        </div>

        <div class="card">
          <div class="card-title">
            <span>Fast Fourier Transform (FFT) Power Spectrum</span>
          </div>
          <div id="fft-plot" class="chart-container"></div>
        </div>
      </div>

      <!-- Spectral Features Table -->
      <div class="card">
        <div class="card-title">
          <span>Extracted Spectral Feature Summary</span>
        </div>
        <div class="table-container">
          <table class="data-table" id="spectral-table">
            <thead>
              <tr>
                <th>Feature Parameter</th>
                <th>Computed Value</th>
                <th>Unit / Domain</th>
                <th>Physical Role</th>
              </tr>
            </thead>
            <tbody>
              <tr><td><strong>Mean Magnitude</strong></td><td>${feat.mean ? feat.mean.toFixed(4) : "N/A"}</td><td>g</td><td>Static gravitational offset (~1.0g).</td></tr>
              <tr><td><strong>RMS Acceleration</strong></td><td>${feat.rms ? feat.rms.toFixed(4) : "N/A"}</td><td>g</td><td>Total dynamic disturbance energy used in C_P.</td></tr>
              <tr><td><strong>Variance</strong></td><td>${feat.variance ? feat.variance.toFixed(6) : "N/A"}</td><td>g²</td><td>Signal dispersion around mean gravity.</td></tr>
              <tr><td><strong>Peak Acceleration</strong></td><td>${feat.peak ? feat.peak.toFixed(4) : "N/A"}</td><td>g</td><td>Maximum single-sample shock amplitude.</td></tr>
              <tr><td><strong>Peak-to-RMS Ratio</strong></td><td>${feat.peak_to_rms ? feat.peak_to_rms.toFixed(3) : "N/A"}</td><td>ratio</td><td>Crest factor indicating acute mechanical impact.</td></tr>
              <tr><td><strong>Spectral Energy</strong></td><td>${feat.spectral_energy ? feat.spectral_energy.toFixed(2) : "N/A"}</td><td>AU</td><td>Total integrated AC power across frequency bins.</td></tr>
              <tr><td><strong>Dominant Frequency</strong></td><td>${feat.dominant_frequency ? feat.dominant_frequency.toFixed(2) : "N/A"}</td><td>Hz</td><td>Characteristic vibration mode (8 Hz vessel / 2 Hz wave).</td></tr>
              <tr><td><strong>Spectral Entropy</strong></td><td>${feat.spectral_entropy ? feat.spectral_entropy.toFixed(3) : "N/A"}</td><td>bits</td><td>Spectral flatness distinguishing narrowband vibration from broadband noise.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Render Triaxial Plot
    const traceAx = { x: wf.timestamps, y: wf.ax, name: "ax (X-axis)", type: "scatter", mode: "lines", line: { color: "#3b82f6" } };
    const traceAy = { x: wf.timestamps, y: wf.ay, name: "ay (Y-axis)", type: "scatter", mode: "lines", line: { color: "#10b981" } };
    const traceAz = { x: wf.timestamps, y: wf.az, name: "az (Z-axis)", type: "scatter", mode: "lines", line: { color: "#8b5cf6" } };

    // Marked packet drops
    const dropIndices = wf.packet_received.map((p, idx) => (!p ? idx : -1)).filter((idx) => idx !== -1);
    const dropTimes = dropIndices.map((i) => wf.timestamps[i]);
    const dropVals = dropIndices.map(() => 1.0);

    const traceDrops = {
      x: dropTimes,
      y: dropVals,
      name: "Packet Dropped",
      mode: "markers",
      marker: { color: "#ef4444", symbol: "x", size: 9 },
    };

    buildPlot("waveform-plot", [traceAx, traceAy, traceAz, traceDrops], {
      xaxis: { title: "Timestamp (seconds)" },
      yaxis: { title: "Acceleration (g)" },
    });

    // Render Magnitude Plot
    const traceMag = { x: wf.timestamps, y: wf.magnitude, name: "Magnitude |a|", type: "scatter", mode: "lines", line: { color: "#f97316", width: 2 } };
    buildPlot("magnitude-plot", [traceMag], {
      xaxis: { title: "Timestamp (seconds)" },
      yaxis: { title: "Magnitude (g)" },
    });

    // Render FFT Spectrum Plot
    const traceFFT = { x: wf.frequency_bins, y: wf.spectral_power, name: "Power", type: "scatter", mode: "lines", fill: "tozeroy", line: { color: "#06b6d4" } };
    buildPlot("fft-plot", [traceFFT], {
      xaxis: { title: "Frequency (Hz)", range: [0, 25] },
      yaxis: { title: "Spectral Power" },
    });
  }

  sel.addEventListener("change", updateView);
  document.getElementById("download-signals-btn").addEventListener("click", () => {
    const tbl = document.getElementById("spectral-table");
    if (tbl) exportTableToCSV(tbl, `spectral_features_${sel.value}.csv`);
  });

  updateView();
}
