"""Plotly chart builders for the cloud acceleration dashboard."""

from typing import Dict, List, Optional, Tuple

import plotly.graph_objects as go

from data.schemas import BatchResult, EventAssignment, ParetoPoint


TIER_COLORS = {
    "gpu_poor": "#e74c3c",
    "gpu_moderate": "#f39c12",
    "gpu_rich": "#2ecc71",
}


def create_pareto_chart(
    points: List[ParetoPoint],
    optimal: Optional[ParetoPoint] = None,
    title: str = "Cloud Acceleration: Cost vs. Turnaround Time",
) -> go.Figure:
    """Scatter plot with Pareto frontier line highlighted."""
    pareto = [p for p in points if p.is_pareto_optimal]
    non_pareto = [p for p in points if not p.is_pareto_optimal]

    fig = go.Figure()

    # Sub-optimal points
    if non_pareto:
        fig.add_trace(go.Scatter(
            x=[p.cost for p in non_pareto],
            y=[p.time / 3600 for p in non_pareto],
            mode="markers",
            name="Sub-optimal",
            marker=dict(size=7, opacity=0.35, color="gray"),
            hovertemplate=(
                "<b>%{customdata}</b><br>"
                "Cloud cost: $%{x:.2f}<br>"
                "Turnaround: %{y:.1f} hrs<extra></extra>"
            ),
            customdata=[p.config_id for p in non_pareto],
        ))

    # Pareto frontier line + points
    if pareto:
        pareto_sorted = sorted(pareto, key=lambda p: p.cost)

        fig.add_trace(go.Scatter(
            x=[p.cost for p in pareto_sorted],
            y=[p.time / 3600 for p in pareto_sorted],
            mode="lines",
            name="Pareto Frontier",
            line=dict(color="#3498db", width=2, dash="dash"),
            hoverinfo="skip",
        ))

        fig.add_trace(go.Scatter(
            x=[p.cost for p in pareto_sorted],
            y=[p.time / 3600 for p in pareto_sorted],
            mode="markers",
            name="Pareto-Optimal",
            marker=dict(size=10, color="#3498db", line=dict(width=1, color="white")),
            hovertemplate=(
                "<b>%{customdata}</b><br>"
                "Cloud cost: $%{x:.2f}<br>"
                "Turnaround: %{y:.1f} hrs<extra></extra>"
            ),
            customdata=[p.config_id for p in pareto_sorted],
        ))

    # Highlight recommended point
    if optimal:
        fig.add_trace(go.Scatter(
            x=[optimal.cost],
            y=[optimal.time / 3600],
            mode="markers",
            name="Recommended",
            marker=dict(size=16, color="#e74c3c", symbol="star", line=dict(width=2, color="white")),
            hovertemplate=(
                "<b>%{customdata} (Recommended)</b><br>"
                "Cloud cost: $%{x:.2f}<br>"
                "Turnaround: %{y:.1f} hrs<extra></extra>"
            ),
            customdata=[optimal.config_id],
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Additional Cloud Cost ($)",
        yaxis_title="Batch Turnaround Time (hours)",
        hovermode="closest",
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
        template="plotly_white",
    )

    return fig


def create_multi_site_chart(
    site_frontiers: Dict[str, Tuple[List[ParetoPoint], str]],
) -> go.Figure:
    """Overlay Pareto frontiers for multiple site profiles.

    Args:
        site_frontiers: {label: (points, tier)} where tier is used for color.
    """
    fig = go.Figure()

    for label, (points, tier) in site_frontiers.items():
        optimal = [p for p in points if p.is_pareto_optimal]
        if not optimal:
            continue
        optimal_sorted = sorted(optimal, key=lambda p: p.cost)
        color = TIER_COLORS.get(tier, "#3498db")

        fig.add_trace(go.Scatter(
            x=[p.cost for p in optimal_sorted],
            y=[p.time / 3600 for p in optimal_sorted],
            mode="lines+markers",
            name=label,
            line=dict(color=color, width=2),
            marker=dict(size=6, color=color),
            hovertemplate=(
                f"<b>{label}</b><br>"
                "%{customdata}<br>"
                "Cloud cost: $%{x:.2f}<br>"
                "Turnaround: %{y:.1f} hrs<extra></extra>"
            ),
            customdata=[p.config_id for p in optimal_sorted],
        ))

    fig.update_layout(
        title="Pareto Frontiers by Site GPU Configuration",
        xaxis_title="Additional Cloud Cost ($)",
        yaxis_title="Batch Turnaround Time (hours)",
        hovermode="closest",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        template="plotly_white",
    )

    return fig


def create_assignment_bar(result: BatchResult) -> go.Figure:
    """Stacked bar showing processor load balance from a single batch result."""
    if not result.assignments:
        fig = go.Figure()
        fig.add_annotation(text="No assignment data (run with track_assignments=True)",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    # Group load by processor
    proc_loads: Dict[int, float] = {}
    proc_type: Dict[int, str] = {}
    for a in result.assignments:
        proc_loads[a.processor_id] = proc_loads.get(a.processor_id, 0) + a.effective_time_sec
        proc_type[a.processor_id] = a.assigned_to

    # Separate on-prem and cloud
    on_prem_ids = sorted(pid for pid, t in proc_type.items() if t == "on_prem")
    cloud_ids = sorted(pid for pid, t in proc_type.items() if t == "cloud")

    labels = [f"GPU {i}" for i in range(len(on_prem_ids))] + [f"Cloud {i}" for i in range(len(cloud_ids))]
    values = [proc_loads[pid] / 3600 for pid in on_prem_ids] + [proc_loads[pid] / 3600 for pid in cloud_ids]
    colors = ["#2ecc71"] * len(on_prem_ids) + ["#3498db"] * len(cloud_ids)

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color=colors,
        hovertemplate="<b>%{x}</b><br>Load: %{y:.1f} hrs<extra></extra>",
    ))

    fig.update_layout(
        title=f"Processor Load Balance ({result.config_id})",
        xaxis_title="Processor",
        yaxis_title="Total Load (hours)",
        template="plotly_white",
    )

    return fig


def create_event_type_breakdown(assignments: List[EventAssignment]) -> go.Figure:
    """Show how event types (Batting/Pitching) are distributed across on-prem vs cloud."""
    categories = {}
    for a in assignments:
        key = (a.assigned_to, a.event_type)
        categories[key] = categories.get(key, 0) + 1

    on_prem_batting = categories.get(("on_prem", "Batting"), 0)
    on_prem_pitching = categories.get(("on_prem", "Pitching"), 0)
    cloud_batting = categories.get(("cloud", "Batting"), 0)
    cloud_pitching = categories.get(("cloud", "Pitching"), 0)

    fig = go.Figure(data=[
        go.Bar(name="Batting", x=["On-Prem", "Cloud"],
               y=[on_prem_batting, cloud_batting], marker_color="#2ecc71"),
        go.Bar(name="Pitching", x=["On-Prem", "Cloud"],
               y=[on_prem_pitching, cloud_pitching], marker_color="#3498db"),
    ])

    fig.update_layout(
        title="Event Type Distribution by Location",
        barmode="stack",
        xaxis_title="Processing Location",
        yaxis_title="Event Count",
        template="plotly_white",
    )

    return fig


def create_processing_time_histogram(assignments: List[EventAssignment]) -> go.Figure:
    """Histogram of on-prem measured processing times, colored by assignment."""
    on_prem = [a.processing_time_sec / 60 for a in assignments if a.assigned_to == "on_prem"]
    cloud = [a.processing_time_sec / 60 for a in assignments if a.assigned_to == "cloud"]

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=on_prem, name="Assigned On-Prem", marker_color="#2ecc71", opacity=0.7, nbinsx=25))
    fig.add_trace(go.Histogram(
        x=cloud, name="Assigned to Cloud", marker_color="#3498db", opacity=0.7, nbinsx=25))

    fig.update_layout(
        title="Processing Time Distribution by Assignment",
        xaxis_title="On-Prem Measured Time (minutes)",
        yaxis_title="Event Count",
        barmode="overlay",
        template="plotly_white",
    )

    return fig


def create_sensitivity_chart(
    frontiers: Dict[str, List[ParetoPoint]],
    param_name: str = "Parameter",
) -> go.Figure:
    """Overlay Pareto frontiers for different parameter values."""
    fig = go.Figure()

    colors = ["#e74c3c", "#f39c12", "#3498db", "#2ecc71", "#9b59b6", "#1abc9c"]

    for i, (label, points) in enumerate(frontiers.items()):
        optimal = sorted([p for p in points if p.is_pareto_optimal], key=lambda p: p.cost)
        if not optimal:
            continue
        color = colors[i % len(colors)]

        fig.add_trace(go.Scatter(
            x=[p.cost for p in optimal],
            y=[p.time / 3600 for p in optimal],
            mode="lines+markers",
            name=label,
            line=dict(color=color, width=2),
            marker=dict(size=5, color=color),
        ))

    fig.update_layout(
        title=f"Sensitivity Analysis: {param_name}",
        xaxis_title="Additional Cloud Cost ($)",
        yaxis_title="Batch Turnaround Time (hours)",
        hovermode="closest",
        template="plotly_white",
    )

    return fig
