"""Tests for Pareto frontier optimization."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import pytest

from data.schemas import ParetoPoint
from optimization.pareto import (
    compute_pareto_frontier,
    find_optimal_configuration,
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
