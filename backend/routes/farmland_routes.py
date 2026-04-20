from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, validator
from typing import Optional

from controllers.farmland_controller import analyze, change_detection
from utils.api_error import APIError

router = APIRouter()

class GeoJSONPolygon(BaseModel):
    type: str = Field(..., example="Polygon")
    coordinates: list = Field(..., description="GeoJSON coordinate rings")
 
    @validator("type")
    def must_be_polygon(cls, v):
        if v != "Polygon":
            raise ValueError("Only 'Polygon' type is supported.")
        return v
    
class AnalyzeRequest(BaseModel):
    polygon:   GeoJSONPolygon
    days_back: Optional[int] = Field(60, ge=1, le=365, description="Imagery composite window in days")
 
    class Config:
        schema_extra = {
            "example": {
                "polygon": {
                    "type": "Polygon",
                    "coordinates": [[
                        [78.15, 29.97], [78.20, 29.97],
                        [78.20, 29.92], [78.15, 29.92],
                        [78.15, 29.97]
                    ]]
                },
                "days_back": 60
            }
        }

class DateRange(BaseModel):
    start: str = Field(..., example="2023-01-01", description="YYYY-MM-DD")
    end:   str = Field(..., example="2023-03-31", description="YYYY-MM-DD")
 
class ChangeRequest(BaseModel):
    polygon:   GeoJSONPolygon
    date_from: DateRange
    date_to:   DateRange
 
    class Config:
        schema_extra = {
            "example": {
                "polygon": {
                    "type": "Polygon",
                    "coordinates": [[
                        [78.15, 29.97], [78.20, 29.97],
                        [78.20, 29.92], [78.15, 29.92],
                        [78.15, 29.97]
                    ]]
                },
                "date_from": {"start": "2022-01-01", "end": "2022-04-30"},
                "date_to":   {"start": "2024-01-01", "end": "2024-04-30"}
            }
        }
 
def _handle(exc: Exception):
    if isinstance(exc, APIError):
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    raise HTTPException(status_code=500, detail=str(exc))
 

@router.post("/analyze")
async def analyze_route(body: AnalyzeRequest):
    """
    Full 9-class Dynamic World land cover segmentation.
    """
    try:
        return await analyze({
            "polygon":   body.polygon.dict(),
            "days_back": body.days_back,
        })
    except Exception as exc:
        _handle(exc)

@router.post("/change")
async def change_route(body: ChangeRequest):
    """
    Two-period land cover change detection.
    """
    try:
        return await change_detection({
            "polygon":   body.polygon.dict(),
            "date_from": {"start": body.date_from.start, "end": body.date_from.end},
            "date_to":   {"start": body.date_to.start,   "end": body.date_to.end},
        })
    except Exception as exc:
        _handle(exc)
