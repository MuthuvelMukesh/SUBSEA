import json

with open("artifacts/simulation/scenario_matrix.json") as f:
    m = json.load(f)

for sid, d in m["scenario_summaries"].items():
    u = d["mean_uncertainty"]
    cp = d["mean_physical_confidence"]
    ca = d["mean_association_confidence"]
    dec = d["decision_distribution"]
    print(f"{sid}: u={u:.3f}, cp={cp:.3f}, ca={ca:.3f}, dec={dec}")
