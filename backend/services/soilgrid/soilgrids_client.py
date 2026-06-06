"""
SoilGrids v2 — async, COG-based, globally applicable.

REST API is currently paused by ISRIC. All reads use Cloud Optimized GeoTIFF
files directly via rasterio + GDAL VSI curl.

Unit scaling:
  phh2o    pH × 10       → ÷ 10  → actual pH
  nitrogen cg/kg         → ÷ 100 → g/kg
  soc      dg/kg         → ÷ 100 → %
  cec      mmol(c)/kg    → ÷ 10  → cmol(c)/kg
  bdod     cg/cm³        → ÷ 100 → g/cm³
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask
from rasterio.warp import transform as warp_transform
from rasterio.warp import transform_geom
import traceback

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SOILGRIDS_BASE = "https://rest.isric.org/soilgrids/v2.0"
TIMEOUT        = 30.0
MAX_RETRIES    = 3
BACKOFF_BASE   = 1.5
CONCURRENCY    = 5
NODATA_VALUE   = -32768

# How long (seconds) to wait for ALL parallel COG futures to finish
COG_POINT_TIMEOUT   = 45
COG_POLYGON_TIMEOUT = 90

PROPERTY_KEY_MAP: Dict[str, str] = {
    "phh2o":    "ph",
    "nitrogen": "nitrogen",
    "soc":      "soc",
    "cec":      "cec",
    "bdod":     "bulk_density",
}

COG_URLS: Dict[str, str] = {
    "phh2o":    "https://files.isric.org/soilgrids/latest/data/phh2o/phh2o_0-5cm_mean.vrt",
    "nitrogen": "https://files.isric.org/soilgrids/latest/data/nitrogen/nitrogen_0-5cm_mean.vrt",
    "soc":      "https://files.isric.org/soilgrids/latest/data/soc/soc_0-5cm_mean.vrt",
    "cec":      "https://files.isric.org/soilgrids/latest/data/cec/cec_0-5cm_mean.vrt",
    "bdod":     "https://files.isric.org/soilgrids/latest/data/bdod/bdod_0-5cm_mean.vrt",
}
WRB_COG_URL = "https://files.isric.org/soilgrids/latest/data/wrb/MostProbable.vrt"

COG_SCALING: Dict[str, float] = {
    "phh2o":    0.10,
    "nitrogen": 0.01,
    "soc":      0.10,
    "cec":      0.10,
    "bdod":     0.01,
}
SOIL_PROPERTIES = list(COG_SCALING.keys())

# ── GDAL environment ──────────────────────────────────────────────────────────
# VSI_CACHE / CPL_VSIL_CURL_CACHE_SIZE   → in-process HTTP tile cache.
#   After the first fetch of a COG tile the bytes stay in RAM; subsequent
#   reads of the same area (batch queries, retries) cost no extra HTTP round trip.
# GDAL_HTTP_CONNECTTIMEOUT / GDAL_HTTP_TIMEOUT
#   → hard ceiling on how long GDAL waits for ISRIC — prevents silent hangs.
COG_ENV = {
    "GDAL_HTTP_MERGE_CONSECUTIVE_REQUESTS": "YES",
    "GDAL_HTTP_MULTIPLEX":                  "YES",
    "GDAL_HTTP_VERSION":                    "2",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS":     ".vrt,.tif,.tiff",
    "GDAL_DISABLE_READDIR_ON_OPEN":         "EMPTY_DIR",
    # ── caching ──
    "VSI_CACHE":                  True,
    "VSI_CACHE_SIZE":             25000000,    # 25 MB per file handle
    "CPL_VSIL_CURL_CACHE_SIZE":   200000000,   # 200 MB shared HTTP cache
    "GDAL_CACHEMAX":              512,          # 512 MB GDAL block cache (MB)
    # ── timeouts ──
    "GDAL_HTTP_CONNECTTIMEOUT":   10,           # seconds to establish TCP
    "GDAL_HTTP_TIMEOUT":          30,           # seconds for the full request
}

_executor = ThreadPoolExecutor(max_workers=8)


# ── COG sync helpers ──────────────────────────────────────────────────────────

def _read_one_property_point(
    param: str, url: str, lat: float, lon: float
) -> Tuple[str, Optional[float]]:
    """
    Read ONE pixel from a COG for a lat/lon point.

    Uses src.sample() instead of rasterio_mask so GDAL issues a single
    HTTP range request for the relevant tile rather than fetching a window.
    This is the correct fast path for point queries on remote COGs.
    """
    try:
        with rasterio.Env(**COG_ENV):
            with rasterio.open(url) as src:
                nodata = src.nodata if src.nodata is not None else NODATA_VALUE
                # Reproject the point into the COG's native CRS
                xs, ys = warp_transform(
                    "EPSG:4326",
                    src.crs,
                    [float(lon)],
                    [float(lat)]
                )

                x = float(xs[0])
                y = float(ys[0])

                logger.info(
                    f"{param} transformed point "
                    f"x={x} ({type(x)}), "
                    f"y={y} ({type(y)})"
                )
                samples = list(src.sample([(x, y)]))
                if not samples:
                    logger.warning(f"COG point {param}: empty sample at ({lat}, {lon})")
                    return param, None
                raw_val = samples[0][0]

                if raw_val is None:
                    return param, None

                val = float(raw_val)

                if np.isnan(val):
                    return param, None

                if nodata is not None:
                    try:
                        if np.isclose(val, float(nodata)):
                            return param, None
                    except Exception:
                        pass
                    
                if val <= 0:
                    return param, None
                scaled = round(val * COG_SCALING[param], 6)
                logger.debug(f"COG point {param} ({lat},{lon}): {scaled}")
                return param, scaled
    except Exception as exc:
        logger.error(
            f"COG point read failed [{param}] ({lat},{lon})\n"
            f"{traceback.format_exc()}"
        )
        return param, None


def _read_one_property_polygon(
    param: str, url: str, polygon_geojson: dict
) -> Tuple[str, Optional[float]]:
    """
    Read the mean value of a property over a polygon using rasterio.mask.
    Correct for polygon queries where a spatial window is needed.
    """
    try:
        with rasterio.Env(**COG_ENV):
            with rasterio.open(url) as src:
                nodata = src.nodata if src.nodata is not None else NODATA_VALUE
                geom_reproj = transform_geom("EPSG:4326", src.crs.to_string(), polygon_geojson)
                out_image, _ = rasterio_mask(
                    src, [geom_reproj], crop=True, nodata=nodata, filled=True
                )
                data = out_image[0]
                valid = data[(data != nodata) & (data > 0)]
                del out_image, data

                if valid.size == 0:
                    logger.warning(f"COG polygon {param}: no valid pixels")
                    return param, None

                mean_val = round(float(np.mean(valid)) * COG_SCALING[param], 6)
                del valid
                logger.debug(f"COG polygon {param}: {mean_val}")
                return param, mean_val
    except Exception as exc:
        logger.error(
            f"COG point read failed [{param}] \n"
            f"{traceback.format_exc()}"
        )
        return param, None


def _read_soil_class_cog_sync(lat: float, lon: float) -> Optional[str]:
    """Blocking WRB class read from COG — run inside executor."""
    from services.soilgrid.soil_geojson_service import WRB_LEGEND
    try:
        with rasterio.Env(**COG_ENV):
            with rasterio.open(WRB_COG_URL) as src:
                xs, ys = warp_transform("EPSG:4326", src.crs, [lon], [lat])
                x = float(xs[0])
                y = float(ys[0])

                row, col = src.index(x, y)

                row = int(row)
                col = int(col)

                data = src.read(
                    1,
                    window=((row, row + 1), (col, col + 1))
                )

                if data.size == 0:
                    return None

                raw_val = data[0, 0]

                if np.isnan(raw_val):
                    return None

                val = int(raw_val)

                nodata = src.nodata

                if nodata is not None:
                    try:
                        if np.isclose(float(raw_val), float(nodata)):
                            return None
                    except Exception:
                        pass
                if val == nodata or val <= 0:
                    return None
                return WRB_LEGEND.get(val)
    except Exception as exc:
        logger.error(
            f"COG soil class read failed ({lat},{lon})\n"
            f"{traceback.format_exc()}"
        )
        return None


def _collect_futures(
    futures: Dict, timeout: float, context: str
) -> Dict[str, Optional[float]]:
    """
    Drain a dict of {Future: param} within `timeout` seconds.
    Timed-out or failed futures get None so callers always get a complete dict.
    """
    raw: Dict[str, Optional[float]] = {}
    try:
        for future in as_completed(futures, timeout=timeout):
            param = futures[future]
            try:
                _, value = future.result()
                raw[param] = value
            except Exception as exc:
                logger.error(f"{context} future error [{param}]: {exc!r}")
                raw[param] = None
    except FuturesTimeoutError:
        # Some futures did not finish; mark them None and cancel the rest
        finished = set(raw.keys())
        for future, param in futures.items():
            if param not in finished:
                future.cancel()
                logger.warning(f"{context} timed out for [{param}] — returning None")
                raw[param] = None
    return raw


def _read_all_properties_point_parallel(
    lat: float, lon: float
) -> Dict[str, Optional[float]]:
    """Read all 5 properties for a point in parallel. Returns friendly-key dict."""
    futures = {
        _executor.submit(_read_one_property_point, param, url, lat, lon): param
        for param, url in COG_URLS.items()
    }
    raw = _collect_futures(futures, timeout=COG_POINT_TIMEOUT, context=f"point({lat},{lon})")
    result = {PROPERTY_KEY_MAP[k]: raw.get(k) for k in PROPERTY_KEY_MAP}
    logger.info(f"COG point properties ({lat},{lon}): {result}")
    return result


def _read_all_properties_polygon_parallel(
    polygon_geojson: dict,
) -> Dict[str, Optional[float]]:
    """Read all 5 properties over a polygon in parallel. Returns friendly-key dict."""
    futures = {
        _executor.submit(_read_one_property_polygon, param, url, polygon_geojson): param
        for param, url in COG_URLS.items()
    }
    raw = _collect_futures(futures, timeout=COG_POLYGON_TIMEOUT, context="polygon")
    result = {PROPERTY_KEY_MAP[k]: raw.get(k) for k in PROPERTY_KEY_MAP}
    logger.info(f"COG polygon properties: {result}")
    return result


# ── Client ────────────────────────────────────────────────────────────────────

class SoilGridsClient:
    """
    Async SoilGrids client — COG-only while the REST API is paused.

    The _get / _parse_properties REST plumbing is preserved so re-enabling
    REST is a one-line swap in get_soil_class / get_soil_properties.
    """

    def __init__(self):
        self._sem = asyncio.Semaphore(CONCURRENCY)

    # ── REST helper (kept for future re-enablement) ───────────────────────────

    async def _get(self, url: str, params: List[Tuple[str, Any]]) -> Optional[Dict]:
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (429, 503, 502, 504):
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(
                        f"SoilGrids HTTP {status} — retrying in {wait:.1f}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(wait)
                elif status == 404:
                    logger.warning("SoilGrids: no data at location (404).")
                    return None
                else:
                    logger.error(f"SoilGrids HTTP {status}: {exc!r}")
                    return None
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning(
                    f"SoilGrids {type(exc).__name__} "
                    f"(attempt {attempt + 1}/{MAX_RETRIES}): {exc!r}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE ** attempt)
        logger.error(f"SoilGrids: all {MAX_RETRIES} attempts failed for {url}")
        return None

    async def _get_with_limit(self, coro):
        async with self._sem:
            return await coro

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_soil_class(self, lat: float, lon: float) -> Optional[str]:
        """Most probable WRB soil class for a point, e.g. 'Fluvisols'."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, _read_soil_class_cog_sync, lat, lon)

    async def get_soil_properties(
        self, lat: float, lon: float
    ) -> Dict[str, Optional[float]]:
        """
        Scaled soil properties for a point.
        Keys: ph, nitrogen, soc, cec, bulk_density
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _executor, _read_all_properties_point_parallel, lat, lon
        )

    async def get_soil_properties_polygon(
        self, polygon_geojson: dict
    ) -> Dict[str, Optional[float]]:
        """Polygon mean soil properties — non-blocking, runs in thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _executor, _read_all_properties_polygon_parallel, polygon_geojson
        )

    def _parse_properties(self, data: Dict) -> Dict[str, Optional[float]]:
        """Parse a REST API response (kept for when the API returns)."""
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
            raw = depths[0].get("values", {}).get("mean")
            if raw is None or raw == NODATA_VALUE:
                result[mapped_name] = None
                continue
            d_factor = layer.get("unit_measure", {}).get("d_factor", 1)
            result[mapped_name] = round(raw / d_factor, 4)
        for mapped in PROPERTY_KEY_MAP.values():
            result.setdefault(mapped, None)
        logger.info(f"Parsed REST soil properties: {result}")
        return result

    async def batch_get_classes(
        self, points: List[Tuple[float, float]]
    ) -> List[Optional[str]]:
        tasks = [
            self._get_with_limit(self.get_soil_class(lat, lon)) for lat, lon in points
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r if not isinstance(r, Exception) else None for r in results]

    async def batch_get_properties(
        self, points: List[Tuple[float, float]]
    ) -> List[Dict[str, Optional[float]]]:
        tasks = [
            self._get_with_limit(self.get_soil_properties(lat, lon))
            for lat, lon in points
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)


soilgrids_client = SoilGridsClient()