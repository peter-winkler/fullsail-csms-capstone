"""Mock data generators for realistic KinaTrax processing scenarios."""

import random
from datetime import datetime, timedelta
from typing import List, Optional

from faker import Faker

from .schemas import (
    C3DVerificationResult,
    CostTimeEstimate,
    JobPriority,
    JobStatus,
    ParetoPoint,
    ProcessingJob,
    ProcessingLocation,
)

fake = Faker()

# Real MLB team names for realistic data
MLB_TEAMS = [
    "New York Yankees",
    "Boston Red Sox",
    "Los Angeles Dodgers",
    "Chicago Cubs",
    "San Francisco Giants",
    "St. Louis Cardinals",
    "Houston Astros",
    "Atlanta Braves",
    "Philadelphia Phillies",
    "New York Mets",
    "Seattle Mariners",
    "San Diego Padres",
    "Texas Rangers",
    "Arizona Diamondbacks",
    "Cleveland Guardians",
]

MLB_VENUES = [
    "Yankee Stadium",
    "Fenway Park",
    "Dodger Stadium",
    "Wrigley Field",
    "Oracle Park",
    "Busch Stadium",
    "Minute Maid Park",
    "Truist Park",
    "Citizens Bank Park",
    "Citi Field",
    "T-Mobile Park",
    "Petco Park",
    "Globe Life Field",
    "Chase Field",
    "Progressive Field",
]


def generate_processing_job(
    game_date: Optional[datetime] = None,
    status: Optional[JobStatus] = None,
    priority: Optional[JobPriority] = None,
) -> ProcessingJob:
    """Generate a realistic processing job."""
    if game_date is None:
        game_date = fake.date_time_between(start_date="-7d", end_date="now")

    team_idx = random.randint(0, len(MLB_TEAMS) - 1)

    queued_at = game_date + timedelta(hours=random.randint(1, 4))
    job_status = status or random.choice(list(JobStatus))

    started_at = None
    completed_at = None

    if job_status in [JobStatus.PROCESSING, JobStatus.COMPLETED]:
        started_at = queued_at + timedelta(minutes=random.randint(5, 60))

    if job_status == JobStatus.COMPLETED:
        completed_at = started_at + timedelta(hours=random.uniform(2, 8))

    return ProcessingJob(
        game_id=f"gid_{game_date.strftime('%Y_%m_%d')}_{random.randint(1, 3):02d}",
        team_name=MLB_TEAMS[team_idx],
        venue=MLB_VENUES[team_idx],
        game_date=game_date,
        pitcher_count=random.randint(3, 12),
        total_pitches=random.randint(80, 250),
        camera_count=random.choice([8, 10, 12]),
        fps=300,
        status=job_status,
        priority=priority or random.choice(list(JobPriority)),
        queued_at=queued_at,
        started_at=started_at,
        completed_at=completed_at,
    )


def generate_cost_time_estimate(
    job: ProcessingJob,
    location: ProcessingLocation,
) -> CostTimeEstimate:
    """Generate realistic cost/time estimates based on location."""
    # Base processing time: roughly 6-8 hours for on-prem per game
    base_hours = (job.total_pitches / 150) * 6.5

    # Adjust based on location
    if location == ProcessingLocation.ON_PREMISES:
        processing_hours = base_hours * random.uniform(0.95, 1.05)
        queue_wait = random.uniform(0.5, 4.0)  # Variable queue
        compute_cost = 0.0  # Already paid for
        storage_cost = 0.02 * job.total_pitches
        network_cost = 0.0
    elif location == ProcessingLocation.CLOUD_AWS:
        processing_hours = base_hours * random.uniform(0.4, 0.6)  # ~2x faster
        queue_wait = random.uniform(0.1, 0.5)  # Minimal queue
        compute_cost = processing_hours * 8.50  # GPU instance $/hr
        storage_cost = 0.023 * job.total_pitches
        network_cost = 0.09 * (job.total_pitches * 0.5)  # Egress
    elif location == ProcessingLocation.CLOUD_GCP:
        processing_hours = base_hours * random.uniform(0.45, 0.65)
        queue_wait = random.uniform(0.1, 0.6)
        compute_cost = processing_hours * 7.80
        storage_cost = 0.020 * job.total_pitches
        network_cost = 0.08 * (job.total_pitches * 0.5)
    else:  # HYBRID
        processing_hours = base_hours * random.uniform(0.6, 0.8)
        queue_wait = random.uniform(0.2, 1.5)
        compute_cost = processing_hours * 4.25
        storage_cost = 0.015 * job.total_pitches
        network_cost = 0.05 * (job.total_pitches * 0.3)

    total_hours = processing_hours + queue_wait
    total_cost = compute_cost + storage_cost + network_cost

    return CostTimeEstimate(
        job_id=job.job_id,
        location=location,
        estimated_processing_hours=round(processing_hours, 2),
        estimated_queue_wait_hours=round(queue_wait, 2),
        total_estimated_hours=round(total_hours, 2),
        compute_cost=round(compute_cost, 2),
        storage_cost=round(storage_cost, 2),
        network_egress_cost=round(network_cost, 2),
        total_cost=round(total_cost, 2),
        gpu_utilization_percent=round(random.uniform(75, 98), 1),
        cpu_utilization_percent=round(random.uniform(60, 95), 1),
        memory_utilization_percent=round(random.uniform(50, 85), 1),
    )


def generate_event_queue(queue_size: int = 15) -> List[ProcessingJob]:
    """Generate a realistic processing queue."""
    jobs = []

    # Mix of statuses
    processing_count = min(3, queue_size // 5)
    completed_count = min(2, queue_size // 7)
    queued_count = queue_size - processing_count - completed_count

    for _ in range(processing_count):
        jobs.append(generate_processing_job(status=JobStatus.PROCESSING))

    for _ in range(queued_count):
        jobs.append(generate_processing_job(status=JobStatus.QUEUED))

    for _ in range(completed_count):
        jobs.append(generate_processing_job(status=JobStatus.COMPLETED))

    return sorted(jobs, key=lambda j: j.queued_at)


def generate_pareto_frontier_data(jobs: List[ProcessingJob]) -> List[ParetoPoint]:
    """Generate Pareto frontier points for cost vs time optimization."""
    points = []

    for job in jobs:
        for location in ProcessingLocation:
            estimate = generate_cost_time_estimate(job, location)
            points.append(
                ParetoPoint(
                    job_id=job.job_id,
                    configuration_id=f"{job.job_id}_{location.value}",
                    location=location,
                    total_hours=estimate.total_estimated_hours,
                    total_cost=estimate.total_cost,
                    is_pareto_optimal=False,
                    time_score=0.0,
                    cost_score=0.0,
                )
            )

    return points


def generate_c3d_verification(job_id: str) -> C3DVerificationResult:
    """Generate C3D output verification result (always matching for demo)."""
    common_hash = fake.sha256()

    return C3DVerificationResult(
        job_id=job_id,
        on_premises_hash=common_hash,
        cloud_hash=common_hash,
        hashes_match=True,
        marker_count_match=True,
        frame_count_match=True,
        trajectory_rmse=round(random.uniform(0.001, 0.05), 4),  # Very small
        is_within_tolerance=True,
    )
