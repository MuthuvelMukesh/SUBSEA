import json

import pytest

from subsea.experiments import run_method_comparison
from subsea.reporting import generate_paper_outputs


def test_paper_outputs_are_generated_from_executed_manifest(tmp_path):
    manifest_path = run_method_comparison(["S01", "S04"], trials=1, seed=2, output=tmp_path / "experiment", methods=("proposed", "physical_only"))
    output = tmp_path / "paper"
    generated = generate_paper_outputs(manifest_path, output)
    assert generated["status"] == "EXECUTED"
    assert (output / "table_methods.csv").is_file()
    assert (output / "table_methods.tex").is_file()
    if pytest.importorskip("matplotlib"):
        assert (output / "figure_method_comparison.png").is_file()
    payload = json.loads((output / "paper_output_manifest.json").read_text())
    assert payload["source_manifest"] == str(manifest_path)
    assert payload["source_sha256"]
    assert payload["seed"] == 2


def test_paper_outputs_reject_unverified_manifest(tmp_path):
    manifest = tmp_path / "fabricated.json"
    manifest.write_text(json.dumps({"status": "EXECUTED", "methods": ["proposed"], "summaries": {"proposed": {"status": "EXECUTED", "value": {"f1": 0.9}}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        generate_paper_outputs(manifest, tmp_path / "paper")


def test_paper_outputs_recompute_summary_values(tmp_path):
    manifest_path = run_method_comparison(["S01", "S04"], trials=1, seed=2, output=tmp_path / "experiment")
    manifest = json.loads(manifest_path.read_text())
    manifest["summaries"]["proposed"]["value"]["f1"] = 0.99
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        generate_paper_outputs(tampered, tmp_path / "paper")


def test_paper_outputs_reject_duplicate_records(tmp_path):
    manifest_path = run_method_comparison(["S01", "S04"], trials=1, seed=2, output=tmp_path / "experiment")
    manifest = json.loads(manifest_path.read_text())
    manifest["records"][-1] = manifest["records"][0]
    tampered = tmp_path / "duplicate.json"
    tampered.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="coverage"):
        generate_paper_outputs(tampered, tmp_path / "paper")
