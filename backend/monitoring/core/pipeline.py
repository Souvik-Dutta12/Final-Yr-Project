"""
MonitoringPipeline — orchestrates all analysis services for one farm cycle.

Design principles:
  1. Each analysis step is independent and can fail gracefully.
  2. Partial results are still persisted (a missing soil result doesn't
     invalidate a good land cover snapshot).
  3. All TS interactions happen at the END — compute first, persist after.
  4. task_id is threaded through for progress reporting.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from monitoring.config import monitoring_config
from monitoring.models.snapshot_models import (
    LandCoverStats, MonitoringSnapshot, NDVIStats, SoilStats
)
from monitoring.analyzers.ndvi_analyzer import extract_ndvi_stats
from monitoring.utils.ts_client import ts_client

# Reuse existing services
from services.farmland_detection.landcover_service import analyze_land_cover
from services.soil_quality_analysis.soil_quality_service import soil_quality_service
from services.earth_engine.ee_service import fetch_dynamic_world
from utils.farmland_detection.polygon_utils import validate_polygon
from utils.api_error import APIError


logger = logging.getLogger(__name__)


class MonitoringPipeline:
    """
    Full monitoring cycle for one farm.
    Instantiate once per job to keep task_id clean.
    """
    def __init__(self, task_id: str = "manual"):
        self.task_id = task_id

    async def run(
        self,
        farm_id: str,
        polygon: Dict[str, Any],
        days_back: int = 60,
        include_soil: bool = True,
        include_crop_analysis: bool = True,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute the full monitoring pipeline.

        Steps:
          1. Validate polygon
          2. Fetch satellite data (GEE) — shared across all analyzers
          3. Land cover analysis (reuse existing service)
          4. NDVI statistics extraction (free — uses already-fetched arrays)
          5. Soil analysis (optional — SoilGrids calls)
          6. Build snapshot model
          7. Persist snapshot to TS server
          8. Return summary

        Returns a dict with: farm_id, snapshot_id, alert_count, duration_seconds, ...
        """

        start_time = time.time()
        logger.info("Pipeline start | farm=%s | task=%s", farm_id, self.task_id)


        # Step 1: Validate polygon
        try:
            polygon = validate_polygon(polygon)
        except ValueError as e:
            raise APIError(400, f"Invalid polygon: {e}")


        # Step 2: Land cover + spectral indices (one GEE call covers both)
        logger.info("Step 2/5: Fetching satellite data | farm=%s", farm_id)
        land_cover_result = await analyze_land_cover(polygon, days_back=days_back)
        metadata = land_cover_result.get("metadata", {})
        # Extract raw GEE data to get indices (without extra GEE call)
        # fetch_dynamic_world uses its own TTL cache — no double billing
        gee_data = fetch_dynamic_world(polygon, days_back=days_back)


        # Step 3: Parse land cover stats
        lc_stats = self._parse_land_cover_stats(land_cover_result)
        logger.info("Step 3/5: Land cover parsed | classes=%d | farm=%s", len(lc_stats), farm_id)


        # Step 4: NDVI stats — free computation on already-fetched arrays
        ndvi_stats = extract_ndvi_stats(gee_data["indices"])
        logger.info(
            "Step 4/5: NDVI stats | mean=%.3f | farm=%s",
            ndvi_stats.ndvi_mean if ndvi_stats else 0, farm_id
        )


        # Step 5: Soil analysis (optional — can be slow due to SoilGrids)
        soil_stats: Optional[SoilStats] = None
        if include_soil:
            logger.info("Step 5/5: Fetching soil data | farm=%s", farm_id)
            try:
                soil_result = await soil_quality_service.analyze_polygon(polygon)
                soil_stats = SoilStats(
                    ph=soil_result.get("ph"),
                    nitrogen=soil_result.get("nitrogen"),
                    soc=soil_result.get("soc"),
                    cec=soil_result.get("cec"),
                    bulk_density=soil_result.get("bulk_density"),
                    soil_quality_index=soil_result.get("soil_quality_index"),
                    soil_quality=soil_result.get("soil_quality"),
                    confidence=soil_result.get("confidence"),
                )
            except Exception as e:
                # Soil failure is non-fatal — log and continue
                logger.warning("Soil analysis failed (non-fatal): %s | farm=%s", e, farm_id)


        # Step 6: Build snapshot
        snapshot = MonitoringSnapshot(
            farm_id=farm_id,
            captured_at=datetime.utcnow(),
            polygon=polygon,
            land_cover_stats=lc_stats,
            ndvi_stats=ndvi_stats,
            soil_stats=soil_stats,
            resolution_m=metadata.get("resolution_m"),
            scene_count=metadata.get("scene_count"),
            date_range=metadata.get("date_range"),
            area_km2=metadata.get("area_km2"),
        )


        # Step 7: Persist to TS server
        snapshot_id = None
        if persist:
            try:
                ts_resp = await ts_client.persist_snapshot(
                    self._snapshot_to_payload(snapshot, land_cover_result)
                )
                snapshot_id = ts_resp.get("id")
                logger.info("Snapshot persisted | id=%s | farm=%s", snapshot_id, farm_id)
            except Exception as e:
                logger.error("Failed to persist snapshot: %s | farm=%s", e, farm_id)


        duration = round(time.time() - start_time, 2)

        return {
            "farm_id":  farm_id,
            "snapshot_id": snapshot_id,
            "snapshot": snapshot.model_dump(),
            "alert_count":  0,      # filled by alert engine in Phase 8
            "critical_alerts":  0,
            "duration_seconds": duration,
            "classes_detected": [s.class_name for s in lc_stats],
            "ndvi_mean": ndvi_stats.ndvi_mean if ndvi_stats else None,
        }


    def _parse_land_cover_stats(
        self, land_cover_result: Dict
    ) -> List[LandCoverStats]:
        """Convert analyze_land_cover result → list of LandCoverStats."""
        stats = land_cover_result.get("metadata", {}).get("class_stats", {})
        result = []
        for class_name, data in stats.items():
            if data.get("pixel_count", 0) > 0:
                result.append(LandCoverStats(
                    class_name=class_name,
                    label=data.get("label", class_name),
                    area_ha=data.get("area_ha", 0.0),
                    coverage_pct=data.get("coverage_pct", 0.0),
                    confidence=data.get("confidence"),
                ))
        return result


    def _snapshot_to_payload(
        self,
        snapshot: MonitoringSnapshot,
        raw_land_cover: Dict,
    ) -> Dict[str, Any]:
        """Serialize snapshot for TS server persistence."""
        return {
            "farm_id":  snapshot.farm_id,
            "captured_at":  snapshot.captured_at.isoformat(),
            "polygon":  snapshot.polygon,
            "land_cover_json": {
                "stats":   [s.model_dump() for s in snapshot.land_cover_stats],
                "geojson": raw_land_cover,  # full GeoJSON stored in TS
            },
            "ndvi_json":    snapshot.ndvi_stats.model_dump() if snapshot.ndvi_stats else None,
            "soil_json":    snapshot.soil_stats.model_dump() if snapshot.soil_stats else None,
            "metadata_json": {
                "resolution_m": snapshot.resolution_m,
                "scene_count": snapshot.scene_count,
                "date_range":   snapshot.date_range,
                "area_km2": snapshot.area_km2,
                "task_id":  self.task_id,
            },
        }