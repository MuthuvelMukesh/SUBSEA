from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

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


def _write_figure(rows: list[dict[str, object]], path: Path) -> str:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
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
    result = {"status": "EXECUTED" if figure_status == "EXECUTED" else "PARTIAL", "data_kind": manifest["data_kind"], "source_manifest": str(source), "source_sha256": source_hash, "software_version": __version__, "seed": manifest["seed"], "scenario_ids": manifest["scenario_ids"], "methods": manifest["methods"], "figure_status": figure_status, "tables": ["table_methods.csv", "table_methods.tex"]}
    (destination / "paper_output_manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
