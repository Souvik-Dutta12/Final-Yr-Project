from fastapi import Request
from utils.api_response import APIResponse
from utils.api_error import APIError
from services.crop_recomendation.crop_service import get_crop_insights, get_crop_insights_polygon

async def get_crop_insights_controller(body: dict):

    features = body.get("features")
    
    print(features)

    if not features:
        raise APIError(
            400,
            "Missing features ."
        )
    
    required_features = ["N", "temperature", "humidity", "ph", "rainfall"]

    for key in required_features:
        if features.get(key) is None:
            raise APIError(400, f"Missing feature: {key}")

    result = get_crop_insights(features)

    return APIResponse(
        200,
        data=result,
        message="Crop insights fetched successfully"
    ).to_dict()

async def get_crop_insights_polygon_controller(body: dict):
    
    soil_data = body.get("soil_data")

    if not soil_data:
        raise APIError(400, "Missing soil_data")

    if "data" not in soil_data:
        raise APIError(400, "Invalid soil_data format")

    if "soil_quality_by_class" not in soil_data["data"]:
        raise APIError(400, "Missing soil_quality_by_class")


    soils = soil_data["data"]["soil_quality_by_class"]
    if not isinstance(soils, list) or len(soils) == 0:
        raise APIError(400, "No soil classes found")
    
    # 🔹 Call servicecd 
    result = get_crop_insights_polygon(
        soil_data=soil_data,
    )

    return APIResponse(
        200,
        data=result,
        message="Polygon crop insights fetched successfully"
    ).to_dict()
