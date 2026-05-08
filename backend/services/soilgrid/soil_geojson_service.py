import json
import logging
import hashlib
from typing import List, Tuple

from rasterio.crs import CRS
from shapely.geometry import shape, mapping, MultiPolygon,MultiPoint, Point
from shapely.ops import voronoi_diagram,unary_union
from shapely.validation import make_valid

from utils.farmland_detection.cache import TTLCache
from utils.soil_properties.polygon_sampler import adaptive_sample_points
from services.soilgrid.soilgrids_client import soilgrids_client

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


async def get_soil_coverage_geojson(
        polygon_geojson: dict
    ) -> dict:
    cache_key = TTLCache.make_key(
        "geojson_cov",
        polygon=json.dumps(polygon_geojson, sort_keys=True),
    )
    cached = _geojson_cache.get(cache_key)
    if cached is not None:
        return cached

    user_polygon = shape(polygon_geojson)

    # Same source as get_soil_distribution 
    points: List[Tuple[float, float]] = adaptive_sample_points(polygon_geojson)
    api_classes = await soilgrids_client.batch_get_classes(points)

    valid_pairs = [
        (pt, cls)
        for pt, cls in zip(points, api_classes)
        if cls is not None
    ]

    if not valid_pairs:
        logger.error("No soil class data returned for polygon.")
        return _empty_feature_collection()

    # Build Shapely points — tuples are (lat, lon) 
    shapely_points: List[Point] = [
        Point(pt[1], pt[0])   # pt[0]=lat, pt[1]=lon → Point(x=lon, y=lat)
        for pt, _ in valid_pairs
    ]

    # Voronoi tessellation clipped to user polygon 
    if len(shapely_points) == 1:
        only_class = valid_pairs[0][1]
        class_geoms = {only_class: user_polygon}
    else:
        multipoint = MultiPoint(shapely_points)
        voronoi_collection = voronoi_diagram(multipoint, envelope=user_polygon)
        voronoi_cells = list(voronoi_collection.geoms)

        class_geoms_raw: dict[str, list] = {}
        for cell in voronoi_cells:
            clipped_cell = cell.intersection(user_polygon)
            if clipped_cell.is_empty:
                continue

            # Find which sample point falls inside this Voronoi cell
            matched_cls = None
            for p, (_, cls) in zip(shapely_points, valid_pairs):
                if cell.contains(p):
                    matched_cls = cls
                    break

            if matched_cls is None:
                # Fallback: nearest point to cell centroid
                centroid = clipped_cell.centroid
                matched_cls = min(
                    zip(shapely_points, valid_pairs),
                    key=lambda x: centroid.distance(x[0])
                )[1][1]

            class_geoms_raw.setdefault(matched_cls, []).append(clipped_cell)

        class_geoms = {
            cls: make_valid(unary_union(geoms))
            for cls, geoms in class_geoms_raw.items()
        }

    # Compute areas
    total_area = sum(_area_km2(g) for g in class_geoms.values())
    # Build GeoJSON features
    features = []
    for wrb_class, geom in sorted(
        class_geoms.items(),
        key=lambda x: _area_km2(x[1]),
        reverse=True,
    ):
        if geom.is_empty:
            continue
        area = _area_km2(geom)
        pct  = round(area / total_area * 100, 2) if total_area > 0 else 0.0
        features.append({
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": {
                "soil_class": wrb_class,
                "color": _color_for_class(wrb_class),
                "area_km2": round(area, 4),
                "percentage": pct,
            },
        })

    if not features:
        return _empty_feature_collection()

    result = {
        "type": "FeatureCollection", 
        "features": features
    }
    _geojson_cache.set(cache_key, result)
    return result

def _empty_feature_collection() -> dict:
    return {
        "type": "FeatureCollection", 
        "features": []
    }