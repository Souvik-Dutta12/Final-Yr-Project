from fastapi import FastAPI
from fastapi.responses import JSONResponse
from utils.api_error import APIError
from routes.soil_routes import router as soil_router
from routes.farmland_routes import router as farmland_router
from routes.crop_routes import router as crop_router

app = FastAPI()

@app.exception_handler(APIError)
async def api_error_handler(request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

app.include_router(soil_router)
app.include_router(farmland_router)
app.include_router(crop_router)

@app.get("/")
def home():
    return {"message": "Backend is running..."}

@app.get("/health")
def health():
    """
    Lightweight liveness probe.
    Returns 200 immediately — no I/O, no external calls.
    Used by the frontend queue manager to decide whether to accept new jobs.
    """
    return {"status": "ok"}
 