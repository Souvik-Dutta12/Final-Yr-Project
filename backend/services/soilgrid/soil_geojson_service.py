import json
import logging
import hashlib
from typing import Optional

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.mask import mask as rasterio_mask
from rasterio.features import shapes
from rasterio.warp import transform_geom
from shapely.geometry import shape, mapping, MultiPolygon
from shapely.ops import unary_union

from utils.farmland_detection.cache import TTLCache

logger = logging.getLogger(__name__)

WRB_COG_URL = (
    "https://files.isric.org/soilgrids/latest/data/wrb/MostProbable.vrt"
)

# GDAL env vars that enable efficient COG windowed reads over HTTPS
COG_ENV = {
    "GDAL_HTTP_MERGE_CONSECUTIVE_REQUESTS": "YES",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_VERSION": "2",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".vrt,.tif,.tiff",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
}

WRB_LEGEND: dict[int, str] = {
    0:  "No Data",
    1:  "Acrisols",
    2:  "Albeluvisols",
    3:  "Alisols",
    4:  "Andosols",
    5:  "Arenosols",
    6:  "Calcisols",
    7:  "Cambisols",
    8:  "Chernozems",
    9:  "Cryosols",
    10: "Durisols",
    11: "Ferralsols",
    12: "Fluvisols",
    13: "Gleysols",
    14: "Gypsisols",
    15: "Histosols",
    16: "Kastanozems",
    17: "Leptosols",
    18: "Lixisols",
    19: "Luvisols",
    20: "Nitisols",
    21: "Phaeozems",
    22: "Planosols",
    23: "Plinthosols",
    24: "Podzols",
    25: "Regosols",
    26: "Retisols",
    27: "Solonchaks",
    28: "Solonetz",
    29: "Stagnosols",
    30: "Technosols",
    31: "Umbrisols",
    32: "Vertisols",
}

_PALETTE = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
    "#AEC6CF", "#FFD700", "#C9E4CA", "#FF6F61", "#6B5B95",
    "#88B04B", "#F7CAC9", "#92A8D1", "#955251", "#B5838D",
    "#E8A090", "#FAD02C", "#7EC8E3", "#5B5EA6", "#9B2335",
    "#DFCFBE", "#BC243C", "#C3447A", "#98B4D4", "#E4D192",
    "#00A591", "#DD4132",
]

_class_color_cache: dict[str, str] = {}


def _color_for_class(soil_class: str) -> str:
    """Returns a stable hex color for a given soil class name."""
    if soil_class not in _class_color_cache:
        idx = int(hashlib.sha256(soil_class.encode()).hexdigest(), 16) % len(_PALETTE)
        _class_color_cache[soil_class] = _PALETTE[idx]
    return _class_color_cache[soil_class]

_geojson_cache = TTLCache(ttl_seconds=3600, max_entries=32)


def _area_km2(geom) -> float:
    """Rough area in km² from a WGS-84 shapely geometry."""
    import math
    minx, miny, maxx, maxy = geom.bounds
    lat_mid = (miny + maxy) / 2
    km_lat = 111.32
    km_lon = 111.32 * math.cos(math.radians(lat_mid))
    return geom.area * km_lat * km_lon


def get_soil_coverage_geojson(polygon_geojson: dict) -> dict:
    cache_key = TTLCache.make_key(
        "geojson_cov", 
        polygon=json.dumps(
            polygon_geojson, 
            sort_keys=True
            )
        )
    cached = _geojson_cache.get(cache_key)
    if cached is not None:
        return cached

    user_polygon = shape(polygon_geojson)

    try:
        with rasterio.Env(**COG_ENV):
            with rasterio.open(WRB_COG_URL) as src:

                # Reproject user polygon to raster CRS for masking 
                raster_crs = src.crs
                if raster_crs != CRS.from_epsg(4326):
                    polygon_in_raster_crs = shape(
                        transform_geom("EPSG:4326", raster_crs.to_string(), polygon_geojson)
                    )
                else:
                    polygon_in_raster_crs = user_polygon

                # Windowed read — only downloads the bounding-box tiles
                clipped, clipped_transform = rasterio_mask(
                    src,
                    [mapping(polygon_in_raster_crs)],
                    crop=True,
                    nodata=0,
                    filled=True,
                )
                data = clipped[0].astype(np.uint8)   # single band, uint8

        # Vectorize pixels → raw polygon geometries 
        raw_shapes = list(
            shapes(data, mask=(data > 0), transform=clipped_transform)
        )

        if not raw_shapes:
            return _empty_feature_collection()

        # Group geometries by class value, reproject to WGS-84 
        class_geoms: dict[str, list] = {}
        for geom_dict, pixel_val in raw_shapes:
            wrb_class = WRB_LEGEND.get(int(pixel_val), f"Class_{int(pixel_val)}")
            if wrb_class == "No Data":
                continue

            # Reproject back to EPSG:4326
            if raster_crs != CRS.from_epsg(4326):
                geom_dict = transform_geom(raster_crs.to_string(), "EPSG:4326", geom_dict)

            class_geoms.setdefault(wrb_class, []).append(shape(geom_dict))

        if not class_geoms:
            return _empty_feature_collection()

        # Dissolve + clip to user polygon 
        total_area = 0.0
        dissolved: dict[str, object] = {}

        for wrb_class, geoms in class_geoms.items():
            merged = unary_union(geoms)
            clipped_geom = merged.intersection(user_polygon)
            if clipped_geom.is_empty:
                continue
            area = _area_km2(clipped_geom)
            dissolved[wrb_class] = {
                "geom": clipped_geom, 
                "area_km2": area
            }
            total_area += area

        # Build FeatureCollection 
        features = []
        for wrb_class, entry in sorted(
            dissolved.items(),
            key=lambda x: x[1]["area_km2"],
            reverse=True,
        ):
            geom = entry["geom"]
            area = entry["area_km2"]
            pct = round(area / total_area * 100, 2) if total_area > 0 else 0.0
            color = _color_for_class(wrb_class)

            features.append({
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": {
                    "soil_class": wrb_class,
                    "color": color,
                    "area_km2": round(area, 4),
                    "percentage": pct,
                },
            })

        result = {
            "type": "FeatureCollection", 
            "features": features
        }
        _geojson_cache.set(cache_key, result)
        return result

    except Exception as exc:
        logger.error(f"Soil coverage GeoJSON failed: {exc}", exc_info=True)
        return _empty_feature_collection()


def _empty_feature_collection() -> dict:
    return {
        "type": "FeatureCollection", 
        "features": []
    }