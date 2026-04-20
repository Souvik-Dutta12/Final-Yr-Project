"""
GeoJSON Service — Raster masks → optimised GeoJSON FeatureCollection
 
Pipeline per class
------------------
1. Vectorise raster  (rasterio.features.shapes)
2. Reproject         (src CRS → EPSG:4326, if needed)
3. Union             (merge fragmented polygons of the same class)
4. Simplify          (adaptive Douglas-Peucker tolerance)
5. Filter slivers    (< min_area_m2)
6. Round coordinates (6 d.p. ≈ 0.1 m precision — safe for web maps)
7. Build Feature     (with class stats in properties)
 
Engineering notes
-----------------
▸ Adaptive tolerance: large polygons simplify more aggressively, keeping GeoJSON payloads small without losing meaningful shape detail.
▸ Confidence summary: the mean probability of the winning class is included as `confidence` so clients can shade uncertain areas.
▸ All geometry operations use Shapely 2.x (GEOS backend) which is substantially faster than 1.x for large union operations.
"""
import logging
from typing import Any, Dict, List, Optional

import numpy as np
import rasterio.features
from pyproj import Transformer
from rasterio.transform import Affine
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

from services.farmland_detection.constants.dw_classes import DW_CLASSES, IDX_TO_CLASS, NAME_TO_CLASS


logger = logging.getLogger(__name__)

def _adaptive_tolerance(area_deg2: float) -> float:
    """
    Douglas-Peucker ε in degrees, scaled to polygon area.
    """
    if area_deg2 > 0.01:    return 0.0005   # ≥ ~100 km²
    if area_deg2 > 0.001:   return 0.0002   # ≥ ~10 km²
    if area_deg2 > 0.0001:  return 0.0001   # ≥ ~1 km²
    return 0.00005                           # small / precise areas

def _round_coords(geometry: dict, precision: int = 6) -> dict:
    """Round all coordinates to `precision` decimal places in-palce"""
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

def _reproject_geometry(geometry: dict,
                        src_crs: str ,
                        dst_crs: str = "EPSG:4326") -> dict:
    """Reproject a GeoJSON geometry dict between two EPSG CRS strings."""
    
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

def mask_to_feature(
    class_name:  str,
    mask:        np.ndarray,
    transform:   Affine,
    prob_map:    Optional[np.ndarray] = None,
    src_crs:     str = "EPSG:4326",
    min_area_m2: float = 1_000.0,
) -> Optional[Dict[str,Any]]:
    """
    Convert a single boolean class mask to a GeoJSON Feature.
 
    Parameters
    ----------
    class_name  : DW class name (e.g. 'crops')
    mask        : (H, W) bool array
    transform   : rasterio Affine for the raster
    prob_map    : (H, W) float32 — DW probability for this class (optional)
    src_crs     : CRS of the raster ('EPSG:4326' when downloaded from GEE)
    min_area_m2 : skip polygons smaller than this (avoids noisy slivers)
 
    Returns
    -------
    GeoJSON Feature dict, or None if no valid pixels / all filtered.
    """
     
    if not mask.any():
        return None

    #vectorise
    raw = list(rasterio.features.shapes(
        mask.astype("uint8"),
        mask=mask.astype("uint8"),
        transform=transform,
    ))
    if not raw:
        return None
    
    # reproject
    need_reproject = src_crs.upper() != "EPSG:4326"
    geoms = []
    for geom_dict, _ in raw:
        if need_reproject:
            geom_dict = _reproject_geometry(geom_dict, src_crs)
        geoms.append(shape(geom_dict))

    # union
    merged = unary_union(geoms)
    tol        = _adaptive_tolerance(merged.area)
    simplified = merged.simplify(tol, preserve_topology=True)

    min_deg2 = min_area_m2 / (111_000 ** 2)
    glist    = (
        list(simplified.geoms)
        if simplified.geom_type in ("GeometryCollection", "MultiPolygon")
        else [simplified]
    )
    filtered = [g for g in glist
                if g.geom_type in ("Polygon", "MultiPolygon") and g.area >= min_deg2]
    if not filtered:
        return None
 
    final    = unary_union(filtered)
    area_ha  = round(final.area * (111_000 ** 2) / 10_000, 3)
 
    # Build Properties
    dw_cls       = NAME_TO_CLASS.get(class_name)
    pixel_count  = int(mask.sum())
    confidence   = None
    if prob_map is not None:
        valid_probs = prob_map[mask & np.isfinite(prob_map)]
        confidence  = round(float(valid_probs.mean()), 3) if valid_probs.size else None
 
    properties = {
        "class":        class_name,
        "label":        dw_cls.label if dw_cls else class_name,
        "color":        dw_cls.color if dw_cls else "#999999",
        "area_ha":      area_ha,
        "pixel_count":  pixel_count,
        "confidence":   confidence,  # mean DW probability (0-1)
    }

    geom_dict = _round_coords(mapping(final))
 
    return {
        "type":       "Feature",
        "geometry":   geom_dict,
        "properties": properties,
    }
 
def masks_to_geojson(
    masks: Dict[str, np.ndarray],
    transform: Affine,
    probs: Optional[Dict[str, np.ndarray]] = None,
    src_crs: str = "EPSG:4326",
    min_area_m2: float = 1_000.0
    ) -> List[Dict[str, Any]]:
    
    """
    Convert all class masks → list of GeoJSON Features.
 
    Parameters
    ----------
    masks       : dict of class_name → bool (H, W) mask
    transform   : rasterio Affine
    probs       : dict of class_name → float32 (H, W) probability
    src_crs     : raster CRS
    min_area_m2 : minimum polygon area to retain
 
    Returns
    -------
    List of GeoJSON Feature dicts (one per class that has pixels).
    """
    features = []

    for class_name, mask in masks.items():
        prob_map = probs.get(class_name) if probs else None
        feature  = mask_to_feature(
            class_name=class_name,
            mask=mask,
            transform=transform,
            prob_map=prob_map,
            src_crs=src_crs,
            min_area_m2=min_area_m2,
        )
        if feature:
            features.append(feature)
            logger.debug(
                "  %-22s → %.2f ha  |  confidence=%s",
                class_name,
                feature["properties"]["area_ha"],
                feature["properties"]["confidence"],
            )
        else:
            logger.debug("  %-22s → (no pixels / all filtered)", class_name)

    return features