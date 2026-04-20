"""
Land Cover Service — Full 9-class Dynamic World pipeline
 
Endpoint contract
-----------------
Input  : GeoJSON Polygon (EPSG:4326)
Output : {
    type:     'FeatureCollection',
    features: [ ...GeoJSON Feature per class... ],
    metadata: {
        scale_m, area_km2, scene_count, date_range,
        class_stats, index_stats,
        imagery_source, model
    }
}
"""
import logging
from typing import Dict, Any

import numpy as np

from utils.api_error import APIError
from services.farmland_detection.constants.dw_classes import DW_CLASSES, IDX_TO_CLASS, DW_BAND_NAMES
from services.earth_engine.ee_service import fetch_dynamic_world
from services.farmland_detection.geo_json_service import masks_to_geojson

logger = logging.getLogger(__name__)

# summery stats
def _class_stats(
    label:    np.ndarray,
    probs:    Dict[str, np.ndarray],
    scale_m:  int,
) -> Dict[str, Dict[str, Any]]:
    """
    Per-class pixel count, area, coverage and mean confidence.
    """
    total  = label.size
    px_m2  = scale_m ** 2
    result = {}
    for cls in DW_CLASSES:
        mask    = label == cls.idx
        px      = int(mask.sum())
        prob_m  = probs.get(cls.name)
        conf    = None
        if prob_m is not None and px > 0:
            vals = prob_m[mask & np.isfinite(prob_m)]
            conf = round(float(vals.mean()), 3) if vals.size else None
 
        result[cls.name] = {
            "label":         cls.label,
            "color":         cls.color,
            "pixel_count":   px,
            "area_ha":       round(px * px_m2 / 10_000, 3),
            "coverage_pct":  round(px / total * 100, 2),
            "confidence":    conf,
        }
    return result
 
def _index_stats(indices: Dict[str, np.ndarray]) -> Dict[str, Dict]:
    """
    Min / max / mean / std for each spectral index.
    """
    result = {}
    for name, arr in indices.items():
        valid = arr[np.isfinite(arr)]
        if valid.size == 0:
            result[name] = None
            continue
        result[name] = {
            "min":  round(float(valid.min()),  4),
            "max":  round(float(valid.max()),  4),
            "mean": round(float(valid.mean()), 4),
            "std":  round(float(valid.std()),  4),
        }
    return result

def _dominant_confidence(label: np.ndarray, probs: Dict[str, np.ndarray]) -> float:
    """
    Mean probability of the winning class across all pixels.
    High value → model is confident; low → high spatial ambiguity.
    """
    # Stack all probability bands (9, H, W)
    stack = np.stack([probs[n] for n in DW_BAND_NAMES], axis=0)  # (9, H, W)
    max_prob = stack.max(axis=0)   # (H, W)
    valid = max_prob[np.isfinite(max_prob)]
    return round(float(valid.mean()), 3) if valid.size else 0.0
 
async def analyze_land_cover(
    polygon:  dict,
    days_back: int = 60,
) -> Dict[str, Any]:
    """
    Full 9-class land cover analysis via Dynamic World V1.
 
    Parameters
    ----------
    polygon   : validated GeoJSON Polygon dict (EPSG:4326)
    days_back : imagery composite window (default 60 days)
 
    Returns
    -------
    GeoJSON FeatureCollection with metadata
    """
    
    # Fetch dynamic world + sentinel indices
    dw = fetch_dynamic_world(polygon, days_back=days_back)
 
    label     = dw["label"]
    probs     = dw["probs"]
    indices   = dw["indices"]
    transform = dw["transform"]
    scale_m   = dw["scale"]

    # Build per-class boolean masks from the mode label 
    # Only classes actually present in the AOI are included.
    masks = {}
    for cls in DW_CLASSES:
        m = label == cls.idx
        if m.any():
            masks[cls.name] = m
 
    logger.info(
        "Classes detected: %s",
        [k for k in masks]
    )

    #convert into  geojson
    features = masks_to_geojson(
        masks       = masks,
        transform   = transform,
        probs       = probs,
        src_crs     = dw["crs"],
        min_area_m2 = _min_area_for_scale(scale_m),
    )
    

    class_stats  = _class_stats(label, probs, scale_m)
    index_stats  = _index_stats(indices)
    dom_conf     = _dominant_confidence(label, probs)
    
    return {
        "type":     "FeatureCollection",
        "features": features,
        "metadata": {
            "model":            "Dynamic World V1 (Google / WRI, pre-trained deep learning)",
            "imagery_source":   "Sentinel-2 SR Harmonized",
            "resolution_m":     scale_m,
            "area_km2":         round(dw["area_km2"], 2),
            "date_range":       {
                "start": dw["date_range"][0],
                "end":   dw["date_range"][1],
            },
            "scene_count":      dw["scene_count"],
            "total_pixels":     dw["pixel_count"],
            "classes_detected": list(masks.keys()),
            "dominant_confidence": dom_conf,   # 0–1 overall model confidence
            "class_stats":      class_stats,
            "index_stats":      index_stats,
        },
    }

def _min_area_for_scale(scale_m: int) -> float:
    """
    Minimum polygon area (m²) to retain in GeoJSON output.
    Scales with resolution to avoid keeping 1-pixel artefacts.
    Roughly 9 pixels minimum.
    """
    return max(1_000.0, (scale_m ** 2) * 9)
