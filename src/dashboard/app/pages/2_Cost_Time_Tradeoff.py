"""Cost-Time Tradeoff Page - Pareto frontier visualization."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from components.charts import create_pareto_chart
from config import settings
from data import generate_event_queue, generate_pareto_frontier_data
from data.schemas import ProcessingLocation
from optimization import compute_pareto_frontier, find_optimal_configuration

st.set_page_config(
    page_title="Cost-Time Tradeoff - KinaTrax",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

st.title(":chart_with_upwards_trend: Cost vs. Time Trade-off Analysis")
st.markdown(
    """
Visualize the **Pareto frontier** to identify optimal processing configurations.
Points on the frontier represent configurations where you cannot improve cost
without sacrificing time, or vice versa.
"""
)

# Initialize data
if "queue_data" not in st.session_state:
    st.session_state.queue_data = generate_event_queue(settings.default_queue_size)

if "pareto_data" not in st.session_state:
    raw_points = generate_pareto_frontier_data(st.session_state.queue_data)
    st.session_state.pareto_data = compute_pareto_frontier(raw_points)

# Sidebar controls
st.sidebar.header("Optimization Preferences")

cost_weight = st.sidebar.slider(
    "Cost Priority",
    min_value=0.0,
    max_value=1.0,
    value=0.5,
    step=0.1,
    help="Higher = prioritize lower cost",
)

time_weight = 1.0 - cost_weight
st.sidebar.write(f"Time Priority: {time_weight:.1f}")

st.sidebar.divider()

# Constraints
st.sidebar.subheader("Constraints (Optional)")
max_cost = st.sidebar.number_input(
    "Max Budget ($)",
    min_value=0.0,
    value=0.0,
    step=50.0,
    help="Leave at 0 for no limit",
)
max_time = st.sidebar.number_input(
    "Max Time (hours)",
    min_value=0.0,
    value=0.0,
    step=1.0,
    help="Leave at 0 for no limit",
)

# Location filter
st.sidebar.divider()
st.sidebar.subheader("Filter by Location")
show_locations = st.sidebar.multiselect(
    "Show locations",
    options=[loc.value for loc in ProcessingLocation],
    default=[loc.value for loc in ProcessingLocation],
)

# Regenerate button
if st.sidebar.button("Regenerate Data", type="secondary"):
    st.session_state.queue_data = generate_event_queue(settings.default_queue_size)
    raw_points = generate_pareto_frontier_data(st.session_state.queue_data)
    st.session_state.pareto_data = compute_pareto_frontier(raw_points)
    st.rerun()

# Filter points by location
points = st.session_state.pareto_data
if show_locations:
    points = [p for p in points if p.location.value in show_locations]

# Find optimal configuration
optimal = find_optimal_configuration(
    points,
    cost_weight=cost_weight,
    time_weight=time_weight,
    max_cost=max_cost if max_cost > 0 else None,
    max_time=max_time if max_time > 0 else None,
)

# Display Pareto chart
st.subheader("Pareto Frontier Visualization")
fig = create_pareto_chart(points)
st.plotly_chart(fig, use_container_width=True)

# Summary statistics
st.divider()
col1, col2, col3 = st.columns(3)

pareto_points = [p for p in points if p.is_pareto_optimal]

with col1:
    st.metric("Total Configurations", len(points))

with col2:
    st.metric("Pareto-Optimal", len(pareto_points))

with col3:
    if points:
        cost_range = f"${min(p.total_cost for p in points):.0f} - ${max(p.total_cost for p in points):.0f}"
        st.metric("Cost Range", cost_range)

# Recommended configuration
st.divider()
st.subheader("Recommended Configuration")

if optimal:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Location", optimal.location.value.replace("_", " ").title())

    with col2:
        st.metric("Estimated Cost", f"${optimal.total_cost:.2f}")

    with col3:
        st.metric("Estimated Time", f"{optimal.total_hours:.2f} hrs")

    with col4:
        combined_score = (cost_weight * optimal.cost_score) + (
            time_weight * optimal.time_score
        )
        st.metric("Optimization Score", f"{combined_score:.2f}")

    if optimal.is_pareto_optimal:
        st.success("This configuration is Pareto-optimal!")
    else:
        st.warning("This configuration is not Pareto-optimal but meets your constraints.")
else:
    st.error("No configuration meets the specified constraints. Try relaxing your limits.")

# Pareto frontier table
st.divider()
st.subheader("Pareto-Optimal Configurations")

if pareto_points:
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "Job": p.job_id[:8] + "...",
                "Location": p.location.value.replace("_", " ").title(),
                "Cost ($)": f"{p.total_cost:.2f}",
                "Time (hrs)": f"{p.total_hours:.2f}",
                "Cost Score": f"{p.cost_score:.2f}",
                "Time Score": f"{p.time_score:.2f}",
            }
            for p in sorted(pareto_points, key=lambda x: x.total_cost)
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No Pareto-optimal points found with current filters.")
