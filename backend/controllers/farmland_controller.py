"""
Land Cover Controller
 
Exposes two endpoints:
 
  POST /land-cover/analyze
  ─────────────────────────
  Body:  { "polygon": <GeoJSON Polygon>, "days_back": 60 }  (days_back optional)
  Returns: FeatureCollection with all 9 DW classes + metadata
 
  POST /land-cover/change
  ─────────────────────────
  Body:  {
      "polygon":   <GeoJSON Polygon>,
      "date_from": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
      "date_to":   {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
  }
  Returns: Change detection report
 
Validation is centralised here; services receive clean, validated data.
"""

import logging
 
from utils.api_error import APIError
from utils.api_response import APIResponse
from utils.farmland_detection.polygon_utils import validate_polygon
from services.farmland_detection.landcover_service import analyze_land_cover
from services.farmland_detection.change_detection import detect_changes
 
logger = logging.getLogger(__name__)
 
def _parse_date_range(obj: dict, field: str) -> tuple:
    """Extract and validate a {"start": ..., "end": ...} date range."""
    dr = obj.get(field)
    if not dr:
        raise APIError(400, f"'{field}' is required.")
    start = dr.get("start")
    end   = dr.get("end")
    if not start or not end:
        raise APIError(400, f"'{field}' must have 'start' and 'end' in YYYY-MM-DD format.")
    return start, end

async def analyze(body: dict):
    """
    POST /land-cover/analyze
 
    Full 9-class Dynamic World segmentation for a polygon.
    """
    # Validate inputs
    raw_polygon = body.get("polygon")
    if not raw_polygon:
        raise APIError(400, "Request body must contain a 'polygon' field.")
 
    try:
        polygon = validate_polygon(raw_polygon)
    except ValueError as exc:
        raise APIError(400, str(exc)) from exc
 
    days_back = int(body.get("days_back", 60))
    if not (1 <= days_back <= 365):
        raise APIError(400, "'days_back' must be between 1 and 365.")
 
    logger.info("Land cover analysis requested | days_back=%d", days_back)
 
    result = await analyze_land_cover(polygon, days_back=days_back)
 
    return APIResponse(
        200,
        result,
        f"Land cover analysis complete — "
        f"{len(result['features'])} classes detected."
    ).to_dict()
 
async def change_detection(body: dict):
    """
    POST /land-cover/change
 
    Two-period land cover change detection for a polygon.
    """
    raw_polygon = body.get("polygon")
    if not raw_polygon:
        raise APIError(400, "Request body must contain a 'polygon' field.")
 
    try:
        polygon = validate_polygon(raw_polygon)
    except ValueError as exc:
        raise APIError(400, str(exc)) from exc
 
    date_from = _parse_date_range(body, "date_from")
    date_to   = _parse_date_range(body, "date_to")
 
    if date_from[0] >= date_to[1]:
        raise APIError(400, "'date_from' must be earlier than 'date_to'.")
 
    logger.info(
        "Change detection requested | %s→%s vs %s→%s",
        *date_from, *date_to
    )
 
    result = detect_changes(polygon, date_from=date_from, date_to=date_to)
 
    return APIResponse(
        200,
        result,
        "Change detection analysis complete."
    ).to_dict()