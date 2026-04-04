from fastapi import FastAPI
from fastapi.responses import JSONResponse
from utils.api_error import APIError
from routes.soil_routes import router as soil_router

app = FastAPI()

@app.exception_handler(APIError)
async def api_error_handler(request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

app.include_router(soil_router)

@app.get("/")
def home():
    return {"message": "Backend is running..."}
