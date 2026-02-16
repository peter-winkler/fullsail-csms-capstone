"""Tests for Pareto frontier optimization."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import pytest

from data.schemas import CloudCostModel, Event, InstanceType, ParetoPoint, SiteProfile
from optimization.pareto import (
    compute_pareto_frontier,
    compute_pareto_frontier_multi,
    find_optimal_configuration,
    generate_multi_instance_sweep,
    is_dominated,
)


class TestIsDominated:
    """Tests for the is_dominated helper."""

    def test_dominated_both_better(self) -> None:
        assert is_dominated((100, 10), (50, 5)) is True

    def test_dominated_one_equal(self) -> None:
        assert is_dominated((100, 10), (100, 5)) is True
        assert is_dominated((100, 10), (50, 10)) is True

    def test_not_dominated_trade_off(self) -> None:
        assert is_dominated((50, 10), (100, 5)) is False

    def test_not_dominated_identical(self) -> None:
        assert is_dominated((100, 10), (100, 10)) is False


class TestComputeParetoFrontier:
    """Tests for compute_pareto_frontier function."""

    def test_empty_list(self) -> None:
        result = compute_pareto_frontier([])
        assert result == []

    def test_single_point_is_pareto_optimal(self) -> None:
        points = [("G5_C0", 0.0, 3600.0)]
        result = compute_pareto_frontier(points)

        assert len(result) == 1
        assert result[0].is_pareto_optimal is True
        assert result[0].config_id == "G5_C0"

    def test_dominated_point_not_optimal(self) -> None:
        points = [
            ("G5_C0", 100.0, 5000.0),  # dominated
            ("G5_C5", 80.0, 4000.0),   # dominates in both
        ]
        result = compute_pareto_frontier(points)

        assert result[0].is_pareto_optimal is False  # G5_C0
        assert result[1].is_pareto_optimal is True   # G5_C5

    def test_non_dominated_points_are_optimal(self) -> None:
        points = [
            ("G5_C0", 0.0, 10000.0),    # cheaper but slower
            ("G5_C10", 100.0, 5000.0),   # faster but more expensive
        ]
        result = compute_pareto_frontier(points)

        assert result[0].is_pareto_optimal is True
        assert result[1].is_pareto_optimal is True

    def test_three_point_frontier(self) -> None:
        points = [
            ("G5_C0", 0.0, 10000.0),     # cheapest, slowest
            ("G5_C5", 50.0, 7000.0),      # middle trade-off
            ("G5_C10", 100.0, 5000.0),    # fastest, most expensive
            ("G5_C3", 80.0, 8000.0),      # dominated by C5
        ]
        result = compute_pareto_frontier(points)

        assert result[0].is_pareto_optimal is True   # G5_C0
        assert result[1].is_pareto_optimal is True   # G5_C5
        assert result[2].is_pareto_optimal is True   # G5_C10
        assert result[3].is_pareto_optimal is False  # G5_C3 (dominated)


class TestFindOptimalConfiguration:
    """Tests for find_optimal_configuration function."""

    def test_empty_list_returns_none(self) -> None:
        result = find_optimal_configuration([])
        assert result is None

    def test_cost_weight_favors_cheapest(self) -> None:
        points = [
            ParetoPoint(config_id="G5_C0", cost=0.0, time=10000.0, is_pareto_optimal=True),
            ParetoPoint(config_id="G5_C10", cost=100.0, time=5000.0, is_pareto_optimal=True),
        ]
        result = find_optimal_configuration(points, cost_weight=1.0)
        assert result.config_id == "G5_C0"

    def test_time_weight_favors_fastest(self) -> None:
        points = [
            ParetoPoint(config_id="G5_C0", cost=0.0, time=10000.0, is_pareto_optimal=True),
            ParetoPoint(config_id="G5_C10", cost=100.0, time=5000.0, is_pareto_optimal=True),
        ]
        result = find_optimal_configuration(points, cost_weight=0.0)
        assert result.config_id == "G5_C10"

    def test_balanced_weight(self) -> None:
        points = [
            ParetoPoint(config_id="G5_C0", cost=0.0, time=10000.0, is_pareto_optimal=True),
            ParetoPoint(config_id="G5_C5", cost=50.0, time=7000.0, is_pareto_optimal=True),
            ParetoPoint(config_id="G5_C10", cost=100.0, time=5000.0, is_pareto_optimal=True),
        ]
        result = find_optimal_configuration(points, cost_weight=0.5)
        # Middle point should score best with balanced weights
        assert result is not None


# --- New tests for multi-instance features ---


def _make_events(n: int = 10) -> list:
    """Create test events with varied processing times."""
    return [
        Event(
            event_name=f"test_event_{i}",
            venue="TST",
            event_type="Pitching" if i % 2 == 0 else "Batting",
            processing_time_sec=300.0 + i * 50,
        )
        for i in range(n)
    ]


def _make_instance_types() -> list:
    """Create a small set of instance types for testing."""
    return [
        InstanceType(name="g4dn.xlarge", gpu="Tesla T4",   rate_ondemand=0.526, rate_spot=0.21, rate_1yr_ri=0.33, rate_3yr_ri=0.21, ratio=2.18),
        InstanceType(name="g6.xlarge",   gpu="NVIDIA L4",  rate_ondemand=0.980, rate_spot=0.34, rate_1yr_ri=0.61, rate_3yr_ri=0.43, ratio=1.278),
    ]


class TestCloudCostModelRatio:
    """Tests for ratio-based CloudCostModel."""

    def test_ratio_based_time(self) -> None:
        model = CloudCostModel(ratio=2.0, container_startup_sec=30, data_transfer_sec_per_event=60)
        # 500s on-prem -> 2.0 * 500 + 30 + 60 = 1090s
        assert model.event_cloud_time_for(500.0) == pytest.approx(1090.0)

    def test_ratio_none_uses_fixed_time(self) -> None:
        model = CloudCostModel(cloud_time_per_event_sec=1000.0, container_startup_sec=30, data_transfer_sec_per_event=60)
        # No ratio -> uses fixed 1000 + 30 + 60 = 1090s
        assert model.event_cloud_time_for(500.0) == pytest.approx(1090.0)

    def test_from_instance_sets_ratio(self) -> None:
        inst = InstanceType(name="test", gpu="Test GPU", rate_ondemand=1.0, rate_spot=0.5, rate_1yr_ri=0.7, rate_3yr_ri=0.4, ratio=1.5)
        model = CloudCostModel.from_instance(inst, "spot")
        assert model.ratio == 1.5
        assert model.cost_per_hour == 0.5
        assert model.instance_type == "test"
        assert model.pricing_tier == "spot"

    def test_ratio_based_cost(self) -> None:
        model = CloudCostModel(ratio=2.0, cost_per_hour=1.0, container_startup_sec=0, data_transfer_sec_per_event=0, data_transfer_cost_per_event=0)
        # 3600s on-prem -> 2.0 * 3600 = 7200s cloud processing
        # 7200s / 3600 = 2.0 hours * $1.00 = $2.00
        assert model.event_cloud_cost_for(3600.0) == pytest.approx(2.0)

    def test_variable_event_times(self) -> None:
        model = CloudCostModel(ratio=2.0, container_startup_sec=0, data_transfer_sec_per_event=0)
        t1 = model.event_cloud_time_for(100.0)
        t2 = model.event_cloud_time_for(500.0)
        assert t1 < t2  # Shorter on-prem -> shorter cloud


class TestMultiInstanceSweep:
    """Tests for generate_multi_instance_sweep."""

    def test_sweep_count(self) -> None:
        events = _make_events(5)
        site = SiteProfile(name="Test", venue_code="TST", available_gpus=2, tier="gpu_poor")
        instances = _make_instance_types()
        pricing = ["ondemand", "spot"]
        max_c = 5

        points = generate_multi_instance_sweep(
            events, site, instances, pricing, max_cloud_containers=max_c,
        )
        # 2 instances x 2 pricing x (5+1) counts = 24
        assert len(points) == 24

    def test_full_sweep_816_configs(self) -> None:
        events = _make_events(5)
        site = SiteProfile(name="Test", venue_code="TST", available_gpus=2, tier="gpu_poor")
        instances = [
            InstanceType(name="a", gpu="A", rate_ondemand=1, rate_spot=0.5, rate_1yr_ri=0.7, rate_3yr_ri=0.4, ratio=2.0),
            InstanceType(name="b", gpu="B", rate_ondemand=2, rate_spot=0.8, rate_1yr_ri=1.2, rate_3yr_ri=0.9, ratio=1.5),
            InstanceType(name="c", gpu="C", rate_ondemand=1.5, rate_spot=0.6, rate_1yr_ri=0.9, rate_3yr_ri=0.6, ratio=1.2),
            InstanceType(name="d", gpu="D", rate_ondemand=3, rate_spot=1.0, rate_1yr_ri=2.0, rate_3yr_ri=1.5, ratio=1.4),
        ]
        pricing = ["ondemand", "spot", "1yr_ri", "3yr_ri"]

        points = generate_multi_instance_sweep(
            events, site, instances, pricing, max_cloud_containers=50,
        )
        # 4 instances x 4 pricing x 51 counts = 816
        assert len(points) == 816

    def test_sweep_has_metadata(self) -> None:
        events = _make_events(3)
        site = SiteProfile(name="Test", venue_code="TST", available_gpus=1, tier="gpu_poor")
        instances = _make_instance_types()[:1]
        pricing = ["spot"]

        points = generate_multi_instance_sweep(
            events, site, instances, pricing, max_cloud_containers=2,
        )
        # Each point should be (config_id, cost, time, instance_name, pricing, cloud_containers)
        assert len(points[0]) == 6
        assert points[0][3] == "g4dn.xlarge"
        assert points[0][4] == "spot"
        assert points[0][5] == 0  # first point has 0 containers

    def test_zero_containers_has_zero_cost(self) -> None:
        events = _make_events(3)
        site = SiteProfile(name="Test", venue_code="TST", available_gpus=2, tier="gpu_poor")
        instances = _make_instance_types()[:1]
        pricing = ["spot"]

        points = generate_multi_instance_sweep(
            events, site, instances, pricing, max_cloud_containers=2,
        )
        # First point (C=0) should have zero cloud cost
        assert points[0][1] == 0.0


class TestComputeParetoFrontierMulti:
    """Tests for compute_pareto_frontier_multi."""

    def test_preserves_metadata(self) -> None:
        points = [
            ("T4_spot_C0", 0.0, 10000.0, "g4dn.xlarge", "spot"),
            ("L4_spot_C5", 50.0, 5000.0, "g6.xlarge", "spot"),
        ]
        result = compute_pareto_frontier_multi(points)

        assert len(result) == 2
        assert result[0].instance_type == "g4dn.xlarge"
        assert result[0].pricing_tier == "spot"
        assert result[1].instance_type == "g6.xlarge"
        assert result[1].pricing_tier == "spot"

    def test_dominated_detection(self) -> None:
        points = [
            ("A_C1", 100.0, 8000.0, "inst_a", "spot"),  # dominated by B
            ("B_C1", 50.0, 5000.0, "inst_b", "spot"),    # dominates A
            ("C_C0", 0.0, 12000.0, "inst_c", "spot"),    # non-dominated (cheapest)
        ]
        result = compute_pareto_frontier_multi(points)

        assert result[0].is_pareto_optimal is False  # A dominated
        assert result[1].is_pareto_optimal is True   # B on frontier
        assert result[2].is_pareto_optimal is True   # C on frontier (cheapest)

    def test_empty_input(self) -> None:
        result = compute_pareto_frontier_multi([])
        assert result == []

    def test_frontier_fewer_than_total(self) -> None:
        events = _make_events(5)
        site = SiteProfile(name="Test", venue_code="TST", available_gpus=2, tier="gpu_poor")
        instances = _make_instance_types()
        pricing = ["ondemand", "spot"]

        raw_points = generate_multi_instance_sweep(
            events, site, instances, pricing, max_cloud_containers=10,
        )
        result = compute_pareto_frontier_multi(raw_points)

        total = len(result)
        frontier = sum(1 for p in result if p.is_pareto_optimal)
        assert frontier < total  # Some must be dominated


class TestInstanceType:
    """Tests for InstanceType model."""

    def test_rate_for_pricing(self) -> None:
        inst = InstanceType(name="test", gpu="Test", rate_ondemand=1.0, rate_spot=0.5, rate_1yr_ri=0.7, rate_3yr_ri=0.4, ratio=2.0)
        assert inst.rate_for_pricing("ondemand") == 1.0
        assert inst.rate_for_pricing("spot") == 0.5
        assert inst.rate_for_pricing("1yr_ri") == 0.7
        assert inst.rate_for_pricing("3yr_ri") == 0.4

    def test_invalid_pricing_raises(self) -> None:
        inst = InstanceType(name="test", gpu="Test", rate_ondemand=1.0, rate_spot=0.5, rate_1yr_ri=0.7, rate_3yr_ri=0.4, ratio=2.0)
        with pytest.raises(KeyError):
            inst.rate_for_pricing("invalid")

    def test_none_ri_returns_none(self) -> None:
        inst = InstanceType(name="p3", gpu="V100", rate_ondemand=3.06, rate_spot=0.33, ratio=1.37)
        assert inst.rate_for_pricing("1yr_ri") is None
        assert inst.rate_for_pricing("3yr_ri") is None
        assert inst.rate_for_pricing("ondemand") == 3.06
        assert inst.rate_for_pricing("spot") == 0.33

    def test_available_pricing_all_tiers(self) -> None:
        inst = InstanceType(name="test", gpu="Test", rate_ondemand=1.0, rate_spot=0.5, rate_1yr_ri=0.7, rate_3yr_ri=0.4, ratio=2.0)
        assert inst.available_pricing() == ["ondemand", "spot", "1yr_ri", "3yr_ri"]

    def test_available_pricing_no_ri(self) -> None:
        inst = InstanceType(name="p3", gpu="V100", rate_ondemand=3.06, rate_spot=0.33, ratio=1.37)
        assert inst.available_pricing() == ["ondemand", "spot"]

    def test_from_instance_unavailable_raises(self) -> None:
        inst = InstanceType(name="p3", gpu="V100", rate_ondemand=3.06, rate_spot=0.33, ratio=1.37)
        with pytest.raises(ValueError, match="not available"):
            CloudCostModel.from_instance(inst, "1yr_ri")


class TestMultiInstanceSweepSkipsUnavailable:
    """Tests that sweep correctly skips unavailable pricing tiers."""

    def test_sweep_skips_none_ri(self) -> None:
        events = _make_events(3)
        site = SiteProfile(name="Test", venue_code="TST", available_gpus=2, tier="gpu_poor")
        # One instance with RI, one without
        instances = [
            InstanceType(name="with_ri", gpu="A", rate_ondemand=1.0, rate_spot=0.5, rate_1yr_ri=0.7, rate_3yr_ri=0.4, ratio=2.0),
            InstanceType(name="no_ri", gpu="B", rate_ondemand=3.0, rate_spot=0.3, ratio=1.4),
        ]
        pricing = ["ondemand", "spot", "1yr_ri", "3yr_ri"]
        max_c = 2

        points = generate_multi_instance_sweep(
            events, site, instances, pricing, max_cloud_containers=max_c,
        )
        # with_ri: 4 pricing x 3 counts = 12
        # no_ri: 2 pricing x 3 counts = 6
        # Total: 18
        assert len(points) == 18

        # Verify no_ri instance only has ondemand and spot
        no_ri_tiers = set(p[4] for p in points if p[3] == "no_ri")
        assert no_ri_tiers == {"ondemand", "spot"}
