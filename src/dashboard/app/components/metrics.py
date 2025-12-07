"""Metric display components for the dashboard."""

from typing import Optional

import streamlit as st


def display_metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: str = "normal",
    help_text: Optional[str] = None,
) -> None:
    """
    Display a single metric card.

    Args:
        label: Metric label
        value: Current value
        delta: Change from previous (optional)
        delta_color: "normal", "inverse", or "off"
        help_text: Tooltip text (optional)
    """
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help_text,
    )


def display_metric_row(
    metrics: list[dict],
    columns: int = 4,
) -> None:
    """
    Display a row of metric cards.

    Args:
        metrics: List of dicts with keys: label, value, delta (optional)
        columns: Number of columns to display
    """
    cols = st.columns(columns)

    for i, metric in enumerate(metrics):
        with cols[i % columns]:
            display_metric_card(
                label=metric.get("label", ""),
                value=metric.get("value", ""),
                delta=metric.get("delta"),
                delta_color=metric.get("delta_color", "normal"),
                help_text=metric.get("help"),
            )
