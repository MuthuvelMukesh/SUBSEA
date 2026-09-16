import json

with open("artifacts/adversarial/adversarial_manifest.json") as f:
    m = json.load(f)

print(f"Total attack rows: {len(m['results'])}")
for r in m["results"][:15]:
    atk = r["attack"]
    sev = r["severity"]
    aer = r["AER"]
    dec = r.get("decisions", {})
    u = r.get("mean_uncertainty", None)
    cp = r.get("mean_physical_confidence", None)
    ca = r.get("mean_association_confidence", None)
    fs = r.get("mean_fused_score", None)
    print(f"{atk} (sev={sev}): AER={aer}, dec={dec}, U={u}, Cp={cp}, Ca={ca}, Fused={fs}")
