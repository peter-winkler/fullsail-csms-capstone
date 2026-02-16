"""Pareto frontier optimization algorithms."""

from typing import List, Optional, Tuple

import numpy as np

from data.schemas import CloudCostModel, Event, InstanceType, ParetoPoint, SiteProfile
from simulation.scheduler import schedule_lpt


def is_dominated(point: Tuple[float, float], other: Tuple[float, float]) -> bool:
    """Check if 'point' is dominated by 'other'.

    A point is dominated if another point is better or equal in all objectives
    and strictly better in at least one objective.

    For minimization of both cost and time:
    - point is dominated by other if:
      other.cost <= point.cost AND other.time <= point.time
      AND (other.cost < point.cost OR other.time < point.time)
    """
    cost_better_or_equal = other[0] <= point[0]
    time_better_or_equal = other[1] <= point[1]
    strictly_better = other[0] < point[0] or other[1] < point[1]

    return cost_better_or_equal and time_better_or_equal and strictly_better


def compute_pareto_frontier(
    points: List[Tuple[str, float, float]]
) -> List[ParetoPoint]:
    """Compute the Pareto frontier from a list of (config_id, cost, time) tuples.

    Algorithm complexity: O(n^2) where n is the number of points.

    Args:
        points: List of (config_id, cost, time) tuples

    Returns:
        List of ParetoPoint objects with is_pareto_optimal flag set
    """
    n = len(points)
    pareto_optimal = [True] * n

    for i in range(n):
        if not pareto_optimal[i]:
            continue

        for j in range(n):
            if i == j:
                continue

            point_i = (points[i][1], points[i][2])  # (cost, time)
            point_j = (points[j][1], points[j][2])

            if is_dominated(point_i, point_j):
                pareto_optimal[i] = False
                break

    result = []
    for i, pt in enumerate(points):
        config_id, cost, time = pt[0], pt[1], pt[2]
        cc = pt[3] if len(pt) > 3 else 0
        result.append(ParetoPoint(
            config_id=config_id,
            cost=cost,
            time=time,
            cloud_containers=cc,
            is_pareto_optimal=pareto_optimal[i]
        ))

    return result


def compute_pareto_frontier_numpy(
    costs: np.ndarray,
    times: np.ndarray,
    config_ids: List[str]
) -> List[ParetoPoint]:
    """Vectorized Pareto frontier computation using NumPy.

    More efficient for large datasets.

    Args:
        costs: Array of cost values
        times: Array of time values
        config_ids: List of configuration IDs

    Returns:
        List of ParetoPoint objects
    """
    n = len(costs)
    pareto_optimal = np.ones(n, dtype=bool)

    for i in range(n):
        if not pareto_optimal[i]:
            continue

        cost_better = costs <= costs[i]
        time_better = times <= times[i]
        strictly_better = (costs < costs[i]) | (times < times[i])

        dominates = cost_better & time_better & strictly_better
        dominates[i] = False

        if np.any(dominates):
            pareto_optimal[i] = False

    result = []
    for i in range(n):
        result.append(ParetoPoint(
            config_id=config_ids[i],
            cost=float(costs[i]),
            time=float(times[i]),
            is_pareto_optimal=bool(pareto_optimal[i])
        ))

    return result


def calculate_weighted_score(
    cost: float,
    time: float,
    cost_weight: float,
    cost_range: Tuple[float, float],
    time_range: Tuple[float, float]
) -> float:
    """Calculate weighted score for a configuration.

    Normalizes cost and time to [0, 1] range and computes weighted sum.
    Lower score is better.
    """
    time_weight = 1.0 - cost_weight

    cost_norm = (cost - cost_range[0]) / (cost_range[1] - cost_range[0] + 1e-10)
    time_norm = (time - time_range[0]) / (time_range[1] - time_range[0] + 1e-10)

    return cost_weight * cost_norm + time_weight * time_norm


def find_optimal_configuration(
    pareto_points: List[ParetoPoint],
    cost_weight: float = 0.5
) -> ParetoPoint:
    """Find the optimal configuration from Pareto-optimal points based on weights.

    Args:
        pareto_points: List of Pareto points (should be filtered to optimal only)
        cost_weight: Weight for cost optimization (0 = prioritize time, 1 = prioritize cost)

    Returns:
        The optimal ParetoPoint based on weighted scoring
    """
    optimal_only = [p for p in pareto_points if p.is_pareto_optimal]

    if not optimal_only:
        return pareto_points[0] if pareto_points else None

    costs = [p.cost for p in optimal_only]
    times = [p.time for p in optimal_only]

    cost_range = (min(costs), max(costs))
    time_range = (min(times), max(times))

    best_point = None
    best_score = float('inf')

    for point in optimal_only:
        score = calculate_weighted_score(
            point.cost, point.time, cost_weight, cost_range, time_range
        )
        if score < best_score:
            best_score = score
            best_point = point

    return best_point


def generate_cloud_sweep(
    events: List[Event],
    site: SiteProfile,
    cloud_model: CloudCostModel,
    max_cloud_containers: int = 50,
    step: int = 1,
) -> List[Tuple[str, float, float]]:
    """Sweep cloud container count from 0 to max, generating (config_id, cost, time) tuples.

    Each point runs the LPT scheduler with a fixed number of on-prem GPUs
    (from the site profile) and a varying number of cloud containers.

    C=0: pure on-prem baseline ($0 cloud cost, longest turnaround)
    C=max: maximum cloud acceleration (highest cost, shortest turnaround)

    Returns:
        List of (config_id, cloud_cost, turnaround_time_sec) tuples
        suitable for compute_pareto_frontier().
    """
    points: List[Tuple[str, float, float, int]] = []

    for c in range(0, max_cloud_containers + 1, step):
        result = schedule_lpt(events, site, c, cloud_model)
        points.append((result.config_id, result.cloud_cost, result.turnaround_time_sec, c))

    return points


def generate_multi_instance_sweep(
    events: List[Event],
    site: SiteProfile,
    instance_types: List[InstanceType],
    pricing_modes: List[str],
    max_cloud_containers: int = 50,
    step: int = 1,
) -> List[Tuple[str, float, float, str, str, int]]:
    """Sweep all instance types x available pricing modes x container counts.

    Skips pricing tiers that aren't available for a given instance
    (e.g. p3.2xlarge has no reserved instances).

    Returns:
        List of (config_id, cost, time, instance_name, pricing, cloud_containers) tuples.
    """
    points: List[Tuple[str, float, float, str, str, int]] = []

    for instance in instance_types:
        available = instance.available_pricing()
        for pricing in pricing_modes:
            if pricing not in available:
                continue
            cloud_model = CloudCostModel.from_instance(instance, pricing)
            for c in range(0, max_cloud_containers + 1, step):
                result = schedule_lpt(events, site, c, cloud_model)
                config_id = f"{instance.gpu}_{pricing}_C{c}"
                points.append((
                    config_id,
                    result.cloud_cost,
                    result.turnaround_time_sec,
                    instance.name,
                    pricing,
                    c,
                ))

    return points


def compute_pareto_frontier_multi(
    points: List[Tuple],
) -> List[ParetoPoint]:
    """Compute Pareto frontier preserving instance/pricing metadata.

    Args:
        points: List of (config_id, cost, time, instance_name, pricing[, cloud_containers]) tuples.

    Returns:
        List of ParetoPoint objects with instance_type and pricing_tier set.
    """
    n = len(points)
    if n == 0:
        return []

    costs = np.array([p[1] for p in points])
    times = np.array([p[2] for p in points])

    pareto_optimal = np.ones(n, dtype=bool)

    for i in range(n):
        if not pareto_optimal[i]:
            continue
        dominates = (costs <= costs[i]) & (times <= times[i]) & ((costs < costs[i]) | (times < times[i]))
        dominates[i] = False
        if np.any(dominates):
            pareto_optimal[i] = False

    result = []
    for i, pt in enumerate(points):
        config_id, cost, time, inst, pricing = pt[0], pt[1], pt[2], pt[3], pt[4]
        cc = pt[5] if len(pt) > 5 else 0
        result.append(ParetoPoint(
            config_id=config_id,
            cost=cost,
            time=time,
            cloud_containers=cc,
            is_pareto_optimal=bool(pareto_optimal[i]),
            instance_type=inst,
            pricing_tier=pricing,
        ))

    return result
