import pandas as pd
import joblib
import numpy as np


model = joblib.load("services/crop_recomendation/model/stacking_model.pkl")
scaler = joblib.load("services/crop_recomendation/model/standard_scaler.pkl")
pt = joblib.load("services/crop_recomendation/model/power_transformer.pkl")
le = joblib.load("services/crop_recomendation/model/label_encoder.pkl")

skewed_cols = ['N', 'humidity', 'rainfall', 'N_humidity', 'rain_temp_ratio', 'log_rainfall', 'log_N']
other_cols = ['temperature', 'ph', 'humidity_temp', 'ph_dev']

def add_features(X):
    X = X.copy()
    # Humidity × Temperature → heat-moisture stress index
    X['humidity_temp'] = X['humidity'] * X['temperature']
    # Rainfall / (temperature + 1) → moisture efficiency
    X['rain_temp_ratio'] = X['rainfall'] / (X['temperature'] + 1)
    # ph deviation from neutral (7)
    X['ph_dev'] = (X['ph'] - 7).abs()
    # N × humidity → nitrogen availability under moisture
    X['N_humidity'] = X['N'] * X['humidity']
    # Log-transform heavy-tailed features
    X['log_rainfall'] = np.log1p(X['rainfall'])
    X['log_N'] = np.log1p(X['N'])
    return X

def preprocess_input(df):
    df = add_features(df)

    df[skewed_cols] = pt.transform(df[skewed_cols])
    df[other_cols] = scaler.transform(df[other_cols])

    return df


def get_crop_insights(features):
    # ML Prediction (Top 3)
    X = pd.DataFrame([{
        "N": float(features["N"]),
        "temperature": float(features["temperature"]),
        "humidity": float(features["humidity"]),
        "ph": float(features["ph"]),
        "rainfall": float(features["rainfall"])
    }])

    X = preprocess_input(X)

    probs = model.predict_proba(X)[0]
    top_idx = np.argsort(probs)[::-1][:3]
    crops = le.classes_[top_idx]
    confidence = probs[top_idx]

    return {
        "recommendedCrops": [
            {
                "crop": crop,
                "confidence": float(round(conf * 100,2))
            }

            for crop,conf in zip(crops,confidence)
        ]
    }


def get_crop_insights_polygon(soil_data):

    result = []
    soil_classes = soil_data["data"]["soil_quality_by_class"]

    for soil in soil_classes:


        soil_class = soil.get("soil_class")
        props = soil.get("properties", {})
        weather = soil.get("weather", {})


        if not all([
            props.get("nitrogen"),
            props.get("ph"),
            weather.get("temperature"),
            weather.get("humidity"),
            weather.get("rainfall")
        ]):
            continue

        # ML Prediction
        X = pd.DataFrame([{
            "N": float(props["nitrogen"]),
            "temperature": float(weather["temperature"]),
            "humidity": float(weather["humidity"]),
            "ph": float(props["ph"]),
            "rainfall": float(weather["rainfall"])
        }])

        
        X = preprocess_input(X)

        probs = model.predict_proba(X)[0]
        top_idx = np.argsort(probs)[::-1][:3]

        crops = le.classes_[top_idx]
        confidences = probs[top_idx]

        result.append({
            "soil_class": soil_class,
            "recommendedCrops": [
                {
                    "crop":crop,
                    "confidence":float(round(conf * 100,2))
                }
                for crop, conf in zip(crops, confidences)
            ]
        })

    return {
        "results": result
    }