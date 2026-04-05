from utils.api_response import APIResponse
from utils.api_error import APIError

from services.farmland_detection.farmland_service import process_farmland


async def analyze_farmland(body: dict):

    polygon = body.get("polygon")

    if not polygon:
        raise APIError(400, "Polygon is required")

    result = await process_farmland(polygon)

    return APIResponse(
        200,
        result,
        "Farmland detected successfully"
    ).to_dict()