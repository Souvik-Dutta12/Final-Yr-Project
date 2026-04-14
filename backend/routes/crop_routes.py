from fastapi import APIRouter
from controllers.crop_controller import get_crop_insights_controller, get_crop_insights_polygon_controller
from utils.async_handler import async_handler

router = APIRouter(prefix="/crops-reccomendation", tags=["Crops"])

@router.post("/crop-insights")
@async_handler
async def crop_insights(body: dict):
    return await get_crop_insights_controller(body)

@router.post("/crop-insights/polygon")
@async_handler
async def crop_insights_polygon(body: dict):
    return await get_crop_insights_polygon_controller(body)