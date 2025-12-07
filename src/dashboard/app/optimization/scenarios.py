"""Scenario calculation for comparing processing strategies."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List

from data.generators import generate_cost_time_estimate
from data.schemas import (
    JobPriority,
    ProcessingJob,
    ProcessingLocation,
    ScenarioResult,
)


def calculate_scenario(
    jobs: List[ProcessingJob],
    location_strategy: str,
) -> ScenarioResult:
    """
    Calculate aggregate metrics for a given processing strategy.

    Args:
        jobs: List of processing jobs to evaluate
        location_strategy: One of "on_premises", "cloud", or "optimized"

    Returns:
        ScenarioResult with aggregate cost/time metrics
    """
    if not jobs:
        return ScenarioResult(
            scenario_name="Empty",
            description="No jobs to process",
            total_jobs=0,
            total_cost=0.0,
            total_hours=0.0,
            average_cost_per_job=0.0,
            average_hours_per_job=0.0,
            jobs_on_premises=0,
            jobs_cloud=0,
            c3d_outputs_match=True,
        )

    total_cost = 0.0
    total_hours = 0.0
    jobs_on_prem = 0
    jobs_cloud = 0

    for job in jobs:
        if location_strategy == "on_premises":
            location = ProcessingLocation.ON_PREMISES
            jobs_on_prem += 1
        elif location_strategy == "cloud":
            location = ProcessingLocation.CLOUD_AWS
            jobs_cloud += 1
        else:  # optimized - use hybrid based on urgency
            if job.priority in [JobPriority.HIGH, JobPriority.CRITICAL]:
                location = ProcessingLocation.CLOUD_AWS
                jobs_cloud += 1
            else:
                location = ProcessingLocation.ON_PREMISES
                jobs_on_prem += 1

        estimate = generate_cost_time_estimate(job, location)
        total_cost += estimate.total_cost
        total_hours += estimate.total_estimated_hours

    scenario_names = {
        "on_premises": "All On-Premises",
        "cloud": "All Cloud (AWS)",
        "optimized": "Optimized Hybrid",
    }

    descriptions = {
        "on_premises": (
            "Process all jobs on existing stadium servers. "
            "Best cost efficiency, longest processing time."
        ),
        "cloud": (
            "Process all jobs on AWS cloud GPUs. "
            "Fastest processing, highest cost."
        ),
        "optimized": (
            "Route high-priority jobs to cloud, normal priority on-prem. "
            "Balanced cost and time trade-off."
        ),
    }

    return ScenarioResult(
        scenario_name=scenario_names.get(location_strategy, "Unknown"),
        description=descriptions.get(location_strategy, ""),
        total_jobs=len(jobs),
        total_cost=round(total_cost, 2),
        total_hours=round(total_hours, 2),
        average_cost_per_job=round(total_cost / len(jobs), 2),
        average_hours_per_job=round(total_hours / len(jobs), 2),
        jobs_on_premises=jobs_on_prem,
        jobs_cloud=jobs_cloud,
        c3d_outputs_match=True,  # Always match for demo
    )


def calculate_all_scenarios(
    jobs: List[ProcessingJob],
) -> dict[str, ScenarioResult]:
    """
    Calculate all three scenarios for comparison.

    Args:
        jobs: List of processing jobs to evaluate

    Returns:
        Dict mapping strategy name to ScenarioResult
    """
    return {
        "on_premises": calculate_scenario(jobs, "on_premises"),
        "cloud": calculate_scenario(jobs, "cloud"),
        "optimized": calculate_scenario(jobs, "optimized"),
    }
