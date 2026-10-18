# Standalone Web Front End — Progress Log (`PROGRESS_WEB.md`)

## Summary Tracker

| Phase | Description | Deliverables | Test Count | AbyssLink Status | Commit | Status |
|-------|-------------|--------------|------------|------------------|--------|--------|
| **Phase 0** | Baseline & Plan | `PLAN_WEB.md`, `PROGRESS_WEB.md`, `dashboard/app.py` deprecation | 258 | VERIFIED UNCHANGED | `docs(web): phase 0 baseline, plan, and dashboard deprecation` | COMPLETED |
| **Phase 1** | Exporter & Data Layer | `src/subsea/web_export.py`, `scripts/export_web_data.py`, `tests/test_web_export.py`, `web/data/*.json` | 266 | VERIFIED UNCHANGED | `feat(web): phase 1 exporter, data layer, and tests` | COMPLETED |
| **Phase 2** | Site Shell & Components | `web/index.html`, `style.css`, Plotly vendored, `app.js`, `router.js`, `theme.js`, `banner.js`, `charts.js`, `components.js` | 266 | VERIFIED UNCHANGED | `feat(web): phase 2 site shell, styling, plotly vendoring, and router` | COMPLETED |
| **Phase 3** | Pages 1–5 | Overview, Scenarios, Signals, Geometry, Evidence Timeline | 266 | VERIFIED UNCHANGED | `feat(web): phase 3 pages 1-5 overview scenarios signals geometry timeline` | COMPLETED |
| **Phase 4** | Pages 6–10 | Decision Path, Hypotheses, Adversarial, Baselines, Robustness | Pending | Pending | - | PENDING |
| **Phase 5** | Pages 11, 13, 14 | Real DAS, Provenance, Publications | Pending | Pending | - | PENDING |
| **Phase 6** | Page 12 (Live HIL) | Live HIL dashboard with polling, drag-and-drop, and disclaimer | Pending | Pending | - | PENDING |
| **Phase 7** | Documentation | `docs/WEB.md`, `README.md` update | Pending | Pending | - | PENDING |
| **Phase 8** | Smoke & Tamper Tests | E2E browser smoke tests & provenance tamper verification | Pending | Pending | - | PENDING |
| **Phase 9** | Pyodide Feasibility | In-browser Python assessment | Pending | Pending | - | PENDING |

---

## Phase Details

### Phase 0: Baseline & Plan
- **Baseline Test Suite**: 258 passed, 0 failures in 52.01s.
- **AbyssLink Hashes**: Recorded in `$env:TEMP\abysslink_hashes_baseline.txt` and scratch backup. Verified 5 files matching baseline.
- **Files Touched**: `dashboard/app.py` (deprecation note added), `PLAN_WEB.md`, `PROGRESS_WEB.md`.
- **Status**: COMPLETED.

### Phase 1: Exporter & Data Layer
- **Test Suite**: 266 passed, 0 failures in 26.24s (8 new tests in `tests/test_web_export.py`).
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created/Modified**: `src/subsea/web_export.py`, `scripts/export_web_data.py`, `tests/test_web_export.py`, `web/data/*.json` (17 JSON files), `web/assets/figures/*.png` (copied static figures).
- **Status**: COMPLETED.

### Phase 2: Site Shell & Components
- **Test Suite**: 266 passed, 0 failures in 32.07s.
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created**: `web/index.html`, `web/assets/style.css`, `web/vendor/plotly.min.js`, `web/js/app.js`, `web/js/router.js`, `web/js/theme.js`, `web/js/banner.js`, `web/js/charts.js`, `web/js/components.js`.
- **Status**: COMPLETED.

### Phase 3: Pages 1–5
- **Test Suite**: 266 passed, 0 failures in 67.53s.
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created**:
  - `web/js/pages/overview.js` (Page 1: System KPI cards, decision state definitions, cohort breakdown, scientific disclaimers)
  - `web/js/pages/scenarios.js` (Page 2: S01–S22 selector, 6 attack types, 5 severities, metric comparison charts)
  - `web/js/pages/signals.js` (Page 3: Triaxial acceleration waveform, magnitude, packet loss markers, FFT spectrum, spectral features table & CSV download)
  - `web/js/pages/geometry.js` (Page 4: 2D metric coordinate map, 10m interaction corridor, vessel trajectory, distance vs time, CPA, dwell time, crossing detection)
  - `web/js/pages/timeline.js` (Page 5: Sliding-window multi-trace chart of C_P, C_A, R, U, discrete decision state sequence, window table & CSV export)
- **Status**: COMPLETED.
