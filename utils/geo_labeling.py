import numpy as np
import rasterio
from rasterio.windows import Window

def load_soil_map(soil_map_path):
    """
    Opens the reference soil raster.
    """
    soil_ds = rasterio.open(soil_map_path)
    return soil_ds


def label_patch_majority(
    soil_ds,
    x_offset,
    y_offset,
    patch_size,
    dominance_threshold=0.7
):
    """
    Assigns a soil label to a patch using majority rule.

    Returns:
        (label, dominance_ratio) or (None, None)
    """

    window = Window(
        col_off=x_offset,
        row_off=y_offset,
        width=patch_size,
        height=patch_size
    )

    soil_patch = soil_ds.read(1, window=window)

    # remove nodata
    nodata = soil_ds.nodata
    if nodata is not None:
        soil_patch = soil_patch[soil_patch != nodata]

    if soil_patch.size == 0:
        return None, None

    values, counts = np.unique(soil_patch, return_counts=True)

    dominant_index = np.argmax(counts)
    dominant_label = values[dominant_index]
    dominance_ratio = counts[dominant_index] / counts.sum()

    if dominance_ratio < dominance_threshold:
        return None, dominance_ratio

    return dominant_label, dominance_ratio