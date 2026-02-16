"""Data models for cloud acceleration cost-benefit analysis."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class InstanceType(BaseModel):
    """AWS GPU instance type with pricing across all tiers.

    RI rates are Optional — some instances (e.g. p3.2xlarge) don't offer
    reserved pricing. Use available_pricing() to get the list of valid
    tiers, and rate_for_pricing() returns None for unavailable tiers.
    """

    name: str           # "g4dn.xlarge"
    gpu: str            # "Tesla T4"
    rate_ondemand: float
    rate_spot: float
    rate_1yr_ri: Optional[float] = None
    rate_3yr_ri: Optional[float] = None
    ratio: float        # cloud/on-prem processing time ratio
    has_real_data: bool = False

    def rate_for_pricing(self, pricing: str) -> Optional[float]:
        rates: Dict[str, Optional[float]] = {
            "ondemand": self.rate_ondemand,
            "spot": self.rate_spot,
            "1yr_ri": self.rate_1yr_ri,
            "3yr_ri": self.rate_3yr_ri,
        }
        return rates[pricing]

    def available_pricing(self) -> List[str]:
        """Return list of pricing tiers that are available for this instance."""
        tiers = ["ondemand", "spot"]
        if self.rate_1yr_ri is not None:
            tiers.append("1yr_ri")
        if self.rate_3yr_ri is not None:
            tiers.append("3yr_ri")
        return tiers


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
    """Parameterized cloud pricing model. All cloud cost assumptions in one place.

    Supports two modes:
    - Fixed timing (legacy): cloud_time_per_event_sec is used directly
    - Ratio-based timing: cloud time = ratio * on_prem_time per event
    When ratio is set, it takes precedence over cloud_time_per_event_sec.
    """

    instance_type: str = "g4dn.xlarge"
    cost_per_hour: float = 0.526  # AWS on-demand
    spot_cost_per_hour: Optional[float] = 0.16  # AWS spot estimate (~70% discount)
    use_spot: bool = False
    cloud_time_per_event_sec: float = 1378.0  # 23 min avg from 15-event T4 pilot
    container_startup_sec: float = 30.0
    data_transfer_sec_per_event: float = 0.0
    data_transfer_cost_per_event: float = 0.02  # S3 pricing estimate
    ratio: Optional[float] = None  # cloud/on-prem time ratio (e.g. 2.18 for T4)
    pricing_tier: Optional[str] = None  # "ondemand", "spot", "1yr_ri", "3yr_ri"

    @property
    def effective_cost_per_hour(self) -> float:
        """Active hourly rate based on pricing selection."""
        if self.use_spot and self.spot_cost_per_hour is not None:
            return self.spot_cost_per_hour
        return self.cost_per_hour

    def event_cloud_time_for(self, on_prem_time_sec: float) -> float:
        """Cloud wall-clock time for one event, accounting for ratio if set.

        Note: container startup is handled once per container in the scheduler
        heap initialization, NOT per-event here.
        """
        if self.ratio is not None:
            processing = self.ratio * on_prem_time_sec
        else:
            processing = self.cloud_time_per_event_sec
        return processing + self.data_transfer_sec_per_event

    def event_cloud_cost_for(self, on_prem_time_sec: float) -> float:
        """Cloud cost for one event, using ratio-based or fixed timing.

        Container startup cost is amortized across all events on that container,
        not charged per-event. The scheduler handles startup time separately.
        """
        if self.ratio is not None:
            processing = self.ratio * on_prem_time_sec
        else:
            processing = self.cloud_time_per_event_sec
        compute_hours = processing / 3600.0
        return compute_hours * self.effective_cost_per_hour + self.data_transfer_cost_per_event

    def event_cloud_cost(self) -> float:
        """Total cloud cost for one event (compute + transfer). Legacy fixed-time mode."""
        compute_sec = self.cloud_time_per_event_sec + self.container_startup_sec
        compute_hours = compute_sec / 3600.0
        return compute_hours * self.effective_cost_per_hour + self.data_transfer_cost_per_event

    def event_cloud_time(self) -> float:
        """Total wall-clock time for one cloud event. Legacy fixed-time mode."""
        return (
            self.cloud_time_per_event_sec
            + self.container_startup_sec
            + self.data_transfer_sec_per_event
        )

    @classmethod
    def from_instance(cls, instance: "InstanceType", pricing: str, **kwargs) -> "CloudCostModel":
        """Build a CloudCostModel from an InstanceType and pricing tier.

        Raises ValueError if the pricing tier is not available for this instance.
        """
        rate = instance.rate_for_pricing(pricing)
        if rate is None:
            raise ValueError(
                f"{pricing} pricing not available for {instance.name} ({instance.gpu})"
            )
        return cls(
            instance_type=instance.name,
            cost_per_hour=rate,
            use_spot=False,  # rate already selected
            ratio=instance.ratio,
            pricing_tier=pricing,
            **kwargs,
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
    cloud_containers: int = 0
    is_pareto_optimal: bool = False
    instance_type: Optional[str] = None   # "g4dn.xlarge"
    pricing_tier: Optional[str] = None    # "spot"

    class Config:
        frozen = True
