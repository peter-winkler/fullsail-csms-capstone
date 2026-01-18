"""File browser utilities for navigating data directories."""

from pathlib import Path
from typing import List, Optional


def list_teams(data_root: Path) -> List[str]:
    """List all team directories."""
    if not data_root.exists():
        return []
    return sorted([d.name for d in data_root.iterdir() if d.is_dir()])


def list_sessions(data_root: Path, team: str) -> List[str]:
    """List all sessions for a team (across all years)."""
    team_path = data_root / team
    if not team_path.exists():
        return []

    sessions = []
    for year_dir in team_path.iterdir():
        if year_dir.is_dir():
            for session_dir in year_dir.iterdir():
                if session_dir.is_dir():
                    sessions.append(f"{year_dir.name}/{session_dir.name}")
    return sorted(sessions)


def list_event_types(data_root: Path, team: str, session: str) -> List[str]:
    """List event types (Batting/Pitching) for a session."""
    session_path = data_root / team / session
    if not session_path.exists():
        return []
    return sorted([d.name for d in session_path.iterdir() if d.is_dir() and d.name in ["Batting", "Pitching"]])


def list_events(data_root: Path, team: str, session: str, event_type: str) -> List[str]:
    """List events within an event type."""
    events_path = data_root / team / session / event_type
    if not events_path.exists():
        return []

    events = []
    for event_dir in events_path.iterdir():
        if event_dir.is_dir():
            c3d_files = list(event_dir.glob("*.c3d"))
            if c3d_files:
                events.append(event_dir.name)
    return sorted(events)


def get_c3d_path(data_root: Path, team: str, session: str, event_type: str, event: str) -> Optional[Path]:
    """Get the path to a C3D file for an event."""
    event_path = data_root / team / session / event_type / event
    c3d_files = list(event_path.glob("*.c3d"))
    return c3d_files[0] if c3d_files else None


def list_cameras(data_root: Path, team: str, session: str, event_type: str, event: str) -> List[str]:
    """List all camera directories for an event."""
    event_path = data_root / team / session / event_type / event
    if not event_path.exists():
        return []
    cameras = []
    for subdir in sorted(event_path.iterdir()):
        if subdir.is_dir() and list(subdir.glob("*.mp4")):
            cameras.append(subdir.name)
    return cameras


def get_video_path(data_root: Path, team: str, session: str, event_type: str, event: str, camera: Optional[str] = None) -> Optional[Path]:
    """Get the path to a video file for an event.

    Args:
        camera: Specific camera directory name. If None, returns first available.
    """
    event_path = data_root / team / session / event_type / event

    if camera:
        camera_path = event_path / camera
        if camera_path.exists():
            # Prefer skeleton overlay video, fall back to regular
            skeleton_videos = list(camera_path.glob("*.skeleton.mp4"))
            if skeleton_videos:
                return skeleton_videos[0]
            videos = list(camera_path.glob("*.mp4"))
            if videos:
                return videos[0]
        return None

    # No camera specified - return first available
    for subdir in event_path.iterdir():
        if subdir.is_dir():
            videos = list(subdir.glob("*.mp4"))
            if videos:
                return videos[0]
    return None
