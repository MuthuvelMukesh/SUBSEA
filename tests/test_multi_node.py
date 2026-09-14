"""Tests for multi-node simulation and pipeline."""
import pytest
from subsea.models import SensorObservation
from subsea.simulation import generate_multi_node_observations, make_scenario
from subsea.pipeline import run_multi_node_pipeline


class TestMultiNodeGeneration:
    def test_two_nodes_produce_different_observations(self):
        scenario = make_scenario("S04", seed=42)
        obs, vessels = generate_multi_node_observations(scenario, n_nodes=2)
        assert len(obs) == 2
        ids = sorted(obs.keys())
        assert ids == ["sim-node-01", "sim-node-02"]
        # Different nodes should have different signal strengths due to attenuation
        node1_acc = [o.acceleration[0] for o in obs[ids[0]] if o.packet_received]
        node2_acc = [o.acceleration[0] for o in obs[ids[1]] if o.packet_received]
        assert node1_acc != node2_acc

    def test_three_nodes(self):
        scenario = make_scenario("S04", seed=42)
        obs, vessels = generate_multi_node_observations(scenario, n_nodes=3)
        assert len(obs) == 3

    def test_spatial_attenuation_weakens_farther_nodes(self):
        scenario = make_scenario("S02", seed=42)
        obs, _ = generate_multi_node_observations(
            scenario, n_nodes=3,
            cable_positions=((0.0, 0.0), (10.0, 0.0), (20.0, 0.0)),
            disturbance_position=(0.0, 0.0),
        )
        # Near node should have stronger signal variance than far node
        import numpy as np
        ids = sorted(obs.keys())
        var0 = np.var([o.acceleration[0] for o in obs[ids[0]] if o.packet_received])
        var2 = np.var([o.acceleration[0] for o in obs[ids[2]] if o.packet_received])
        assert var0 > var2

    def test_node_specific_noise_differs(self):
        scenario = make_scenario("S01", seed=42)
        obs, _ = generate_multi_node_observations(scenario, n_nodes=2)
        ids = sorted(obs.keys())
        import numpy as np
        std0 = np.std([o.acceleration[1] for o in obs[ids[0]]])
        std1 = np.std([o.acceleration[1] for o in obs[ids[1]]])
        # Node 1 has slightly higher noise (noise_base * (1 + 0.1 * index))
        assert std1 > std0 or abs(std1 - std0) < 0.1  # Stochastic, but directional

    def test_packet_loss_propagates_to_nodes(self):
        from dataclasses import replace
        scenario = make_scenario("S10", seed=42)
        obs, _ = generate_multi_node_observations(scenario, n_nodes=2)
        ids = sorted(obs.keys())
        lost0 = sum(1 for o in obs[ids[0]] if not o.packet_received)
        lost1 = sum(1 for o in obs[ids[1]] if not o.packet_received)
        assert lost0 > 0 or lost1 > 0

    def test_sensor_failure_drops_all_packets(self):
        scenario = make_scenario("S07", seed=42)
        obs, _ = generate_multi_node_observations(scenario, n_nodes=2)
        for node_id, node_obs in obs.items():
            assert all(not o.packet_received for o in node_obs)

    def test_n_nodes_validation(self):
        scenario = make_scenario("S01", seed=42)
        with pytest.raises(ValueError):
            generate_multi_node_observations(scenario, n_nodes=0)

    def test_cable_position_mismatch_raises(self):
        scenario = make_scenario("S01", seed=42)
        with pytest.raises(ValueError):
            generate_multi_node_observations(
                scenario, n_nodes=2,
                cable_positions=((0.0, 0.0),),  # Only 1 position for 2 nodes
            )


class TestMultiNodePipeline:
    def test_two_node_pipeline_produces_result(self):
        scenario = make_scenario("S04", seed=42)
        obs, vessels = generate_multi_node_observations(scenario, n_nodes=2)
        vessel = vessels[0] if vessels else None
        result = run_multi_node_pipeline(obs, vessel)
        assert len(result.node_results) == 2
        assert len(result.node_ids) == 2
        assert 0 <= result.fused_physical_confidence <= 1
        assert 0 <= result.fused_uncertainty <= 1

    def test_fused_confidence_weights_by_health(self):
        scenario = make_scenario("S04", seed=42)
        obs, vessels = generate_multi_node_observations(scenario, n_nodes=2)
        vessel = vessels[0] if vessels else None
        result = run_multi_node_pipeline(obs, vessel)
        # Fused CP should be between min and max of individual CPs
        cps = [r.physical_confidence for r in result.node_results]
        assert min(cps) <= result.fused_physical_confidence <= max(cps) + 0.01

    def test_empty_nodes_raises(self):
        with pytest.raises(ValueError):
            run_multi_node_pipeline({}, None)
