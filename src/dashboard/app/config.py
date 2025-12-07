"""Dashboard configuration settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "KinaTrax Decision Support Dashboard"
    app_version: str = "0.1.0"
    debug: bool = False

    # API Backend (for future integration)
    api_base_url: str = "http://localhost:8000/api/v1"
    use_mock_data: bool = True

    # Feature flags
    enable_real_time_updates: bool = False
    enable_job_submission: bool = False

    # Mock data settings
    default_queue_size: int = 15
    mock_data_seed: int | None = None  # Set for reproducible data

    # Cost calculation defaults (USD)
    on_prem_hourly_rate: float = 0.0  # Already paid for
    aws_gpu_hourly_rate: float = 8.50  # p3.2xlarge equivalent
    gcp_gpu_hourly_rate: float = 7.80
    storage_cost_per_pitch: float = 0.023
    egress_cost_per_pitch: float = 0.09

    # Processing time defaults (hours per 150 pitches)
    base_processing_hours: float = 6.5
    cloud_speedup_factor: float = 0.5  # 2x faster in cloud

    class Config:
        env_prefix = "KINATRAX_DASHBOARD_"
        env_file = ".env"


settings = Settings()
