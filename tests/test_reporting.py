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


def test_individual_figures_and_tables_generation(tmp_path):
    from subsea.reporting import (
        generate_architecture_figure,
        generate_fusion_pipeline_figure,
        generate_das_ais_figure,
        generate_dataset_characteristics_table,
        generate_scenario_performance_table,
        generate_ablation_figure,
        generate_ablation_table,
        generate_calibration_table,
        generate_real_data_association_table,
    )
    from subsea.experiments import run_ablation_study, run_calibration_analysis

    out = tmp_path / "figs_and_tbls"
    out.mkdir()

    # Figures 1, 2, 10
    assert generate_architecture_figure(out) == "EXECUTED"
    assert (out / "figure_architecture.png").is_file()

    assert generate_fusion_pipeline_figure(out) == "EXECUTED"
    assert (out / "figure_fusion_pipeline.png").is_file()

    assert generate_das_ais_figure(out) == "EXECUTED"
    assert (out / "figure_das_ais_association.png").is_file()

    # Table II
    assert generate_dataset_characteristics_table(out) == "EXECUTED"
    assert (out / "table_dataset_characteristics.csv").is_file()
    assert (out / "table_dataset_characteristics.tex").is_file()

    # Table IV from method comparison manifest
    manifest_path = run_method_comparison(["S01", "S04"], trials=1, seed=2, output=tmp_path / "comp")
    assert generate_scenario_performance_table(manifest_path, out) == "EXECUTED"
    assert (out / "table_scenario_performance.csv").is_file()
    assert (out / "table_scenario_performance.tex").is_file()

    # Figure 5 & Table V from ablation manifest
    abl_path = run_ablation_study(["S01", "S04"], trials=1, seed=2, output=tmp_path / "abl")
    assert generate_ablation_figure(abl_path, out) == "EXECUTED"
    assert (out / "figure_ablation_study.png").is_file()
    assert generate_ablation_table(abl_path, out) == "EXECUTED"
    assert (out / "table_ablation.csv").is_file()
    assert (out / "table_ablation.tex").is_file()

    # Table VIII from calibration manifest
    cal_path = run_calibration_analysis(["S01", "S04"], trials=1, seed=2, output=tmp_path / "cal")
    assert generate_calibration_table(cal_path, out) == "EXECUTED"
    assert (out / "table_calibration.csv").is_file()
    assert (out / "table_calibration.tex").is_file()

    # Table IX (Real-data association, marked NOT EXECUTED if external data missing)
    assert generate_real_data_association_table(out) == "EXECUTED"
    assert (out / "table_real_data_association.csv").is_file()
    assert (out / "table_real_data_association.tex").is_file()
    # Ensure it states NOT EXECUTED
    content = (out / "table_real_data_association.csv").read_text()
    assert "NOT EXECUTED" in content

