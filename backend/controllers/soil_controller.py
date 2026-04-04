from services.soil_service import (
    get_soil_type,
    analyze_soil_polygon
)
from utils.api_response import APIResponse
from utils.api_error import APIError


async def get_soil_point(lat, lon):

    if lat is None or lon is None:
        raise APIError(
            400,
            "Latitude and Longitude required"
        )
    soil = get_soil_type(lat, lon)

    return APIResponse(
        200,
        {
            "lat":lat,
            "lon":lon,
            "soil_type": soil
        },
        "Soil type fetched"
    ).to_dict()


async def get_soil_polygon(polygon):
    if not polygon:
        raise APIError(400,"Polygon required")
    
    result = analyze_soil_polygon(polygon)

    return APIResponse(
        200,
        result,
        "Soil information fetched successfully"
    ).to_dict()