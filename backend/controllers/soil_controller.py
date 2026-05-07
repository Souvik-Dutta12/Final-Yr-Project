import asyncio
import logging
from typing import Optional

from services.soil_type_classification.soil_service import (
    get_soil_type,
    get_soil_distribution,
)
from services.soilgrid.soil_geojson_service import get_soil_coverage_geojson
from services.soil_quality_analysis.soil_quality_service import soil_quality_service
from utils.farmland_detection.polygon_utils import validate_polygon, polygon_centroid
from utils.api_response import APIResponse
from utils.api_error import APIError
logger = logging.getLogger(__name__)

async def get_soil_point(
        lat: Optional[float],
        lon: Optional[float]
    ) -> dict:

    if lat is None or lon is None:
        raise APIError(
            400,
            "Latitude and Longitude required"
        )
    
    soil_class, quality = await asyncio.gather(
        get_soil_type(lat, lon),
        soil_quality_service.analyze_point(lat, lon),
    )

    if not soil_class:
        raise APIError(
            503, 
            "Could not retrieve soil classification from SoilGrids."
        )

    return APIResponse(
        200,
        {
            "lat":lat,
            "lon":lon,  
            "soil_type": soil_class,
            "soil_quality": quality
        },
        "Soil analysis complete."
    ).to_dict()

async def get_soil_polygon(
        polygon_geojson: Optional[dict]
    )-> dict:

    if not polygon_geojson:
        raise APIError(400,"Polygon GeoJSON is required")
    
    try:
        polygon_geojson = validate_polygon(polygon_geojson)
    except ValueError as exc:
        raise APIError(400, str(exc))

    loop = asyncio.get_event_loop()

    distribution, polygon_quality, coverage_geojson = await asyncio.gather(
        get_soil_distribution(polygon_geojson),
        soil_quality_service.analyze_polygon(polygon_geojson),
        loop.run_in_executor(None, get_soil_coverage_geojson, polygon_geojson)
    )

    if not distribution:
        raise APIError(503, "Could not retrieve soil data for this polygon.")

    clon, clat = polygon_centroid(polygon_geojson)

    soil_quality_by_class = []
    
    def _weighted_avg(
            param: str
        ) -> Optional[float]:
        total = weight_sum = 0.0
        for item in soil_quality_by_class:
            val = item["quality"].get(param)
            w = item["area_percentage"] / 100
            if val is not None:
                total += val * w
                weight_sum += w
        return round(total / weight_sum, 6) if weight_sum > 0 else None
        
    overall = {
        param: _weighted_avg(param)
        for param in ["ph", "nitrogen", "soc", "cec", "bulk_density"]
    }

    return APIResponse(
        200,
        {
            "distribution": distribution,
            "soil_quality_by_class": polygon_quality,
            "overall_weighted_quality": overall,
            "coverage_geojson": coverage_geojson
        },
        "Soil polygon analysis complete.",
    ).to_dict()
