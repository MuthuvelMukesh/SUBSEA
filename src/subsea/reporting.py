from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__


def _latex(value: object) -> str:
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(character, character) for character in str(value))


def _read_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "EXECUTED":
        raise ValueError("paper outputs require an EXECUTED source manifest")
    required = {"data_kind", "causal_ground_truth", "seed", "trials", "scenario_ids", "summaries", "methods", "records"}
    if not required <= manifest.keys() or manifest["data_kind"] != "synthetic" or manifest["causal_ground_truth"] is not False:
        raise ValueError("source manifest is missing verified provenance")
    if not isinstance(manifest["seed"], int) or isinstance(manifest["seed"], bool) or not isinstance(manifest["trials"], int) or isinstance(manifest["trials"], bool) or manifest["trials"] <= 0:
        raise ValueError("source manifest has invalid provenance")
    if not isinstance(manifest["scenario_ids"], list) or not manifest["scenario_ids"] or not isinstance(manifest["records"], list) or len(manifest["records"]) != len(manifest["methods"]) * len(manifest["scenario_ids"]) * manifest["trials"]:
        raise ValueError("source manifest has incomplete method records")
    allowed_decisions = {"T0", "T1", "T2", "T3", "TX"}
    records_by_method: dict[str, list[dict[str, Any]]] = {method: [] for method in manifest["methods"]}
    expected_keys = {(method, scenario_id, manifest["seed"] + scenario_index * manifest["trials"] + trial) for method in manifest["methods"] for scenario_index, scenario_id in enumerate(manifest["scenario_ids"]) for trial in range(manifest["trials"])}
    observed_keys: set[tuple[str, str, int]] = set()
    for record in manifest["records"]:
        truth = record.get("truth", {}) if isinstance(record, dict) else {}
        truth_fields = ("vessel_present", "disturbance_present", "environmental_event", "sensor_failure", "spoofing", "timestamp_manipulation")
        if not isinstance(record, dict) or record.get("method") not in records_by_method or record.get("scenario_id") not in manifest["scenario_ids"] or not isinstance(record.get("seed"), int) or record.get("decision") not in allowed_decisions or record.get("status") != "EXECUTED" or not isinstance(truth, dict) or any(not isinstance(truth.get(field), bool) for field in truth_fields):
            raise ValueError("source manifest has invalid method records")
        key = (record["method"], record["scenario_id"], record["seed"])
        if key in observed_keys or key not in expected_keys:
            raise ValueError("source manifest has invalid record coverage")
        observed_keys.add(key)
        records_by_method[record["method"]].append(record)
    for method in manifest["methods"]:
        summary = manifest["summaries"].get(method, {})
        if summary.get("status") == "EXECUTED":
            values = summary.get("value", {})
            if any(not isinstance(values.get(name), (int, float)) or isinstance(values[name], bool) or not 0 <= values[name] <= 1 for name in ("accuracy", "precision", "recall", "f1")):
                raise ValueError("source manifest has invalid metric values")
            expected = _summary_values(records_by_method[method])
            if any(not math.isclose(float(values[name]), expected[name], rel_tol=1e-12, abs_tol=1e-12) for name in ("accuracy", "precision", "recall", "f1")):
                raise ValueError("source manifest summary does not match records")
    return manifest


def _summary_values(records: list[dict[str, Any]]) -> dict[str, float]:
    actual = [bool(record["truth"]["vessel_present"] and record["truth"]["disturbance_present"] and not record["truth"]["environmental_event"]) for record in records]
    predicted = [record["decision"] in {"T2", "T3"} for record in records]
    true_positive = sum(left and right for left, right in zip(actual, predicted))
    false_positive = sum(not left and right for left, right in zip(actual, predicted))
    false_negative = sum(left and not right for left, right in zip(actual, predicted))
    accuracy = sum(left == right for left, right in zip(actual, predicted)) / len(actual)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


def _summary_rows(manifest: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for method in manifest["methods"]:
        summary = manifest["summaries"].get(method, {})
        values = summary.get("value") or {}
        rows.append({
            "method": method,
            "status": summary.get("status", "NOT EXECUTED"),
            "accuracy": values.get("accuracy"),
            "precision": values.get("precision"),
            "recall": values.get("recall"),
            "f1": values.get("f1"),
            "trials": values.get("trials"),
            "reason": summary.get("reason"),
        })
    return rows


def _write_csv(rows: list[dict[str, object]], path: Path) -> None:
    fields = ["method", "status", "accuracy", "precision", "recall", "f1", "trials", "reason"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_latex(rows: list[dict[str, object]], path: Path) -> None:
    columns = ("method", "status", "accuracy", "precision", "recall", "f1", "trials")
    lines = ["\\begin{tabular}{lrrrrrr}", "\\toprule", "Method & Status & Accuracy & Precision & Recall & F1 & Trials \\\\", "\\midrule"]
    for row in rows:
        values = [_latex(row[column]) for column in columns]
        lines.append(" & ".join(values) + " \\\\")
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Publication figure generation
# ---------------------------------------------------------------------------

def _ensure_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        return None


def _write_figure(rows: list[dict[str, object]], path: Path) -> str:
    plt = _ensure_matplotlib()
    if plt is None:
        return "NOT EXECUTED: matplotlib is not installed"
    executed = [row for row in rows if row["status"] == "EXECUTED" and row["f1"] is not None]
    if not executed:
        return "NOT EXECUTED: no executed F1 summaries"
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.bar([str(row["method"]) for row in executed], [float(row["f1"]) for row in executed], color="#176b87")
    axis.set_ylim(0, 1)
    axis.set_ylabel("F1 score")
    axis.set_title("Executed synthetic method comparison")
    axis.tick_params(axis="x", rotation=35)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return "EXECUTED"


def generate_scenario_performance_figure(manifest_path: Path, output_dir: Path) -> str:
    """Figure 3: Scenario-wise performance."""
    plt = _ensure_matplotlib()
    if plt is None:
        return "NOT EXECUTED: matplotlib not installed"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records", [])
    if not records:
        return "NOT EXECUTED: no records"
    # Group by scenario for 'proposed' method
    proposed = [r for r in records if r.get("method") == "proposed"]
    if not proposed:
        proposed = records
    scenarios: dict[str, list[bool]] = {}
    for r in proposed:
        sid = r.get("scenario_id", "unknown")
        is_h1 = r["truth"]["vessel_present"] and r["truth"]["disturbance_present"] and not r["truth"]["environmental_event"]
        correct = (r["decision"] in {"T2", "T3"}) == is_h1
        scenarios.setdefault(sid, []).append(correct)
    sids = sorted(scenarios.keys())
    accs = [sum(scenarios[s]) / len(scenarios[s]) for s in sids]
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ["#176b87" if a >= 0.7 else "#e74c3c" if a < 0.5 else "#f39c12" for a in accs]
    ax.bar(sids, accs, color=colors)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Accuracy")
    ax.set_xlabel("Scenario")
    ax.set_title("Scenario-wise classification accuracy (synthetic)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(output_dir / "figure_scenario_performance.png", dpi=180)
    plt.close(fig)
    return "EXECUTED"


def generate_adversarial_figures(sweep_path: Path, output_dir: Path) -> dict[str, str]:
    """Figure 6-7: AER/FHER vs adversarial severity."""
    plt = _ensure_matplotlib()
    if plt is None:
        return {"AER": "NOT EXECUTED", "FHER": "NOT EXECUTED"}
    sweep = json.loads(sweep_path.read_text(encoding="utf-8"))
    rows = sweep.get("rows", [])
    if not rows:
        return {"AER": "NOT EXECUTED: no rows", "FHER": "NOT EXECUTED: no rows"}
    severities = [r["severity"] for r in rows]
    results = {}
    for metric_key, label, filename, color in [
        ("AER", "Adversarial Error Rate", "figure_aer_vs_severity.png", "#e74c3c"),
        ("FHER", "False High Escalation Rate", "figure_fher_vs_severity.png", "#3498db"),
    ]:
        values = []
        for r in rows:
            m = r.get(metric_key, {})
            if isinstance(m, dict) and m.get("status") == "EXECUTED":
                values.append(m["value"])
            else:
                values.append(None)
        valid = [(s, v) for s, v in zip(severities, values) if v is not None]
        if not valid:
            results[metric_key] = f"NOT EXECUTED: no valid {metric_key} values"
            continue
        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.plot([s for s, _ in valid], [v for _, v in valid], "o-", color=color, linewidth=2, markersize=6)
        ax.set_xlabel("Attack Severity")
        ax.set_ylabel(label)
        ax.set_title(f"{label} vs Adversarial Severity (synthetic)")
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=180)
        plt.close(fig)
        results[metric_key] = "EXECUTED"
    return results


def generate_robustness_figure(sweep_path: Path, output_dir: Path, sweep_type: str) -> str:
    """Figure 8: Uncertainty vs data degradation."""
    plt = _ensure_matplotlib()
    if plt is None:
        return "NOT EXECUTED: matplotlib not installed"
    sweep = json.loads(sweep_path.read_text(encoding="utf-8"))
    rows = sweep.get("rows", [])
    if not rows:
        return "NOT EXECUTED: no rows"
    if sweep_type == "noise":
        x = [r["noise_level"] for r in rows]
        xlabel = "Noise Level"
    elif sweep_type == "packet_loss":
        x = [r["packet_loss_rate"] for r in rows]
        xlabel = "Packet Loss Rate"
    else:
        x = [r.get("position_uncertainty", 0) for r in rows]
        xlabel = "Position Uncertainty"
    y_unc = [r["mean_uncertainty"] for r in rows]
    y_tx = [r["TX_rate"] for r in rows]
    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.plot(x, y_unc, "o-", color="#e74c3c", label="Mean Uncertainty", linewidth=2)
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel("Mean Uncertainty", color="#e74c3c")
    ax2 = ax1.twinx()
    ax2.plot(x, y_tx, "s--", color="#3498db", label="TX Rate", linewidth=2)
    ax2.set_ylabel("TX Rate", color="#3498db")
    ax1.set_title(f"Degradation under {sweep_type.replace('_', ' ')} (synthetic)")
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"figure_{sweep_type}_robustness.png", dpi=180)
    plt.close(fig)
    return "EXECUTED"


def generate_calibration_figure(cal_path: Path, output_dir: Path) -> str:
    """Figure 9: Calibration curve."""
    plt = _ensure_matplotlib()
    if plt is None:
        return "NOT EXECUTED: matplotlib not installed"
    cal = json.loads(cal_path.read_text(encoding="utf-8"))
    curve = cal.get("calibration_curve")
    if not curve:
        return "NOT EXECUTED: no calibration curve"
    fig, ax = plt.subplots(figsize=(6, 6))
    midpoints = [(b["lower"] + b["upper"]) / 2 for b in curve if b["count"] > 0]
    empirical = [b["empirical_rate"] for b in curve if b["count"] > 0]
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Perfect calibration")
    ax.plot(midpoints, empirical, "o-", color="#176b87", linewidth=2, label="Observed")
    ax.set_xlabel("Mean predicted confidence")
    ax.set_ylabel("Empirical positive rate")
    ax.set_title("Calibration curve (synthetic)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "figure_calibration.png", dpi=180)
    plt.close(fig)
    return "EXECUTED"


def generate_decision_distribution_figure(manifest_path: Path, output_dir: Path) -> str:
    """Figure 12: Decision-state distribution."""
    plt = _ensure_matplotlib()
    if plt is None:
        return "NOT EXECUTED: matplotlib not installed"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records", [])
    if not records:
        return "NOT EXECUTED: no records"
    proposed = [r for r in records if r.get("method") == "proposed"]
    if not proposed:
        proposed = records
    dist: dict[str, int] = {}
    for r in proposed:
        d = r.get("decision", "unknown")
        dist[d] = dist.get(d, 0) + 1
    states = ["T0", "T1", "T2", "T3", "TX"]
    counts = [dist.get(s, 0) for s in states]
    colors = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#95a5a6"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(states, counts, color=colors)
    ax.set_ylabel("Count")
    ax.set_title("Decision-state distribution (synthetic)")
    fig.tight_layout()
    fig.savefig(output_dir / "figure_decision_distribution.png", dpi=180)
    plt.close(fig)
    return "EXECUTED"


def generate_hypothesis_figure(manifest_path: Path, output_dir: Path) -> str:
    """Figure 11: Competing hypothesis scores across scenarios."""
    plt = _ensure_matplotlib()
    if plt is None:
        return "NOT EXECUTED: matplotlib not installed"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records", [])
    if not records:
        return "NOT EXECUTED: no records"
    proposed = [r for r in records if r.get("method") == "proposed"]
    if not proposed:
        proposed = records
    # Aggregate hypothesis scores by scenario
    from subsea.models import Hypothesis
    hyp_keys = [h.value for h in Hypothesis]
    scenario_scores: dict[str, dict[str, list[float]]] = {}
    for r in proposed:
        sid = r.get("scenario_id", "unknown")
        scores = r.get("inputs", {}).get("hypothesis_scores", {})
        if not scores:
            continue
        if sid not in scenario_scores:
            scenario_scores[sid] = {h: [] for h in hyp_keys}
        for h in hyp_keys:
            scenario_scores[sid][h].append(scores.get(h, 0.0))
    if not scenario_scores:
        return "NOT EXECUTED: no hypothesis scores"
    sids = sorted(scenario_scores.keys())
    fig, ax = plt.subplots(figsize=(14, 5))
    x = np.arange(len(sids))
    width = 0.2
    colors_h = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]
    for i, h in enumerate(hyp_keys):
        vals = [float(np.mean(scenario_scores[s][h])) for s in sids]
        ax.bar(x + i * width, vals, width, label=h.replace("_", " "), color=colors_h[i % len(colors_h)])
    ax.set_xticks(x + 1.5 * width)
    ax.set_xticklabels(sids, rotation=45)
    ax.set_ylabel("Mean hypothesis score")
    ax.set_title("Competing hypothesis scores by scenario (synthetic)")
    ax.legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(output_dir / "figure_competing_hypotheses.png", dpi=180)
    plt.close(fig)
    return "EXECUTED"


# ---------------------------------------------------------------------------
# Publication table generation
# ---------------------------------------------------------------------------

def generate_scenario_table(output_dir: Path) -> str:
    """Table I: Scenario definitions."""
    from .simulation import _DEFINITIONS, make_scenario
    rows = []
    for sid in sorted(_DEFINITIONS.keys()):
        scenario = make_scenario(sid, 42)
        rows.append({
            "scenario_id": sid,
            "description": scenario.description,
            "vessel_present": scenario.vessel_present,
            "disturbance_present": scenario.disturbance_present,
            "environmental": scenario.environmental_event,
            "adversarial": scenario.spoofing or scenario.timestamp_manipulation or scenario.spatial_manipulation,
        })
    path = output_dir / "table_scenarios.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return "EXECUTED"


def generate_adversarial_table(sweep_path: Path, output_dir: Path) -> str:
    """Table VI: Adversarial attack results."""
    sweep = json.loads(sweep_path.read_text(encoding="utf-8"))
    rows = sweep.get("rows", [])
    if not rows:
        return "NOT EXECUTED: no rows"
    path = output_dir / "table_adversarial.csv"
    fields = ["severity", "AER_status", "AER_value", "FHER_status", "FHER_value", "mean_uncertainty"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            aer = r.get("AER", {})
            fher = r.get("FHER", {})
            writer.writerow({
                "severity": r["severity"],
                "AER_status": aer.get("status", "NOT EXECUTED"),
                "AER_value": aer.get("value"),
                "FHER_status": fher.get("status", "NOT EXECUTED"),
                "FHER_value": fher.get("value"),
                "mean_uncertainty": r.get("mean_uncertainty"),
            })
    return "EXECUTED"


def generate_robustness_table(noise_path: Path, pl_path: Path, output_dir: Path) -> str:
    """Table VII: Noise/packet-loss robustness."""
    rows_out: list[dict[str, Any]] = []
    for path, sweep_type, level_key in [(noise_path, "noise", "noise_level"), (pl_path, "packet_loss", "packet_loss_rate")]:
        if path.is_file():
            sweep = json.loads(path.read_text(encoding="utf-8"))
            for r in sweep.get("rows", []):
                rows_out.append({
                    "type": sweep_type,
                    "level": r.get(level_key),
                    "f1": r.get("f1"),
                    "TX_rate": r.get("TX_rate"),
                    "mean_uncertainty": r.get("mean_uncertainty"),
                })
    if not rows_out:
        return "NOT EXECUTED: no sweep data"
    path_out = output_dir / "table_robustness.csv"
    fields = ["type", "level", "f1", "TX_rate", "mean_uncertainty"]
    with path_out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows_out)
    return "EXECUTED"


# ---------------------------------------------------------------------------
# Main paper output generation
# ---------------------------------------------------------------------------

def generate_paper_outputs(manifest_path: str | Path, output: str | Path) -> dict[str, object]:
    source = Path(manifest_path)
    destination = Path(output)
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = _read_manifest(source)
    rows = _summary_rows(manifest)
    _write_csv(rows, destination / "table_methods.csv")
    _write_latex(rows, destination / "table_methods.tex")
    figure_status = _write_figure(rows, destination / "figure_method_comparison.png")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    # Generate additional figures if manifest has records
    scenario_fig = generate_scenario_performance_figure(source, destination)
    decision_fig = generate_decision_distribution_figure(source, destination)
    hypothesis_fig = generate_hypothesis_figure(source, destination)
    scenario_tbl = generate_scenario_table(destination)
    result = {
        "status": "EXECUTED" if figure_status == "EXECUTED" else "PARTIAL",
        "data_kind": manifest["data_kind"],
        "source_manifest": str(source),
        "source_sha256": source_hash,
        "software_version": __version__,
        "seed": manifest["seed"],
        "scenario_ids": manifest["scenario_ids"],
        "methods": manifest["methods"],
        "figure_status": figure_status,
        "scenario_figure_status": scenario_fig,
        "decision_figure_status": decision_fig,
        "hypothesis_figure_status": hypothesis_fig,
        "scenario_table_status": scenario_tbl,
        "tables": ["table_methods.csv", "table_methods.tex", "table_scenarios.csv"],
    }
    (destination / "paper_output_manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
