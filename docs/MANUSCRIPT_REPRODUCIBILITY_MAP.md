# Manuscript Reproducibility Map

This document establishes the bidirectional traceability matrix mapping every quantitative claim, metric, and experimental outcome in the IEEE manuscript (`paper/paper.tex`) to its underlying executable source code, raw dataset, and generated artifact.

## Traceability Matrix

| Manuscript Claim | Source Code | Dataset | Artifact | Verified |
| :--- | :--- | :--- | :--- | :---: |
| **Marlinks Window Count** (60 windows, 10~s windows, 590~s total) | `src/subsea/real_data.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/real_data_evaluation/marlinks_manifest.json` | YES |
| **Marlinks Spatial Channel Count** (250 channels, indices 1440--1690) | `src/subsea/real_data.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/real_data_evaluation/marlinks_manifest.json` | YES |
| **Marlinks Closest Point of Approach** ($y_{\mathrm{cpa}} = 26.22$~m at step 26) | `src/subsea/real_evaluation.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/real_data_evaluation/marlinks_manifest.json` | YES |
| **Marlinks Energy vs Inverse Distance** ($\rho = 0.9482, r = 0.3629$) | `src/subsea/real_evaluation.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/tables/table2_marlinks_validation.tex` | YES |
| **Marlinks CPA Spatial Concentration** (Gini = 0.8739, PAR = 14.86) | `src/subsea/real_evaluation.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/real_data_evaluation/marlinks_manifest.json` | YES |
| **Marlinks Transit Range Tracking** ($\rho = -0.914, p = 2.1\times10^{-24}$) | `src/subsea/real_evaluation.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/real_data_evaluation/marlinks_manifest.json` | YES |
| **Marlinks 1~km Corridor Detection AUC** ($\text{AUC} = 0.959$, 95\% CI $[0.887, 1.000]$) | `src/subsea/real_evaluation.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/tables/table_marlinks_auc.tex` | YES |
| **Marlinks Range Regressor Generalisation** ($R^2_{\log} = 0.849$, median rel err 34.2\%) | `src/subsea/real_evaluation.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/real_data_evaluation/marlinks_manifest.json` | YES |
| **EMSO Spatial Channels** (2,963 channels, continuous deep seafloor) | `src/subsea/real_data.py` | `data/emso_ionian/decimated_20250610T030504.010529_1050_seconds_10_Hz.npy` | `artifacts/real_data_evaluation/emso_manifest.json` | YES |
| **EMSO Duration and Sampling** (1,050~s, 10,500 samples, 10~Hz) | `src/subsea/real_data.py` | `data/emso_ionian/decimated_20250610T030504.010529_1050_seconds_10_Hz.npy` | `artifacts/real_data_evaluation/emso_manifest.json` | YES |
| **EMSO Baseline Temporal Stability** ($\text{CV} = 0.0008 = 0.08\%$) | `src/subsea/real_evaluation.py` | `data/emso_ionian/decimated_20250610T030504.010529_1050_seconds_10_Hz.npy` | `artifacts/tables/table3_emso_baseline.tex` | YES |
| **EMSO Zero Escalations** (0 / 85 windows escalated to T2/T3) | `src/subsea/real_evaluation.py` | `data/emso_ionian/decimated_20250610T030504.010529_1050_seconds_10_Hz.npy` | `artifacts/real_data_evaluation/emso_manifest.json` | YES |
| **Oliktok Evaluation Windows** (215 hourly windows, 27.625 days) | `src/subsea/oliktok.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/real_data_evaluation/oliktok_manifest.json` | YES |
| **Oliktok Spatial Channels** (183 physical channels, Ch 1088--3672, 8.8--30.0~km) | `src/subsea/oliktok.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/real_data_evaluation/oliktok_manifest.json` | YES |
| **Oliktok Spectral Bins** (32 frequency bins, 0.0078--0.4941~Hz) | `src/subsea/oliktok.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/real_data_evaluation/oliktok_manifest.json` | YES |
| **Oliktok Mean Strain RMS** ($550.85~\mathrm{nm/m/s}$, median 553.59) | `src/subsea/oliktok_evaluation.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/tables/table_oliktok_validation.tex` | YES |
| **Oliktok Spatial Dispersion** ($\text{CV}_{\text{spatial}} = 0.2349$, Gini = 0.1265) | `src/subsea/oliktok_evaluation.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/tables/table_oliktok_validation.tex` | YES |
| **Oliktok Temporal Stability** ($\text{CV}_{\text{temporal}} = 0.1239$, drift $+0.0188/\mathrm{hr}$) | `src/subsea/oliktok_evaluation.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/tables/table_oliktok_validation.tex` | YES |
| **Oliktok Drift Significance** ($p = 0.8037$, no systematic drift) | `src/subsea/oliktok_evaluation.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/real_data_evaluation/oliktok_manifest.json` | YES |
| **Oliktok Wave Height Correlation** ($\rho = +0.3141, p = 2.63\times10^{-6}$) | `src/subsea/oliktok_evaluation.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/tables/table_oliktok_validation.tex` | YES |
| **Oliktok Pressure Variance Correlation** ($\rho = +0.4951, p = 1.07\times10^{-14}$) | `src/subsea/oliktok_evaluation.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/tables/table_oliktok_validation.tex` | YES |
| **Oliktok Decision Distribution** (T0: 93, T1: 122, T2: 0, T3: 0, TX: 0) | `src/subsea/oliktok_evaluation.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/tables/table_oliktok_validation.tex` | YES |
| **Oliktok Environmental Escalation Rate** (0.0\%, zero T2/T3 vessel alarms) | `src/subsea/oliktok_evaluation.py` | `data/Dryad_Oliktok/oliktok_das_mooring_hourly_dataset.nc` | `artifacts/tables/table_oliktok_validation.tex` | YES |
| **Decision Rule Backward Compatibility** (22/22 identical decisions, 0 changed) | `src/subsea/decision.py` | Controlled Benchmark Scenarios (S01--S22) | `artifacts/audit/decision_regression_report.json` | YES |
| **Controlled Simulation Trials** (2,200 trials across S01--S22, 100 seeds each) | `scripts/run_phase3_validation.py` | Synthetic Benchmark Suite | `artifacts/simulation/scenario_matrix.json` | YES |
| **Controlled Simulation Escalation F1** (Proposed F1 = 0.2353, Weighted = 0.3333) | `scripts/run_phase3_validation.py` | Synthetic Benchmark Suite | `artifacts/tables/table5_baseline_comparison.tex` | YES |
| **Controlled Simulation Physical+Temporal F1** (F1 = 0.5714, Acc = 0.5909) | `scripts/run_phase3_validation.py` | Synthetic Benchmark Suite | `artifacts/tables/table6_ablation_study.tex` | YES |
| **Adversarial Evasion Rate** (AER = 0.0 across 4 attack families $\times$ 5 severities) | `src/subsea/adversarial.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/tables/table8_adversarial_robustness.tex` | YES |
| **Real Transit Method Comparison** (Proposed F1 = 0.462, Weighted = 0.824) | `scripts/run_phase3_validation.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/tables/table_transit_methods.tex` | YES |
| **Calibration Reliability** (Brier score = 0.122, 10-bin ECE = 0.224) | `src/subsea/metrics.py` | `data/marlinks_demo/reduced_dataset_sensor_range_1440_1690.h5` | `artifacts/real_data_evaluation/marlinks_manifest.json` | YES |
| **Computational Performance: End-to-End Mean** (8.289~ms, Median 6.230~ms, P95 19.526~ms) | `scripts/run_phase3_validation.py` | Benchmark Iterations ($N=1{,}000$) | `artifacts/tables/table10_computational_performance.tex` | YES |
| **Computational Performance: Decision State Machine** (0.009~ms mean, 111,271.8~Hz) | `scripts/run_phase3_validation.py` | Benchmark Iterations ($N=1{,}000$) | `artifacts/tables/table10_computational_performance.tex` | YES |
| **Computational Performance: DAS Processing** (0.918~ms mean, 1,088.8~Hz throughput) | `scripts/run_phase3_validation.py` | Benchmark Iterations ($N=1{,}000$) | `artifacts/tables/table10_computational_performance.tex` | YES |
| **Computational Performance: Spatio-Temporal Association** (0.031~ms mean, 32,083.4~Hz) | `scripts/run_phase3_validation.py` | Benchmark Iterations ($N=1{,}000$) | `artifacts/tables/table10_computational_performance.tex` | YES |
| **Computational Performance: Multimodal Fusion** (0.189~ms mean, 5,278.5~Hz throughput) | `scripts/run_phase3_validation.py` | Benchmark Iterations ($N=1{,}000$) | `artifacts/tables/table10_computational_performance.tex` | YES |

## Execution Commands for Complete Verification

```powershell
# 1. Compile all source code packages
python -m compileall -q src scripts dashboard

# 2. Run complete test suite (240 unit and integration tests)
PYTHONPATH=src python -m pytest tests -q

# 3. Validate LaTeX syntax, balanced environments, citations, references, and figures
python scripts/validate_manuscript.py

# 4. Execute numerical and scientific consistency audit
python scripts/audit_manuscript_consistency.py
```
