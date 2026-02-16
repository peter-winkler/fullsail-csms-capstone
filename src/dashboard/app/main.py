"""KinaTrax Cloud Acceleration Dashboard - Main Entry Point.

Run with: streamlit run main.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st

from config import settings
from data.loaders import load_onprem_results, INSTANCE_TYPES, SITE_GPU_COUNTS, PRESET_SITE_PROFILES

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
    1. **Pareto Frontier** - Multi-instance and single-instance cost vs. turnaround trade-offs
    2. **Site Comparison** - Compare frontiers across GPU-poor, moderate, and rich sites
    3. **Batch Detail** - Inspect per-event scheduling assignments
    4. **Sensitivity Analysis** - Parameter sweeps across pricing models and GPU types
    """
    )

    st.divider()

    events = load_events()

    # --- Load combined results for cloud stats ---
    combined_path = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "data" / "combined_results_final.csv"
    onprem_times = []
    cloud_times = []
    ratios = []
    if combined_path.exists():
        with open(combined_path, newline="") as f:
            for row in csv.DictReader(f):
                op = float(row["onprem_time_sec"])
                ct = float(row["cloud_time_sec"])
                onprem_times.append(op)
                cloud_times.append(ct)
                if op > 0:
                    ratios.append(ct / op)

    # --- Processing Results Overview ---
    st.subheader("Processing Results Overview")

    if onprem_times and cloud_times:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**On-Premises (RTX 4000 Ada)**")
            avg_op = sum(onprem_times) / len(onprem_times)
            st.metric("Events", len(onprem_times))
            st.metric("Mean", f"{avg_op / 60:.1f} min")
            st.metric("Range", f"{min(onprem_times) / 60:.1f} - {max(onprem_times) / 60:.1f} min")

        with col2:
            st.markdown("**Cloud (Tesla T4)**")
            avg_ct = sum(cloud_times) / len(cloud_times)
            st.metric("Events", len(cloud_times))
            st.metric("Mean", f"{avg_ct / 60:.1f} min")
            st.metric("Range", f"{min(cloud_times) / 60:.1f} - {max(cloud_times) / 60:.1f} min")

        with col3:
            st.markdown("**Comparison**")
            avg_ratio = sum(ratios) / len(ratios)
            st.metric("Cloud/On-Prem Ratio", f"{avg_ratio:.2f}x")
            batting_count = sum(1 for e in events if e.event_type == "Batting")
            pitching_count = sum(1 for e in events if e.event_type == "Pitching")
            st.metric("Batting / Pitching", f"{batting_count} / {pitching_count}")
            fps_300 = [e for e in events if e.fps == 300]
            fps_600 = [e for e in events if e.fps == 600]
            st.metric("300fps / 600fps", f"{len(fps_300)} / {len(fps_600)}")

        st.caption(
            "200 curated events processed on both platforms. "
            "On-prem: RTX 4000 Ada (KinaTrax stadium server). "
            "Cloud: Tesla T4 (g4dn.xlarge spot instance)."
        )
    else:
        # Fallback: on-prem only
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

    # Cloud GPU instances
    st.divider()
    st.subheader("Cloud GPU Instance Types")

    df_instances = pd.DataFrame([
        {
            "Instance": it.name,
            "GPU": it.gpu,
            "Spot $/hr": f"${it.rate_spot:.2f}",
            "Ratio": f"{it.ratio:.3f}x",
            "Cost/On-Prem-Hr": f"${it.rate_spot * it.ratio:.2f}",
        }
        for it in INSTANCE_TYPES
    ])
    st.dataframe(df_instances, use_container_width=True, hide_index=True)

    st.caption(
        "Ratios from 25-event stratified pilot benchmarks (Feb 2026). "
        "Cost/On-Prem-Hr = spot rate x ratio = effective cost per hour of on-prem equivalent work."
    )

    # Footer
    st.divider()
    st.caption(f"{settings.app_name} v{settings.app_version} | "
               "Full Sail University CSMS Capstone Project")


if __name__ == "__main__":
    main()
