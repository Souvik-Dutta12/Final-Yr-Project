"""
Polygon point sampler — generates a systematic grid of (lat, lon) points
inside any GeoJSON polygon for SoilGrids batch queries.

Integrates with utils/polygon_utils.py for area estimation.
"""

import math
import numpy as np
from shapely.geometry import Point, shape
from typing import List, Tuple

from utils.farmland_detection.polygon_utils import polygon_area_km2

def sample_points_in_polygon(
    polygon,            # shapely geometry (EPSG:4326)
    target_points: int = 25,
) -> List[Tuple[float, float]]:
    """
    Returns a list of (lat, lon) tuples uniformly distributed inside `polygon`.
    Falls back to the centroid if the polygon is too small for a grid.
    """
    minlon, minlat, maxlon, maxlat = polygon.bounds
    n_side = max(3, math.ceil(math.sqrt(target_points * 1.5)))

    lons = np.linspace(minlon, maxlon, n_side + 2)[1:-1]
    lats = np.linspace(minlat, maxlat, n_side + 2)[1:-1]

    points: List[Tuple[float, float]] = [
        (float(lat), float(lon))
        for lat in lats
        for lon in lons
        if polygon.contains(Point(lon, lat))
    ]

    if not points:
        c = polygon.centroid
        points = [(float(c.y), float(c.x))]

    return points

def adaptive_sample_points(polygon_geojson: dict) -> List[Tuple[float, float]]:
    """
    Chooses target point count based on polygon area (km²) then samples.
    Accepts a GeoJSON dict — same format already validated in the controller.
    """
    area = polygon_area_km2(polygon_geojson)

    if area < 10:
        target = 9
    elif area < 100:
        target = 16
    elif area < 1_000:
        target = 25
    elif area < 10_000:
        target = 36
    else:
        target = 49

    return sample_points_in_polygon(shape(polygon_geojson), target)