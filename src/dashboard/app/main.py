"""KinaTrax Decision Support Dashboard - Main Entry Point."""

import streamlit as st

from config import settings
from data import generate_event_queue
from data.schemas import JobStatus

# Page configuration
st.set_page_config(
    page_title="KinaTrax Decision Support Dashboard",
    page_icon=":baseball:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "queue_data" not in st.session_state:
    st.session_state.queue_data = generate_event_queue(settings.default_queue_size)

if "cost_weight" not in st.session_state:
    st.session_state.cost_weight = 0.5


def main() -> None:
    """Main dashboard home page."""
    st.title(":baseball: KinaTrax Decision Support Dashboard")

    st.markdown(
        """
    Welcome to the **KinaTrax Decision Support Dashboard**. This interface helps
    Data Processing Engineers optimize job configuration by visualizing
    cost vs. time trade-offs for biomechanical analysis processing.

    ### Navigate using the sidebar to:
    1. **Event Queue** - View current processing jobs
    2. **Cost-Time Tradeoff** - Analyze Pareto-optimal configurations
    3. **Scenario Comparison** - Compare on-prem vs cloud vs hybrid
    4. **Job Configuration** - Configure new processing jobs
    5. **C3D Verification** - Verify output equivalence between systems
    """
    )

    st.divider()

    # Quick metrics from current queue
    jobs = st.session_state.queue_data
    queued = len([j for j in jobs if j.status == JobStatus.QUEUED])
    processing = len([j for j in jobs if j.status == JobStatus.PROCESSING])
    completed = len([j for j in jobs if j.status == JobStatus.COMPLETED])

    # Calculate average processing time from completed jobs
    completed_jobs = [j for j in jobs if j.status == JobStatus.COMPLETED]
    if completed_jobs and all(j.started_at and j.completed_at for j in completed_jobs):
        avg_hours = sum(
            (j.completed_at - j.started_at).total_seconds() / 3600
            for j in completed_jobs
            if j.started_at and j.completed_at
        ) / len(completed_jobs)
    else:
        avg_hours = 4.2  # Default estimate

    # Display metrics
    st.subheader("Current Queue Status")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Jobs in Queue",
            value=str(queued),
            delta=f"+{queued}" if queued > 0 else None,
            help="Number of jobs waiting to be processed",
        )

    with col2:
        st.metric(
            label="Currently Processing",
            value=str(processing),
            delta=None,
            help="Number of jobs actively being processed",
        )

    with col3:
        st.metric(
            label="Avg. Processing Time",
            value=f"{avg_hours:.1f} hrs",
            delta="-0.8 hrs" if avg_hours < 5 else "+0.5 hrs",
            delta_color="inverse",
            help="Average time to process a game",
        )

    with col4:
        st.metric(
            label="C3D Match Rate",
            value="100%",
            delta="0%",
            help="Percentage of jobs with matching C3D outputs",
        )

    st.divider()

    # System status
    st.subheader("System Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.info(
            f"""
        **Data Source:** {'Mock Data' if settings.use_mock_data else 'Live API'}
        **API Endpoint:** {settings.api_base_url}
        **Version:** {settings.app_version}
        """
        )

    with col2:
        st.success(
            """
        **On-Premises Status:** Connected
        **AWS Status:** Available
        **Monitoring:** Active
        """
        )

    # Footer
    st.divider()
    st.caption(
        "KinaTrax Decision Support Dashboard v0.1.0 | "
        "Full Sail University CSMS Capstone Project"
    )


if __name__ == "__main__":
    main()
