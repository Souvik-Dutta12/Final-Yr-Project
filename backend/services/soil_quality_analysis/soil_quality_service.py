import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from services.soilgrid.soilgrids_client import soilgrids_client
from services.soil_quality_analysis.quality_index import calculate_sqi
from utils.soil_properties.polygon_sampler import adaptive_sample_points

logger = logging.getLogger(__name__)

_SOILGRIDS_SEMAPHORE = asyncio.Semaphore(5)
 
class SoilQualityService:

    async def analyze_point(
            self, 
            lat: float, 
            lon: float
        ) -> dict:
        """Full quality profile for a single coordinate."""
        async with _SOILGRIDS_SEMAPHORE:
            props = await soilgrids_client.get_soil_properties(lat, lon)
        missing = [k for k, v in props.items() if v is None]
        sqi = calculate_sqi(props)
        return {
            **props, 
            **sqi, 
            "missing_parameters": missing
        }
    
    async def analyze_polygon(
            self, 
            polygon_geojson: dict
        ) -> dict:
        """
        Quality profile for a polygon — averages values from a point grid.
        Accepts the same GeoJSON dict the controller already validated.
        Concurrent SoilGrids calls are capped at 5 via _SOILGRIDS_SEMAPHORE
        to avoid overwhelming the upstream API.
        """
        points: List[Tuple[float, float]] = adaptive_sample_points(polygon_geojson)
        logger.info(f"Polygon quality: {len(points)} sample points via SoilGrids")

        async def _fetch_one(lat: float, lon: float) -> dict:
            async with _SOILGRIDS_SEMAPHORE:
                return await soilgrids_client.get_soil_properties(lat, lon)

        all_props = await asyncio.gather(*[_fetch_one(lat, lon) for lat, lon in points])

        accum: Dict[str, List[float]] = defaultdict(list)
        for props in all_props:
            for key, val in props.items():
                if val is not None:
                    accum[key].append(val)

        param_keys = ["ph", "nitrogen", "soc", "cec", "bulk_density"]
        averaged: Dict[str, Optional[float]] = {
            key: round(sum(vals) / len(vals), 6) if (vals := accum.get(key, []))
            else None
            for key in param_keys
        }

        missing = [k for k, v in averaged.items() if v is None]
        sqi = calculate_sqi(averaged)

        return {
            **averaged,
            **sqi,
            "missing_parameters": missing,
            "samples_used": len(points),
        }

soil_quality_service = SoilQualityService()