"""
Normalization + SQI calculation.

Units (after SoilGrids scaling in soilgrids_client.py):
  ph           → actual pH (dimensionless)
  nitrogen     → g/kg
  soc          → %  (g/100g)
  cec          → cmol(c)/kg
  bulk_density → g/cm³
"""

WEIGHTS = {
    "ph":           0.25,
    "nitrogen":     0.20,
    "soc":          0.25,
    "cec":          0.15,
    "bulk_density": 0.15,
}

def normalize_ph(ph: float) -> float:
    if 6.0 <= ph <= 7.5: return 1.0
    if (5.0 <= ph < 6.0) or (7.5 < ph <= 8.5): return 0.7
    return 0.3

def normalize_n(n: float) -> float:
    if n > 0.5: return 1.0
    if n > 0.2: return 0.7
    return 0.3

def normalize_soc(soc: float) -> float:
    if soc > 1.0: return 1.0
    if soc > 0.5: return 0.7
    return 0.3

def normalize_cec(cec: float) -> float:
    if cec > 25: return 1.0
    if cec > 10: return 0.7
    return 0.3

def normalize_bd(bd: float) -> float:
    if bd < 1.3: return 1.0
    if bd < 1.6: return 0.7
    return 0.3

_NORMALIZERS = {
    "ph":           normalize_ph,
    "nitrogen":     normalize_n,
    "soc":          normalize_soc,
    "cec":          normalize_cec,
    "bulk_density": normalize_bd,
}


def calculate_sqi(data: dict) -> dict:
    """
    Compute Soil Quality Index from {param: value | None}.
    Returns soil_quality_index, soil_quality label, and confidence (0–1).
    """
    score = 0.0
    total_weight = 0.0

    for key, value in data.items():
        if value is None or key not in _NORMALIZERS:
            continue
        score += _NORMALIZERS[key](value) * WEIGHTS[key]
        total_weight += WEIGHTS[key]

    if total_weight == 0:
        return {"soil_quality_index": None, "soil_quality": "No Data", "confidence": 0.0}

    final_score = score / total_weight
    confidence  = round(total_weight / sum(WEIGHTS.values()), 4)

    quality = (
        "Good" if final_score > 0.80 else
        "Average" if final_score > 0.50 else
        "Poor"
    )

    return {
        "soil_quality_index": round(final_score, 4),
        "soil_quality": quality,
        "confidence": confidence,
    }