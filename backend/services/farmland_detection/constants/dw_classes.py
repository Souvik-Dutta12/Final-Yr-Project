"""
Dynamic World V1 — All 9 Land Cover Classes
Google / World Resources Institute pre-trained deep-learning model.
Sentinel-2 input · 10 m native resolution · Global coverage.
 
Reference: https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
 
@dataclass(frozen=True)
class DWClass:
    idx:   int
    name:  str      # GEE band name  (used as dict key)
    label: str      # Human-readable label
    color: str      # Hex colour for map / legend

# Master class registry 
DW_CLASSES: List[DWClass] = [
    DWClass(0, "water",              "Water",              "#419BDF"),
    DWClass(1, "trees",              "Trees",              "#397D49"),
    DWClass(2, "grass",              "Grass",              "#88B053"),
    DWClass(3, "flooded_vegetation", "Flooded Vegetation", "#7A87C6"),
    DWClass(4, "crops",              "Crops",              "#E49635"),
    DWClass(5, "shrub_and_scrub",    "Shrub & Scrub",      "#DFC35A"),
    DWClass(6, "built",              "Built-up",           "#C4281B"),
    DWClass(7, "bare",               "Bare Ground",        "#A59B8F"),
    DWClass(8, "snow_and_ice",       "Snow & Ice",         "#B39FE1"),
]
 

DW_BAND_NAMES:  List[str]        = [c.name  for c in DW_CLASSES]
IDX_TO_CLASS:   Dict[int, DWClass] = {c.idx: c for c in DW_CLASSES}
NAME_TO_CLASS:  Dict[str, DWClass] = {c.name: c for c in DW_CLASSES}

S2_RGB_BANDS = ["B4", "B3", "B2"]   


def hex_to_rgb01(hex_color: str) -> Tuple[float, float, float]:
    """'#RRGGBB' → (r, g, b) in 0-1 range."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
 
# ── Adaptive resolution table ──────────────────────────────────────────────────
# GEE download scale is chosen based on polygon area so that:
#   1) The pixel count stays within GEE's 32 M pixel limit per band.
#   2) Network payload & server-side compute stay manageable.
SCALE_TABLE: List[Tuple[float, int]] = [
    (25,   10),   # ≤ 25 km²  → 10 m  (DW native)
    (100,  20),   # ≤ 100 km² → 20 m
    (300,  30),   # ≤ 300 km² → 30 m
    (500,  50),   # ≤ 500 km² → 50 m
]
 
MAX_POLYGON_AREA_KM2 = 500
 
 
def adaptive_scale(area_km2: float) -> int:
    """
    Return the smallest GEE download scale (metres) safe for *area_km2*.
    """
    for limit, scale in SCALE_TABLE:
        if area_km2 <= limit:
            return scale
    return SCALE_TABLE[-1][1]