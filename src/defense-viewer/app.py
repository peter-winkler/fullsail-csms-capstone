"""Defense Data Viewer - C3D Verification Tool for Thesis Defense."""

import time
import streamlit as st
from pathlib import Path

from file_browser import (
    list_teams,
    list_sessions,
    list_event_types,
    list_events,
    list_cameras,
    get_c3d_path,
    get_video_path,
)
from c3d_parser import compare_c3d_files, extract_point_data
import plotly.graph_objects as go

# Configuration - Data paths (update these to match your data location)
DATA_BASE = Path("/home/peter/vault/01-Education/FullSail-CSMS/Capstone-Project/data")
ON_PREM_ROOT = DATA_BASE / "samples"
CLOUD_ROOT = DATA_BASE / "cloud-results"

st.set_page_config(
    page_title="KinaTrax C3D Verification",
    page_icon="✓",
    layout="wide",
)

st.title("KinaTrax C3D Verification Viewer")
st.markdown("*Compare on-premises vs cloud processing results*")

# Sidebar - Navigation
st.sidebar.header("Select Data")

# Team selection
teams = list_teams(ON_PREM_ROOT)
if not teams:
    st.error(f"No data found in {ON_PREM_ROOT}")
    st.stop()

selected_team = st.sidebar.selectbox("Team", teams)

# Session selection
sessions = list_sessions(ON_PREM_ROOT, selected_team)
if not sessions:
    st.sidebar.warning("No sessions found for this team")
    st.stop()

selected_session = st.sidebar.selectbox("Session", sessions)

# Event type selection
event_types = list_event_types(ON_PREM_ROOT, selected_team, selected_session)
if not event_types:
    st.sidebar.warning("No event types found")
    st.stop()

selected_event_type = st.sidebar.selectbox("Event Type", event_types)

# Event selection
events = list_events(ON_PREM_ROOT, selected_team, selected_session, selected_event_type)
if not events:
    st.sidebar.warning("No events found")
    st.stop()

selected_event = st.sidebar.selectbox("Event", events)

# Sidebar - File Status
st.sidebar.markdown("---")
st.sidebar.header("File Status")

onprem_c3d = get_c3d_path(ON_PREM_ROOT, selected_team, selected_session, selected_event_type, selected_event)
cloud_c3d = get_c3d_path(CLOUD_ROOT, selected_team, selected_session, selected_event_type, selected_event)

if onprem_c3d and onprem_c3d.exists():
    st.sidebar.success("✓ On-Prem: Found")
else:
    st.sidebar.error("✗ On-Prem: Not found")

if cloud_c3d and cloud_c3d.exists():
    st.sidebar.success("✓ Cloud: Found")
else:
    st.sidebar.warning("⚠ Cloud: Not found")

# Main content
col1, col2 = st.columns([1, 1])

# Video Player
with col1:
    st.subheader("Video Preview")
    cameras = list_cameras(ON_PREM_ROOT, selected_team, selected_session, selected_event_type, selected_event)
    if cameras:
        selected_camera = st.selectbox("Camera", cameras, key="camera_select")
        video_path = get_video_path(ON_PREM_ROOT, selected_team, selected_session, selected_event_type, selected_event, selected_camera)
        if video_path and video_path.exists():
            st.video(str(video_path))
        else:
            st.info("No video available for this camera")
    else:
        st.info("No video available for this event")

# Verification Results
with col2:
    st.subheader("Verification Status")

    if onprem_c3d and cloud_c3d:
        result = compare_c3d_files(onprem_c3d, cloud_c3d)

        if result.status == "match":
            st.success("✓ **MATCH** - Files are identical")
            st.metric("Hash Match", "YES")
        elif result.status == "mismatch":
            st.error("✗ **MISMATCH** - Files differ")
            for diff in result.differences:
                st.write(f"- {diff}")
        elif result.status == "missing_cloud":
            st.warning("⚠ Cloud file not yet processed")
        else:
            st.error(f"Error: {result.error_message}")

        # Detailed comparison (expandable)
        if result.onprem_metadata:
            with st.expander("Detailed Comparison"):
                import pandas as pd

                onprem = result.onprem_metadata
                cloud = result.cloud_metadata

                data = {
                    "Metric": ["MD5 Hash", "File Size", "Point Count", "Frame Count", "Frame Rate", "First Frame", "Last Frame", "Analog Channels"],
                    "On-Premises": [
                        onprem.md5_hash[:16] + "...",
                        f"{onprem.file_size_bytes:,} bytes",
                        str(onprem.point_count),
                        str(onprem.frame_count),
                        f"{onprem.frame_rate} Hz",
                        str(onprem.first_frame),
                        str(onprem.last_frame),
                        str(onprem.analog_channel_count),
                    ],
                    "Cloud": [
                        (cloud.md5_hash[:16] + "...") if cloud else "N/A",
                        f"{cloud.file_size_bytes:,} bytes" if cloud else "N/A",
                        str(cloud.point_count) if cloud else "N/A",
                        str(cloud.frame_count) if cloud else "N/A",
                        f"{cloud.frame_rate} Hz" if cloud else "N/A",
                        str(cloud.first_frame) if cloud else "N/A",
                        str(cloud.last_frame) if cloud else "N/A",
                        str(cloud.analog_channel_count) if cloud else "N/A",
                    ],
                    "Match": [
                        "✓" if cloud and onprem.md5_hash == cloud.md5_hash else "✗",
                        "✓" if cloud and onprem.file_size_bytes == cloud.file_size_bytes else "✗",
                        "✓" if cloud and onprem.point_count == cloud.point_count else "✗",
                        "✓" if cloud and onprem.frame_count == cloud.frame_count else "✗",
                        "✓" if cloud and onprem.frame_rate == cloud.frame_rate else "✗",
                        "✓" if cloud and onprem.first_frame == cloud.first_frame else "✗",
                        "✓" if cloud and onprem.last_frame == cloud.last_frame else "✗",
                        "✓" if cloud and onprem.analog_channel_count == cloud.analog_channel_count else "✗",
                    ]
                }

                df = pd.DataFrame(data)
                st.dataframe(df, width="stretch", hide_index=True)

                # Marker labels
                st.markdown("**Marker Labels:**")
                st.text(", ".join(onprem.marker_labels[:20]) + ("..." if len(onprem.marker_labels) > 20 else ""))
    else:
        if not onprem_c3d:
            st.error("On-premises C3D file not found")
        if not cloud_c3d:
            st.info("Cloud C3D file not yet available. Process this event in AWS first.")

# 3D Skeleton Visualization
st.markdown("---")
st.subheader("3D Skeleton View")

# KinaTrax skeleton bone connections
BONES = [
    # Spine
    ("HIPS", "JSPI"), ("JSPI", "SPIN"), ("SPIN", "NECK"),
    ("NECK", "JHEA"), ("JHEA", "HEAD"),
    # Left arm
    ("SPIN", "JLUA"), ("JLUA", "LUAR"), ("LUAR", "LFAR"),
    ("LFAR", "LWRI"), ("LWRI", "LHND"),
    # Right arm
    ("SPIN", "JRUA"), ("JRUA", "RUAR"), ("RUAR", "RFAR"),
    ("RFAR", "RWRI"), ("RWRI", "RHND"),
    # Left leg
    ("HIPS", "JLTH"), ("JLTH", "LTHI"), ("LTHI", "LSHI"),
    ("LSHI", "LANK"), ("LANK", "LFOO"),
    # Right leg
    ("HIPS", "JRTH"), ("JRTH", "RTHI"), ("RTHI", "RSHI"),
    ("RSHI", "RANK"), ("RANK", "RFOO"),
]

if onprem_c3d and onprem_c3d.exists():
    from c3d_parser import extract_c3d_metadata
    try:
        metadata = extract_c3d_metadata(onprem_c3d)

        if metadata.frame_count > 0:
            frame_step = 5  # Skip frames for performance

            # Limit total frames for performance
            max_frames = min(metadata.frame_count, 500)
            frame_indices = list(range(0, max_frames, frame_step))

            with st.spinner(f"Loading {len(frame_indices)} frames..."):
                # Collect all frame data
                all_frames_data = []
                for f_idx in frame_indices:
                    point_data = extract_point_data(onprem_c3d, f_idx)
                    if point_data and len(point_data.x) > 0:
                        all_frames_data.append((f_idx, point_data))

            if all_frames_data:
                # Build initial frame
                first_frame_idx, first_data = all_frames_data[0]
                label_to_idx = {label: i for i, label in enumerate(first_data.labels)}

                def build_bone_coords(point_data, label_to_idx):
                    bone_x, bone_y, bone_z = [], [], []
                    for start, end in BONES:
                        if start in label_to_idx and end in label_to_idx:
                            i, j = label_to_idx[start], label_to_idx[end]
                            bone_x.extend([point_data.x[i], point_data.x[j], None])
                            bone_y.extend([point_data.y[i], point_data.y[j], None])
                            bone_z.extend([point_data.z[i], point_data.z[j], None])
                    return bone_x, bone_y, bone_z

                bone_x, bone_y, bone_z = build_bone_coords(first_data, label_to_idx)

                # Create figure with initial data
                fig = go.Figure()

                # Bones trace
                fig.add_trace(go.Scatter3d(
                    x=bone_x, y=bone_y, z=bone_z,
                    mode="lines",
                    line=dict(color="cyan", width=4),
                    hoverinfo="skip",
                    name="Skeleton",
                ))

                # Joints trace
                fig.add_trace(go.Scatter3d(
                    x=first_data.x,
                    y=first_data.y,
                    z=first_data.z,
                    mode="markers",
                    marker=dict(size=3, color="red"),
                    text=first_data.labels,
                    hovertemplate="<b>%{text}</b><br>X: %{x:.1f}<br>Y: %{y:.1f}<br>Z: %{z:.1f}<extra></extra>",
                    name="Joints",
                ))

                # Build animation frames
                frames = []
                for f_idx, point_data in all_frames_data:
                    bone_x, bone_y, bone_z = build_bone_coords(point_data, label_to_idx)
                    frames.append(go.Frame(
                        data=[
                            go.Scatter3d(x=bone_x, y=bone_y, z=bone_z),
                            go.Scatter3d(x=point_data.x, y=point_data.y, z=point_data.z),
                        ],
                        name=str(f_idx)
                    ))

                fig.frames = frames

                # Animation controls
                fig.update_layout(
                    scene=dict(
                        aspectmode="data",
                        xaxis=dict(visible=False, showgrid=False, showticklabels=False, title=""),
                        yaxis=dict(visible=False, showgrid=False, showticklabels=False, title=""),
                        zaxis=dict(visible=False, showgrid=False, showticklabels=False, title=""),
                        camera=dict(
                            up=dict(x=0, y=-1, z=0),
                            eye=dict(x=1.5, y=-0.5, z=1.5),
                        ),
                    ),
                    margin=dict(l=0, r=0, t=30, b=0),
                    height=550,
                    showlegend=False,
                    updatemenus=[dict(
                        type="buttons",
                        showactive=False,
                        y=0,
                        x=0.1,
                        xanchor="right",
                        buttons=[
                            dict(label="Play",
                                 method="animate",
                                 args=[None, dict(frame=dict(duration=30, redraw=True),
                                                  fromcurrent=True,
                                                  mode="immediate")]),
                            dict(label="Pause",
                                 method="animate",
                                 args=[[None], dict(frame=dict(duration=0, redraw=False),
                                                    mode="immediate")]),
                        ]
                    )],
                    sliders=[dict(
                        active=0,
                        steps=[dict(args=[[str(f_idx)],
                                          dict(frame=dict(duration=0, redraw=True),
                                               mode="immediate")],
                                    label=str(f_idx),
                                    method="animate")
                               for f_idx, _ in all_frames_data],
                        x=0.1,
                        len=0.9,
                        xanchor="left",
                        y=0,
                        currentvalue=dict(prefix="Frame: ", visible=True, xanchor="right"),
                        transition=dict(duration=0),
                    )]
                )

                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"{len(all_frames_data)} frames loaded (step={frame_step}) | {len(first_data.labels)} segments")
            else:
                st.info("No valid marker positions found")
        else:
            st.info("This C3D file has no frame data (may be a calibration file)")
    except Exception as e:
        st.error(f"Error loading 3D data: {e}")
else:
    st.info("Select an event to view 3D skeleton data")
