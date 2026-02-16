"""Batch Detail - Inspect per-event scheduling assignments."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from components.charts import (
    create_assignment_bar,
    create_event_type_breakdown,
    create_processing_time_histogram,
)
from config import settings
from data.loaders import (
    INSTANCE_TYPES,
    PRICING_LABELS,
    PRICING_MODES,
    PRESET_SITE_PROFILES,
    load_onprem_results,
    sample_game_batch,
)
from data.schemas import CloudCostModel, SiteProfile
from simulation.scheduler import schedule_lpt

st.set_page_config(page_title="Batch Detail", page_icon=":mag:", layout="wide")

st.title(":mag: Batch Detail")
st.markdown(
    "Run a single simulation and inspect how the LPT scheduler assigns "
    "events across on-prem GPUs and cloud containers."
)


@st.cache_data
def load_events():
    return load_onprem_results()


events = load_events()

# --- Sidebar ---
st.sidebar.header("Simulation Setup")

site_options = {s.name: s for s in PRESET_SITE_PROFILES}
site_name = st.sidebar.selectbox("Site Profile", list(site_options.keys()), index=1)
site = site_options[site_name]

cloud_containers = st.sidebar.slider("Cloud Containers", 0, 50, 10)
batch_size = st.sidebar.slider("Batch Size", 100, 1200, settings.default_batch_size, step=50)

st.sidebar.divider()
st.sidebar.subheader("Cloud Configuration")

instance_options = {f"{it.gpu} ({it.name})": it for it in INSTANCE_TYPES}
instance_label = st.sidebar.selectbox(
    "GPU Instance Type",
    list(instance_options.keys()),
    index=2,  # Default to L4
)
selected_instance = instance_options[instance_label]

available_tiers = selected_instance.available_pricing()
pricing_tier = st.sidebar.radio(
    "Pricing Tier",
    available_tiers,
    format_func=lambda x: PRICING_LABELS[x],
    index=1 if len(available_tiers) > 1 else 0,
)

cloud_model = CloudCostModel.from_instance(selected_instance, pricing_tier)
batch = sample_game_batch(events, batch_size)

# --- Run with per-event tracking ---
result = schedule_lpt(batch, site, cloud_containers, cloud_model, track_assignments=True)

# --- Summary metrics ---
gpu_label = selected_instance.gpu
pricing_label = PRICING_LABELS[pricing_tier]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Config", result.config_id)
with col2:
    st.metric("Turnaround", f"{result.turnaround_time_sec / 3600:.1f} hrs")
with col3:
    st.metric("Cloud Cost", f"${result.cloud_cost:.2f}")
with col4:
    st.metric("Events on Cloud", f"{result.events_on_cloud} / {result.total_events}")

st.caption(f"Cloud: {gpu_label} | {pricing_label} | Ratio: {selected_instance.ratio:.3f}x")

st.divider()

# --- Charts ---
col1, col2 = st.columns(2)

with col1:
    fig_bar = create_assignment_bar(result)
    st.plotly_chart(fig_bar, use_container_width=True)

with col2:
    if result.assignments:
        fig_type = create_event_type_breakdown(result.assignments)
        st.plotly_chart(fig_type, use_container_width=True)

if result.assignments:
    fig_hist = create_processing_time_histogram(result.assignments)
    st.plotly_chart(fig_hist, use_container_width=True)

# --- On-prem vs cloud finish times ---
st.divider()
st.subheader("Timing Breakdown")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("On-Prem Finish", f"{result.on_prem_finish_sec / 3600:.1f} hrs")
with col2:
    st.metric("Cloud Finish", f"{result.cloud_finish_sec / 3600:.1f} hrs")
with col3:
    bottleneck = "On-Prem" if result.on_prem_finish_sec >= result.cloud_finish_sec else "Cloud"
    st.metric("Bottleneck", bottleneck)

# --- Assignment table ---
if result.assignments:
    st.divider()
    st.subheader("Event Assignments")

    df = pd.DataFrame([
        {
            "Event": a.event_name[:30],
            "Type": a.event_type,
            "On-Prem Time (min)": f"{a.processing_time_sec / 60:.1f}",
            "Assigned To": a.assigned_to.replace("_", " ").title(),
            "Processor": a.processor_id,
            "Effective Time (min)": f"{a.effective_time_sec / 60:.1f}",
            "FPS": int(a.fps) if a.fps else "",
        }
        for a in result.assignments
    ])

    st.dataframe(df, use_container_width=True, hide_index=True, height=400)

    cloud_events = [a for a in result.assignments if a.assigned_to == "cloud"]
    prem_events = [a for a in result.assignments if a.assigned_to == "on_prem"]

    if cloud_events and prem_events:
        avg_cloud = sum(a.processing_time_sec for a in cloud_events) / len(cloud_events)
        avg_prem = sum(a.processing_time_sec for a in prem_events) / len(prem_events)
        st.caption(
            f"LPT offloads heavier events to cloud: "
            f"cloud avg {avg_cloud / 60:.1f} min vs on-prem avg {avg_prem / 60:.1f} min "
            f"(on-prem measured time)"
        )
