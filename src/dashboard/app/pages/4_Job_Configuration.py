"""Job Configuration Page - Configure new processing jobs."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from datetime import datetime

from config import settings
from data import generate_cost_time_estimate, generate_processing_job
from data.schemas import JobPriority, ProcessingLocation

st.set_page_config(
    page_title="Job Configuration - KinaTrax",
    page_icon=":gear:",
    layout="wide",
)

st.title(":gear: Job Configuration")
st.markdown(
    """
Configure processing parameters and preview cost/time estimates before submitting.
Adjust the sliders to see how different configurations affect processing outcomes.
"""
)

# Sidebar preference sliders
st.sidebar.header("Optimization Preferences")

cost_priority = st.sidebar.slider(
    "Cost Priority",
    min_value=0,
    max_value=100,
    value=50,
    help="Higher = prioritize cost savings over speed",
)

time_priority = 100 - cost_priority
st.sidebar.write(f"Time Priority: {time_priority}%")

st.sidebar.divider()
st.sidebar.subheader("Budget Constraints")

max_budget = st.sidebar.number_input(
    "Maximum Budget ($)",
    min_value=0.0,
    value=500.0,
    step=50.0,
)

max_hours = st.sidebar.number_input(
    "Maximum Processing Time (hrs)",
    min_value=0.0,
    value=8.0,
    step=1.0,
)

# Main form
st.subheader("Job Parameters")

col1, col2 = st.columns(2)

with col1:
    team_name = st.text_input("Team Name", value="New York Yankees")
    venue = st.text_input("Venue", value="Yankee Stadium")
    game_date = st.date_input("Game Date", value=datetime.now())

with col2:
    total_pitches = st.slider(
        "Total Pitches",
        min_value=50,
        max_value=300,
        value=150,
        step=10,
    )
    camera_count = st.selectbox("Camera Count", options=[8, 10, 12], index=0)
    priority = st.selectbox(
        "Priority",
        options=[p.value.upper() for p in JobPriority],
        index=1,  # NORMAL
    )

st.divider()

# Generate estimates
st.subheader("Processing Estimates")

# Create a mock job for estimation
mock_job = generate_processing_job()
mock_job.team_name = team_name
mock_job.venue = venue
mock_job.total_pitches = total_pitches
mock_job.camera_count = camera_count
mock_job.priority = JobPriority(priority.lower())

# Calculate estimates for each location
estimates = {
    loc: generate_cost_time_estimate(mock_job, loc) for loc in ProcessingLocation
}

# Display estimates in columns
cols = st.columns(4)
locations = list(ProcessingLocation)
location_labels = {
    ProcessingLocation.ON_PREMISES: ("On-Premises", "#2ecc71"),
    ProcessingLocation.CLOUD_AWS: ("AWS Cloud", "#3498db"),
    ProcessingLocation.CLOUD_GCP: ("GCP Cloud", "#9b59b6"),
    ProcessingLocation.HYBRID: ("Hybrid", "#f39c12"),
}

for i, loc in enumerate(locations):
    est = estimates[loc]
    label, color = location_labels[loc]

    with cols[i]:
        st.markdown(f"#### {label}")

        # Check constraints
        within_budget = est.total_cost <= max_budget
        within_time = est.total_estimated_hours <= max_hours
        is_recommended = within_budget and within_time

        st.metric("Est. Cost", f"${est.total_cost:.2f}")
        st.metric("Est. Time", f"{est.total_estimated_hours:.1f} hrs")

        # Status indicators
        if within_budget and within_time:
            st.success("Meets constraints")
        elif not within_budget:
            st.error(f"Over budget by ${est.total_cost - max_budget:.2f}")
        else:
            st.warning(f"Exceeds time by {est.total_estimated_hours - max_hours:.1f} hrs")

# Recommendation
st.divider()
st.subheader("Recommended Configuration")

# Find best option based on priorities
best_loc = None
best_score = -1

for loc, est in estimates.items():
    # Skip if constraints not met
    if est.total_cost > max_budget or est.total_estimated_hours > max_hours:
        continue

    # Normalize scores (lower is better, so invert)
    max_cost = max(e.total_cost for e in estimates.values())
    max_time = max(e.total_estimated_hours for e in estimates.values())

    cost_score = (max_cost - est.total_cost) / max_cost if max_cost > 0 else 0
    time_score = (max_time - est.total_estimated_hours) / max_time if max_time > 0 else 0

    # Weighted score
    score = (cost_priority / 100) * cost_score + (time_priority / 100) * time_score

    if score > best_score:
        best_score = score
        best_loc = loc

if best_loc:
    est = estimates[best_loc]
    label, color = location_labels[best_loc]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Recommended", label)
    with col2:
        st.metric("Cost", f"${est.total_cost:.2f}")
    with col3:
        st.metric("Time", f"{est.total_estimated_hours:.1f} hrs")
    with col4:
        st.metric("Score", f"{best_score:.2f}")

    st.success(
        f"Based on your priorities (Cost: {cost_priority}%, Time: {time_priority}%), "
        f"**{label}** is the optimal choice."
    )
else:
    st.error(
        "No configuration meets your constraints. "
        "Try increasing the budget or time limit."
    )

# Submit button
st.divider()

col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    if st.button("Submit Job", type="primary", disabled=not settings.enable_job_submission):
        st.success("Job submitted successfully! (Demo mode)")

with col2:
    if st.button("Reset Form"):
        st.rerun()

if not settings.enable_job_submission:
    st.caption("Job submission is disabled in demo mode.")
