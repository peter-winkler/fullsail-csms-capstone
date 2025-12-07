"""Plotly chart builders for the dashboard."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List

import plotly.express as px
import plotly.graph_objects as go

from data.schemas import ParetoPoint, ProcessingJob, ScenarioResult


def create_pareto_chart(points: List[ParetoPoint]) -> go.Figure:
    """
    Create an interactive Pareto frontier chart.

    Args:
        points: List of ParetoPoints with is_pareto_optimal computed

    Returns:
        Plotly figure with all points and highlighted Pareto frontier
    """
    # Separate Pareto-optimal from non-optimal points
    pareto = [p for p in points if p.is_pareto_optimal]
    non_pareto = [p for p in points if not p.is_pareto_optimal]

    fig = go.Figure()

    # Non-optimal points (smaller, faded)
    if non_pareto:
        fig.add_trace(
            go.Scatter(
                x=[p.total_cost for p in non_pareto],
                y=[p.total_hours for p in non_pareto],
                mode="markers",
                name="Sub-optimal",
                marker=dict(size=8, opacity=0.4, color="gray"),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Location: %{customdata[1]}<br>"
                    "Cost: $%{x:.2f}<br>"
                    "Time: %{y:.2f} hrs<br>"
                    "<extra></extra>"
                ),
                customdata=[
                    [p.job_id[:8], p.location.value] for p in non_pareto
                ],
            )
        )

    # Pareto-optimal points (larger, highlighted)
    if pareto:
        # Sort by cost for the frontier line
        pareto_sorted = sorted(pareto, key=lambda p: p.total_cost)

        # Frontier line
        fig.add_trace(
            go.Scatter(
                x=[p.total_cost for p in pareto_sorted],
                y=[p.total_hours for p in pareto_sorted],
                mode="lines",
                name="Pareto Frontier",
                line=dict(color="red", width=2, dash="dash"),
                hoverinfo="skip",
            )
        )

        # Color by location
        location_colors = {
            "on_premises": "#2ecc71",  # Green
            "cloud_aws": "#3498db",  # Blue
            "cloud_gcp": "#9b59b6",  # Purple
            "hybrid": "#f39c12",  # Orange
        }

        for location in ["on_premises", "cloud_aws", "cloud_gcp", "hybrid"]:
            location_points = [p for p in pareto if p.location.value == location]
            if location_points:
                fig.add_trace(
                    go.Scatter(
                        x=[p.total_cost for p in location_points],
                        y=[p.total_hours for p in location_points],
                        mode="markers",
                        name=location.replace("_", " ").title(),
                        marker=dict(
                            size=14,
                            color=location_colors[location],
                            symbol="star",
                            line=dict(width=1, color="white"),
                        ),
                        hovertemplate=(
                            "<b>%{customdata[0]}</b><br>"
                            "Location: %{customdata[1]}<br>"
                            "Cost: $%{x:.2f}<br>"
                            "Time: %{y:.2f} hrs<br>"
                            "Cost Score: %{customdata[2]:.2f}<br>"
                            "Time Score: %{customdata[3]:.2f}<br>"
                            "<extra></extra>"
                        ),
                        customdata=[
                            [
                                p.job_id[:8],
                                p.location.value.replace("_", " ").title(),
                                p.cost_score,
                                p.time_score,
                            ]
                            for p in location_points
                        ],
                    )
                )

    fig.update_layout(
        title="Cost vs. Time Trade-off Analysis (Pareto Frontier)",
        xaxis_title="Total Cost ($)",
        yaxis_title="Total Time (hours)",
        hovermode="closest",
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
        template="plotly_white",
    )

    return fig


def create_timeline_chart(jobs: List[ProcessingJob]) -> go.Figure:
    """
    Create a Gantt-style timeline of processing jobs.

    Args:
        jobs: List of ProcessingJobs with timing information

    Returns:
        Plotly figure showing job timeline
    """
    # Filter to jobs with timing info
    timed_jobs = [j for j in jobs if j.started_at is not None]

    if not timed_jobs:
        fig = go.Figure()
        fig.add_annotation(
            text="No jobs with timing data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return fig

    fig = px.timeline(
        [
            {
                "Job": f"{j.team_name[:15]}...",
                "Start": j.started_at,
                "End": j.completed_at or j.started_at,
                "Status": j.status.value,
            }
            for j in timed_jobs
            if j.started_at
        ],
        x_start="Start",
        x_end="End",
        y="Job",
        color="Status",
        title="Processing Timeline",
    )

    fig.update_layout(template="plotly_white")
    return fig


def create_scenario_comparison_chart(
    scenarios: dict[str, ScenarioResult],
) -> go.Figure:
    """
    Create a grouped bar chart comparing scenarios.

    Args:
        scenarios: Dict of scenario name to ScenarioResult

    Returns:
        Plotly figure comparing cost and time across scenarios
    """
    names = list(scenarios.keys())
    results = list(scenarios.values())

    fig = go.Figure()

    # Cost bars
    fig.add_trace(
        go.Bar(
            name="Total Cost ($)",
            x=[r.scenario_name for r in results],
            y=[r.total_cost for r in results],
            text=[f"${r.total_cost:.2f}" for r in results],
            textposition="outside",
            marker_color="#e74c3c",
        )
    )

    # Time bars (scaled for visibility)
    max_cost = max(r.total_cost for r in results)
    max_time = max(r.total_hours for r in results)
    time_scale = max_cost / max_time if max_time > 0 else 1

    fig.add_trace(
        go.Bar(
            name="Total Time (hrs, scaled)",
            x=[r.scenario_name for r in results],
            y=[r.total_hours * time_scale for r in results],
            text=[f"{r.total_hours:.1f} hrs" for r in results],
            textposition="outside",
            marker_color="#3498db",
        )
    )

    fig.update_layout(
        title="Scenario Comparison: Cost vs Time",
        barmode="group",
        template="plotly_white",
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
    )

    return fig


def create_cost_breakdown_chart(scenario: ScenarioResult) -> go.Figure:
    """
    Create a pie chart showing job distribution by location.

    Args:
        scenario: ScenarioResult with job counts

    Returns:
        Plotly pie chart
    """
    labels = ["On-Premises", "Cloud"]
    values = [scenario.jobs_on_premises, scenario.jobs_cloud]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker_colors=["#2ecc71", "#3498db"],
            )
        ]
    )

    fig.update_layout(
        title=f"Job Distribution: {scenario.scenario_name}",
        template="plotly_white",
    )

    return fig
