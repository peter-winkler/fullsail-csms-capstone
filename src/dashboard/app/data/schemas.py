"""Pydantic models for dashboard data structures."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProcessingLocation(str, Enum):
    """Where processing can occur."""

    ON_PREMISES = "on_premises"
    CLOUD_AWS = "cloud_aws"
    CLOUD_GCP = "cloud_gcp"
    HYBRID = "hybrid"


class JobPriority(str, Enum):
    """Processing priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class JobStatus(str, Enum):
    """Job processing status."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJob(BaseModel):
    """Represents a single processing job in the queue."""

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    game_id: str
    team_name: str
    venue: str
    game_date: datetime
    pitcher_count: int = Field(ge=1, le=15)
    total_pitches: int = Field(ge=50, le=300)
    camera_count: int = Field(default=8, ge=6, le=16)
    fps: int = Field(default=300)

    # Processing metadata
    status: JobStatus = JobStatus.QUEUED
    priority: JobPriority = JobPriority.NORMAL
    queued_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Assignment
    assigned_location: Optional[ProcessingLocation] = None


class CostTimeEstimate(BaseModel):
    """Cost and time estimate for a processing configuration."""

    job_id: str
    location: ProcessingLocation

    # Time estimates (hours)
    estimated_processing_hours: float
    estimated_queue_wait_hours: float
    total_estimated_hours: float

    # Cost estimates (USD)
    compute_cost: float
    storage_cost: float
    network_egress_cost: float
    total_cost: float

    # Resource utilization
    gpu_utilization_percent: float
    cpu_utilization_percent: float
    memory_utilization_percent: float


class ParetoPoint(BaseModel):
    """A point on the Pareto frontier."""

    job_id: str
    configuration_id: str
    location: ProcessingLocation

    # The two optimization axes
    total_hours: float
    total_cost: float

    # Whether this point is on the Pareto frontier
    is_pareto_optimal: bool = False

    # Normalized scores (0-1 scale)
    time_score: float = 0.0  # 0 = slowest, 1 = fastest
    cost_score: float = 0.0  # 0 = most expensive, 1 = cheapest


class ScenarioResult(BaseModel):
    """Results for a specific processing scenario."""

    scenario_name: str
    description: str

    # Aggregate metrics
    total_jobs: int
    total_cost: float
    total_hours: float
    average_cost_per_job: float
    average_hours_per_job: float

    # Job distribution
    jobs_on_premises: int
    jobs_cloud: int

    # C3D output verification
    c3d_outputs_match: bool = True


class C3DVerificationResult(BaseModel):
    """Verification that C3D outputs match between systems."""

    job_id: str
    on_premises_hash: str
    cloud_hash: str
    hashes_match: bool

    # Detailed comparison
    marker_count_match: bool
    frame_count_match: bool
    trajectory_rmse: float  # Root mean square error in mm
    is_within_tolerance: bool  # < 0.1mm difference
