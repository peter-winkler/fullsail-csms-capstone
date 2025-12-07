"""Pareto frontier optimization for cost vs. time trade-offs.

The Pareto frontier represents the set of configurations where no other
configuration is better in BOTH cost AND time. These are the "optimal"
trade-off points that decision makers should consider.
"""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Optional, Tuple

import numpy as np

from data.schemas import ParetoPoint


def compute_pareto_frontier(points: List[ParetoPoint]) -> List[ParetoPoint]:
    """
    Identify Pareto-optimal points in the cost-time trade-off space.

    A point is Pareto-optimal if no other point is better in both
    cost AND time. This is a classic multi-objective optimization problem.

    Algorithm: Simple pairwise dominance check O(n^2)
    For production with larger datasets, consider NSGA-II or scipy.optimize.

    Args:
        points: List of ParetoPoint configurations to evaluate

    Returns:
        The same list with is_pareto_optimal and scores updated
    """
    if not points:
        return []

    # Extract cost and time arrays
    costs = np.array([p.total_cost for p in points])
    times = np.array([p.total_hours for p in points])

    n = len(points)
    is_pareto = np.ones(n, dtype=bool)

    for i in range(n):
        if not is_pareto[i]:
            continue
        for j in range(n):
            if i == j:
                continue
            # Check if j dominates i (j is better in both dimensions)
            if costs[j] <= costs[i] and times[j] <= times[i]:
                if costs[j] < costs[i] or times[j] < times[i]:
                    is_pareto[i] = False
                    break

    # Mark Pareto-optimal points
    for i, point in enumerate(points):
        point.is_pareto_optimal = bool(is_pareto[i])

    # Calculate normalized scores (0-1, higher is better)
    cost_min, cost_max = float(costs.min()), float(costs.max())
    time_min, time_max = float(times.min()), float(times.max())

    for i, point in enumerate(points):
        # Invert: lower is better, so (max - val) / range = higher score
        if cost_max > cost_min:
            point.cost_score = (cost_max - costs[i]) / (cost_max - cost_min)
        else:
            point.cost_score = 1.0

        if time_max > time_min:
            point.time_score = (time_max - times[i]) / (time_max - time_min)
        else:
            point.time_score = 1.0

    return points


def find_optimal_configuration(
    points: List[ParetoPoint],
    cost_weight: float = 0.5,
    time_weight: float = 0.5,
    max_cost: Optional[float] = None,
    max_time: Optional[float] = None,
) -> Optional[ParetoPoint]:
    """
    Find the best configuration given user preferences.

    Uses weighted scoring to balance cost and time preferences,
    with optional hard constraints on maximum acceptable values.

    Args:
        points: List of possible configurations (should be Pareto-computed)
        cost_weight: How much to weight cost savings (0-1)
        time_weight: How much to weight time savings (0-1)
        max_cost: Optional budget constraint (USD)
        max_time: Optional deadline constraint (hours)

    Returns:
        The optimal ParetoPoint based on weighted scoring, or None if
        no configuration meets the constraints
    """
    if not points:
        return None

    # Normalize weights
    total_weight = cost_weight + time_weight
    if total_weight == 0:
        cost_weight = 0.5
        time_weight = 0.5
    else:
        cost_weight = cost_weight / total_weight
        time_weight = time_weight / total_weight

    # Filter by constraints
    candidates = points.copy()
    if max_cost is not None:
        candidates = [p for p in candidates if p.total_cost <= max_cost]
    if max_time is not None:
        candidates = [p for p in candidates if p.total_hours <= max_time]

    if not candidates:
        return None

    # Calculate weighted score for each candidate
    best: Optional[ParetoPoint] = None
    best_score = -1.0

    for point in candidates:
        score = (cost_weight * point.cost_score) + (time_weight * point.time_score)
        if score > best_score:
            best_score = score
            best = point

    return best


def calculate_pareto_frontier_line(
    points: List[ParetoPoint],
) -> List[Tuple[float, float]]:
    """
    Return the points that form the Pareto frontier line for plotting.

    Args:
        points: List of ParetoPoints with is_pareto_optimal computed

    Returns:
        List of (cost, time) tuples sorted by cost (low to high)
    """
    pareto_points = [p for p in points if p.is_pareto_optimal]
    sorted_points = sorted(pareto_points, key=lambda p: p.total_cost)
    return [(p.total_cost, p.total_hours) for p in sorted_points]
