import pytest
from pathlib import Path
from file_browser import list_teams, list_sessions, list_event_types, list_events, get_c3d_path, get_video_path

DATA_ROOT = Path("/home/peter/vault/01-Education/FullSail-CSMS/Capstone-Project/data/samples")

def test_list_teams():
    """Should return list of team directories."""
    if not DATA_ROOT.exists():
        pytest.skip("Sample data not available")

    teams = list_teams(DATA_ROOT)

    assert isinstance(teams, list)
    assert len(teams) > 0
    assert "ARI" in teams

def test_list_sessions():
    """Should return sessions for a team."""
    if not DATA_ROOT.exists():
        pytest.skip("Sample data not available")

    sessions = list_sessions(DATA_ROOT, "ARI")

    assert isinstance(sessions, list)
    assert len(sessions) > 0

def test_list_event_types():
    """Should return Batting and/or Pitching."""
    if not DATA_ROOT.exists():
        pytest.skip("Sample data not available")

    sessions = list_sessions(DATA_ROOT, "ARI")
    if not sessions:
        pytest.skip("No sessions available")

    event_types = list_event_types(DATA_ROOT, "ARI", sessions[0])

    assert isinstance(event_types, list)
    assert any(et in event_types for et in ["Batting", "Pitching"])

def test_list_events():
    """Should return events with C3D files."""
    if not DATA_ROOT.exists():
        pytest.skip("Sample data not available")

    sessions = list_sessions(DATA_ROOT, "ARI")
    event_types = list_event_types(DATA_ROOT, "ARI", sessions[0])
    if not event_types:
        pytest.skip("No event types available")

    events = list_events(DATA_ROOT, "ARI", sessions[0], event_types[0])

    assert isinstance(events, list)
    assert len(events) > 0

def test_get_c3d_path():
    """Should return path to C3D file."""
    if not DATA_ROOT.exists():
        pytest.skip("Sample data not available")

    sessions = list_sessions(DATA_ROOT, "ARI")
    event_types = list_event_types(DATA_ROOT, "ARI", sessions[0])
    events = list_events(DATA_ROOT, "ARI", sessions[0], event_types[0])

    c3d_path = get_c3d_path(DATA_ROOT, "ARI", sessions[0], event_types[0], events[0])

    assert c3d_path is not None
    assert c3d_path.suffix == ".c3d"
    assert c3d_path.exists()
