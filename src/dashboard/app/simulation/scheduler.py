"""Batch scheduling simulation using Longest Processing Time First (LPT).

LPT is a well-known 4/3-OPT approximation for makespan minimization
(Graham 1969). Events are sorted by descending processing time, then
greedily assigned to the least-loaded processor.

On-prem processors use real measured times from CSV. Cloud processors use
variable timing: ratio x on_prem_time when CloudCostModel.ratio is set,
or a fixed time for backward compatibility.
"""

import heapq
from typing import List, Optional

from data.schemas import BatchResult, CloudCostModel, Event, EventAssignment, SiteProfile


def schedule_lpt(
    events: List[Event],
    site: SiteProfile,
    cloud_containers: int,
    cloud_model: CloudCostModel,
    track_assignments: bool = False,
) -> BatchResult:
    """Schedule a batch of events across on-prem GPUs and cloud containers.

    Uses LPT (Longest Processing Time First) to minimize makespan.
    O(N log(G+C)) where N=events, G=on-prem GPUs, C=cloud containers.

    Cloud event timing uses ratio-based calculation when cloud_model.ratio
    is set (cloud_time = ratio * on_prem_time + startup + transfer),
    or falls back to fixed cloud_time_per_event_sec for backward
    compatibility.

    Args:
        events: List of events with real processing times.
        site: On-prem GPU configuration.
        cloud_containers: Number of cloud containers to use (0 = pure on-prem).
        cloud_model: Cloud pricing and timing parameters.
        track_assignments: If True, record per-event assignment detail.

    Returns:
        BatchResult with cost, turnaround time, and event allocation.
    """
    on_prem_gpus = site.available_gpus
    total_processors = on_prem_gpus + cloud_containers

    if total_processors == 0:
        raise ValueError("Must have at least one processor (on-prem GPU or cloud container)")

    # Sort events by processing time descending (LPT)
    sorted_events = sorted(events, key=lambda e: e.processing_time_sec, reverse=True)

    # Min-heap: (current_load_sec, processor_index, is_cloud)
    # Cloud processors start with container startup overhead
    heap: List[tuple] = []
    for i in range(on_prem_gpus):
        heapq.heappush(heap, (0.0, i, False))
    for i in range(cloud_containers):
        heapq.heappush(heap, (cloud_model.container_startup_sec, on_prem_gpus + i, True))

    cloud_event_count = 0
    on_prem_event_count = 0
    total_cloud_cost = 0.0
    assignments: Optional[List[EventAssignment]] = [] if track_assignments else None

    for event in sorted_events:
        load, proc_id, is_cloud = heapq.heappop(heap)

        if is_cloud:
            event_time = cloud_model.event_cloud_time_for(event.processing_time_sec)
            total_cloud_cost += cloud_model.event_cloud_cost_for(event.processing_time_sec)
            cloud_event_count += 1
        else:
            event_time = event.processing_time_sec
            on_prem_event_count += 1

        if assignments is not None:
            assignments.append(EventAssignment(
                event_name=event.event_name,
                event_type=event.event_type,
                processing_time_sec=event.processing_time_sec,
                fps=event.fps,
                assigned_to="cloud" if is_cloud else "on_prem",
                processor_id=proc_id,
                effective_time_sec=event_time,
            ))

        heapq.heappush(heap, (load + event_time, proc_id, is_cloud))

    # Extract final loads to compute makespan and per-type finish times
    on_prem_finish = 0.0
    cloud_finish = 0.0
    makespan = 0.0

    while heap:
        load, proc_id, is_cloud = heapq.heappop(heap)
        makespan = max(makespan, load)
        if is_cloud:
            cloud_finish = max(cloud_finish, load)
        else:
            on_prem_finish = max(on_prem_finish, load)

    config_id = f"G{on_prem_gpus}_C{cloud_containers}"

    return BatchResult(
        config_id=config_id,
        on_prem_gpus=on_prem_gpus,
        cloud_containers=cloud_containers,
        total_events=len(events),
        cloud_cost=total_cloud_cost,
        turnaround_time_sec=makespan,
        events_on_prem=on_prem_event_count,
        events_on_cloud=cloud_event_count,
        on_prem_finish_sec=on_prem_finish,
        cloud_finish_sec=cloud_finish,
        assignments=assignments,
    )
