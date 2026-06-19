"""Job lifecycle schemas."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class MonitoringJobConfig(BaseModel):
    """Configuration for a single monitoring run."""
    farm_id: str
    polygon: Dict[str, Any]
    days_back: int = 60
    include_soil: bool = True
    include_crop_analysis: bool = True
    include_weather_proxies: bool = True
    triggered_by: str = "scheduler"  # "scheduler" | "manual" | "webhook"

class MonitoringJobResult(BaseModel):
    """Summary result stored after a job completes."""
    job_id: str
    farm_id: str
    status: JobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    snapshot_id: Optional[str] = None
    alert_count: int = 0
    critical_alerts: int = 0
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
