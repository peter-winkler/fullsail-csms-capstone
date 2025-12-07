"""C3D Verification Page - Verify output equivalence between systems."""

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from components.tables import display_verification_table
from config import settings
from data import generate_c3d_verification, generate_event_queue
from data.schemas import JobStatus

st.set_page_config(
    page_title="C3D Verification - KinaTrax",
    page_icon=":white_check_mark:",
    layout="wide",
)

st.title(":white_check_mark: C3D Output Verification")
st.markdown(
    """
Verify that C3D biomechanical output files are **identical** between on-premises
and cloud processing. This ensures that the decision support system does not
compromise the accuracy of biomechanical analysis.

**C3D Format**: Standard biomechanics file format containing:
- 3D marker trajectories
- Joint angles and constraints
- Force plate data
- Analog signals
"""
)

# Initialize data
if "queue_data" not in st.session_state:
    st.session_state.queue_data = generate_event_queue(settings.default_queue_size)

# Get completed jobs for verification
completed_jobs = [
    j for j in st.session_state.queue_data if j.status == JobStatus.COMPLETED
]

# Generate verification results
verifications = [generate_c3d_verification(j.job_id) for j in completed_jobs]

# If no completed jobs, generate some sample verifications
if not verifications:
    sample_jobs = generate_event_queue(10)
    verifications = [generate_c3d_verification(j.job_id) for j in sample_jobs[:5]]

# Summary metrics
st.subheader("Verification Summary")

col1, col2, col3, col4 = st.columns(4)

total = len(verifications)
passed = len([v for v in verifications if v.hashes_match])
avg_rmse = sum(v.trajectory_rmse for v in verifications) / total if total > 0 else 0
within_tolerance = len([v for v in verifications if v.is_within_tolerance])

with col1:
    st.metric("Total Verified", total)

with col2:
    st.metric(
        "Hash Match Rate",
        f"{(passed / total * 100):.1f}%" if total > 0 else "N/A",
    )

with col3:
    st.metric("Avg RMSE", f"{avg_rmse:.4f} mm")

with col4:
    st.metric(
        "Within Tolerance",
        f"{(within_tolerance / total * 100):.1f}%" if total > 0 else "N/A",
    )

# Overall status
st.divider()

if passed == total and total > 0:
    st.success(
        f"""
    :white_check_mark: **All {total} jobs passed verification!**

    C3D outputs from cloud processing are identical to on-premises processing.
    The decision support system maintains 100% accuracy.
    """
    )
else:
    failed = total - passed
    st.error(
        f"""
    :x: **{failed} of {total} jobs failed verification!**

    Some C3D outputs differ between cloud and on-premises processing.
    Investigation required.
    """
    )

# Verification table
st.divider()
st.subheader("Verification Results")
display_verification_table(verifications)

# Technical details
st.divider()

with st.expander("Technical Details"):
    st.markdown(
        """
    ### Verification Process

    1. **Hash Comparison**: SHA-256 hash of C3D file content
       - Files must be byte-for-byte identical
       - Any difference indicates processing discrepancy

    2. **Marker Count Verification**: Number of tracked markers
       - Both systems must track the same markers
       - Missing markers indicate tracking failure

    3. **Frame Count Verification**: Number of frames processed
       - Both systems must process same frame count
       - Differences indicate timing/sync issues

    4. **Trajectory RMSE**: Root Mean Square Error of marker positions
       - Measures positional accuracy in millimeters
       - Tolerance: < 0.1mm for production use

    ### Tolerance Thresholds

    | Metric | Tolerance | Status |
    |--------|-----------|--------|
    | Hash Match | Identical | Required |
    | Marker Count | Equal | Required |
    | Frame Count | Equal | Required |
    | Trajectory RMSE | < 0.1mm | Required |
    """
    )

# Refresh button
st.divider()
if st.button("Refresh Verification Data"):
    st.session_state.queue_data = generate_event_queue(settings.default_queue_size)
    st.rerun()
