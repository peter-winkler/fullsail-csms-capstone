"""Dashboard configuration settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "KinaTrax Cloud Acceleration Dashboard"
    app_version: str = "3.0.0"

    # Batch simulation defaults
    default_batch_size: int = 600
    default_max_cloud: int = 30

    # Display
    time_unit: str = "hours"  # "hours" or "seconds"


settings = Settings()
