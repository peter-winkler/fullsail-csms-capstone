"""Data models for cloud acceleration cost-benefit analysis."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Event(BaseModel):
    """One processed event from on-prem results CSV."""

    event_name: str
    venue: str
    venue_type: str = "mlb"
    event_type: str  # Batting or Pitching
    gpu_model: str = "RTX_4000_Ada"
    processing_time_sec: float = Field(..., gt=0)
    exit_code: int = 0
    c3d_valid: bool = True
    c3d_size_bytes: int = 0
    timestamp: Optional[str] = None  # When this event was processed on-prem

    # Enrichment from event ledger join
    session: Optional[str] = None
    fps: Optional[float] = None  # 300 or 600 — affects processing complexity
    s3_path: Optional[str] = None


class EventAssignment(BaseModel):
    """Where a single event was assigned by the scheduler."""

    event_name: str
    event_type: str
    processing_time_sec: float  # On-prem measured time
    fps: Optional[float] = None
    assigned_to: str  # "on_prem" or "cloud"
    processor_id: int
    effective_time_sec: float  # Actual time used (on-prem real time or cloud fixed time)


class CloudCostModel(BaseModel):
    """Parameterized cloud pricing model. All cloud cost assumptions in one place."""

    instance_type: str = "g4dn.xlarge"
    cost_per_hour: float = 0.526  # AWS on-demand
    spot_cost_per_hour: Optional[float] = 0.16  # AWS spot estimate (~70% discount)
    use_spot: bool = False
    cloud_time_per_event_sec: float = 1378.0  # 23 min avg from 15-event T4 pilot (range 450-2784s)
    container_startup_sec: float = 30.0
    data_transfer_sec_per_event: float = 60.0
    data_transfer_cost_per_event: float = 0.02  # S3 pricing estimate

    @property
    def effective_cost_per_hour(self) -> float:
        """Active hourly rate based on on-demand vs spot selection."""
        if self.use_spot and self.spot_cost_per_hour is not None:
            return self.spot_cost_per_hour
        return self.cost_per_hour

    def event_cloud_cost(self) -> float:
        """Total cloud cost for one event (compute + transfer)."""
        compute_sec = self.cloud_time_per_event_sec + self.container_startup_sec
        compute_hours = compute_sec / 3600.0
        return compute_hours * self.effective_cost_per_hour + self.data_transfer_cost_per_event

    def event_cloud_time(self) -> float:
        """Total wall-clock time for one cloud event (processing + transfer)."""
        return (
            self.cloud_time_per_event_sec
            + self.container_startup_sec
            + self.data_transfer_sec_per_event
        )


class SiteProfile(BaseModel):
    """Stadium GPU configuration for simulation."""

    name: str
    venue_code: str
    available_gpus: int = Field(..., ge=0)
    tier: str  # "gpu_poor", "gpu_moderate", "gpu_rich"

    @classmethod
    def gpu_poor(cls, gpus: int = 5) -> "SiteProfile":
        return cls(name="GPU-Poor Site", venue_code="BOS", available_gpus=gpus, tier="gpu_poor")

    @classmethod
    def gpu_moderate(cls, gpus: int = 15) -> "SiteProfile":
        return cls(name="GPU-Moderate Site", venue_code="MIA", available_gpus=gpus, tier="gpu_moderate")

    @classmethod
    def gpu_rich(cls, gpus: int = 36) -> "SiteProfile":
        return cls(name="GPU-Rich Site", venue_code="SEA", available_gpus=gpus, tier="gpu_rich")


class BatchResult(BaseModel):
    """Output of one simulation run — one point in the sweep."""

    config_id: str  # e.g. "G5_C10"
    on_prem_gpus: int
    cloud_containers: int
    total_events: int
    cloud_cost: float  # X axis: additional $ beyond on-prem baseline
    turnaround_time_sec: float  # Y axis: batch wall-clock time (makespan)
    events_on_prem: int
    events_on_cloud: int
    on_prem_finish_sec: float
    cloud_finish_sec: float
    # Per-event assignment detail (populated when track_assignments=True)
    assignments: Optional[List[EventAssignment]] = None


class ParetoPoint(BaseModel):
    """A point on the Pareto frontier."""

    config_id: str
    cost: float
    time: float
    is_pareto_optimal: bool = False

    class Config:
        frozen = True
