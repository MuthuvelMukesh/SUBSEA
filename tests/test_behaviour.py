import pytest

from subsea.behaviour import behaviour_components


def test_behaviour_returns_separate_interpretable_components():
    trajectory = ((0.0, 2.0), (1.0, 0.5), (2.0, -0.5), (3.0, -2.0))
    timestamps = (0.0, 1.0, 2.0, 3.0)
    components = behaviour_components(
        trajectory,
        timestamps,
        ((0.0, 0.0), (3.0, 0.0)),
        speeds=(4.0, 4.0, 4.0, 4.0),
        headings=(270.0, 270.0, 270.0, 270.0),
        interaction_radius=2.0,
    )
    assert set(components) == {"proximity", "approach_direction", "speed", "heading", "dwell", "crossing", "cpa"}
    assert all(0.0 <= value <= 1.0 for value in components.values())
    assert components["crossing"] == 1.0
    assert components["cpa"] == pytest.approx(0.75)
