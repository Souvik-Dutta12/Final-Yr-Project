import pandas as pd
import joblib
import numpy as np
from services.load_files import PREV_CROP_DATA_PATH

df = pd.read_csv(PREV_CROP_DATA_PATH)

model = joblib.load("services/crop_recomendation/model/crop_model.pkl")
le = joblib.load("services/crop_recomendation/model/label_encoder.pkl")
scaler = joblib.load("services/crop_recomendation/model/scalar.pkl")


def get_crop_insights(state , district, features):
    # Normalize text
    df["state_name"] = df["state_name"].str.lower()
    df["district_name"] = df["district_name"].str.lower()

    state = state.lower()
    district = district.lower()

    # Current crops
    filtered = df[
        (df["state_name"] == state) &
        (df["district_name"] == district)
    ]

    current_crops = list(filtered["crop_name"].unique()) if not filtered.empty else []

    # ML Prediction (Top 3)
    X = pd.DataFrame([{
        "N": features["N"],
        "temperature": features["temperature"],
        "humidity": features["humidity"],
        "ph": features["ph"],
        "rainfall": features["rainfall"]
    }])

    X_scaled = scaler.transform(X)
    X_scaled = pd.DataFrame(X_scaled, columns=X.columns)
    probs = model.predict_proba(X_scaled)
    top3_idx = np.argsort(probs[0])[-3:]

    predicted_crops = le.inverse_transform(top3_idx)

    # Remove duplicates
    extra_crops = [c for c in predicted_crops if c not in current_crops]

    return {
        "currentCrops": current_crops,
        "recommendedCrops": extra_crops
    }