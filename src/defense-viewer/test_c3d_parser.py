import pytest
import tempfile
from pathlib import Path
from c3d_parser import compute_file_hash, extract_c3d_metadata, C3DMetadata, compare_c3d_files, ComparisonResult, EquivalenceResult


# Unit tests with temporary files (always run)
def test_compute_file_hash_returns_md5_format():
    """Hash should be 32-char hex string."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content")
        temp_path = Path(f.name)

    try:
        result = compute_file_hash(temp_path)

        assert isinstance(result, str)
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)
    finally:
        temp_path.unlink()


def test_compute_file_hash_consistent_temp():
    """Same file should always produce same hash."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"consistent content")
        temp_path = Path(f.name)

    try:
        hash1 = compute_file_hash(temp_path)
        hash2 = compute_file_hash(temp_path)

        assert hash1 == hash2
    finally:
        temp_path.unlink()


def test_compute_file_hash_different_content():
    """Different content should produce different hashes."""
    with tempfile.NamedTemporaryFile(delete=False) as f1:
        f1.write(b"content one")
        temp_path1 = Path(f1.name)

    with tempfile.NamedTemporaryFile(delete=False) as f2:
        f2.write(b"content two")
        temp_path2 = Path(f2.name)

    try:
        hash1 = compute_file_hash(temp_path1)
        hash2 = compute_file_hash(temp_path2)

        assert hash1 != hash2
    finally:
        temp_path1.unlink()
        temp_path2.unlink()


def test_compute_file_hash_known_value():
    """Verify hash against known MD5 value."""
    # MD5 of "hello world" is 5eb63bbbe01eeed093cb22bb8f5acdc3
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"hello world")
        temp_path = Path(f.name)

    try:
        result = compute_file_hash(temp_path)
        assert result == "5eb63bbbe01eeed093cb22bb8f5acdc3"
    finally:
        temp_path.unlink()


# Integration tests with real C3D data (skip if not available)
# Sample data is at project root level (/home/peter/vault/01-Education/FullSail-CSMS/Capstone-Project/data/samples/ from src/defense-viewer/)
SAMPLE_C3D = Path("/home/peter/vault/01-Education/FullSail-CSMS/Capstone-Project/data/samples/ARI/2022/2022_07_18_22_33_29/Batting/2022_07_18_22_51_52_Arizona_Diamondbacks_Background/2022_07_18_22_51_52_Arizona_Diamondbacks_Background.c3d")


def test_compute_file_hash_returns_md5():
    """Hash should be 32-char hex string."""
    if not SAMPLE_C3D.exists():
        pytest.skip("Sample data not available")

    result = compute_file_hash(SAMPLE_C3D)

    assert isinstance(result, str)
    assert len(result) == 32
    assert all(c in "0123456789abcdef" for c in result)


def test_compute_file_hash_consistent():
    """Same file should always produce same hash."""
    if not SAMPLE_C3D.exists():
        pytest.skip("Sample data not available")

    hash1 = compute_file_hash(SAMPLE_C3D)
    hash2 = compute_file_hash(SAMPLE_C3D)

    assert hash1 == hash2


# Metadata extraction tests
def test_extract_c3d_metadata_returns_dataclass():
    """Should return C3DMetadata with expected fields."""
    if not SAMPLE_C3D.exists():
        pytest.skip("Sample data not available")

    result = extract_c3d_metadata(SAMPLE_C3D)

    assert isinstance(result, C3DMetadata)
    # point_count can be 0 for background/calibration files
    assert result.point_count >= 0
    # frame_count should be at least 1 for valid files
    assert result.frame_count >= 1
    # frame_rate can be 0 for background files
    assert result.frame_rate >= 0
    assert isinstance(result.marker_labels, list)


def test_extract_c3d_metadata_file_size():
    """File size should match actual file."""
    if not SAMPLE_C3D.exists():
        pytest.skip("Sample data not available")

    result = extract_c3d_metadata(SAMPLE_C3D)

    assert result.file_size_bytes == SAMPLE_C3D.stat().st_size


# Test with a pitching file that has more frame data
PITCHING_C3D = Path("/home/peter/vault/01-Education/FullSail-CSMS/Capstone-Project/data/samples/PHI/2024/2024_03_29_12_53_58/Pitching/2024_03_29_15_07_23_Philadelphia_Phillies_45_Zack_Wheeler_Home/2024_03_29_15_07_23_Philadelphia_Phillies_45_Zack_Wheeler_Home.c3d")


def test_extract_c3d_metadata_pitching_file():
    """Pitching file should have positive frame count and frame rate."""
    if not PITCHING_C3D.exists():
        pytest.skip("Pitching sample data not available")

    result = extract_c3d_metadata(PITCHING_C3D)

    assert isinstance(result, C3DMetadata)
    assert result.frame_count > 0
    assert result.frame_rate > 0
    assert result.file_path == str(PITCHING_C3D)
    assert len(result.md5_hash) == 32


# Comparison function tests
def test_compare_identical_files():
    """Comparing file to itself should return MATCH."""
    test_file = Path("/home/peter/vault/01-Education/FullSail-CSMS/Capstone-Project/data/samples/ARI/2022/2022_07_18_22_33_29/Batting/2022_07_18_22_51_52_Arizona_Diamondbacks_Background/2022_07_18_22_51_52_Arizona_Diamondbacks_Background.c3d")
    if not test_file.exists():
        pytest.skip("Sample data not available")

    result = compare_c3d_files(test_file, test_file)

    assert result.status == "byte_identical"
    assert result.hash_match is True
    assert len(result.differences) == 0


def test_compare_missing_file():
    """Missing file should return appropriate status."""
    test_file = Path("/home/peter/vault/01-Education/FullSail-CSMS/Capstone-Project/data/samples/ARI/2022/2022_07_18_22_33_29/Batting/2022_07_18_22_51_52_Arizona_Diamondbacks_Background/2022_07_18_22_51_52_Arizona_Diamondbacks_Background.c3d")
    missing_file = Path("nonexistent.c3d")

    if not test_file.exists():
        pytest.skip("Sample data not available")

    result = compare_c3d_files(test_file, missing_file)

    assert result.status == "missing_cloud"
