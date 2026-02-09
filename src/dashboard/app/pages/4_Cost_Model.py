"""Cost Model - Sensitivity analysis for cloud pricing parameters."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from components.charts import create_sensitivity_chart
from config import settings
from data.loaders import load_onprem_results, sample_game_batch, PRESET_SITE_PROFILES
from data.schemas import CloudCostModel
from optimization.pareto import compute_pareto_frontier, generate_cloud_sweep

st.set_page_config(page_title="Cost Model", page_icon=":moneybag:", layout="wide")

st.title(":moneybag: Cost Model Sensitivity")
st.markdown(
    "Explore how changing cloud pricing assumptions shifts the Pareto frontier. "
    "Useful for evaluating on-demand vs. spot pricing, different instance types, "
    "or expected improvements in processing speed."
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
seed = st.sidebar.number_input("Random Seed", value=settings.default_seed, min_value=0)

st.sidebar.divider()
st.sidebar.subheader("Sensitivity Variable")

sensitivity_var = st.sidebar.radio(
    "Vary Parameter",
    ["Hourly Rate", "Processing Time", "Pricing Model"],
)

batch = sample_game_batch(events, batch_size, seed=seed)

# --- Generate frontiers for sensitivity sweep ---
frontiers = {}

if sensitivity_var == "Hourly Rate":
    rates = [0.25, 0.526, 0.75, 1.00, 1.50]
    for rate in rates:
        model = CloudCostModel(cost_per_hour=rate)
        sweep = generate_cloud_sweep(batch, site, model, max_cloud_containers=max_cloud)
        frontier = compute_pareto_frontier(sweep)
        frontiers[f"${rate:.3f}/hr"] = frontier
    param_name = "Cloud Hourly Rate (On-Demand)"

elif sensitivity_var == "Processing Time":
    times_min = [10.0, 15.0, 23.0, 30.0, 45.0]
    for t in times_min:
        model = CloudCostModel(cloud_time_per_event_sec=t * 60)
        sweep = generate_cloud_sweep(batch, site, model, max_cloud_containers=max_cloud)
        frontier = compute_pareto_frontier(sweep)
        frontiers[f"{t:.0f} min/event"] = frontier
    param_name = "Cloud Processing Time per Event"

else:  # Pricing Model
    # On-demand
    model_od = CloudCostModel(cost_per_hour=0.526, use_spot=False)
    sweep_od = generate_cloud_sweep(batch, site, model_od, max_cloud_containers=max_cloud)
    frontiers["On-Demand ($0.526/hr)"] = compute_pareto_frontier(sweep_od)

    # Spot
    model_spot = CloudCostModel(cost_per_hour=0.526, spot_cost_per_hour=0.16, use_spot=True)
    sweep_spot = generate_cloud_sweep(batch, site, model_spot, max_cloud_containers=max_cloud)
    frontiers["Spot ($0.16/hr)"] = compute_pareto_frontier(sweep_spot)

    # Reserved (estimated)
    model_reserved = CloudCostModel(cost_per_hour=0.33, use_spot=False)
    sweep_reserved = generate_cloud_sweep(batch, site, model_reserved, max_cloud_containers=max_cloud)
    frontiers["Reserved ($0.33/hr)"] = compute_pareto_frontier(sweep_reserved)

    param_name = "AWS Pricing Model"

# --- Display ---
fig = create_sensitivity_chart(frontiers, param_name=param_name)
st.plotly_chart(fig, use_container_width=True)

# Summary table
st.subheader("Frontier Comparison")

import pandas as pd

rows = []
for label, points in frontiers.items():
    optimal = [p for p in points if p.is_pareto_optimal]
    if not optimal:
        continue
    baseline = next((p for p in optimal if p.cost == 0), optimal[0])
    cheapest = min(optimal, key=lambda p: p.cost)
    fastest = min(optimal, key=lambda p: p.time)

    rows.append({
        "Scenario": label,
        "Pareto Points": len(optimal),
        "Baseline Time (hrs)": f"{baseline.time / 3600:.1f}",
        "Fastest (hrs)": f"{fastest.time / 3600:.1f}",
        "Cost at Fastest": f"${fastest.cost:.2f}",
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# Key insight
st.divider()
st.subheader("Cloud Cost Model Assumptions")
st.markdown(f"""
| Parameter | Value | Source |
|-----------|-------|--------|
| Instance Type | g4dn.xlarge (T4 GPU) | AWS pricing page |
| On-Demand Rate | $0.526/hr | AWS us-east-1 |
| Spot Rate | ~$0.16/hr | AWS spot history |
| Processing Time | 23 min/event (mean) | 15-event T4 pilot (range 7.5–46 min) |
| Container Startup | 30 sec | Estimated |
| Data Transfer | 60 sec/event | Estimated (S3 download) |
| Transfer Cost | $0.02/event | S3 pricing |

**Note:** Cloud processing is ~2.4x slower per-event than on-prem (T4 vs RTX 4000 Ada),
but adds parallel capacity. The real value is reducing batch turnaround by distributing
the workload across more processors.
""")
