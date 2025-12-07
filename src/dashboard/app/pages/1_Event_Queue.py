"""Event Queue Page - View and manage processing jobs."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from components.tables import display_job_table
from config import settings
from data import generate_event_queue
from data.schemas import JobPriority, JobStatus

st.set_page_config(
    page_title="Event Queue - KinaTrax",
    page_icon=":inbox_tray:",
    layout="wide",
)

st.title(":inbox_tray: Event Queue")
st.markdown("View and filter current processing jobs in the queue.")

# Initialize or get queue data
if "queue_data" not in st.session_state:
    st.session_state.queue_data = generate_event_queue(settings.default_queue_size)

# Sidebar filters
st.sidebar.header("Filters")

# Status filter
status_options = ["All"] + [s.value.upper() for s in JobStatus]
selected_status = st.sidebar.selectbox("Status", status_options)

# Priority filter
priority_options = ["All"] + [p.value.upper() for p in JobPriority]
selected_priority = st.sidebar.selectbox("Priority", priority_options)

# Refresh button
if st.sidebar.button("Refresh Queue", type="primary"):
    st.session_state.queue_data = generate_event_queue(settings.default_queue_size)
    st.rerun()

# Filter jobs
jobs = st.session_state.queue_data

if selected_status != "All":
    jobs = [j for j in jobs if j.status.value.upper() == selected_status]

if selected_priority != "All":
    jobs = [j for j in jobs if j.priority.value.upper() == selected_priority]

# Display metrics
col1, col2, col3, col4 = st.columns(4)

all_jobs = st.session_state.queue_data
with col1:
    queued = len([j for j in all_jobs if j.status == JobStatus.QUEUED])
    st.metric("Queued", queued)

with col2:
    processing = len([j for j in all_jobs if j.status == JobStatus.PROCESSING])
    st.metric("Processing", processing)

with col3:
    completed = len([j for j in all_jobs if j.status == JobStatus.COMPLETED])
    st.metric("Completed", completed)

with col4:
    high_priority = len(
        [j for j in all_jobs if j.priority in [JobPriority.HIGH, JobPriority.CRITICAL]]
    )
    st.metric("High Priority", high_priority)

st.divider()

# Job table
st.subheader(f"Jobs ({len(jobs)} shown)")
display_job_table(jobs, show_details=True)

# Job details expander
if jobs:
    st.divider()
    st.subheader("Job Details")

    selected_job_id = st.selectbox(
        "Select a job to view details",
        options=[j.job_id[:8] + "..." for j in jobs],
        index=0,
    )

    if selected_job_id:
        # Find the full job
        job = next(
            (j for j in jobs if j.job_id.startswith(selected_job_id[:8])), None
        )

        if job:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(
                    f"""
                **Game Details**
                - **Team:** {job.team_name}
                - **Venue:** {job.venue}
                - **Game Date:** {job.game_date.strftime('%Y-%m-%d')}
                - **Game ID:** `{job.game_id}`
                """
                )

            with col2:
                st.markdown(
                    f"""
                **Processing Info**
                - **Total Pitches:** {job.total_pitches}
                - **Pitcher Count:** {job.pitcher_count}
                - **Cameras:** {job.camera_count}
                - **FPS:** {job.fps}
                """
                )

            st.markdown(
                f"""
            **Timing**
            - **Queued At:** {job.queued_at.strftime('%Y-%m-%d %H:%M:%S')}
            - **Started At:** {job.started_at.strftime('%H:%M:%S') if job.started_at else 'Not started'}
            - **Completed At:** {job.completed_at.strftime('%H:%M:%S') if job.completed_at else 'Not completed'}
            """
            )
