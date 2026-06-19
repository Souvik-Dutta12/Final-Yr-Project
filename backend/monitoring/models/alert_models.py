"""
Alert data models.
Severity levels: CRITICAL > HIGH > MEDIUM > LOW > INFO
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class AlertType(str, Enum):
    # Land cover
    DEFORESTATION = "DEFORESTATION"
    VEGETATION_LOSS = "VEGETATION_LOSS"
    WATER_BODY_EXPANSION = "WATER_BODY_EXPANSION"
    WATER_BODY_SHRINKAGE = "WATER_BODY_SHRINKAGE"
    URBANIZATION = "URBANIZATION"
    CONSTRUCTION_ACTIVITY = "CONSTRUCTION_ACTIVITY"

    # Soil
    SOIL_DEGRADATION = "SOIL_DEGRADATION"
    ORGANIC_MATTER_DECREASE = "ORGANIC_MATTER_DECREASE"
    MOISTURE_REDUCTION = "MOISTURE_REDUCTION"
    SOIL_HEALTH_DECLINE = "SOIL_HEALTH_DECLINE"

    # Crop
    CROP_SUITABILITY_REDUCTION = "CROP_SUITABILITY_REDUCTION"
    CROP_STRESS = "CROP_STRESS"
    VEGETATION_ANOMALY = "VEGETATION_ANOMALY"

    # Weather
    DROUGHT_RISK = "DROUGHT_RISK"
    FLOOD_RISK = "FLOOD_RISK"
    HEATWAVE_RISK = "HEATWAVE_RISK"
    RAINFALL_ANOMALY = "RAINFALL_ANOMALY"

class Alert(BaseModel):
    """A single generated alert."""
    
    alert_type: AlertType
    severity: AlertSeverity
    farm_id: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    # Human-readable description
    title: str
    description: str
    recommendation: str

    # Numeric evidence
    metric_name: str # e.g. "trees_area_ha"
    metric_value_before: Optional[float] = None
    metric_value_after: Optional[float] = None
    metric_delta: Optional[float] = None
    metric_unit: str = ""

    # Confidence 0-1
    confidence: float = 1.0

    # Extra context (GeoJSON of affected area, etc.)
    context: Dict[str, Any] = {}

class AlertBatch(BaseModel):
    """All alerts generated in one monitoring run."""
    farm_id: str
    job_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    alerts: List[Alert] = []
    total_count: int = 0
    critical_count: int = 0
    high_count: int = 0
