import os
from dataclasses import dataclass, field
from typing import Dict
from dotenv import load_dotenv

load_dotenv()  # Load .env file

@dataclass
class AlertThresholds:
    # Land cover — minimum area in hectares to generate an alert
    deforestation_min_ha: float = 0.5
    vegetation_loss_min_pct: float = 5.0 # % coverage drop
    urbanization_min_ha: float = 0.3
    water_body_change_min_pct: float = 10.0

    # Soil — minimum delta to alert
    soil_quality_index_drop: float = 0.10  # absolute SQI drop
    soc_drop_pct: float = 10.0     # % SOC decrease
    moisture_drop_pct: float = 15.0

    # Crop / NDVI
    ndvi_drop_threshold: float = -0.15   # mean NDVI delta
    crop_suitability_drop_pct: float = 20.0

    # Weather (derived from external data or NDVI proxy)
    drought_ndvi_threshold: float = 0.2  # NDVI below this → drought risk
    flood_ndwi_threshold: float = 0.3 # NDWI above this → flood risk


@dataclass
class MonitoringConfig:
    # TypeScript server base URL (must be set in env)
    ts_server_url: str = field(
        default_factory=lambda: os.getenv("TS_SERVER_URL", "http://localhost:3000")
    )
    ts_internal_token: str = field(
        default_factory=lambda: os.getenv("TS_INTERNAL_TOKEN", "dev-secret")
    )

    # Celery / Redis
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # Concurrency
    job_concurrency: int = field(
        default_factory=lambda: int(os.getenv("MONITORING_JOB_CONCURRENCY", "4"))
    )
    max_farms_per_batch: int = 50

    # Snapshot retention (TS server decides actual storage, this is advisory)
    snapshot_history_limit: int = 90   # days

    # Alert thresholds
    thresholds: AlertThresholds = field(default_factory=AlertThresholds)


# Singleton — import this everywhere
monitoring_config = MonitoringConfig()