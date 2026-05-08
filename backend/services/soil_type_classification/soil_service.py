import logging
from collections import Counter
from typing import Dict, List, Optional, Tuple

from services.soilgrid.soilgrids_client import soilgrids_client
from utils.soil_properties.polygon_sampler import adaptive_sample_points

logger = logging.getLogger(__name__)


async def get_soil_type(
        lat: float,
        lon: float) -> Optional[str]:
    """Most probable WRB soil class for a point, e.g. 'Fluvisols'."""
    
    cls = await soilgrids_client.get_soil_class(lat, lon)
    if not cls:
        logger.warning(f"No soil class returned for ({lat}, {lon})")
    return cls


async def get_soil_distribution(
    polygon_geojson: dict
) -> List[Dict]:
    """
    WRB soil class distribution within a polygon via point sampling.

    Returns:
        [{"soil_class": "Fluvisols", "count": 18, "percentage": 72.0}, ...]
    """
    points: List[Tuple[float, float]] = adaptive_sample_points(polygon_geojson)
    logger.info(f"Soil type distribution: {len(points)} sample points")

    classes = await soilgrids_client.batch_get_classes(points)
    valid   = [c for c in classes if c is not None]

    if not valid:
        logger.error("No soil class data returned for polygon.")
        return []

    total  = len(valid)
    counts = Counter(valid)

    return [
        {
            "soil_class": cls,
            "count":      cnt,
            "percentage": round(cnt / total * 100, 2),
        }
        for cls, cnt in counts.most_common()
    ]