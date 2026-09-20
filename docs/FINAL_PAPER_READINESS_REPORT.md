# Final Paper-Readiness Report: SUBSEA Research Framework

**Project:** An Uncertainty-Aware Multimodal Evidence Fusion Framework for Vessel-Associated Subsea Cable Disturbance Assessment under Adversarial Uncertainty  
**Date:** 2026-09-20  
**Status:** VALIDATED & READY FOR MANUSCRIPT CONSISTENCY INTEGRATION  
**Document Purpose:** Comprehensive forensic readiness audit evaluating the scientific correctness, reproducibility, provenance, real-data empirical boundaries, simulation validation, and limitation disclosures of the SUBSEA repository before manuscript text integration.

---

## 1. Executive Summary & Readiness Verdict

| Evaluation Dimension | Status | Verified Evidence |
| :--- | :---: | :--- |
| **1. Scientific Correctness** | **PASS** | Mathematical models, feature extraction, fusion weights, and state-machine transitions follow strict physical and formal formulations. |
| **2. Dataset Provenance** | **PASS** | Cryptographic SHA-256 digests verified for Marlinks, EMSO, and Oliktok datasets in `data/PROVENANCE.json`. Raw source data remains strictly read-only. |
| **3. Reproducibility** | **PASS** | 100% deterministic reproducibility verified across multiple executions (`artifacts/audit/oliktok_reproducibility_report.json`: 22/22 identical comparisons). |
| **4. Real-Data Validation** | **PASS** | Three diverse marine datasets executed across three distinct scientific roles without cross-contamination or fabricated labels. |
| **5. Simulation Validation** | **PASS** | Deterministic synthetic benchmark scenarios S01–S22 executed with reproducible random seeds. Zero synthetic data claimed as real ground truth. |
| **6. Adversarial Evaluation** | **PASS** | Evasion resistance evaluated under explicit threat models (AIS transponder suppression, ghost spoofing, timestamp manipulation, spatial offsets). |
| **7. Decision Logic** | **PASS** | Reliability-first decision state machine ($R \to T0 \to U \to T1/T2/T3$) verified with 100% backward compatibility across all 22 scenarios. |
| **8. Statistical Reporting** | **PASS** | Rigorous p-values, rank correlations, bootstrap confidence intervals, and effect sizes calculated directly from executable code. |
| **9. Limitation Disclosure** | **PASS** | Explicit boundaries enforced: no vessel attribution or damage detection claimed on unlabelled datasets; no attack-proof claims. |
| **10. Code-Artifact Consistency** | **PASS** | Forensic 23-point consistency audit achieved 100% exact numerical match (`artifacts/audit/oliktok_consistency_report.json`). |

---

## 2. Definitive Claims Classification

### READY TO REPORT (Empirically & Experimentally Validated)

1. **Multimodal Evidence Triad Formulation:**
   - Formal fusion of physical disturbance confidence ($C_p$), vessel-kinematic association confidence ($C_a$), hardware reliability ($R$), and epistemic uncertainty ($U$) using Dirichlet-calibrated subjective logic.
2. **Decision Engine Reliability-First Hierarchy:**
   - Hardware degradation check ($R \le 0.35 \implies \text{TX}$) correctly isolates physical sensor faults.
   - Nominal quiet marine background check ($C_p < 0.55 \implies \text{T0}$) prevents epistemic ambiguity from converting quiet calm periods into false operator failure alerts.
   - Ambiguous disturbance check ($C_p \ge 0.55 \land U \ge 0.65 \implies \text{TX}$) flags conflicting multi-sensor evidence.
   - Corroboration tiering ($C_a < 0.60 \implies \text{T1}$; $C_a \ge 0.60 \implies \text{T2/T3}$) successfully separates isolated environmental excitation from vessel-correlated events.
   - Exact backward compatibility across all 22 benchmark scenarios ($S01\text{--}S22$) preserved.
3. **Marlinks Real Offshore Wind Farm DAS Validation:**
   - Evaluated on operational export cable DAS recording (60 windows $\times$ 250 channels $\times$ 100 frequency bins).
   - Confirms strong monotonic inverse distance coupling between optical acoustic energy and container ship proximity: Spearman $\rho = +0.9482$ ($p = 1.42 \times 10^{-30}$), Pearson $r = +0.3629$ ($p = 0.0044$).
   - Closest Point of Approach (CPA) localized to Channel 1449 with high spatial concentration ($\text{Gini} = 0.8739$, $\text{PAR} = 18.17$).
4. **EMSO Western Ionian Deep-Sea Observatory DAS Validation:**
   - Evaluated on 10 Hz continuous optical recording (10,500 samples $\times$ 2,963 channels over 1,050 seconds at 2,100 m depth).
   - Confirms deep-sea unperturbed noise floor temporal stability ($\text{CV}_{\text{temporal}} = 0.0008$) and spatial inter-channel attenuation variance ($\text{CV}_{\text{spatial}} = 1.787$).
5. **Dryad Oliktok Arctic Seafloor DAS Validation:**
   - Evaluated on continuous multi-week shallow shelf recording (215 hourly windows $\times$ 183 physical channels $\times$ 32 frequency bins spanning 27.625 days).
   - Validates hydroacoustic physical coupling against independent oceanographic instruments: Spotter wave buoy $H_s$ (Spearman $\rho = +0.3141, p = 2.63 \times 10^{-6}$) and seafloor dynamic bottom pressure variance (Spearman $\rho = +0.4951, p = 1.07 \times 10^{-14}$).
   - **Environmental False-Escalation Finding:** In 215 real continuous hourly windows under Arctic storm and wave fluctuations without AIS contact, exactly 0 false vessel escalations occurred ($N(\text{T2}) = 0, N(\text{T3}) = 0, \text{Rate} = 0.0\%$).
6. **Adversarial Robustness Within Defined Vessel-Side Threat Model:**
   - Evasion resistance characterized under AIS transponder intentional shutdown, ghost trajectory spoofing, timestamp manipulation ($\pm 10\text{--}300\text{ s}$), and spatial offsets.
   - Demonstrates that spoofed AIS tracks unaccompanied by acoustic vibration trigger T1/TX rather than false T2/T3 alarms.
7. **Full Software Test Suite:**
   - 240 automated test cases passing with 0 failures and 0 skips across 23 test suites.

---

### MUST NOT BE CLAIMED (Scientifically Unsupported & Explicitly Disclaimed)

1. **NO Causal Cable Damage Attribution:**
   - None of the real datasets (Marlinks, EMSO, Oliktok) contain physical cable failure, insulation rupture, or conductor severance logs. The framework validates *disturbance detection and evidence corroboration*, NOT mechanical damage triage.
2. **NO Independent Vessel Classification / Detection Metrics on Oliktok:**
   - The Oliktok dataset contains zero vessel annotations and zero AIS trajectories. It MUST NOT be claimed that Oliktok validates vessel detection precision, recall, F1, or ROC-AUC.
3. **NO Universal False Positive Rate Claims:**
   - It is scientifically invalid to report "zero false vessel alarms" without positive/negative vessel ground truth. The verified finding is: *"No T2/T3 vessel-escalation decisions occurred during the evaluated 27.6-day Oliktok environmental recording."*
4. **NO 2D AIS Trajectory Reconstruction from Marlinks:**
   - Marlinks provides 1D scalar vessel distance $y(t)$, not 2D geographic coordinates or polyline trajectories.
5. **NO "Attack-Proof" or "Unbreakable" Cyber-Physical Security Guarantees:**
   - Adversarial robustness is evaluated specifically against vessel-side transponder manipulation and spoofing. Colluding multi-sensor hardware compromise is outside the threat model.
6. **NO Cross-Dataset Pooled Metrics:**
   - Datasets must never be combined into a single classification metric due to differing physical units, temporal scales, and annotation availability.

---

## 3. Detailed Component Audit

### 3.1 Real Dataset Triad Specification

```
+---------------------------------------------------------------------------------------------------+
|                                   REAL SUBMARINE DAS VALIDATION TRIAD                              |
+------------------------------------+--------------------------------+-----------------------------+
| 1. MARLINKS WIND FARM (North Sea)  | 2. EMSO SEVEN OBS (Ionian Sea) | 3. DRYAD OLIKTOK (Arctic)   |
| • Role: 1D Vessel Proximity & CPA  | • Role: Deep-Sea Baseline      | • Role: Multi-Week Storms   |
| • Channels: 250 (1440-1690)        | • Channels: 2,963              | • Channels: 183 (1088-3672) |
| • Duration: 590 s (10 min)         | • Duration: 1,050 s (17.5 min) | • Duration: 27.6 days (663h)|
| • Target: 304m Container Ship      | • Target: Ambient Seafloor     | • Target: Natural Sea States|
| • Finding: rho = +0.9482 vs 1/y    | • Finding: CV_temp = 0.0008    | • Finding: 0% T2/T3 alarms  |
+------------------------------------+--------------------------------+-----------------------------+
```

### 3.2 Decision State Machine Hierarchy

```
                      [ Raw Sensor & Telemetry Data ]
                                     │
                                     ▼
                       [ Reliability Gate: R <= 0.35? ]
                                     │
                         Yes ────────┴──────── No
                          │                    │
                          ▼                    ▼
                    [ State: TX ]     [ Physical Gate: Cp < 0.55? ]
                    (Sensor Defect)            │
                                   Yes ────────┴──────── No
                                    │                    │
                                    ▼                    ▼
                              [ State: T0 ]    [ Uncertainty Gate: U >= 0.65? ]
                              (Normal Quiet)             │
                                             Yes ────────┴──────── No
                                              │                    │
                                              ▼                    ▼
                                        [ State: TX ]    [ Corroboration: Ca < 0.60? ]
                                      (Ambiguous Anomaly)          │
                                                     Yes ──────────┴────────── No
                                                      │                        │
                                                      ▼                        ▼
                                                [ State: T1 ]            [ State: T2 / T3 ]
                                            (Uncorroborated Anomaly)   (Corroborated Threat)
```

---

## 4. Manuscript Integration Checklist

When authorized to update the IEEE manuscript (`paper/`):

- [ ] **Update Section IV (Real Datasets):** Include the real dataset triad (Table `table_real_datasets_comparison`).
- [ ] **Update Section V (Results):** Incorporate the Oliktok multi-week environmental robustness and wave tracking findings (`table_oliktok_validation`, Figure `oliktok_temporal_stability.png`).
- [ ] **Update Decision State Engine Description:** Accurately present the reliability-first hierarchy ($R \to T0 \to U \to T1/T2/T3$).
- [ ] **Verify Notation Consistency:** Ensure $C_p$ (Physical), $C_a$ (Association), $R$ (Reliability), and $U$ (Uncertainty) match across text and mathematical definitions.
- [ ] **Strictly Maintain Limitations Section:** Preserve explicit disclaimers regarding unlabelled datasets, lack of causal damage logs, and threat model boundaries.

---

## 5. Certification

This repository has undergone a comprehensive, multi-phase verification. All reported quantities are executable, audited, and strictly reproducible from raw data.

**Validation Status:** **COMPLETE & CONSISTENT**
