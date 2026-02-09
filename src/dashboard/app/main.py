"""KinaTrax Cloud Acceleration Dashboard - Main Entry Point.

Run with: streamlit run main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st

from config import settings
from data.loaders import load_onprem_results, SITE_GPU_COUNTS, PRESET_SITE_PROFILES

st.set_page_config(
    page_title=settings.app_name,
    page_icon=":baseball:",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_events():
    return load_onprem_results()


def main() -> None:
    st.title(":baseball: KinaTrax Cloud Acceleration Dashboard")

    st.markdown(
        """
    This dashboard helps Data Processing Engineers evaluate the cost-benefit
    trade-offs of supplementing on-premises GPU processing with cloud containers.

    ### Pages
    1. **Pareto Frontier** - Visualize cost vs. turnaround trade-offs for a site
    2. **Site Comparison** - Compare frontiers across GPU-poor, moderate, and rich sites
    3. **Batch Detail** - Inspect per-event scheduling assignments
    4. **Cost Model** - Sensitivity analysis for cloud pricing parameters
    """
    )

    st.divider()

    events = load_events()

    # Key metrics
    st.subheader("On-Prem Data Summary")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Events Loaded", len(events))
    with col2:
        avg_time = sum(e.processing_time_sec for e in events) / len(events)
        st.metric("Avg Processing Time", f"{avg_time / 60:.1f} min")
    with col3:
        batting = len([e for e in events if e.event_type == "Batting"])
        st.metric("Batting Events", batting)
    with col4:
        pitching = len([e for e in events if e.event_type == "Pitching"])
        st.metric("Pitching Events", pitching)

    # Processing time range
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    times = [e.processing_time_sec for e in events]

    with col1:
        st.metric("Min Time", f"{min(times) / 60:.1f} min")
    with col2:
        st.metric("Max Time", f"{max(times) / 60:.1f} min")
    with col3:
        fps_300 = [e for e in events if e.fps == 300]
        if fps_300:
            avg_300 = sum(e.processing_time_sec for e in fps_300) / len(fps_300)
            st.metric("300fps Avg", f"{avg_300 / 60:.1f} min")
        else:
            st.metric("300fps Avg", "N/A")
    with col4:
        fps_600 = [e for e in events if e.fps == 600]
        if fps_600:
            avg_600 = sum(e.processing_time_sec for e in fps_600) / len(fps_600)
            st.metric("600fps Avg", f"{avg_600 / 60:.1f} min")
        else:
            st.metric("600fps Avg", "N/A")

    # Venue distribution
    st.divider()
    st.subheader("Events by Venue")

    venue_counts = {}
    for e in events:
        venue_counts[e.venue] = venue_counts.get(e.venue, 0) + 1

    df_venues = pd.DataFrame([
        {"Venue": v, "Events": c} for v, c in sorted(venue_counts.items(), key=lambda x: -x[1])
    ])
    st.dataframe(df_venues, use_container_width=True, hide_index=True)

    # Site GPU profiles
    st.divider()
    st.subheader("MLB Site GPU Configurations")

    df_sites = pd.DataFrame([
        {
            "Site": s.name,
            "Code": s.venue_code,
            "GPUs": s.available_gpus,
            "Tier": s.tier.replace("_", " ").title(),
        }
        for s in PRESET_SITE_PROFILES
    ])
    st.dataframe(df_sites, use_container_width=True, hide_index=True)

    st.caption(
        f"Data: {len(SITE_GPU_COUNTS)} MLB organizations, "
        f"range 0-93 active GPUs. "
        f"Source: Controllers/Containers spreadsheet (Feb 2026)."
    )

    # Footer
    st.divider()
    st.caption(f"{settings.app_name} v{settings.app_version} | "
               "Full Sail University CSMS Capstone Project")


if __name__ == "__main__":
    main()
