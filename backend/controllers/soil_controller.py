import asyncio
import logging
from typing import Optional

from services.soil_type_classification.soil_service import (
    get_soil_type,
    get_soil_distribution,
)
from services.soilgrid.soil_geojson_service import get_soil_coverage_geojson
from services.soil_quality_analysis.soil_quality_service import soil_quality_service
from utils.farmland_detection.polygon_utils import validate_polygon
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

    distribution, polygon_quality, coverage_geojson = await asyncio.gather(
        get_soil_distribution(polygon_geojson),
        soil_quality_service.analyze_polygon(polygon_geojson),
        get_soil_coverage_geojson(polygon_geojson)
    )
    
    if not distribution:
        raise APIError(503, "Could not retrieve soil data for this polygon.") 

    dist_map: dict[str, float] = {
        d["soil_class"]: d["percentage"]
        for d in distribution
    }

    coverage_geojson["features"] = [
        f for f in coverage_geojson.get("features", [])
        if f["properties"]["soil_class"] in dist_map
    ]

    for feature in coverage_geojson["features"]:
        cls = feature["properties"]["soil_class"]
        feature["properties"]["percentage"] = dist_map[cls]
    
    geojson_classes = {
        f["properties"]["soil_class"]
        for f in coverage_geojson["features"]
    }

    missing_from_geojson = set(dist_map.keys()) - geojson_classes
    if missing_from_geojson:
        logger.warning(
            f"Classes in distribution but missing from coverage_geojson "
            f"(too few sample points for Voronoi): {missing_from_geojson}"
        )

    # Build soil_quality_by_class 
    # Each soil class in distribution gets the overall polygon quality values
    # (since we couldn't reliably extract per-class quality from mismatched sources)    
    soil_quality_by_class = [
        {
            "soil_class": dist_entry["soil_class"],
            "area_percentage": dist_entry["percentage"],
            "quality": {
                "ph": polygon_quality.get("ph"),
                "nitrogen": polygon_quality.get("nitrogen"),
                "soc": polygon_quality.get("soc"),
                "cec": polygon_quality.get("cec"),
                "bulk_density": polygon_quality.get("bulk_density"),
                "soil_quality_index": polygon_quality.get("soil_quality_index"),
                "soil_quality": polygon_quality.get("soil_quality"),
                "confidence": polygon_quality.get("confidence"),
                "missing_parameters": polygon_quality.get("missing_parameters", []),
            }
        }
        for dist_entry in distribution
    ]
    
    def _weighted_avg(param: str) -> Optional[float]:
        """Calculate weighted average of a parameter across all soil classes."""
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
            "soil_quality_by_class": soil_quality_by_class,
            "overall_weighted_quality": overall,
            "coverage_geojson": coverage_geojson
        },
        "Soil polygon analysis complete.",
    ).to_dict()
