"""Data models and generators for the dashboard."""

from .generators import (
    generate_c3d_verification,
    generate_cost_time_estimate,
    generate_event_queue,
    generate_pareto_frontier_data,
    generate_processing_job,
)
from .schemas import (
    C3DVerificationResult,
    CostTimeEstimate,
    JobPriority,
    JobStatus,
    ParetoPoint,
    ProcessingJob,
    ProcessingLocation,
    ScenarioResult,
)

__all__ = [
    # Schemas
    "ProcessingLocation",
    "JobPriority",
    "JobStatus",
    "ProcessingJob",
    "CostTimeEstimate",
    "ParetoPoint",
    "ScenarioResult",
    "C3DVerificationResult",
    # Generators
    "generate_processing_job",
    "generate_cost_time_estimate",
    "generate_event_queue",
    "generate_pareto_frontier_data",
    "generate_c3d_verification",
]
