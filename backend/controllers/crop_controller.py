from fastapi import Request
from utils.api_response import APIResponse
from utils.api_error import APIError
from services.crop_recomendation.crop_service import get_crop_insights

async def get_crop_insights_controller(body: dict):
    state = body.get("state")
    district = body.get("district")
    features = body.get("features")

    if not state or not district or not features:
        raise APIError(400, "Missing required fields")

    required_features = ["N", "temperature", "humidity", "ph", "rainfall"]
    for key in required_features:
        if features.get(key) is None:
            return APIResponse(
                200,
                data = {"msg":"soil is not suitable for any type of crops ."},
                message = "Crop insights fetched successfully"
            ).to_dict()
        if key not in features:
            raise APIError(400, f"Missing feature: {key}")

    result = get_crop_insights(state, district, features)

    return APIResponse(
        200,
        data=result,
        message="Crop insights fetched successfully"
    ).to_dict()