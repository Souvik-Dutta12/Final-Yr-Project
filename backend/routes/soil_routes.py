from fastapi import APIRouter
from controllers.soil_controller import (
    get_soil_point,
    get_soil_polygon
)
from utils.async_handler import async_handler

router = APIRouter(prefix="/soil", tags=["Soil"])

@router.get("/")
@async_handler
async def get_soil(lat: float, lon: float):
    return await get_soil_point(lat, lon)

@router.post("/polygon")
@async_handler
async def get_soil_poly(data: dict):
    polygon = data.get("polygon")

    return await get_soil_polygon(polygon)