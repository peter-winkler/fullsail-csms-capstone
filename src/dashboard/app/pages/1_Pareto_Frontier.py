"""Pareto Frontier - Cost vs. Turnaround Trade-off Analysis."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from components.charts import create_pareto_chart
from config import settings
from data.loaders import load_onprem_results, sample_game_batch, PRESET_SITE_PROFILES
from data.schemas import CloudCostModel, SiteProfile
from optimization.pareto import compute_pareto_frontier, find_optimal_configuration, generate_cloud_sweep

st.set_page_config(page_title="Pareto Frontier", page_icon=":chart_with_upwards_trend:", layout="wide")

st.title(":chart_with_upwards_trend: Pareto Frontier Analysis")
st.markdown(
    "Sweep cloud container count to visualize the cost vs. turnaround "
    "trade-off for a selected site profile."
)


@st.cache_data
def load_events():
    return load_onprem_results()


events = load_events()

# --- Sidebar controls ---
st.sidebar.header("Simulation Parameters")

site_options = {s.name: s for s in PRESET_SITE_PROFILES}
site_name = st.sidebar.selectbox("Site Profile", list(site_options.keys()), index=1)
site = site_options[site_name]

custom_gpus = st.sidebar.number_input(
    "Override GPU Count", min_value=1, max_value=100,
    value=site.available_gpus, help="Adjust on-prem GPUs for what-if analysis"
)
if custom_gpus != site.available_gpus:
    site = SiteProfile(
        name=f"{site.name} (custom)",
        venue_code=site.venue_code,
        available_gpus=custom_gpus,
        tier=site.tier,
    )

batch_size = st.sidebar.slider("Batch Size (events)", 100, 1200, settings.default_batch_size, step=50)
max_cloud = st.sidebar.slider("Max Cloud Containers", 5, 100, settings.default_max_cloud, step=5)
seed = st.sidebar.number_input("Random Seed", value=settings.default_seed, min_value=0)

st.sidebar.divider()
st.sidebar.subheader("Cloud Pricing")

cost_per_hour = st.sidebar.number_input("On-Demand $/hr", value=0.526, format="%.3f", step=0.01)
cloud_time = st.sidebar.number_input("Cloud Processing (min)", value=23.0, format="%.1f", step=1.0)
startup_sec = st.sidebar.number_input("Container Startup (sec)", value=30, min_value=0, max_value=300)
transfer_sec = st.sidebar.number_input("Data Transfer (sec)", value=60, min_value=0, max_value=600)

use_spot = st.sidebar.checkbox("Use Spot Pricing")
spot_rate = st.sidebar.number_input("Spot $/hr", value=0.16, format="%.3f", step=0.01, disabled=not use_spot)

cost_weight = st.sidebar.slider(
    "Cost vs. Time Priority",
    0.0, 1.0, 0.5, step=0.05,
    help="0.0 = minimize time only, 1.0 = minimize cost only"
)

# --- Build cloud model and run simulation ---
cloud_model = CloudCostModel(
    cost_per_hour=cost_per_hour,
    spot_cost_per_hour=spot_rate if use_spot else None,
    use_spot=use_spot,
    cloud_time_per_event_sec=cloud_time * 60,
    container_startup_sec=float(startup_sec),
    data_transfer_sec_per_event=float(transfer_sec),
)

batch = sample_game_batch(events, batch_size, seed=seed)
sweep = generate_cloud_sweep(batch, site, cloud_model, max_cloud_containers=max_cloud)
frontier = compute_pareto_frontier(sweep)
optimal = find_optimal_configuration(frontier, cost_weight=cost_weight)

# --- Display ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Site GPUs", site.available_gpus)
with col2:
    st.metric("Batch Events", batch_size)
with col3:
    pareto_count = sum(1 for p in frontier if p.is_pareto_optimal)
    st.metric("Pareto-Optimal Points", pareto_count)
with col4:
    if optimal:
        st.metric("Recommended", optimal.config_id)

st.divider()

fig = create_pareto_chart(frontier, optimal=optimal,
                          title=f"Cloud Acceleration: {site.name} ({site.available_gpus} GPUs)")
st.plotly_chart(fig, use_container_width=True)

# Summary table
st.subheader("Pareto-Optimal Configurations")
optimal_points = sorted([p for p in frontier if p.is_pareto_optimal], key=lambda p: p.cost)

import pandas as pd

df = pd.DataFrame([
    {
        "Config": p.config_id,
        "Cloud Cost": f"${p.cost:.2f}",
        "Turnaround": f"{p.time / 3600:.1f} hrs",
        "Selected": ">>>" if optimal and p.config_id == optimal.config_id else "",
    }
    for p in optimal_points
])
st.dataframe(df, use_container_width=True, hide_index=True)

# Baseline comparison
baseline = next((p for p in frontier if p.cost == 0), None)
if baseline and optimal and optimal.config_id != baseline.config_id:
    st.divider()
    st.subheader("Recommendation vs. Baseline")
    col1, col2 = st.columns(2)
    with col1:
        time_saved = baseline.time - optimal.time
        st.metric("Time Saved", f"{time_saved / 3600:.1f} hrs",
                  delta=f"-{time_saved / baseline.time * 100:.0f}%")
    with col2:
        st.metric("Additional Cost", f"${optimal.cost:.2f}")
