"""C3D file parsing and comparison utilities."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import ezc3d


def compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        32-character hex string of MD5 hash
    """
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


@dataclass
class C3DMetadata:
    """Metadata extracted from a C3D file."""

    file_path: str
    file_size_bytes: int
    md5_hash: str
    point_count: int
    frame_count: int
    frame_rate: float
    first_frame: int
    last_frame: int
    analog_channel_count: int
    marker_labels: List[str]


def extract_c3d_metadata(file_path: Path) -> C3DMetadata:
    """Extract metadata from a C3D file.

    Args:
        file_path: Path to the C3D file

    Returns:
        C3DMetadata dataclass with file information
    """
    c3d = ezc3d.c3d(str(file_path))

    header = c3d["header"]
    parameters = c3d["parameters"]

    # Get marker labels from POINT group
    marker_labels = []
    if "POINT" in parameters and "LABELS" in parameters["POINT"]:
        marker_labels = [label.strip() for label in parameters["POINT"]["LABELS"]["value"]]

    return C3DMetadata(
        file_path=str(file_path),
        file_size_bytes=file_path.stat().st_size,
        md5_hash=compute_file_hash(file_path),
        point_count=header["points"]["size"],
        frame_count=header["points"]["last_frame"] - header["points"]["first_frame"] + 1,
        frame_rate=header["points"]["frame_rate"],
        first_frame=header["points"]["first_frame"],
        last_frame=header["points"]["last_frame"],
        analog_channel_count=header["analogs"]["size"],
        marker_labels=marker_labels,
    )


@dataclass
class ComparisonResult:
    """Result of comparing two C3D files."""
    status: str  # "match", "mismatch", "missing_onprem", "missing_cloud", "error"
    hash_match: Optional[bool]
    onprem_metadata: Optional[C3DMetadata]
    cloud_metadata: Optional[C3DMetadata]
    differences: List[str]
    error_message: Optional[str] = None


@dataclass
class PointData:
    """3D point data for a single frame."""
    labels: List[str]
    x: List[float]
    y: List[float]
    z: List[float]
    frame: int
    total_frames: int


def extract_point_data(file_path: Path, frame: int = 0) -> Optional[PointData]:
    """Extract 3D positions for a specific frame.

    Handles both traditional marker data (points) and KinaTrax rotation matrices.

    Args:
        file_path: Path to the C3D file
        frame: Frame index to extract (0-based)

    Returns:
        PointData with positions, or None if no data
    """
    c3d = ezc3d.c3d(str(file_path))

    header = c3d["header"]
    parameters = c3d["parameters"]
    n_frames = header["points"]["last_frame"] - header["points"]["first_frame"] + 1

    if n_frames == 0:
        return None

    # Clamp frame to valid range
    frame = max(0, min(frame, n_frames - 1))

    valid_x, valid_y, valid_z, valid_labels = [], [], [], []

    # First try traditional point markers
    n_markers = header["points"]["size"]
    if n_markers > 0:
        points = c3d["data"]["points"]
        labels = []
        if "POINT" in parameters and "LABELS" in parameters["POINT"]:
            labels = [label.strip() for label in parameters["POINT"]["LABELS"]["value"]]

        for i in range(n_markers):
            x, y, z = points[0, i, frame], points[1, i, frame], points[2, i, frame]
            if (x != 0 or y != 0 or z != 0) and not (x != x):  # Skip invalid
                valid_x.append(float(x))
                valid_y.append(float(y))
                valid_z.append(float(z))
                valid_labels.append(labels[i] if i < len(labels) else f"M{i}")

    # If no point markers, try KinaTrax rotation matrices
    if not valid_x and "rotations" in c3d["data"]:
        rotations = c3d["data"]["rotations"]  # Shape: (4, 4, n_segments, n_frames)
        if rotations.shape[2] > 0:
            labels = []
            if "ROTATION" in parameters and "LABELS" in parameters["ROTATION"]:
                labels = [label.strip() for label in parameters["ROTATION"]["LABELS"]["value"]]

            n_segments = rotations.shape[2]
            for i in range(n_segments):
                # Position is in the translation column (index 3) of the 4x4 matrix
                x = rotations[0, 3, i, frame]
                y = rotations[1, 3, i, frame]
                z = rotations[2, 3, i, frame]
                if (x != 0 or y != 0 or z != 0) and not (x != x):
                    valid_x.append(float(x))
                    valid_y.append(float(y))
                    valid_z.append(float(z))
                    valid_labels.append(labels[i] if i < len(labels) else f"Seg{i}")

    if not valid_x:
        return None

    return PointData(
        labels=valid_labels,
        x=valid_x,
        y=valid_y,
        z=valid_z,
        frame=frame,
        total_frames=n_frames,
    )


def compare_c3d_files(onprem_path: Path, cloud_path: Path) -> ComparisonResult:
    """Compare two C3D files for equivalence.

    Uses hash-first approach: if hashes match, files are identical.

    Args:
        onprem_path: Path to on-premises C3D file
        cloud_path: Path to cloud-processed C3D file

    Returns:
        ComparisonResult with match status and any differences
    """
    # Check file existence
    if not onprem_path.exists():
        return ComparisonResult(
            status="missing_onprem",
            hash_match=None,
            onprem_metadata=None,
            cloud_metadata=None,
            differences=["On-premises file not found"],
        )

    if not cloud_path.exists():
        return ComparisonResult(
            status="missing_cloud",
            hash_match=None,
            onprem_metadata=extract_c3d_metadata(onprem_path),
            cloud_metadata=None,
            differences=["Cloud file not found"],
        )

    try:
        onprem_meta = extract_c3d_metadata(onprem_path)
        cloud_meta = extract_c3d_metadata(cloud_path)
    except Exception as e:
        return ComparisonResult(
            status="error",
            hash_match=None,
            onprem_metadata=None,
            cloud_metadata=None,
            differences=[],
            error_message=str(e),
        )

    # Hash-first comparison
    hash_match = onprem_meta.md5_hash == cloud_meta.md5_hash

    if hash_match:
        return ComparisonResult(
            status="match",
            hash_match=True,
            onprem_metadata=onprem_meta,
            cloud_metadata=cloud_meta,
            differences=[],
        )

    # If hashes differ, find specific differences
    differences = []
    if onprem_meta.point_count != cloud_meta.point_count:
        differences.append(f"Point count: {onprem_meta.point_count} vs {cloud_meta.point_count}")
    if onprem_meta.frame_count != cloud_meta.frame_count:
        differences.append(f"Frame count: {onprem_meta.frame_count} vs {cloud_meta.frame_count}")
    if onprem_meta.frame_rate != cloud_meta.frame_rate:
        differences.append(f"Frame rate: {onprem_meta.frame_rate} vs {cloud_meta.frame_rate}")
    if set(onprem_meta.marker_labels) != set(cloud_meta.marker_labels):
        differences.append("Marker labels differ")

    return ComparisonResult(
        status="mismatch",
        hash_match=False,
        onprem_metadata=onprem_meta,
        cloud_metadata=cloud_meta,
        differences=differences if differences else ["Files differ (hash mismatch)"],
    )
