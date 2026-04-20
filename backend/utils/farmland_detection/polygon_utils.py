"""
Polygon utilities — area estimation, validation, bounding box helpers.
 
All functions operate on plain GeoJSON Polygon dicts so they work the
same in the controller, service, and Earth Engine layers.
"""
 
import math
from typing import Tuple
from shapely.geometry import shape, mapping
from shapely.validation import make_valid
 
 # Area estimation
 
def polygon_area_km2(polygon: dict) -> float:
    """
    Rough area in km² from a WGS-84 GeoJSON Polygon.
 
    Uses a local equirectangular approximation — good enough for scale
    selection (< 5% error for polygons < 500 km² at mid-latitudes).
    """
    geom = shape(polygon)
    minx, miny, maxx, maxy = geom.bounds
    lat_mid = (miny + maxy) / 2.0
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * math.cos(math.radians(lat_mid))
    # shapely .area is in degrees²; convert component-by-component
    return geom.area * km_per_deg_lat * km_per_deg_lon
 

 # Validation 
def validate_polygon(polygon: dict) -> dict:
    """
    Validate and auto-repair a GeoJSON Polygon dict.
 
    Returns the (possibly repaired) polygon dict.
    Raises ValueError with a clear message on hard failures.
    """
    if not polygon:
        raise ValueError("Polygon is required.")
 
    if polygon.get("type") != "Polygon":
        raise ValueError(
            f"Expected GeoJSON type 'Polygon', got '{polygon.get('type')}'."
        )
 
    coords = polygon.get("coordinates")
    if not coords or not coords[0] or len(coords[0]) < 4:
        raise ValueError(
            "Polygon must have at least 4 coordinate pairs (first = last to close)."
        )
 
    geom = shape(polygon)
 
    # Auto-repair self-intersections / ring direction issues
    if not geom.is_valid:
        geom = make_valid(geom)
        if geom.is_empty:
            raise ValueError("Polygon is invalid and could not be repaired.")
 
    # Return the repaired polygon as a plain dict
    repaired = mapping(geom)
    # make_valid can return a GeometryCollection; take the largest polygon
    if repaired["type"] == "GeometryCollection":
        polygons = [
            g for g in repaired["geometries"]
            if g["type"] in ("Polygon", "MultiPolygon")
        ]
        if not polygons:
            raise ValueError("No valid polygon geometry found after repair.")
        repaired = max(polygons, key=lambda g: shape(g).area)
 
    return dict(repaired)

# Bounding-box helpers
def polygon_bounds(polygon: dict) -> Tuple[float, float, float, float]:
    """Return (minx, miny, maxx, maxy) for the polygon."""
    return shape(polygon).bounds
 
 
def polygon_centroid(polygon: dict) -> Tuple[float, float]:
    """Return (lon, lat) centroid."""
    c = shape(polygon).centroid
    return c.x, c.y