"""C3D file parsing and comparison utilities."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import ezc3d
import numpy as np


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
class EquivalenceResult:
    """Four-level equivalence assessment for C3D files processed on different GPUs.

    cuDNN non-determinism in convolution kernel selection means C3D files will
    almost never be byte-identical across GPU architectures (or even same GPU).
    This checks structural, statistical, and clinical equivalence instead.
    """

    structural_match: bool  # Same frame count, frame rate, labels
    mean_abs_diff_mm: float  # Mean absolute difference across all frames
    p95_max_diff_mm: float  # 95th percentile of per-frame max differences
    statistical_pass: bool  # mean_abs_diff < 1.0mm
    clinical_pass: bool  # p95_max_diff < 5.0mm
    is_equivalent: bool  # structural AND statistical AND clinical all pass
    frame_diffs: List[float] = field(default_factory=list)  # Per-frame max diffs


@dataclass
class ComparisonResult:
    """Result of comparing two C3D files."""
    # "byte_identical", "equivalent", "divergent", "structural_mismatch",
    # "missing_onprem", "missing_cloud", "error"
    status: str
    hash_match: Optional[bool]
    onprem_metadata: Optional[C3DMetadata]
    cloud_metadata: Optional[C3DMetadata]
    differences: List[str]
    error_message: Optional[str] = None
    equivalence: Optional[EquivalenceResult] = None


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


def _extract_all_values(c3d_data) -> Optional[np.ndarray]:
    """Extract per-frame numeric values from a C3D object for comparison.

    Returns array of shape (n_frames, n_values) or None if no data found.
    Handles both standard point data and KinaTrax rotation matrix format.
    """
    header = c3d_data["header"]
    n_frames = header["points"]["last_frame"] - header["points"]["first_frame"] + 1
    if n_frames == 0:
        return None

    # Try standard point markers first
    n_markers = header["points"]["size"]
    if n_markers > 0:
        points = c3d_data["data"]["points"]  # (4, n_markers, n_frames)
        # Flatten x,y,z for each marker into (n_frames, n_markers*3)
        return np.stack([
            points[0, :, :].T,  # x: (n_frames, n_markers)
            points[1, :, :].T,  # y
            points[2, :, :].T,  # z
        ], axis=-1).reshape(n_frames, -1)

    # Try KinaTrax rotation matrices
    if "rotations" in c3d_data["data"]:
        rotations = c3d_data["data"]["rotations"]  # (4, 4, n_segments, n_frames)
        if rotations.shape[2] > 0:
            n_segments = rotations.shape[2]
            # Flatten all 16 matrix elements per segment into (n_frames, n_segments*16)
            return rotations.reshape(16, n_segments, n_frames).transpose(2, 1, 0).reshape(n_frames, -1)

    return None


def compute_frame_differences(
    onprem_path: Path, cloud_path: Path
) -> Optional[EquivalenceResult]:
    """Compute per-frame differences between two C3D files.

    Args:
        onprem_path: Path to on-premises C3D file
        cloud_path: Path to cloud-processed C3D file

    Returns:
        EquivalenceResult with structural match, statistics, and per-frame diffs,
        or None if files can't be compared (different structure).
    """
    try:
        c3d_onprem = ezc3d.c3d(str(onprem_path))
        c3d_cloud = ezc3d.c3d(str(cloud_path))
    except Exception:
        return None

    h_on = c3d_onprem["header"]
    h_cl = c3d_cloud["header"]

    frames_on = h_on["points"]["last_frame"] - h_on["points"]["first_frame"] + 1
    frames_cl = h_cl["points"]["last_frame"] - h_cl["points"]["first_frame"] + 1

    structural_match = (
        frames_on == frames_cl
        and h_on["points"]["frame_rate"] == h_cl["points"]["frame_rate"]
        and h_on["points"]["size"] == h_cl["points"]["size"]
    )

    if not structural_match:
        return EquivalenceResult(
            structural_match=False,
            mean_abs_diff_mm=float("inf"),
            p95_max_diff_mm=float("inf"),
            statistical_pass=False,
            clinical_pass=False,
            is_equivalent=False,
        )

    vals_on = _extract_all_values(c3d_onprem)
    vals_cl = _extract_all_values(c3d_cloud)

    if vals_on is None or vals_cl is None:
        return EquivalenceResult(
            structural_match=True,
            mean_abs_diff_mm=0.0,
            p95_max_diff_mm=0.0,
            statistical_pass=True,
            clinical_pass=True,
            is_equivalent=True,
        )

    # Per-frame max absolute difference
    abs_diff = np.abs(vals_on - vals_cl)
    frame_max_diffs = abs_diff.max(axis=1)  # (n_frames,)

    mean_abs = float(frame_max_diffs.mean())
    p95 = float(np.percentile(frame_max_diffs, 95))

    statistical_pass = mean_abs < 1.0
    clinical_pass = p95 < 5.0

    return EquivalenceResult(
        structural_match=True,
        mean_abs_diff_mm=mean_abs,
        p95_max_diff_mm=p95,
        statistical_pass=statistical_pass,
        clinical_pass=clinical_pass,
        is_equivalent=structural_match and statistical_pass and clinical_pass,
        frame_diffs=frame_max_diffs.tolist(),
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
            status="byte_identical",
            hash_match=True,
            onprem_metadata=onprem_meta,
            cloud_metadata=cloud_meta,
            differences=[],
        )

    # Hashes differ — check structural match first
    structural_diffs = []
    if onprem_meta.point_count != cloud_meta.point_count:
        structural_diffs.append(f"Point count: {onprem_meta.point_count} vs {cloud_meta.point_count}")
    if onprem_meta.frame_count != cloud_meta.frame_count:
        structural_diffs.append(f"Frame count: {onprem_meta.frame_count} vs {cloud_meta.frame_count}")
    if onprem_meta.frame_rate != cloud_meta.frame_rate:
        structural_diffs.append(f"Frame rate: {onprem_meta.frame_rate} vs {cloud_meta.frame_rate}")
    if set(onprem_meta.marker_labels) != set(cloud_meta.marker_labels):
        structural_diffs.append("Marker labels differ")

    if structural_diffs:
        return ComparisonResult(
            status="structural_mismatch",
            hash_match=False,
            onprem_metadata=onprem_meta,
            cloud_metadata=cloud_meta,
            differences=structural_diffs,
        )

    # Structure matches — run quantitative equivalence analysis
    equiv = compute_frame_differences(onprem_path, cloud_path)

    if equiv and equiv.is_equivalent:
        return ComparisonResult(
            status="equivalent",
            hash_match=False,
            onprem_metadata=onprem_meta,
            cloud_metadata=cloud_meta,
            differences=[],
            equivalence=equiv,
        )

    return ComparisonResult(
        status="divergent",
        hash_match=False,
        onprem_metadata=onprem_meta,
        cloud_metadata=cloud_meta,
        differences=["Exceeds equivalence tolerance"],
        equivalence=equiv,
    )
