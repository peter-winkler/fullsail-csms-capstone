#!/usr/bin/env python3
"""
Collect random sample events from S3 for dry run testing.

This script:
1. Lists all available events across teams
2. Randomly selects N events
3. Downloads them to the local data directory

Terminology:
- Session: A game day capture (e.g., 2024_06_13_13_35_17)
- Event: A single pitch or bat action within a session
- Each event contains 8 camera MP4s + 1 C3D biomechanics file
"""

import subprocess
import random
import json
import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Configuration - use environment variables for sensitive data
S3_BUCKET = os.environ.get("CAPSTONE_S3_BUCKET", "s3://your-bucket/Data")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "default")
LOCAL_DATA_DIR = Path(__file__).parent.parent / "data" / "samples"

# MLB teams to sample from (major league teams with likely more data)
MLB_TEAMS = [
    "ARI", "ATH", "BOS", "CHC", "CIN", "CLE", "LAD", "MIA", "MIN",
    "NYM", "NYY", "OAK", "PHI", "PIT", "SEA", "TBR", "TEX"
]


@dataclass
class Event:
    """Represents a single event (pitch/bat action) within a session."""
    team: str
    year: str
    session: str
    event_type: str  # Pitching or Batting
    event_path: str
    full_s3_path: str


def run_aws_command(args: list[str]) -> str:
    """Run an AWS CLI command and return output."""
    cmd = ["aws", "--profile", AWS_PROFILE] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return ""
    return result.stdout


def list_team_years(team: str) -> list[str]:
    """List available years for a team."""
    output = run_aws_command(["s3", "ls", f"{S3_BUCKET}/{team}/"])
    years = []
    for line in output.strip().split("\n"):
        if line.strip() and "PRE" in line:
            year = line.split("PRE")[-1].strip().rstrip("/")
            if year.isdigit():
                years.append(year)
    return years


def list_sessions(team: str, year: str) -> list[str]:
    """List available sessions for a team/year."""
    output = run_aws_command(["s3", "ls", f"{S3_BUCKET}/{team}/{year}/"])
    sessions = []
    for line in output.strip().split("\n"):
        if line.strip() and "PRE" in line:
            session = line.split("PRE")[-1].strip().rstrip("/")
            sessions.append(session)
    return sessions


def list_events(team: str, year: str, session: str, event_type: str) -> list[Event]:
    """List events for a session."""
    path = f"{S3_BUCKET}/{team}/{year}/{session}/{event_type}/"
    output = run_aws_command(["s3", "ls", path])
    events = []
    for line in output.strip().split("\n"):
        if line.strip() and "PRE" in line:
            event = line.split("PRE")[-1].strip().rstrip("/")
            events.append(Event(
                team=team,
                year=year,
                session=session,
                event_type=event_type,
                event_path=event,
                full_s3_path=f"{path}{event}/"
            ))
    return events


def discover_all_events(teams: list[str], max_per_team: int = 50) -> list[Event]:
    """Discover events across all teams."""
    all_events = []

    for team in teams:
        print(f"Scanning {team}...", end=" ", flush=True)
        team_events = []

        years = list_team_years(team)
        for year in years:
            sessions = list_sessions(team, year)
            for session in sessions[:5]:  # Limit sessions per year for speed
                for event_type in ["Pitching", "Batting"]:
                    events = list_events(team, year, session, event_type)
                    team_events.extend(events)

                    if len(team_events) >= max_per_team:
                        break
                if len(team_events) >= max_per_team:
                    break
            if len(team_events) >= max_per_team:
                break

        print(f"found {len(team_events)} events")
        all_events.extend(team_events[:max_per_team])

    return all_events


def download_event(event: Event, dest_dir: Path) -> bool:
    """Download a single event to local directory."""
    # Create destination path maintaining structure
    dest_path = dest_dir / event.team / event.year / event.session / event.event_type / event.event_path
    dest_path.mkdir(parents=True, exist_ok=True)

    print(f"  Downloading {event.event_path}...")
    result = run_aws_command([
        "s3", "sync",
        event.full_s3_path,
        str(dest_path),
        "--quiet"
    ])
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Collect sample events from S3")
    parser.add_argument("-n", "--count", type=int, default=100, help="Number of events to collect")
    parser.add_argument("--discover-only", action="store_true", help="Only discover, don't download")
    parser.add_argument("--manifest", type=str, help="Save/load manifest file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)

    manifest_path = Path(args.manifest) if args.manifest else LOCAL_DATA_DIR / "manifest.json"

    # Check for existing manifest
    if manifest_path.exists() and not args.discover_only:
        print(f"Loading existing manifest from {manifest_path}")
        with open(manifest_path) as f:
            data = json.load(f)
            events = [Event(**r) for r in data["events"]]
    else:
        print(f"Discovering events across {len(MLB_TEAMS)} teams...")
        all_events = discover_all_events(MLB_TEAMS)
        print(f"\nTotal events found: {len(all_events)}")

        # Randomly select N events
        events = random.sample(all_events, min(args.count, len(all_events)))
        print(f"Selected {len(events)} random events")

        # Save manifest
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w") as f:
            json.dump({
                "count": len(events),
                "seed": args.seed,
                "events": [vars(r) for r in events]
            }, f, indent=2)
        print(f"Manifest saved to {manifest_path}")

    if args.discover_only:
        print("\nDiscovery complete. Run without --discover-only to download.")
        return

    # Download events
    print(f"\nDownloading {len(events)} events to {LOCAL_DATA_DIR}...")
    for i, event in enumerate(events, 1):
        print(f"[{i}/{len(events)}] {event.team}/{event.event_path}")
        download_event(event, LOCAL_DATA_DIR)

    print("\nDone!")


if __name__ == "__main__":
    main()
