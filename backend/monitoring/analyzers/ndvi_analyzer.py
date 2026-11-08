"""
NDVI & spectral index analyzer.
Extracts summary statistics from GEE index arrays already fetched
by the land cover service — no additional GEE call needed.
"""
import logging
from typing import Dict, Optional
import numpy as np

from monitoring.models.snapshot_models import NDVIStats

logger = logging.getLogger(__name__)


def extract_ndvi_stats(indices: Dict[str, np.ndarray]) -> Optional[NDVIStats]:
    """
    Compute summary statistics from the spectral index arrays returned
    by fetch_dynamic_world (already in memory — free computation).

    Parameters
    ----------
    indices : dict from ee_service — keys: ndvi, ndwi, ndbi, mndwi, evi

    Returns
    -------
    NDVIStats or None if arrays are empty/invalid.
    """
    ndvi = indices.get("ndvi")
    if ndvi is None:
        return None

    valid_ndvi = ndvi[np.isfinite(ndvi)]
    if valid_ndvi.size == 0:
        logger.warning("NDVI array has no valid pixels")
        return None

    def _safe_mean(key: str) -> Optional[float]:
        arr = indices.get(key)
        if arr is None:
            return None
        valid = arr[np.isfinite(arr)]
        return round(float(valid.mean()), 4) if valid.size > 0 else None

    return NDVIStats(
        ndvi_mean=round(float(valid_ndvi.mean()), 4),
        ndvi_min=round(float(valid_ndvi.min()),  4),
        ndvi_max=round(float(valid_ndvi.max()),  4),
        ndvi_std=round(float(valid_ndvi.std()),  4),
        ndwi_mean=_safe_mean("ndwi"),
        evi_mean=_safe_mean("evi"),
        ndbi_mean=_safe_mean("ndbi"),
    )

def classify_vegetation_health(ndvi_mean: float) -> str:
    """
    Simple NDVI-based vegetation health classification.
    Used for human-readable labels in reports and alerts.
    """
    if ndvi_mean >= 0.6:  return "Excellent"
    if ndvi_mean >= 0.4:  return "Good"
    if ndvi_mean >= 0.2:  return "Moderate"
    if ndvi_mean >= 0.1:  return "Sparse"
    return "Bare / Stressed"

def detect_ndvi_anomaly(
    current_ndvi_mean: float,
    historical_ndvi_means: list[float],
) -> Dict:
    """
    Compare current NDVI to historical baseline.
    Returns anomaly score and direction.
    """
    if not historical_ndvi_means:
        return {
            "anomaly": False, 
            "z_score": None, 
            "delta_from_mean": None
        }

    hist = np.array(historical_ndvi_means)
    mean = float(hist.mean())
    std  = float(hist.std()) if len(hist) > 1 else 0.05

    delta = current_ndvi_mean - mean
    z_score = delta / std if std > 0 else 0.0

    return {
        "anomaly": abs(z_score) > 2.0,
        "z_score": round(z_score, 2),
        "delta_from_mean": round(delta, 4),
        "historical_mean": round(mean, 4),
        "historical_std": round(std, 4),
        "direction": "decline" if delta < 0 else "improvement",
    }