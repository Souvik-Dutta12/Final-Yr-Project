from fastapi import APIRouter, Body
from utils.async_handler import async_handler
from controllers.farmland_controller import analyze_farmland

router = APIRouter()

@router.post("/farmland/analyse")
@async_handler
async def farmland_route(body: dict = Body(...)):
    return await analyze_farmland(body)
