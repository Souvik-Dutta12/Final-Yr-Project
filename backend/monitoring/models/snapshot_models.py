"""
Pydantic schemas for monitoring snapshots.
A Snapshot is a point-in-time capture of all analysis results for one farm.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class LandCoverStats(BaseModel):
    """Per-class land cover summary — extracted from analyze_land_cover result."""
    class_name: str
    label: str
    area_ha: float
    coverage_pct: float
    confidence: Optional[float] = None

class NDVIStats(BaseModel):
    """Spectral index statistics for one snapshot."""
    ndvi_mean: float
    ndvi_min: float
    ndvi_max: float
    ndvi_std: float
    ndwi_mean: Optional[float] = None
    evi_mean: Optional[float] = None
    ndbi_mean: Optional[float] = None

class SoilStats(BaseModel):
    """Soil quality summary for one snapshot."""
    ph: Optional[float] = None
    nitrogen: Optional[float] = None
    soc: Optional[float] = None
    cec: Optional[float] = None
    bulk_density: Optional[float] = None
    soil_quality_index: Optional[float] = None
    soil_quality: Optional[str] = None
    confidence: Optional[float] = None

class MonitoringSnapshot(BaseModel):
    """Complete monitoring snapshot for one farm at one point in time."""
    farm_id: str
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    polygon: Dict[str, Any]

    # Analysis results
    land_cover_stats: List[LandCoverStats] = []
    ndvi_stats: Optional[NDVIStats] = None
    soil_stats: Optional[SoilStats] = None

    # Raw GEE metadata
    resolution_m: Optional[int] = None
    scene_count: Optional[int] = None
    date_range: Optional[Dict[str, str]] = None
    area_km2: Optional[float] = None

    # Full raw results stored in TS DB (not kept in memory)
    land_cover_geojson_ref: Optional[str] = None  # key/ID in TS storage
    soil_geojson_ref: Optional[str] = None

class SnapshotComparison(BaseModel):
    """Comparison result between two snapshots."""
    farm_id: str
    snapshot_a_id: str
    snapshot_b_id: str
    snapshot_a_at: datetime
    snapshot_b_at: datetime
    days_between: int

    # Land cover deltas per class
    land_cover_deltas: Dict[str, Dict[str, float]] = {}

    # NDVI change
    ndvi_delta: Optional[float] = None

    # Soil deltas
    soil_deltas: Dict[str, Optional[float]] = {}

    # Change severity 0-100
    overall_change_score: float = 0.0