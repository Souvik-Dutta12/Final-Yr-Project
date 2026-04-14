from fastapi import APIRouter
from controllers.crop_controller import get_crop_insights_controller
from utils.async_handler import async_handler

router = APIRouter()

@router.post("/crop-insights")
@async_handler
async def crop_insights(body: dict):
    return await get_crop_insights_controller(body)