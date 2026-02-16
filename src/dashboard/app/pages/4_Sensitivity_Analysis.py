"""Sensitivity Analysis - Parameter sweep impact on Pareto frontiers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from components.charts import create_sensitivity_chart
from config import settings
from data.loaders import (
    INSTANCE_TYPES,
    PRICING_LABELS,
    PRESET_SITE_PROFILES,
    load_onprem_results,
    sample_game_batch,
)
from data.schemas import CloudCostModel
from optimization.pareto import compute_pareto_frontier, generate_cloud_sweep

st.set_page_config(page_title="Sensitivity Analysis", page_icon=":bar_chart:", layout="wide")

st.title(":bar_chart: Sensitivity Analysis")
st.markdown(
    "Explore how changes in hourly rate, processing speed, and pricing model "
    "shift the Pareto frontier for a given site."
)


@st.cache_data
def load_events():
    return load_onprem_results()


events = load_events()

# --- Sidebar ---
st.sidebar.header("Base Configuration")

site_options = {s.name: s for s in PRESET_SITE_PROFILES}
site_name = st.sidebar.selectbox("Site Profile", list(site_options.keys()), index=1)
site = site_options[site_name]

batch_size = st.sidebar.slider("Batch Size", 100, 1200, settings.default_batch_size, step=50)
max_cloud = st.sidebar.slider("Max Cloud Containers", 5, 100, settings.default_max_cloud, step=5)

st.sidebar.divider()
st.sidebar.subheader("Sensitivity Variable")

sensitivity_var = st.sidebar.radio(
    "Vary Parameter",
    ["Hourly Rate", "Processing Time", "Pricing Model (All GPUs)"],
)

batch = sample_game_batch(events, batch_size)

frontiers = {}

if sensitivity_var == "Hourly Rate":
    rates = [0.25, 0.526, 0.75, 1.00, 1.50]
    for rate in rates:
        model = CloudCostModel(cost_per_hour=rate, ratio=2.18)
        sweep = generate_cloud_sweep(batch, site, model, max_cloud_containers=max_cloud)
        frontier = compute_pareto_frontier(sweep)
        frontiers[f"${rate:.3f}/hr"] = frontier
    param_name = "Cloud Hourly Rate"

elif sensitivity_var == "Processing Time":
    for inst in INSTANCE_TYPES:
        model = CloudCostModel.from_instance(inst, "spot")
        sweep = generate_cloud_sweep(batch, site, model, max_cloud_containers=max_cloud)
        frontier = compute_pareto_frontier(sweep)
        frontiers[f"{inst.gpu} ({inst.ratio:.2f}x)"] = frontier
    param_name = "GPU Processing Speed (Spot Pricing)"

else:  # Pricing Model (All GPUs)
    for inst in INSTANCE_TYPES:
        for pricing in inst.available_pricing():
            model = CloudCostModel.from_instance(inst, pricing)
            sweep = generate_cloud_sweep(batch, site, model, max_cloud_containers=max_cloud)
            frontier = compute_pareto_frontier(sweep)
            label = f"{inst.gpu} {PRICING_LABELS[pricing]}"
            frontiers[label] = frontier
    param_name = "Instance Type x Pricing Model"

fig = create_sensitivity_chart(frontiers, param_name=param_name)
st.plotly_chart(fig, use_container_width=True)

# Summary table
st.subheader("Frontier Comparison")

rows = []
for label, points in frontiers.items():
    optimal = [p for p in points if p.is_pareto_optimal]
    if not optimal:
        continue
    baseline = next((p for p in optimal if p.cost == 0), optimal[0])
    fastest = min(optimal, key=lambda p: p.time)

    rows.append({
        "Scenario": label,
        "Pareto Points": len(optimal),
        "Baseline Time (hrs)": f"{baseline.time / 3600:.1f}",
        "Fastest (hrs)": f"{fastest.time / 3600:.1f}",
        "Cost at Fastest": f"${fastest.cost:.2f}",
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# --- Pricing reference table ---
st.divider()
st.subheader("Cloud Instance Pricing Reference")

pricing_rows = []
for inst in INSTANCE_TYPES:
    pricing_rows.append({
        "Instance": inst.name,
        "GPU": inst.gpu,
        "On-Demand": f"${inst.rate_ondemand:.3f}/hr",
        "Spot": f"${inst.rate_spot:.3f}/hr",
        "1yr RI": f"${inst.rate_1yr_ri:.3f}/hr" if inst.rate_1yr_ri is not None else "N/A",
        "3yr RI": f"${inst.rate_3yr_ri:.3f}/hr" if inst.rate_3yr_ri is not None else "N/A",
        "Ratio": f"{inst.ratio:.3f}x",
        "Cost/On-Prem-Hr (Spot)": f"${inst.rate_spot * inst.ratio:.2f}",
    })

st.dataframe(pd.DataFrame(pricing_rows), use_container_width=True, hide_index=True)

st.caption(
    "Ratios from 25-event stratified pilot benchmarks (Feb 2026). "
    "RI = Reserved Instance (commitment-based discount). "
    "Cost/On-Prem-Hr = effective cost to achieve one hour of on-prem equivalent work."
)
