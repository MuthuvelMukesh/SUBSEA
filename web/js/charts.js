/**
 * Charting Helpers using Vendored Plotly.js
 */

import { getTheme } from "./theme.js";

export function getPlotlyTheme() {
  const isDark = getTheme() === "dark";
  return {
    paper_bgcolor: isDark ? "#151d2e" : "#ffffff",
    plot_bgcolor: isDark ? "#151d2e" : "#ffffff",
    font: {
      family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: isDark ? "#f8fafc" : "#0f172a",
      size: 12,
    },
    gridcolor: isDark ? "#27354f" : "#e2e8f0",
    zerolinecolor: isDark ? "#334155" : "#cbd5e1",
  };
}

export function buildPlot(containerId, traces, customLayout = {}, customConfig = {}) {
  const el = typeof containerId === "string" ? document.getElementById(containerId) : containerId;
  if (!el || !window.Plotly) return;

  const th = getPlotlyTheme();
  const defaultLayout = {
    paper_bgcolor: th.paper_bgcolor,
    plot_bgcolor: th.plot_bgcolor,
    font: th.font,
    margin: { l: 50, r: 30, t: 40, b: 50 },
    xaxis: {
      gridcolor: th.gridcolor,
      zerolinecolor: th.zerolinecolor,
      automargin: true,
    },
    yaxis: {
      gridcolor: th.gridcolor,
      zerolinecolor: th.zerolinecolor,
      automargin: true,
    },
    hovermode: "closest",
    autosize: true,
    ...customLayout,
  };

  const defaultConfig = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
    ...customConfig,
  };

  window.Plotly.newPlot(el, traces, defaultLayout, defaultConfig);

  // Auto-retheme listener
  const themeHandler = () => {
    const newTh = getPlotlyTheme();
    window.Plotly.relayout(el, {
      paper_bgcolor: newTh.paper_bgcolor,
      plot_bgcolor: newTh.plot_bgcolor,
      "font.color": newTh.font.color,
      "xaxis.gridcolor": newTh.gridcolor,
      "xaxis.zerolinecolor": newTh.zerolinecolor,
      "yaxis.gridcolor": newTh.gridcolor,
      "yaxis.zerolinecolor": newTh.zerolinecolor,
    });
  };

  window.removeEventListener("subsea:themechange", el._themeHandler);
  el._themeHandler = themeHandler;
  window.addEventListener("subsea:themechange", themeHandler);
}

export function exportTableToCSV(tableEl, filename = "data.csv") {
  const rows = Array.from(tableEl.querySelectorAll("tr"));
  const csv = rows
    .map((r) =>
      Array.from(r.querySelectorAll("th,td"))
        .map((cell) => `"${cell.textContent.trim().replace(/"/g, '""')}"`)
        .join(",")
    )
    .join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
