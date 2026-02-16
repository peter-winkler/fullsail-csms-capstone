"""Site Comparison - Compare Pareto frontiers across GPU configurations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from components.charts import create_multi_site_chart
from config import settings
from data.loaders import (
    INSTANCE_TYPES,
    PRICING_LABELS,
    PRICING_MODES,
    PRESET_SITE_PROFILES,
    load_onprem_results,
    sample_game_batch,
)
from data.schemas import CloudCostModel
from optimization.pareto import compute_pareto_frontier, generate_cloud_sweep

st.set_page_config(page_title="Site Comparison", page_icon=":bar_chart:", layout="wide")

st.title(":bar_chart: Site Comparison")
st.markdown(
    "Compare Pareto frontiers across different MLB site GPU configurations. "
    "GPU-poor sites benefit most from cloud acceleration; GPU-rich sites see diminishing returns."
)


@st.cache_data
def load_events():
    return load_onprem_results()


events = load_events()

# --- Sidebar ---
st.sidebar.header("Comparison Settings")

batch_size = st.sidebar.slider("Batch Size", 100, 1200, settings.default_batch_size, step=50)
max_cloud = st.sidebar.slider("Max Cloud Containers", 5, 100, settings.default_max_cloud, step=5)
x_axis = st.sidebar.radio("X-Axis", ["Cloud Containers Added", "Additional Cloud Cost ($)"], index=0)

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

st.sidebar.divider()
st.sidebar.subheader("Select Sites")

selected_sites = st.sidebar.multiselect(
    "Sites to Compare",
    [s.name for s in PRESET_SITE_PROFILES],
    default=[s.name for s in PRESET_SITE_PROFILES[:4]],
)

cloud_model = CloudCostModel.from_instance(selected_instance, pricing_tier)
batch = sample_game_batch(events, batch_size)

# --- Generate frontiers for each selected site ---
site_frontiers = {}
site_details = []

for profile in PRESET_SITE_PROFILES:
    if profile.name not in selected_sites:
        continue

    sweep = generate_cloud_sweep(batch, profile, cloud_model, max_cloud_containers=max_cloud)
    frontier = compute_pareto_frontier(sweep)

    label = f"{profile.name} ({profile.available_gpus} GPUs)"
    site_frontiers[label] = (frontier, profile.tier)

    optimal_points = [p for p in frontier if p.is_pareto_optimal]
    baseline = next((p for p in frontier if p.cost == 0), None)
    best_time = min(p.time for p in frontier) if frontier else 0

    site_details.append({
        "Site": profile.name,
        "GPUs": profile.available_gpus,
        "Tier": profile.tier.replace("_", " ").title(),
        "Baseline (hrs)": f"{baseline.time / 3600:.1f}" if baseline else "N/A",
        "Best (hrs)": f"{best_time / 3600:.1f}",
        "Pareto Points": len(optimal_points),
    })

# --- Display ---
gpu_label = selected_instance.gpu
pricing_label = PRICING_LABELS[pricing_tier]
st.caption(f"Cloud: {gpu_label} | {pricing_label} (${selected_instance.rate_for_pricing(pricing_tier):.3f}/hr)")

if site_frontiers:
    x_mode = "containers" if x_axis == "Cloud Containers Added" else "cost"
    fig = create_multi_site_chart(site_frontiers, x_mode=x_mode)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Site Summary")
    import pandas as pd
    st.dataframe(pd.DataFrame(site_details), use_container_width=True, hide_index=True)

    if len(site_details) >= 2:
        poorest = min(site_details, key=lambda s: s["GPUs"])
        richest = max(site_details, key=lambda s: s["GPUs"])
        st.info(
            f"**Key Insight:** {poorest['Site']} ({poorest['GPUs']} GPUs) has "
            f"{poorest['Pareto Points']} trade-off options, while "
            f"{richest['Site']} ({richest['GPUs']} GPUs) has only "
            f"{richest['Pareto Points']}. GPU-rich sites already process "
            f"batches quickly and gain little from additional cloud capacity."
        )
else:
    st.warning("Select at least one site to compare.")
