import pandas as pd
import joblib
import numpy as np
from services.load_files import PREV_CROP_DATA_PATH

df = pd.read_csv(PREV_CROP_DATA_PATH)

model = joblib.load("services/crop_recomendation/model/crop_model.pkl")
le = joblib.load("services/crop_recomendation/model/label_encoder.pkl")
scaler = joblib.load("services/crop_recomendation/model/scalar.pkl")


def get_crop_insights(features):
    # ML Prediction (Top 3)
    X = pd.DataFrame([{
        "N": float(features["N"]),
        "temperature": float(features["temperature"]),
        "humidity": float(features["humidity"]),
        "ph": float(features["ph"]),
        "rainfall": float(features["rainfall"])
    }])

    probs = model.predict_proba(X)
    top3_idx = np.argsort(probs[0])[-3:]

    predicted_crops = le.inverse_transform(top3_idx).tolist()


    return {
        "recommendedCrops": predicted_crops
    }


def get_crop_insights_polygon(soil_data):

    result = []
    soil_classes = soil_data["data"]["soil_quality_by_class"]

    for soil in soil_classes:


        soil_class = soil.get("soil_class")
        props = soil.get("properties", {})
        weather = soil.get("weather", {})


        if props.get("nitrogen") is None or props.get("ph") is None:
            continue

        if (
            weather.get("temperature") is None or
            weather.get("humidity") is None or
            weather.get("rainfall") is None
        ):
            continue

        # ML Prediction
        X = pd.DataFrame([{
            "N": float(props["nitrogen"]),
            "temperature": float(weather["temperature"]),
            "humidity": float(weather["humidity"]),
            "ph": float(props["ph"]),
            "rainfall": float(weather["rainfall"])
        }])

        probs = model.predict_proba(X)
        top3_idx = np.argsort(probs[0])[::-1][:3]

        predicted_crops = le.inverse_transform(top3_idx).tolist()

        result.append({
            "soil_class": soil_class,
            "recommendedCrops": predicted_crops
        })

    return {
        "results": result
    }