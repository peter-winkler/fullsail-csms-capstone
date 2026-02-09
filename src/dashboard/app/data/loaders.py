"""Load real on-prem processing results and site profiles."""

import csv
import random
from pathlib import Path
from typing import Dict, List, Optional

from .schemas import Event, SiteProfile


# Real GPU counts from production controllers spreadsheet (Feb 2026)
SITE_GPU_COUNTS: Dict[str, int] = {
    "NYY": 93, "TEX": 46, "SEA": 36, "CIN": 29, "MIL": 26,
    "PHI": 23, "OAK": 21, "ARZ": 20, "NYM": 18, "CHC": 17,
    "MIA": 12, "BOS": 5, "MIN": 3, "CLE": 0, "LAD": 0, "TBR": 0,
}

# Representative presets across three tiers
PRESET_SITE_PROFILES: List[SiteProfile] = [
    SiteProfile(name="Minnesota Twins", venue_code="MIN", available_gpus=3, tier="gpu_poor"),
    SiteProfile(name="Boston Red Sox", venue_code="BOS", available_gpus=5, tier="gpu_poor"),
    SiteProfile(name="Miami Marlins", venue_code="MIA", available_gpus=12, tier="gpu_moderate"),
    SiteProfile(name="Arizona Diamondbacks", venue_code="ARZ", available_gpus=20, tier="gpu_moderate"),
    SiteProfile(name="Seattle Mariners", venue_code="SEA", available_gpus=36, tier="gpu_rich"),
    SiteProfile(name="New York Yankees", venue_code="NYY", available_gpus=93, tier="gpu_rich"),
]


def _project_root() -> Path:
    """Resolve project root relative to this file.

    Walk up: app/data/loaders.py -> data -> app -> dashboard -> src -> project root
    """
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def _default_csv_path() -> Path:
    return _project_root() / "docs" / "data" / "onprem_results_clean.csv"


def _default_ledger_path() -> Optional[Path]:
    """Return ledger path if the file exists, else None."""
    path = _project_root() / "docs" / "data" / "event_ledger_v3.csv"
    return path if path.exists() else None


def load_event_ledger(csv_path: str) -> Dict[str, dict]:
    """Load event ledger CSV, keyed by event_name."""
    ledger: Dict[str, dict] = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ledger[row["event_name"]] = dict(row)
    return ledger


def load_onprem_results(
    csv_path: Optional[str] = None,
    min_processing_time: float = 60.0,
    require_valid_c3d: bool = True,
    enrich: bool = True,
    ledger_path: Optional[str] = None,
) -> List[Event]:
    """Load on-prem processing results from CSV, optionally enriched with
    event ledger metadata (fps, session, s3_path).

    Filters to usable events: processing_time > min_processing_time and
    optionally valid C3D output.

    When enrich=True (default), automatically joins the event ledger if
    found at the standard location (docs/data/event_ledger_v3.csv).

    Returns ~210 events from the 346-row dataset.
    """
    path = Path(csv_path) if csv_path else _default_csv_path()

    # Pre-load ledger for enrichment
    ledger: Dict[str, dict] = {}
    if enrich:
        lpath = Path(ledger_path) if ledger_path else _default_ledger_path()
        if lpath is not None:
            ledger = load_event_ledger(str(lpath))

    events: List[Event] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            processing_time = float(row["processing_time_sec"])
            c3d_valid = row["c3d_valid"].lower() == "true"

            if processing_time < min_processing_time:
                continue
            if require_valid_c3d and not c3d_valid:
                continue

            meta = ledger.get(row["event_name"], {})

            events.append(Event(
                event_name=row["event_name"],
                venue=row["venue"],
                venue_type=row.get("venue_type", "mlb"),
                event_type=row["event_type"],
                gpu_model=row.get("gpu_model", "RTX_4000_Ada"),
                processing_time_sec=processing_time,
                exit_code=int(row["exit_code"]),
                c3d_valid=c3d_valid,
                c3d_size_bytes=int(row["c3d_size_bytes"]),
                timestamp=row.get("timestamp"),
                session=meta.get("session"),
                fps=float(meta["fps"]) if meta.get("fps") else None,
                s3_path=meta.get("s3_path"),
            ))

    return events


def sample_game_batch(
    events: List[Event],
    batch_size: int = 600,
    seed: Optional[int] = None,
) -> List[Event]:
    """Resample events with replacement to reach realistic game-night batch size.

    Preserves the real processing time distribution from on-prem measurements.
    A typical MLB game produces ~500-700 biomechanical events.
    """
    rng = random.Random(seed)
    return rng.choices(events, k=batch_size)
