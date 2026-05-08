"""
SoilGrids v2 REST API client — async, cached, globally applicable.
Uses the shared TTLCache from utils/cache.py.

SoilGrids unit scaling applied here so all callers get clean physical values:
  phh2o    stored pH × 10       → ÷ 10    → actual pH
  nitrogen stored cg/kg         → ÷ 100   → g/kg
  soc      stored dg/kg         → ÷ 100   → %  (g/kg ÷ 10)
  cec      stored mmol(c)/kg    → ÷ 10    → cmol(c)/kg
  bdod     stored cg/cm³        → ÷ 100   → g/cm³
"""

import httpx
import asyncio
import logging
import numpy as np
import rasterio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, List, Tuple, Any

from utils.farmland_detection.cache import TTLCache

logger = logging.getLogger(__name__)
SOILGRIDS_BASE = "https://rest.isric.org/soilgrids/v2.0"
TIMEOUT        = 30.0
MAX_RETRIES    = 3
BACKOFF_BASE   = 1.5   # seconds
CONCURRENCY    = 5     # max parallel SoilGrids requests (ISRIC guideline)
NODATA_VALUE   = -32768

PROPERTY_KEY_MAP: Dict[str, str] = {
    "phh2o":    "ph",
    "nitrogen": "nitrogen",
    "soc":      "soc",
    "cec":      "cec",
    "bdod":     "bulk_density",
}


# ── COG URLs for properties (REST API is paused, use COG reads instead) ──────
COG_URLS: Dict[str, str] = {
    "ph":           "https://files.isric.org/soilgrids/latest/data/phh2o/phh2o_0-5cm_mean.vrt",
    "nitrogen":     "https://files.isric.org/soilgrids/latest/data/nitrogen/nitrogen_0-5cm_mean.vrt",
    "soc":          "https://files.isric.org/soilgrids/latest/data/soc/soc_0-5cm_mean.vrt",
    "cec":          "https://files.isric.org/soilgrids/latest/data/cec/cec_0-5cm_mean.vrt",
    "bulk_density": "https://files.isric.org/soilgrids/latest/data/bdod/bdod_0-5cm_mean.vrt",
}

COG_SCALING: Dict[str, float] = {
    "phh2o":           0.10,   # pH × 10  → actual pH
    "nitrogen":     0.01,   # cg/kg    → g/kg
    "soc":          0.10,   # dg/kg    → %
    "cec":          0.10,   # mmol/kg  → cmol/kg
    "bdod": 0.01,   # cg/cm³   → g/cm³
}

COG_ENV = {
    "GDAL_HTTP_MERGE_CONSECUTIVE_REQUESTS": "YES",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_VERSION": "2",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".vrt,.tif,.tiff",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
}

SOIL_PROPERTIES = list(COG_SCALING.keys())

soilgrids_cache = TTLCache(ttl_seconds=3600, max_entries=256)
_executor = ThreadPoolExecutor(max_workers=4)


def _read_all_properties_polygon(polygon_geojson: dict) -> Dict[str, Optional[float]]:
    """
    Read mean value of each property over a polygon using rasterio.mask.
    Returns scaled physical values.
    """
    import json
    from rasterio.mask import mask as rasterio_mask
    from rasterio.warp import transform_geom
    from rasterio.crs import CRS

    cache_key = TTLCache.make_key(
        "cog_poly_props",
        polygon=json.dumps(polygon_geojson, sort_keys=True)
    )
    cached = soilgrids_cache.get(cache_key)
    if cached is not None:
        logger.debug("COG polygon properties cache hit")
        return cached

    result: Dict[str, Optional[float]] = {}

    for param, url in COG_URLS.items():
        try:
            with rasterio.Env(**COG_ENV):
                with rasterio.open(url) as src:
                    nodata = src.nodata if src.nodata is not None else NODATA_VALUE

                    # Reproject polygon to raster CRS
                    geom_reproj = transform_geom(
                        "EPSG:4326", src.crs.to_string(), polygon_geojson
                    )

                    out_image, _ = rasterio_mask(
                        src,
                        [geom_reproj],
                        crop=True,
                        nodata=nodata,
                        filled=True,
                    )
                    data = out_image[0]
                    valid = data[(data != nodata) & (data > 0)]
                    
                    if valid.size == 0:
                        logger.warning(f"COG polygon read for {param}: no valid pixels in polygon")
                        result[param] = None
                    else:
                        mean_val = float(np.mean(valid)) * COG_SCALING[param]
                        result[param] = round(mean_val, 6)
                        logger.debug(f"COG polygon read for {param}: {result[param]}")

        except Exception as exc:
            logger.error(f"COG polygon read failed for {param}: {exc}", exc_info=True)
            result[param] = None

    soilgrids_cache.set(cache_key, result)
    logger.info(f"COG polygon properties computed: {result}")
    return result


class SoilGridsClient:
    async def _get(
        self,
        url: str,
        params: List[Tuple[str, Any]],
        cache_key: str,
    ) -> Optional[Dict]:
        cached = soilgrids_cache.get(cache_key)
        if cached is not None:
            return cached

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    soilgrids_cache.set(cache_key, data)
                    return data

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429:
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(f"SoilGrids rate-limited, retrying in {wait}s …")
                    await asyncio.sleep(wait)
                elif status == 404:
                    logger.warning("SoilGrids: no data at this location (404).")
                    return None
                else:
                    logger.error(f"SoilGrids HTTP {status}: {exc}")
                    return None

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning(f"SoilGrids request error (attempt {attempt + 1}): {exc}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE ** attempt)

        logger.error(f"SoilGrids: all {MAX_RETRIES} attempts failed for {url}")
        return None
      
    # Classification
    async def get_soil_class(
            self, 
            lat: float, 
            lon: float
        ) -> Optional[str]:
        """Most probable WRB soil class for a point, e.g. 'Fluvisols'."""
        params = [
            ("lon", round(lon, 6)),
            ("lat", round(lat, 6)),
            ("number_classes", 3),
        ]
        cache_key = TTLCache.make_key("cls", lat=round(lat, 5), lon=round(lon, 5))
        data = await self._get(
            f"{SOILGRIDS_BASE}/classification/query", params, cache_key
        )
        if not data:
            return None
        try:
            probs = data.get("wrb_class_probability", [])
            if not probs:
                return None
        
            first = probs[0]

            # API returns list of dicts: [{"wrb_class_name": "Fluvisols", ...}, ...]
            if isinstance(first, dict):
                return first.get("wrb_class_name")

            # API returns list of lists: [["Fluvisols", 45], ...]
            elif isinstance(first, list):
                return first[0] if first else None

            # API returns list of strings directly: ["Fluvisols", ...]
            elif isinstance(first, str):
                return first
        except Exception as exc:
            logger.error(f"Error parsing soil class response: {exc}")
            return None

    # Properties
    async def get_soil_properties(
        self, 
        lat: float, 
        lon: float
    ) -> Dict[str, Optional[float]]:
        """
        Scaled soil quality properties for a point.
        Keys: ph, nitrogen, soc, cec, bulk_density
        """
        params = [
            ("lon", round(lon, 6)),
            ("lat", round(lat, 6)),
            ("depth", "0-5cm"),
            ("value", "mean"),
        ] + [("property", p) for p in SOIL_PROPERTIES]
       
        cache_key = TTLCache.make_key("props", lat=round(lat, 5), lon=round(lon, 5))
        data = await self._get(
            f"{SOILGRIDS_BASE}/properties/query", params, cache_key
        )

        if not data:
            return {v: None for v in PROPERTY_KEY_MAP.values()}
        return self._parse_properties(data)

    def _parse_properties(
            self, 
            data: Dict
        ) -> Dict[str, Optional[float]]:

        result: Dict[str, Optional[float]] = {}
        layers = data.get("properties", {}).get("layers", [])
        for layer in layers:
            soilgrid_name = layer.get("name")

            mapped_name = PROPERTY_KEY_MAP.get(soilgrid_name)

            if not mapped_name:
                continue

            depths = layer.get("depths", [])

            if not depths:
                result[mapped_name] = None
                continue

            depth_data = depths[0]

            raw = depth_data.get("values", {}).get("mean")

            if raw is None or raw == NODATA_VALUE:
                result[mapped_name] = None
                continue

            d_factor = (
                layer.get("unit_measure", {})
                .get("d_factor", 1)
            )

            result[mapped_name] = round(raw / d_factor, 4)

        for mapped in PROPERTY_KEY_MAP.values():
            result.setdefault(mapped, None)

        logger.info(f"Final parsed soil properties: {result}")

        return result
    
    async def get_soil_properties_polygon(
        self, polygon_geojson: dict
    ) -> Dict[str, Optional[float]]:
        """
        Polygon mean soil properties via COG rasterio.mask.
        Non-blocking — runs in thread pool executor.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, _read_all_properties_polygon, polygon_geojson
        )
    
    async def batch_get_classes(
        self, 
        points: List[Tuple[float, float]]
    ) -> List[Optional[str]]:
        sem = asyncio.Semaphore(CONCURRENCY)

        async def _fetch(lat: float, lon: float) -> Optional[str]:
            async with sem:
                return await self.get_soil_class(lat, lon)

        return list(await asyncio.gather(*[_fetch(la, lo) for la, lo in points]))

    async def batch_get_properties(
        self, 
        points: List[Tuple[float, float]]
    ) -> List[Dict[str, Optional[float]]]:
        sem = asyncio.Semaphore(CONCURRENCY)

        async def _fetch(lat: float, lon: float) -> Dict:
            async with sem:
                return await self.get_soil_properties(lat, lon)

        return list(await asyncio.gather(*[_fetch(la, lo) for la, lo in points]))
    

soilgrids_client = SoilGridsClient()