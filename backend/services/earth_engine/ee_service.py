import ee
import requests, io
import numpy as np
from utils.api_error import APIError
from rasterio.transform import from_bounds
from shapely.geometry import shape
from datetime import datetime

ee.Initialize(project="satelite-490001")

def _polygon_to_ee(polygon: dict) -> ee.Geometry:
    """Convert a GeoJSON Polygon to an Earth Engine Geometry."""
    coords = polygon["coordinates"]
    return ee.Geometry.Polygon(coords)

def fetch_indices(polygon: dict, days_back: int = 30)->dict:
    """
    Fetch a recent Sentinel-2 composite for the polygon and return
    NDVI, NDWI, NDBI, EVI, MNDWI arrays plus the affine transform.

    Returns a dict with keys:
        ndvi, ndwi, ndbi, evi, mndwi   → 2-D float32 np.ndarray
        transform                      → rasterio-compatible Affine
        crs                            → EPSG string
    """

    roi = _polygon_to_ee(polygon)

    # ── Sentinel-2 SR, last N days, cloud < 10% ───────────────────────────
    end   = ee.Date(ee.Date(datetime.now()))
    start = end.advance(-days_back, "day")

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 10))
        .select(["B2", "B3", "B4", "B8", "B11", "B12"])
        .median()          # cloud-free composite
        .clip(roi)
    )


    # ── Spectral indices ──────────────────────────────────────────────────
    B2  = s2.select("B2")   # Blue
    B3  = s2.select("B3")   # Green
    B4  = s2.select("B4")   # Red
    B8  = s2.select("B8")   # NIR
    B11 = s2.select("B11")  # SWIR-1
    B12 = s2.select("B12")  # SWIR-2

    ndvi  = B8.subtract(B4).divide(B8.add(B4)).rename("NDVI")
    ndwi  = B3.subtract(B8).divide(B3.add(B8)).rename("NDWI")
    ndbi  = B11.subtract(B8).divide(B11.add(B8)).rename("NDBI")
    mndwi = B3.subtract(B11).divide(B3.add(B11)).rename("MNDWI")  # better water
    evi   = (
        B8.subtract(B4)
        .multiply(2.5)
        .divide(B8.add(B4.multiply(6)).subtract(B2.multiply(7.5)).add(1))
        .rename("EVI")
    )

    composite = ee.Image([ndvi, ndwi, ndbi, mndwi, evi])

    # ── Sample to numpy via getDownloadURL (30 m native resolution) ───────
    scale = 30  # metres per pixel; increase for very large polygons
    try:
        url = composite.getDownloadURL({
            "region": roi,
            "scale": scale,
            "format": "NPY",       # numpy format supported by GEE
            "crs": "EPSG:4326",
        })
    except ee.EEException as exc:
        raise APIError(500, f"Earth Engine error: {exc}") from exc
    
    response = requests.get(url, timeout=120)
    if response.status_code != 200:
        raise APIError(500, "Failed to download GEE raster")

    arr = np.load(io.BytesIO(response.content))   # structured array, bands as fields

    def band(name: str) -> np.ndarray:
        return arr[name].astype(np.float32)
    
    ndvi_arr  = band("NDVI")
    ndwi_arr  = band("NDWI")
    ndbi_arr  = band("NDBI")
    mndwi_arr = band("MNDWI")
    evi_arr   = band("EVI")

    geom     = shape(polygon)
    minx, miny, maxx, maxy = geom.bounds
    h, w     = ndvi_arr.shape
    transform = from_bounds(minx, miny, maxx, maxy, w, h)

    return {
        "ndvi":     ndvi_arr,
        "ndwi":     ndwi_arr,
        "ndbi":     ndbi_arr,
        "mndwi":    mndwi_arr,
        "evi":      evi_arr,
        "transform": transform,
        "crs":      "EPSG:4326",
    }