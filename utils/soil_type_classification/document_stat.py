import os
import rasterio
import numpy as np
import json
from datetime import datetime

def generate_scene_metadata(drive_dir, soil_type, scene_name):
    """
    Generates metadata for one scene and stores it as metadata.json
    inside the scene directory.
    """

    scene_dir = os.path.join(drive_dir, soil_type, scene_name)
    metadata = {
        "soil_type": soil_type,
        "scene_name": scene_name,
        "satellite": "Sentinel-2",
        "file_format": "JP2",
        "generated_on": datetime.now().isoformat(),
        "bands": {}
    }

    for file in sorted(os.listdir(scene_dir)):
        if not file.lower().endswith(".jp2"):
            continue

        band_name = os.path.splitext(file)[0]
        band_path = os.path.join(scene_dir, file)

        with rasterio.open(band_path) as src:
            band = src.read(1)
            nodata = src.nodata

            if nodata is not None:
                band = band[band != nodata]

            metadata["bands"][band_name] = {
                "path": band_path,
                "crs": str(src.crs),
                "resolution": src.res,
                "shape": band.shape,
                "dtype": str(band.dtype),
                "nodata": nodata,
                "min": float(np.min(band)),
                "max": float(np.max(band)),
                "mean": float(np.mean(band)),
                "std": float(np.std(band))
            }

    # Save metadata.json inside scene folder
    metadata_path = os.path.join(scene_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)

    return metadata_path

def is_jp2_file_valid(jp2_path):
    """
    Checks whether a JP2 file is readable and non-corrupted.

    Returns:
        True  -> file is valid
        False -> file is corrupted or unreadable
    """
    try:
        with rasterio.open(jp2_path) as src:
            band = src.read(1)

            # Basic sanity checks
            if band is None:
                return False

            if band.size == 0:
                return False

            if np.isnan(band).all():
                return False

            if src.width == 0 or src.height == 0:
                return False

        return True

    except Exception as e:
        return False

def verify_scene_integrity(scene_dir):
    """
    Checks all JP2 files inside a scene directory.

    Returns:
        corrupted_files (list)
    """
    corrupted_files = []

    for file in os.listdir(scene_dir):
        if file.lower().endswith(".jp2"):
            path = os.path.join(scene_dir, file)

            if not is_jp2_file_valid(path):
                corrupted_files.append(file)

    return corrupted_files

def verify_dataset_integrity(drive_dir):
    report = {}

    for soil_type in os.listdir(drive_dir):
        soil_path = os.path.join(drive_dir, soil_type)
        if not os.path.isdir(soil_path):
            continue

        for scene_name in os.listdir(soil_path):
            scene_dir = os.path.join(soil_path, scene_name)
            if not os.path.isdir(scene_dir):
                continue

            corrupted = verify_scene_integrity(scene_dir)

            if corrupted:
                report[f"{soil_type}/{scene_name}"] = corrupted

    return report

def compute_scene_band_statistics(scene_dir):
    """
    Computes min, max, mean, std for each JP2 band in a scene directory.

    Expected structure:
    scene_dir/
        *.jp2  (each file = one spectral band)

    Returns:
        stats (dict): {
            band_name: {
                'min': value,
                'max': value,
                'mean': value,
                'std': value
            }
        }
    """

    stats = {}

    for file in sorted(os.listdir(scene_dir)):
        if not file.lower().endswith(".jp2"):
            continue

        band_name = os.path.splitext(file)[0]
        band_path = os.path.join(scene_dir, file)

        with rasterio.open(band_path) as src:
            
            band = src.read(1)
            nodata = src.nodata

            if nodata is not None:
                band = band[band != nodata]

        stats[band_name] = {
            "min": float(np.min(band)),
            "max": float(np.max(band)),
            "mean": float(np.mean(band)),
            "std": float(np.std(band))
        }

    return stats
