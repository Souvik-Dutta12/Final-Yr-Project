from fastapi import FastAPI
from fastapi.responses import JSONResponse
from utils.api_error import APIError
from routes.soil_routes import router as soil_router
from routes.farmland_routes import router as farmland_router
from routes.crop_routes import router as crop_router
from monitoring.routes.monitoring_routes import router as monitoring_router
from monitoring.routes.alert_routes import router as alert_router

app = FastAPI(
    title="Agricultural Monitoring API",
    description="Python Core Server — satellite analysis, monitoring, alerts",
    version="1.0.0"
)

@app.exception_handler(APIError)
async def api_error_handler(request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

app.include_router(soil_router)
app.include_router(farmland_router)
app.include_router(crop_router)
app.include_router(monitoring_router)
app.include_router(alert_router)

@app.get("/")
def home():
    return {"message": "Agricultural Monitoring Platform — Python Core Server"}

@app.get("/health")
def health():
    """
    Lightweight liveness probe.
    Returns 200 immediately — no I/O, no external calls.
    Used by the frontend queue manager to decide whether to accept new jobs.
    """
    return {"status": "ok"}
 