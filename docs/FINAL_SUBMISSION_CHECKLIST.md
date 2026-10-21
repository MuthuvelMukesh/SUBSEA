# Final IEEE Submission Readiness Checklist

This document provides the formal submission readiness verification for the SUBSEA research paper and supporting repository.

**Project Title:** An Uncertainty-Aware Multimodal Evidence Fusion Framework for Vessel-Associated Subsea Cable Disturbance Assessment under Adversarial Uncertainty  
**Target Venue:** IEEE Transactions / Conference Publication  
**Checklist Date:** 2026-09-20  
**Overall Status:** READY WITH MINOR FIXES (Pending local PDF recompilation by user)  

---

## Submission Checklist Matrix

| # | Checklist Item | Status | Verification Detail / Evidence |
| :---: | :--- | :---: | :--- |
| 1 | **Scientific Consistency** | **PASS** | Disturbance detection is cleanly decoupled from vessel attribution. Fail-closed safety property and negative F1 trade-offs are explicitly explained. |
| 2 | **Numerical Consistency** | **PASS** | 54 audited quantitative parameters match source manifests 100%. Obsolete $0.4682$ replaced with $+0.4903$ in Table IV; Spearman $\rho = -0.9482$ synchronized across all sections. |
| 3 | **Dataset Provenance** | **PASS** | Complete cryptographic provenance in `data/PROVENANCE.json` and Section V for Marlinks (`46f5d2838342`), EMSO (`8af2afac41b9`), and Oliktok (`5fa69e4cf90a`). |
| 4 | **Reproducibility** | **PASS** | Execution scripts (`run_real_evaluation.py`, `run_phase3_validation.py`, `audit_manuscript_consistency.py`, `validate_manuscript.py`) tested and reproducible. |
| 5 | **Test Suite** | **PASS** | `pytest tests -q` yields 240 passed, 0 failed, 0 skipped in 14.59s. |
| 6 | **Code Compilation** | **PASS** | `python -m compileall -q src scripts dashboard` exits cleanly with 0 syntax or bytecode compilation errors. |
| 7 | **PDF Compilation** | **NOT VERIFIED** | Existing PDF structurally validated; LaTeX rebuild not independently executed in current environment due to lack of local `pdflatex` binary. |
| 8 | **Figure Validation** | **PASS** | All 8 figures referenced in `paper/paper.tex` exist in `paper/figs/` at publication resolution (300 DPI) and are verified by `validate_manuscript.py`. |
| 9 | **Table Validation** | **PASS** | All 10 tables (Tables I--X) in `paper/paper.tex` are structurally balanced and numerically consistent with evaluation manifests. |
| 10 | **References** | **PASS** | 15 citations verified; 15 bibitems resolved; DOIs and metadata confirmed against IEEE Xplore, Zenodo, and Dryad repositories. |
| 11 | **IEEE Formatting** | **PASS** | Conforms to official `IEEEtran.cls` double-column format with standard title block, abstract, index terms, section hierarchy, and equation styling. |
| 12 | **Claim Discipline** | **PASS** | Zero instances of unsupported claims ("attack-proof", "guaranteed detection", "causal damage"). AER scoped to vessel-side threat model (0/200 observed trials). |
| 13 | **Limitations Section** | **PASS** | Dedicated Section VII documents absence of structural damage ground truth, unlabelled DAS caveats, 1D tracking limits, and unpooled escalation F1 conservatism. |
| 14 | **Supplementary Material** | **NOT APPLICABLE** | All benchmark artifacts, manifests, tables, and figures reside directly within the repository structure. |
| 15 | **Git Repository Status** | **PASS** | Clean working tree; all manuscript corrections tracked; git status and diff verified against upstream `main`. |
