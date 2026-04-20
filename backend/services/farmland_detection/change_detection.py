"""
Change Detection Service — Dynamic World two-period comparison
 
Compares land cover between two date windows and reports:
  ▸ Per-class area gained / lost (ha)
  ▸ Transition matrix  (from-class → to-class pixel counts)
  ▸ Change mask         (pixels that changed class)
  ▸ NDVI delta          (vegetation index difference)
 
This is the "powerful engineering" layer that elevates the project from
a snapshot classifier into a temporal monitoring tool — valuable for:
  • Deforestation / afforestation detection
  • Crop rotation / harvest cycle tracking
  • Urban expansion monitoring
  • Flood inundation mapping
 
Architecture
------------
Both periods are fetched via `fetch_dynamic_world` (with separate cache
keys), so results are automatically cached per window independently.
 
The comparison is done in pure numpy — no additional GEE calls needed.
"""

import logging
import numpy as np
import io
import requests
import ee

from typing import Any, Dict, List, Optional, Tuple 
from scipy.ndimage import uniform_filter   
from rasterio.transform import from_bounds
from datetime import datetime, timedelta

from services.farmland_detection.constants.dw_classes import DW_CLASSES, IDX_TO_CLASS, DW_BAND_NAMES, adaptive_scale
from utils.farmland_detection.polygon_utils import polygon_area_km2, polygon_bounds 
from services.earth_engine.ee_service import (
    fetch_dynamic_world,
    _to_ee_geom,
    _build_s2_indices,
    _download_npy
    )
from utils.farmland_detection.cache import gee_cache
from utils.api_error import APIError



logger = logging.getLogger(__name__)

# High-value transitions worth flagging explicitly
NOTABLE_TRANSITIONS = {
    ("trees",      "built"):      "Deforestation → Urban",
    ("trees",      "crops"):      "Deforestation → Agriculture",
    ("trees",      "bare"):       "Deforestation → Bare Ground",
    ("crops",      "built"):      "Agricultural Land Loss → Urban",
    ("water",      "built"):      "Wetland Reclamation",
    ("flooded_vegetation", "crops"): "Wetland → Cropland",
    ("grass",      "built"):      "Grassland → Urban Sprawl",
    ("bare",       "crops"):      "Land Reclamation → Agriculture",
    ("snow_and_ice","bare"):      "Glacial Retreat",
}
 
# alignment helper
def _align_labels(
    label_a: np.ndarray,
    label_b: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Resize label_b to match label_a's shape if they differ.
    Uses nearest-neighbour resampling (preserves integer class indices).
    """
    if label_a.shape == label_b.shape:
        return label_a, label_b
 
    from PIL import Image as PILImage
    h, w = label_a.shape
    img_b = PILImage.fromarray(label_b.astype(np.uint8))
    label_b_resized = np.array(
        img_b.resize((w, h), PILImage.NEAREST)
    ).astype(np.int8)
    logger.warning(
        "Label grids mismatched; label_b resampled %s → %s",
        label_b.shape, label_a.shape
    )
    return label_a, label_b_resized

def _class_stats(label: np.ndarray, scale_m: int) -> Dict[str, Dict]:
    """Per-class pixel count and area for a single label grid."""
    total  = label.size
    px_m2  = scale_m ** 2
    result = {}
    for cls in DW_CLASSES:
        px        = int((label == cls.idx).sum())
        result[cls.name] = {
            "pixel_count":   px,
            "area_ha":       round(px * px_m2 / 10_000, 3),
            "coverage_pct":  round(px / total * 100, 2),
        }
    return result

def _transition_matrix(
    label_a: np.ndarray,
    label_b: np.ndarray,
    n_classes: int = 9,
) -> np.ndarray:
    """
    Build an n×n transition count matrix.
    matrix[i, j] = pixels that were class i in period A and class j in B.
    """
    flat_a = label_a.flatten().astype(int)
    flat_b = label_b.flatten().astype(int)
    valid  = (flat_a >= 0) & (flat_a < n_classes) & \
             (flat_b >= 0) & (flat_b < n_classes)
    matrix = np.zeros((n_classes, n_classes), dtype=np.int64)
    np.add.at(matrix, (flat_a[valid], flat_b[valid]), 1)
    return matrix
 
def _notable_transitions(matrix: np.ndarray, scale_m: int) -> List[Dict]:
    """Extract human-readable notable transitions above a minimum area."""
    MIN_HA = 0.5
    px_m2  = scale_m ** 2
    results = []
    for (from_name, to_name), label in NOTABLE_TRANSITIONS.items():
        from_cls = next((c for c in DW_CLASSES if c.name == from_name), None)
        to_cls   = next((c for c in DW_CLASSES if c.name == to_name),   None)
        if from_cls is None or to_cls is None:
            continue
        px      = int(matrix[from_cls.idx, to_cls.idx])
        area_ha = round(px * px_m2 / 10_000, 3)
        if area_ha >= MIN_HA:
            results.append({
                "from":     from_name,
                "to":       to_name,
                "label":    label,
                "area_ha":  area_ha,
                "pixels":   px,
            })
    return sorted(results, key=lambda r: r["area_ha"], reverse=True)

def detect_changes(
    polygon:      dict,
    date_from:    Tuple[str, str],  
    date_to:      Tuple[str, str],
) -> Dict[str, Any]:
    
    """
    Compare Dynamic World land cover between two date windows.
 
    Parameters
    ----------
    polygon   : GeoJSON Polygon dict
    date_from : (start, end) for the baseline period
    date_to   : (start, end) for the comparison period
 
    Returns
    -------
    dict with keys:
        period_a_stats    — per-class stats for baseline
        period_b_stats    — per-class stats for comparison
        class_deltas      — area change (ha) per class
        transition_matrix — 9×9 list-of-lists (JSON-safe)
        notable           — list of significant transitions
        ndvi_delta_mean   — mean NDVI change (float)
        changed_pct       — % of pixels that changed class
        scale_m           — resolution used
    """

    # Fetch both periods
    def _days(start_s, end_s):
        from datetime import datetime
        d0 = datetime.strptime(start_s, "%Y-%m-%d")
        d1 = datetime.strptime(end_s,   "%Y-%m-%d")
        return max((d1 - d0).days, 1)
    
    today = datetime.utcnow()
 
    def _days_back_for(start_s, end_s):
        end_d = datetime.strptime(end_s, "%Y-%m-%d")
        return max((today - end_d).days + _days(start_s, end_s), 1)
 
    days_a = _days_back_for(*date_from)
    days_b = _days_back_for(*date_to)

    # two-period control we call GEE directly here.
    result_a = _fetch_for_window(polygon, *date_from)
    result_b = _fetch_for_window(polygon, *date_to)
 
    label_a, label_b = _align_labels(result_a["label"], result_b["label"])
    scale_m = result_a["scale"]

    # preclass stats
    stats_a = _class_stats(label_a, scale_m)
    stats_b = _class_stats(label_b, scale_m)

    # deltas
    deltas = {
        cls.name: {
            "area_ha_a":    stats_a[cls.name]["area_ha"],
            "area_ha_b":    stats_b[cls.name]["area_ha"],
            "delta_ha":     round(stats_b[cls.name]["area_ha"] -
                                  stats_a[cls.name]["area_ha"], 3),
            "delta_pct":    round(stats_b[cls.name]["coverage_pct"] -
                                  stats_a[cls.name]["coverage_pct"], 2),
        }
        for cls in DW_CLASSES
    }
 
    # transition mat
    matrix     = _transition_matrix(label_a, label_b)
    notable    = _notable_transitions(matrix, scale_m)
    changed_px = int((label_a != label_b).sum())
    changed_pct = round(changed_px / label_a.size * 100, 2)

    # NDVI Delta

    ndvi_a = result_a["indices"]["ndvi"]
    ndvi_b = result_b["indices"]["ndvi"]
    # Align shapes if scale differed
    if ndvi_a.shape != ndvi_b.shape:
        from PIL import Image as PILImage
        h, w = ndvi_a.shape
        ndvi_b = np.array(
            PILImage.fromarray(ndvi_b).resize((w, h), PILImage.BILINEAR)
        )
    valid = np.isfinite(ndvi_a) & np.isfinite(ndvi_b)
    ndvi_delta_mean = round(float((ndvi_b[valid] - ndvi_a[valid]).mean()), 4) \
                      if valid.any() else None
    

    return {
        "period_a":           {"start": date_from[0], "end": date_from[1]},
        "period_b":           {"start": date_to[0],   "end": date_to[1]},
        "scale_m":            scale_m,
        "period_a_stats":     stats_a,
        "period_b_stats":     stats_b,
        "class_deltas":       deltas,
        "transition_matrix":  matrix.tolist(),
        "notable_transitions":notable,
        "changed_pct":        changed_pct,
        "ndvi_delta_mean":    ndvi_delta_mean,
        "interpretation": (
            "Positive delta_ha = class expanded; "
            "negative = class shrank. "
            "ndvi_delta_mean > 0 = net vegetation gain."
        ),
    }

def _fetch_for_window(polygon: dict, start_str: str, end_str: str) -> Dict:
    """
    Like fetch_dynamic_world but with an explicit date window instead of
    days_back.  Shares the same numpy / transform logic.
    """
    cache_key = gee_cache.make_key(polygon, start = start_str, end = end_str)
    cached = gee_cache.get(cache_key)
    if cached is not None:
        return cached
 
    area_km2 = polygon_area_km2(polygon)
    scale    = adaptive_scale(area_km2)
    roi      = _to_ee_geom(polygon)
 
    dw_col = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(roi)
        .filterDate(start_str, end_str)
    )
    dw_label_img = dw_col.select("label").mode().clip(roi)
    dw_probs_img = dw_col.select(DW_BAND_NAMES).mean().clip(roi)
 
    s2_col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(start_str, end_str)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .select(["B2", "B3", "B4", "B8", "B11"])
    )
    s2_median   = s2_col.median().clip(roi)
    indices_img = _build_s2_indices(s2_median)
 
    arr_lbl  = _download_npy(dw_label_img, roi, scale)
    arr_prob = _download_npy(dw_probs_img, roi, scale)
    arr_idx  = _download_npy(indices_img,  roi, scale)
 
    label   = arr_lbl["label"].astype(np.int8)
    probs   = {n: arr_prob[n].astype(np.float32) for n in DW_BAND_NAMES}
    indices = {
        "ndvi":  arr_idx["NDVI"].astype(np.float32),
        "ndwi":  arr_idx["NDWI"].astype(np.float32),
        "ndbi":  arr_idx["NDBI"].astype(np.float32),
        "mndwi": arr_idx["MNDWI"].astype(np.float32),
        "evi":   arr_idx["EVI"].astype(np.float32),
    }
 
    minx, miny, maxx, maxy = polygon_bounds(polygon)
    h, w      = label.shape
    transform = from_bounds(minx, miny, maxx, maxy, w, h)
 
    result = {
        "label": label, "probs": probs, "indices": indices,
        "transform": transform, "scale": scale,
    }
    gee_cache.set(cache_key, result)
    return result
 