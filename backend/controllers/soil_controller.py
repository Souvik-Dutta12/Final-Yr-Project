from services.soil_type_classification.soil_service import (
    get_soil_type,
    analyze_soil_polygon
)
from services.soil_quality_analysis.soil_quality_service import soil_service
from utils.api_response import APIResponse
from utils.api_error import APIError
import json
from shapely.geometry import shape
from shapely.ops import unary_union
from collections import defaultdict


async def get_soil_point(lat, lon):

    if lat is None or lon is None:
        raise APIError(
            400,
            "Latitude and Longitude required"
        )
    soil = get_soil_type(lat, lon)

    soil_quality = soil_service.analyze(lat, lon)

    return APIResponse(
        200,
        {
            "lat":lat,
            "lon":lon,
            "soil_type": soil,
            "soil_quality": soil_quality
        },
        "Soil type fetched"
    ).to_dict()


async def get_soil_polygon(polygon):

    if not polygon:
        raise APIError(400,"Polygon required")
    
    result = analyze_soil_polygon(polygon)

    # quality analysis
    
    geojson = json.loads(result["geojson"])
    distribution = result["distribution"]
    soil_groups = defaultdict(list)

    for feature in geojson["features"]:
        soil_class = feature["properties"]["soil_class"]
        geom = shape(feature["geometry"])
        soil_groups[soil_class].append(geom)

    soil_quality_by_class = []

    for soil_class, geoms in soil_groups.items():

        merged_geom = unary_union(geoms)

        quality = soil_service.analyze_polygon(merged_geom)

        percentage = next(
            d["percentage"] for d in distribution if d["soil_class"] == soil_class
        )

        soil_quality_by_class.append({
            "soil_class": soil_class,
            "area_percentage": percentage,
            "properties": quality
        })

    # weighted overall
    def weighted_avg(key):
        total = 0
        for item in soil_quality_by_class:
            val = item["properties"].get(key)
            weight = item["area_percentage"] / 100
            if val is not None:
                total += val * weight
        return total

    overall_quality = {
        "ph": weighted_avg("ph"),
        "nitrogen": weighted_avg("nitrogen"),
        "soc": weighted_avg("soc"),
        "cec": weighted_avg("cec"),
        "bulk_density": weighted_avg("bulk_density")
    }

    return APIResponse(
        200,
        {
            "distribution": distribution,
            "geojson": result["geojson"],
            "soil_quality_by_class": soil_quality_by_class,
            "overall_weighted_quality": overall_quality
        },
        "Soil classification + quality analysis successful"
    ).to_dict()