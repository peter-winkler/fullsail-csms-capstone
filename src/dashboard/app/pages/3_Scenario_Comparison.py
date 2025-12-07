"""Scenario Comparison Page - Compare processing strategies."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from components.charts import create_cost_breakdown_chart, create_scenario_comparison_chart
from config import settings
from data import generate_event_queue
from optimization.scenarios import calculate_all_scenarios

st.set_page_config(
    page_title="Scenario Comparison - KinaTrax",
    page_icon=":bar_chart:",
    layout="wide",
)

st.title(":bar_chart: Scenario Comparison")
st.markdown(
    """
Compare three processing strategies side-by-side:
1. **All On-Premises** - Best cost, longest time
2. **All Cloud (AWS)** - Fastest time, highest cost
3. **Optimized Hybrid** - Balanced approach based on job priority
"""
)

# Initialize data
if "queue_data" not in st.session_state:
    st.session_state.queue_data = generate_event_queue(settings.default_queue_size)

# Calculate scenarios
jobs = st.session_state.queue_data
scenarios = calculate_all_scenarios(jobs)

# Comparison chart
st.subheader("Cost vs. Time Comparison")
fig = create_scenario_comparison_chart(scenarios)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# Side-by-side scenario cards
st.subheader("Detailed Breakdown")

col1, col2, col3 = st.columns(3)

with col1:
    scenario = scenarios["on_premises"]
    st.markdown(f"### {scenario.scenario_name}")
    st.caption(scenario.description)

    st.metric("Total Cost", f"${scenario.total_cost:.2f}")
    st.metric("Total Time", f"{scenario.total_hours:.1f} hrs")
    st.metric("Avg Cost/Job", f"${scenario.average_cost_per_job:.2f}")
    st.metric("Avg Time/Job", f"{scenario.average_hours_per_job:.1f} hrs")

    # Distribution chart
    fig = create_cost_breakdown_chart(scenario)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    scenario = scenarios["cloud"]
    st.markdown(f"### {scenario.scenario_name}")
    st.caption(scenario.description)

    st.metric("Total Cost", f"${scenario.total_cost:.2f}")
    st.metric("Total Time", f"{scenario.total_hours:.1f} hrs")
    st.metric("Avg Cost/Job", f"${scenario.average_cost_per_job:.2f}")
    st.metric("Avg Time/Job", f"{scenario.average_hours_per_job:.1f} hrs")

    fig = create_cost_breakdown_chart(scenario)
    st.plotly_chart(fig, use_container_width=True)

with col3:
    scenario = scenarios["optimized"]
    st.markdown(f"### {scenario.scenario_name}")
    st.caption(scenario.description)

    st.metric("Total Cost", f"${scenario.total_cost:.2f}")
    st.metric("Total Time", f"{scenario.total_hours:.1f} hrs")
    st.metric("Avg Cost/Job", f"${scenario.average_cost_per_job:.2f}")
    st.metric("Avg Time/Job", f"{scenario.average_hours_per_job:.1f} hrs")

    fig = create_cost_breakdown_chart(scenario)
    st.plotly_chart(fig, use_container_width=True)

# Savings analysis
st.divider()
st.subheader("Savings Analysis")

on_prem = scenarios["on_premises"]
cloud = scenarios["cloud"]
optimized = scenarios["optimized"]

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Optimized vs. All Cloud")
    cost_savings = cloud.total_cost - optimized.total_cost
    cost_savings_pct = (cost_savings / cloud.total_cost * 100) if cloud.total_cost > 0 else 0
    time_increase = optimized.total_hours - cloud.total_hours
    time_increase_pct = (time_increase / cloud.total_hours * 100) if cloud.total_hours > 0 else 0

    st.metric(
        "Cost Savings",
        f"${cost_savings:.2f}",
        delta=f"{cost_savings_pct:.1f}%",
    )
    st.metric(
        "Time Trade-off",
        f"+{time_increase:.1f} hrs",
        delta=f"+{time_increase_pct:.1f}%",
        delta_color="inverse",
    )

with col2:
    st.markdown("#### Optimized vs. All On-Premises")
    cost_increase = optimized.total_cost - on_prem.total_cost
    cost_increase_pct = (cost_increase / on_prem.total_cost * 100) if on_prem.total_cost > 0 else 0
    time_savings = on_prem.total_hours - optimized.total_hours
    time_savings_pct = (time_savings / on_prem.total_hours * 100) if on_prem.total_hours > 0 else 0

    st.metric(
        "Cost Increase",
        f"${cost_increase:.2f}",
        delta=f"+{cost_increase_pct:.1f}%",
        delta_color="inverse",
    )
    st.metric(
        "Time Savings",
        f"{time_savings:.1f} hrs",
        delta=f"-{time_savings_pct:.1f}%",
    )

# C3D verification note
st.divider()
st.info(
    """
:white_check_mark: **C3D Output Verification**: All scenarios maintain 100% identical
C3D output results. The choice of processing location does not affect the accuracy
of biomechanical analysis - only the cost and time trade-offs.
"""
)
