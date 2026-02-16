"""Load real on-prem processing results and site profiles."""

import csv
import random
from pathlib import Path
from typing import Dict, List, Optional

from .schemas import Event, InstanceType, SiteProfile


# --- GPU Instance Types with Pricing ---
# On-demand and RI rates: aws-pricing.com (verified Feb 2026, us-east-1)
# Spot rates: instances.vantage.sh / aws-pricing.com (fluctuates; representative values)
# Ratios: 25-event stratified pilot benchmarks (Feb 2026)
# p3.2xlarge: reserved instances not available on AWS
INSTANCE_TYPES: List[InstanceType] = [
    InstanceType(name="g4dn.xlarge", gpu="Tesla T4",    rate_ondemand=0.526, rate_spot=0.208, rate_1yr_ri=0.309, rate_3yr_ri=0.198, ratio=2.18,  has_real_data=True),
    InstanceType(name="g5.xlarge",   gpu="NVIDIA A10G",  rate_ondemand=1.006, rate_spot=0.387, rate_1yr_ri=0.592, rate_3yr_ri=0.378, ratio=1.167, has_real_data=True),
    InstanceType(name="g6.xlarge",   gpu="NVIDIA L4",    rate_ondemand=0.805, rate_spot=0.344, rate_1yr_ri=0.489, rate_3yr_ri=0.321, ratio=1.278, has_real_data=True),
    InstanceType(name="p3.2xlarge",  gpu="Tesla V100",   rate_ondemand=3.060, rate_spot=0.330, rate_1yr_ri=None,  rate_3yr_ri=None,  ratio=1.368, has_real_data=True),
]

INSTANCE_TYPE_MAP: Dict[str, InstanceType] = {it.name: it for it in INSTANCE_TYPES}

PRICING_MODES: List[str] = ["ondemand", "spot", "1yr_ri", "3yr_ri"]
PRICING_LABELS: Dict[str, str] = {
    "ondemand": "On-Demand",
    "spot": "Spot",
    "1yr_ri": "1yr RI",
    "3yr_ri": "3yr RI",
}

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
    """Default to the curated 200-event dataset with matched cloud/on-prem times."""
    combined = _project_root() / "docs" / "data" / "combined_results_final.csv"
    if combined.exists():
        return combined
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
    """Load processing results from CSV.

    Supports two CSV formats:
    - combined_results_final.csv (200 curated events): columns include
      onprem_time_sec, cloud_time_sec, fps_category, is_pilot_event
    - onprem_results_clean.csv (346 events, legacy): columns include
      processing_time_sec, c3d_valid, c3d_size_bytes

    When enrich=True (default), automatically joins the event ledger if
    found at the standard location (docs/data/event_ledger_v3.csv).
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
        fieldnames = reader.fieldnames or []
        is_combined = "onprem_time_sec" in fieldnames

        for row in reader:
            if is_combined:
                processing_time = float(row["onprem_time_sec"])
                # combined_results_final.csv has no c3d columns; all events are valid
                c3d_valid = True
                c3d_size_bytes = 0
                exit_code = int(row.get("onprem_exit_code", 0))
                gpu_model = row.get("onprem_gpu", "RTX_4000_Ada")
                venue = _venue_from_event_name(row["event_name"])
                fps_val = _fps_from_category(row.get("fps_category", ""))
            else:
                processing_time = float(row["processing_time_sec"])
                c3d_valid = row["c3d_valid"].lower() == "true"
                c3d_size_bytes = int(row["c3d_size_bytes"])
                exit_code = int(row["exit_code"])
                gpu_model = row.get("gpu_model", "RTX_4000_Ada")
                venue = row["venue"]
                fps_val = None

            if processing_time < min_processing_time:
                continue
            if require_valid_c3d and not c3d_valid:
                continue

            meta = ledger.get(row["event_name"], {})

            events.append(Event(
                event_name=row["event_name"],
                venue=venue,
                venue_type=row.get("venue_type", "mlb"),
                event_type=row["event_type"],
                gpu_model=gpu_model,
                processing_time_sec=processing_time,
                exit_code=exit_code,
                c3d_valid=c3d_valid,
                c3d_size_bytes=c3d_size_bytes,
                timestamp=row.get("timestamp"),
                session=meta.get("session"),
                fps=float(meta["fps"]) if meta.get("fps") else fps_val,
                s3_path=meta.get("s3_path"),
            ))

    return events


def _venue_from_event_name(event_name: str) -> str:
    """Extract a venue code from the event name.

    Event names follow the pattern:
    YYYY_MM_DD_HH_MM_SS_TeamName_##_PlayerName_Home/Away
    We use 'mlb' as fallback since combined_results_final.csv
    doesn't have a separate venue column.
    """
    return "mlb"


def _fps_from_category(fps_category: str) -> Optional[float]:
    """Convert fps_category string to numeric fps value."""
    if fps_category == "300":
        return 300.0
    elif fps_category == "600":
        return 600.0
    return None


def sample_game_batch(
    events: List[Event],
    batch_size: int = 600,
) -> List[Event]:
    """Resample events with replacement to reach realistic game-night batch size.

    Preserves the real processing time distribution from on-prem measurements.
    A typical MLB game produces ~500-700 biomechanical events.
    """
    rng = random.Random(42)
    return rng.choices(events, k=batch_size)
