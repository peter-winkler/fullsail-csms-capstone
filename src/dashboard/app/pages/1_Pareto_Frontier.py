"""Pareto Frontier - Cost vs. Turnaround Trade-off Analysis."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from components.charts import (
    INSTANCE_GPU_LABELS,
    create_multi_instance_pareto_chart,
    create_pareto_chart,
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
from optimization.pareto import (
    compute_pareto_frontier,
    compute_pareto_frontier_multi,
    find_optimal_configuration,
    generate_cloud_sweep,
    generate_multi_instance_sweep,
)

st.set_page_config(page_title="Pareto Frontier", page_icon=":chart_with_upwards_trend:", layout="wide")

st.title(":chart_with_upwards_trend: Pareto Frontier Analysis")


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

st.sidebar.divider()
st.sidebar.subheader("Display Options")

x_axis = st.sidebar.radio("X-Axis", ["Additional Cloud Cost ($)", "Cloud Containers Added"], index=0)
x_mode = "containers" if x_axis == "Cloud Containers Added" else "cost"

# Multi-instance only makes sense with cost x-axis; containers x-axis
# stacks all GPU types at the same integer positions.
if x_mode == "cost":
    st.sidebar.divider()
    st.sidebar.subheader("Analysis Mode")

    analysis_mode = st.sidebar.radio(
        "View",
        ["Multi-Instance", "Single Instance"],
        help="Multi-Instance sweeps all GPU types and pricing tiers. "
             "Single Instance focuses on one GPU/pricing combination."
    )
else:
    analysis_mode = "Single Instance"

# Single-instance controls (only shown when relevant)
if analysis_mode == "Single Instance":
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

    effective_rate = selected_instance.rate_for_pricing(pricing_tier)
    st.sidebar.caption(
        f"Rate: ${effective_rate:.3f}/hr | "
        f"Ratio: {selected_instance.ratio:.3f}x on-prem"
    )

cost_weight = st.sidebar.slider(
    "Cost vs. Time Priority",
    0.0, 1.0, 0.5, step=0.05,
    help="0.0 = minimize time only, 1.0 = minimize cost only"
)

# --- Run simulation ---
batch = sample_game_batch(events, batch_size)

if analysis_mode == "Multi-Instance":
    st.markdown(
        "Sweep all GPU instance types, pricing tiers, and cloud container counts to find "
        "genuinely optimal configurations. ~91% of configurations are dominated."
    )

    with st.spinner("Running multi-instance sweep..."):
        raw_points = generate_multi_instance_sweep(
            batch, site, INSTANCE_TYPES, PRICING_MODES,
            max_cloud_containers=max_cloud,
        )
        all_points = compute_pareto_frontier_multi(raw_points)

    frontier_points = [p for p in all_points if p.is_pareto_optimal]
    dominated_points = [p for p in all_points if not p.is_pareto_optimal]
    optimal = find_optimal_configuration(all_points, cost_weight=cost_weight)

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Configs", len(all_points))
    with col2:
        st.metric("Frontier Points", len(frontier_points))
    with col3:
        dominated_pct = len(dominated_points) / len(all_points) * 100 if all_points else 0
        st.metric("Dominated", f"{dominated_pct:.0f}%")
    with col4:
        gpu_counts = {}
        for p in frontier_points:
            label = p.instance_type or "unknown"
            gpu_counts[label] = gpu_counts.get(label, 0) + 1
        if gpu_counts:
            top_gpu = max(gpu_counts, key=gpu_counts.get)
            top_label = INSTANCE_GPU_LABELS.get(top_gpu, top_gpu)
            st.metric("Top GPU", f"{top_label} ({gpu_counts[top_gpu]})")

    st.divider()

    fig = create_multi_instance_pareto_chart(
        all_points,
        title=f"Multi-Instance Pareto: {site.name} ({site.available_gpus} GPUs, {batch_size} events)",
        pricing_labels=PRICING_LABELS,
        x_mode=x_mode,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Frontier composition table
    st.subheader("Frontier Composition")

    frontier_rows = []
    for inst in INSTANCE_TYPES:
        for pricing in inst.available_pricing():
            count = sum(1 for p in frontier_points
                        if p.instance_type == inst.name and p.pricing_tier == pricing)
            if count > 0:
                rate = inst.rate_for_pricing(pricing)
                frontier_rows.append({
                    "GPU": inst.gpu,
                    "Instance": inst.name,
                    "Pricing": PRICING_LABELS[pricing],
                    "Rate ($/hr)": f"${rate:.3f}",
                    "Ratio": f"{inst.ratio:.3f}x",
                    "Frontier Points": count,
                })

    if frontier_rows:
        st.dataframe(pd.DataFrame(frontier_rows), use_container_width=True, hide_index=True)

    # GPU share summary
    if gpu_counts:
        st.subheader("GPU Share of Frontier")
        share_rows = []
        for inst in INSTANCE_TYPES:
            count = gpu_counts.get(inst.name, 0)
            pct = count / len(frontier_points) * 100 if frontier_points else 0
            share_rows.append({
                "GPU": inst.gpu,
                "Frontier Points": count,
                "Share": f"{pct:.1f}%",
            })
        st.dataframe(pd.DataFrame(share_rows), use_container_width=True, hide_index=True)

    # Recommendation
    if optimal:
        st.divider()
        st.subheader("Recommendation")
        baseline = next((p for p in all_points if p.cost == 0), None)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            gpu_label = INSTANCE_GPU_LABELS.get(optimal.instance_type or "", optimal.instance_type or "")
            pricing_label = PRICING_LABELS.get(optimal.pricing_tier or "", optimal.pricing_tier or "")
            st.metric("Config", f"{gpu_label} {pricing_label}")
        with col2:
            st.metric("Containers", optimal.cloud_containers)
        with col3:
            st.metric("Cloud Cost", f"${optimal.cost:.2f}")
        with col4:
            if baseline:
                time_saved = baseline.time - optimal.time
                st.metric("Time Saved", f"{time_saved / 3600:.1f} hrs",
                          delta=f"-{time_saved / baseline.time * 100:.0f}%")
            else:
                st.metric("Turnaround", f"{optimal.time / 3600:.1f} hrs")

else:
    # --- Single Instance mode ---
    gpu_label = selected_instance.gpu
    pricing_label = PRICING_LABELS[pricing_tier]
    st.markdown(
        f"Sweep cloud container count for **{gpu_label}** at **{pricing_label}** pricing "
        f"to visualize the cost vs. turnaround trade-off."
    )

    cloud_model = CloudCostModel.from_instance(selected_instance, pricing_tier)
    sweep = generate_cloud_sweep(batch, site, cloud_model, max_cloud_containers=max_cloud)
    frontier = compute_pareto_frontier(sweep)
    optimal = find_optimal_configuration(frontier, cost_weight=cost_weight)

    # Metrics row
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

    fig = create_pareto_chart(
        frontier, optimal=optimal,
        title=f"Cloud Acceleration: {site.name} ({site.available_gpus} GPUs) | {gpu_label} {pricing_label}",
        x_mode=x_mode,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Summary table
    st.subheader("Pareto-Optimal Configurations")
    optimal_points = sorted([p for p in frontier if p.is_pareto_optimal], key=lambda p: p.cost)

    df = pd.DataFrame([
        {
            "Config": p.config_id,
            "Containers": p.cloud_containers,
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
        col1, col2, col3 = st.columns(3)
        with col1:
            time_saved = baseline.time - optimal.time
            st.metric("Time Saved", f"{time_saved / 3600:.1f} hrs",
                      delta=f"-{time_saved / baseline.time * 100:.0f}%")
        with col2:
            st.metric("Additional Cost", f"${optimal.cost:.2f}")
        with col3:
            st.metric("Instance", f"{gpu_label} ({pricing_label})")
