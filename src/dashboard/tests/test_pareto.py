"""Tests for Pareto frontier optimization."""

import pytest

from app.data.schemas import ParetoPoint, ProcessingLocation
from app.optimization.pareto import (
    calculate_pareto_frontier_line,
    compute_pareto_frontier,
    find_optimal_configuration,
)


def create_point(
    job_id: str,
    location: ProcessingLocation,
    cost: float,
    hours: float,
) -> ParetoPoint:
    """Helper to create test points."""
    return ParetoPoint(
        job_id=job_id,
        configuration_id=f"{job_id}_{location.value}",
        location=location,
        total_hours=hours,
        total_cost=cost,
    )


class TestComputeParetoFrontier:
    """Tests for compute_pareto_frontier function."""

    def test_empty_list(self) -> None:
        """Empty list returns empty list."""
        result = compute_pareto_frontier([])
        assert result == []

    def test_single_point_is_pareto_optimal(self) -> None:
        """A single point is always Pareto-optimal."""
        point = create_point("job1", ProcessingLocation.ON_PREMISES, 100.0, 5.0)
        result = compute_pareto_frontier([point])

        assert len(result) == 1
        assert result[0].is_pareto_optimal is True

    def test_dominated_point_not_optimal(self) -> None:
        """A dominated point is not Pareto-optimal."""
        # Point A: cost=100, time=5
        # Point B: cost=80, time=4 (dominates A in both dimensions)
        point_a = create_point("job1", ProcessingLocation.ON_PREMISES, 100.0, 5.0)
        point_b = create_point("job1", ProcessingLocation.CLOUD_AWS, 80.0, 4.0)

        result = compute_pareto_frontier([point_a, point_b])

        # B should be optimal, A should not
        assert result[0].is_pareto_optimal is False  # point_a
        assert result[1].is_pareto_optimal is True  # point_b

    def test_non_dominated_points_are_optimal(self) -> None:
        """Points not dominated by any other are Pareto-optimal."""
        # Point A: cost=50, time=10 (cheaper but slower)
        # Point B: cost=100, time=5 (faster but more expensive)
        # Neither dominates the other
        point_a = create_point("job1", ProcessingLocation.ON_PREMISES, 50.0, 10.0)
        point_b = create_point("job1", ProcessingLocation.CLOUD_AWS, 100.0, 5.0)

        result = compute_pareto_frontier([point_a, point_b])

        assert result[0].is_pareto_optimal is True
        assert result[1].is_pareto_optimal is True

    def test_scores_are_normalized(self) -> None:
        """Scores should be normalized between 0 and 1."""
        points = [
            create_point("job1", ProcessingLocation.ON_PREMISES, 0.0, 10.0),
            create_point("job1", ProcessingLocation.CLOUD_AWS, 100.0, 5.0),
        ]

        result = compute_pareto_frontier(points)

        for point in result:
            assert 0.0 <= point.cost_score <= 1.0
            assert 0.0 <= point.time_score <= 1.0


class TestFindOptimalConfiguration:
    """Tests for find_optimal_configuration function."""

    def test_empty_list_returns_none(self) -> None:
        """Empty list returns None."""
        result = find_optimal_configuration([])
        assert result is None

    def test_respects_cost_constraint(self) -> None:
        """Configuration over budget is excluded."""
        points = [
            create_point("job1", ProcessingLocation.ON_PREMISES, 50.0, 10.0),
            create_point("job1", ProcessingLocation.CLOUD_AWS, 150.0, 5.0),
        ]
        compute_pareto_frontier(points)

        result = find_optimal_configuration(points, max_cost=100.0)

        assert result is not None
        assert result.total_cost <= 100.0

    def test_respects_time_constraint(self) -> None:
        """Configuration over time limit is excluded."""
        points = [
            create_point("job1", ProcessingLocation.ON_PREMISES, 50.0, 10.0),
            create_point("job1", ProcessingLocation.CLOUD_AWS, 150.0, 5.0),
        ]
        compute_pareto_frontier(points)

        result = find_optimal_configuration(points, max_time=6.0)

        assert result is not None
        assert result.total_hours <= 6.0

    def test_no_valid_configuration_returns_none(self) -> None:
        """Returns None if no configuration meets constraints."""
        points = [
            create_point("job1", ProcessingLocation.ON_PREMISES, 100.0, 10.0),
        ]
        compute_pareto_frontier(points)

        result = find_optimal_configuration(points, max_cost=50.0, max_time=5.0)

        assert result is None


class TestCalculateParetoFrontierLine:
    """Tests for calculate_pareto_frontier_line function."""

    def test_returns_only_optimal_points(self) -> None:
        """Only Pareto-optimal points are included."""
        points = [
            create_point("job1", ProcessingLocation.ON_PREMISES, 50.0, 10.0),
            create_point("job1", ProcessingLocation.CLOUD_AWS, 100.0, 5.0),
            create_point("job1", ProcessingLocation.HYBRID, 200.0, 15.0),  # dominated
        ]
        compute_pareto_frontier(points)

        line = calculate_pareto_frontier_line(points)

        # Only 2 points should be in the frontier
        assert len(line) == 2

    def test_sorted_by_cost(self) -> None:
        """Points are sorted by cost (ascending)."""
        points = [
            create_point("job1", ProcessingLocation.CLOUD_AWS, 100.0, 5.0),
            create_point("job1", ProcessingLocation.ON_PREMISES, 50.0, 10.0),
        ]
        compute_pareto_frontier(points)

        line = calculate_pareto_frontier_line(points)

        # Should be sorted: (50, 10), (100, 5)
        assert line[0][0] < line[1][0]
