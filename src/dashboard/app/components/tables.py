"""Data table components for the dashboard."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List

import pandas as pd
import streamlit as st

from data.schemas import C3DVerificationResult, ProcessingJob


def display_job_table(jobs: List[ProcessingJob], show_details: bool = True) -> None:
    """
    Display a table of processing jobs.

    Args:
        jobs: List of ProcessingJob objects
        show_details: Whether to show all columns or simplified view
    """
    if not jobs:
        st.info("No jobs to display")
        return

    # Convert to DataFrame
    data = []
    for job in jobs:
        row = {
            "Job ID": job.job_id[:8] + "...",
            "Team": job.team_name,
            "Venue": job.venue,
            "Status": job.status.value.upper(),
            "Priority": job.priority.value.upper(),
            "Pitches": job.total_pitches,
            "Cameras": job.camera_count,
        }
        if show_details:
            row["Queued"] = job.queued_at.strftime("%Y-%m-%d %H:%M")
            if job.started_at:
                row["Started"] = job.started_at.strftime("%H:%M")
            else:
                row["Started"] = "-"

        data.append(row)

    df = pd.DataFrame(data)

    # Style the status column
    def style_status(val: str) -> str:
        colors = {
            "QUEUED": "background-color: #f39c12; color: white",
            "PROCESSING": "background-color: #3498db; color: white",
            "COMPLETED": "background-color: #2ecc71; color: white",
            "FAILED": "background-color: #e74c3c; color: white",
        }
        return colors.get(val, "")

    def style_priority(val: str) -> str:
        colors = {
            "LOW": "color: #7f8c8d",
            "NORMAL": "color: #2c3e50",
            "HIGH": "color: #e67e22; font-weight: bold",
            "CRITICAL": "color: #e74c3c; font-weight: bold",
        }
        return colors.get(val, "")

    styled_df = df.style.applymap(
        style_status, subset=["Status"]
    ).applymap(style_priority, subset=["Priority"])

    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def display_verification_table(
    verifications: List[C3DVerificationResult],
) -> None:
    """
    Display a table of C3D verification results.

    Args:
        verifications: List of C3DVerificationResult objects
    """
    if not verifications:
        st.info("No verification results to display")
        return

    data = []
    for v in verifications:
        data.append(
            {
                "Job ID": v.job_id[:8] + "...",
                "On-Prem Hash": v.on_premises_hash[:12] + "...",
                "Cloud Hash": v.cloud_hash[:12] + "...",
                "Match": "PASS" if v.hashes_match else "FAIL",
                "RMSE (mm)": f"{v.trajectory_rmse:.4f}",
                "Within Tolerance": "Yes" if v.is_within_tolerance else "No",
            }
        )

    df = pd.DataFrame(data)

    def style_match(val: str) -> str:
        if val == "PASS":
            return "background-color: #2ecc71; color: white; font-weight: bold"
        return "background-color: #e74c3c; color: white; font-weight: bold"

    styled_df = df.style.applymap(style_match, subset=["Match"])

    st.dataframe(styled_df, use_container_width=True, hide_index=True)
