import numpy as np
import rasterio.features
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

def _adaptive_tolerance(area_deg2: float) -> float:
    """
    Larger polygons tolerate more simplification.
    Returns a Douglas-Peucker tolerance in degrees.
    """
    if area_deg2 > 0.01:    # ~100 km²
        return 0.0005
    if area_deg2 > 0.001:   # ~10 km²
        return 0.0002
    return 0.00005           # small areas — preserve more detail

def _round_coords(geometry: dict, precision: int = 6) -> dict:
    """Round all coordinates to `precision` decimal places."""
    def _round_ring(ring):
        return [[round(x, precision), round(y, precision)] for x, y in ring]

    if geometry["type"] == "Polygon":
        return {"type": "Polygon",
                "coordinates": [_round_ring(r) for r in geometry["coordinates"]]}

    if geometry["type"] == "MultiPolygon":
        return {"type": "MultiPolygon",
                "coordinates": [[_round_ring(r) for r in poly]
                                for poly in geometry["coordinates"]]}
    return geometry

def reproject_geometry(geometry: dict,
                        src_crs: str = "EPSG:32645",
                        dst_crs: str = "EPSG:4326") -> dict:
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    def _transform_ring(ring):
        return [list(transformer.transform(x, y)) for x, y in ring]

    if geometry["type"] == "Polygon":
        return {"type": "Polygon",
                "coordinates": [_transform_ring(r) for r in geometry["coordinates"]]}
    if geometry["type"] == "MultiPolygon":
        return {"type": "MultiPolygon",
                "coordinates": [[_transform_ring(r) for r in poly]
                                for poly in geometry["coordinates"]]}
    return geometry

def masks_to_geojson(masks: dict,
                     transform,
                     src_crs: str = "EPSG:4326",
                     min_area_m2: float = 500.0) -> list:
    
    """
    Convert boolean masks → optimised GeoJSON features.

    Steps per class:
      1. Vectorize raster shapes
      2. Reproject to EPSG:4326 (if needed)
      3. Merge adjacent polygons of the same class (unary_union)
      4. Simplify with adaptive Douglas-Peucker tolerance
      5. Drop slivers below min_area_m2
      6. Round coordinates to 6 d.p.
    """
    features = []
    
    # pixel area in m² — used for min_area filter
    pixel_area_m2 = abs(transform.a * transform.e)

    for class_name, mask in masks.items():
        if not mask.any():
            continue

        # ── 1. Vectorize ─────────────────────────────────────────────────
        raw_shapes = list(rasterio.features.shapes(
            mask.astype("uint8"),
            mask=mask.astype("uint8"),   # only yield value=1 shapes
            transform=transform,
        ))

        if not raw_shapes:
            continue

        # ── 2. Reproject if needed ────────────────────────────────────────
        need_reproject = src_crs.upper() != "EPSG:4326"
        geoms = []
        for geom_dict, _ in raw_shapes:
            if need_reproject:
                geom_dict = reproject_geometry(geom_dict, src_crs, "EPSG:4326")
            geoms.append(shape(geom_dict))


        # ── 3. Merge adjacent polygons of this class ──────────────────────
        merged = unary_union(geoms)

        # ── 4. Simplify ───────────────────────────────────────────────────
        total_area = merged.area
        tol = _adaptive_tolerance(total_area)
        simplified = merged.simplify(tol, preserve_topology=True)


        # ── 5. Filter tiny slivers ────────────────────────────────────────
        # area in degrees² → convert to rough m² (1° ≈ 111 km at equator)
        min_area_deg2 = min_area_m2 / (111_000 ** 2)
        geom_list = (
            list(simplified.geoms)
            if simplified.geom_type == "GeometryCollection"
            or simplified.geom_type == "MultiPolygon"
            else [simplified]
        )
        filtered = [g for g in geom_list
                    if g.geom_type in ("Polygon", "MultiPolygon")
                    and g.area >= min_area_deg2]

        if not filtered:
            continue

        final = unary_union(filtered)
        
        # ── 6. Build feature ──────────────────────────────────────────────
        geom_dict = _round_coords(mapping(final))
        area_ha   = round(final.area * (111_000 ** 2) / 10_000, 2)

        features.append({
            "type":     "Feature",
            "geometry": geom_dict,
            "properties": {
                "class":   class_name,
                "area_ha": area_ha,
            },
        })

    return features