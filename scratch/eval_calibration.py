import json
import numpy as np
import sys
sys.path.insert(0, "src")
from subsea.metrics import brier_score, expected_calibration_error, bootstrap_confidence_interval

with open("artifacts/simulation/scenario_matrix.json") as f:
    m = json.load(f)

trials = m["trials"]
labels = [1 if t["ground_truth"]["true_h1"] else 0 for t in trials]

probs_rel = [t["reliability"] for t in trials]
probs_fused = [t["fusion_score"] for t in trials]
probs_hyp = [t["hypothesis_scores"]["vessel_associated_disturbance"] for t in trials]

print("Labels count:", len(labels), "Sum:", sum(labels))
print("probs_rel: Brier =", brier_score(labels, probs_rel), "ECE =", expected_calibration_error(labels, probs_rel))
print("probs_rel CI 95%:", bootstrap_confidence_interval(probs_rel))
print("probs_fused: Brier =", brier_score(labels, probs_fused), "ECE =", expected_calibration_error(labels, probs_fused))
print("probs_hyp: Brier =", brier_score(labels, probs_hyp), "ECE =", expected_calibration_error(labels, probs_hyp))

with open("artifacts/simulation/threshold_calibration_manifest.json") as f:
    cal_m = json.load(f)
print("Saved in threshold_calibration_manifest.json:")
print("  brier_score:", cal_m["brier_score"])
print("  ECE:", cal_m["ECE"])
print("  CI:", cal_m["confidence_interval"])
