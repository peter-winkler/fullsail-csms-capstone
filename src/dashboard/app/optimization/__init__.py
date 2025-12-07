"""Optimization algorithms for cost/time trade-off analysis."""

from .pareto import (
    calculate_pareto_frontier_line,
    compute_pareto_frontier,
    find_optimal_configuration,
)
from .scenarios import calculate_all_scenarios, calculate_scenario

__all__ = [
    "compute_pareto_frontier",
    "find_optimal_configuration",
    "calculate_pareto_frontier_line",
    "calculate_scenario",
    "calculate_all_scenarios",
]
