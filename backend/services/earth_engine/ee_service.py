"""
Key engineering choices
-----------------------
1. Adaptive scale       — pixel budget kept under GEE's 32 M pixel limit
2. Cloud-gap-fill       — median composite over `days_back` window with a fallback to 120-day window on empty results
3. Structured numpy     — downloaded as NPY structured arrays (one field per band), minimising bandwidth vs multi-band TIFF
4. TTL cache            — results cached 15 min to avoid redundant GEE calls
"""

import ee
import requests, io
import numpy as np
import logging
import requests

from rasterio.transform import from_bounds
from shapely.geometry import shape
from datetime import datetime, timedelta
from typing import Dict, Any

from services.farmland_detection.constants.dw_classes import (
    DW_BAND_NAMES, MAX_POLYGON_AREA_KM2, adaptive_scale
)
from utils.farmland_detection.cache import gee_cache
from utils.farmland_detection.polygon_utils import polygon_area_km2, polygon_bounds
from utils.api_error import APIError

logger = logging.getLogger(__name__)
ee.Initialize(project="satelite-490001")


def _to_ee_geom(polygon: dict) -> ee.Geometry:
    return ee.Geometry.Polygon(polygon["coordinates"])
 
def _date_window(days_back: int):
    """Return (start_str, end_str) in 'YYYY-MM-DD' format."""
    end   = datetime.utcnow()
    start = end - timedelta(days=days_back)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
  
def _download_npy(image: ee.Image, roi: ee.Geometry, scale: int) -> np.ndarray:
    """Download a GEE image as a numpy structured array."""
    url = image.getDownloadURL({
        "region": roi,
        "scale":  scale,
        "format": "NPY",
        "crs":    "EPSG:4326",
    })
    resp = requests.get(url, timeout=240)
    if resp.status_code != 200:
        raise APIError(502, f"GEE download failed (HTTP {resp.status_code}).")
    return np.load(io.BytesIO(resp.content))
 
def _build_s2_indices(s2: ee.Image) -> ee.Image:
    """Compute the five spectral indices from an S2 image."""
    B2, B3, B4, B8, B11 = (s2.select(b) for b in ["B2","B3","B4","B8","B11"])
    ndvi  = B8.subtract(B4).divide(B8.add(B4)).rename("NDVI")
    ndwi  = B3.subtract(B8).divide(B3.add(B8)).rename("NDWI")
    ndbi  = B11.subtract(B8).divide(B11.add(B8)).rename("NDBI")
    mndwi = B3.subtract(B11).divide(B3.add(B11)).rename("MNDWI")
    evi   = (B8.subtract(B4).multiply(2.5)
              .divide(B8.add(B4.multiply(6))
                        .subtract(B2.multiply(7.5)).add(1))
              .rename("EVI"))
    return ee.Image([ndvi, ndwi, ndbi, mndwi, evi])
 
# Fetch dynamic world
def fetch_dynamic_world(polygon: dict, days_back: int = 60) -> Dict[str, Any]:
    """
    Fetch Dynamic World labels + per-class probabilities + S2 indices.
 
    Parameters
    ----------
    polygon   : GeoJSON Polygon dict (EPSG:4326)
    days_back : composite window in days (auto-extended on empty results)
 
    Returns
    -------
    dict with keys:
        label      — (H, W) int8 array   : dominant class index per pixel
        probs      — dict[str → (H,W)]   : mean probability per DW class
        indices    — dict[str → (H,W)]   : NDVI / NDWI / NDBI / EVI / MNDWI
        transform  — rasterio Affine
        crs        — 'EPSG:4326'
        scale      — GEE download scale in metres
        area_km2   — polygon area estimate
        date_range — (start_str, end_str) used for the composite
        pixel_count— total valid pixels
    """

    # cache lookup
    cache_key = gee_cache.make_key(polygon, days_back=days_back)
    cached = gee_cache.get(cache_key)
    if cached is not None:
        logger.info("GEE cache hit — skipping download.")
        return cached

    # validate polygon size
    area_km2 = polygon_area_km2(polygon)
    if area_km2 > MAX_POLYGON_AREA_KM2:
        raise APIError(
            400,
            f"Polygon area ({area_km2:.0f} km²) exceeds the maximum allowed "
            f"({MAX_POLYGON_AREA_KM2} km²). Split into smaller tiles or "
            "reduce the area."
        )
 
    scale = adaptive_scale(area_km2)
    roi   = _to_ee_geom(polygon)
 
    logger.info(
        "Fetching DW for %.1f km² polygon | scale=%dm | window=%dd",
        area_km2, scale, days_back
    )

    # Dynamic world compoaites
    start_str, end_str = _date_window(days_back)
    dw_col = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(roi)
        .filterDate(start_str, end_str)
    )

    # extend window if collection is empty
    count = dw_col.size().getInfo()
    if count == 0:
        logger.warning("No DW images in %d-day window; extending to 120 days.", days_back)
        start_str, end_str = _date_window(120)
        dw_col = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(roi)
            .filterDate(start_str, end_str)
        )
        count = dw_col.size().getInfo()
        if count == 0:
            raise APIError(
                404,
                "No Dynamic World imagery found for this area in the last 120 days. "
                "Check polygon location or try again later."
            )
 
    logger.info("Using %d DW scenes (%s → %s)", count, start_str, end_str)

    # Mode composite for label; mean for probability bands
    dw_label_img = dw_col.select("label").mode().clip(roi)
    dw_probs_img = dw_col.select(DW_BAND_NAMES).mean().clip(roi)
 
    # Sentinel-2 indices
    s2_col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(start_str, end_str)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15))
        .select(["B2", "B3", "B4", "B8", "B11"])
    )
 
    s2_fallback = s2_col.size().getInfo() == 0

    if s2_fallback:
        # Widen cloud threshold for very cloudy regions
        s2_col = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(roi)
            .filterDate(start_str, end_str)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
            .select(["B2", "B3", "B4", "B8", "B11"])
        )
 
    s2_median  = s2_col.median().clip(roi)
    indices_img = _build_s2_indices(s2_median)

    # download
    try:
        arr_lbl  = _download_npy(dw_label_img, roi, scale)
        arr_prob = _download_npy(dw_probs_img, roi, scale)
        arr_idx  = _download_npy(indices_img,  roi, scale)
    except ee.EEException as exc:
        raise APIError(502, f"Earth Engine computation error: {exc}") from exc
    
    # parse Numpy array
    label = arr_lbl["label"].astype(np.int8)
    probs = {name: arr_prob[name].astype(np.float32) for name in DW_BAND_NAMES}
    indices = {
        "ndvi":  arr_idx["NDVI"].astype(np.float32),
        "ndwi":  arr_idx["NDWI"].astype(np.float32),
        "ndbi":  arr_idx["NDBI"].astype(np.float32),
        "mndwi": arr_idx["MNDWI"].astype(np.float32),
        "evi":   arr_idx["EVI"].astype(np.float32),
    }

    # buld rasterio transfrom
    minx, miny, maxx, maxy = polygon_bounds(polygon)
    h, w      = label.shape
    transform = from_bounds(minx, miny, maxx, maxy, w, h)
 
    result = {
        "label":       label,
        "probs":       probs,
        "indices":     indices,
        "transform":   transform,
        "crs":         "EPSG:4326",
        "scale":       scale,
        "area_km2":    area_km2,
        "date_range":  (start_str, end_str),
        "pixel_count": int(label.size),
        "scene_count": count,
    }
 
    gee_cache.set(cache_key, result)
    return result