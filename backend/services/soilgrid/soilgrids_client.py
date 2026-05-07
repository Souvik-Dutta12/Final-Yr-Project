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
from typing import Optional, Dict, List, Tuple, Any

from utils.farmland_detection.cache import TTLCache

logger = logging.getLogger(__name__)
SOILGRIDS_BASE = "https://rest.isric.org/soilgrids/v2.0"
TIMEOUT        = 30.0
MAX_RETRIES    = 3
BACKOFF_BASE   = 1.5   # seconds
CONCURRENCY    = 5     # max parallel SoilGrids requests (ISRIC guideline)
NODATA_VALUE   = -32768

PROPERTY_SCALING: Dict[str, float] = {
    "phh2o":    0.10,
    "nitrogen": 0.01,
    "soc":      0.01,
    "cec":      0.10,
    "bdod":     0.01,
}

PROPERTY_KEY_MAP: Dict[str, str] = {
    "phh2o":    "ph",
    "nitrogen": "nitrogen",
    "soc":      "soc",
    "cec":      "cec",
    "bdod":     "bulk_density",
}

SOIL_PROPERTIES = list(PROPERTY_SCALING.keys())

soilgrids_cache = TTLCache(ttl_seconds=3600, max_entries=256)


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
        for layer in data.get("properties", {}).get("layers", []):
            name = layer.get("name", "")
            if name not in PROPERTY_SCALING:
                continue
            value = None
            for depth in layer.get("depths", []):
                if "0-5" in depth.get("label", ""):
                    raw = depth.get("values", {}).get("mean")
                    if raw is not None and raw != NODATA_VALUE and raw > 0:
                        value = raw * PROPERTY_SCALING[name]
                    break
            result[PROPERTY_KEY_MAP[name]] = value

        for key in PROPERTY_KEY_MAP.values():
            result.setdefault(key, None)
        return result
    
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