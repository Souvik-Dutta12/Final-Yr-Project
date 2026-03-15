import os
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from s2cloudless import S2PixelCloudDetector
from skimage.exposure import match_histograms
import h5py

# Finf required bands 
def find_bands(scene_path):

    bands = {}

    for file in os.listdir(scene_path):

        path = os.path.join(scene_path, file)

        # 10m bands
        if "_B02_10m" in file:
            bands["B02"] = path
        elif "_B03_10m" in file:
            bands["B03"] = path
        elif "_B04_10m" in file:
            bands["B04"] = path
        elif "_B08_10m" in file:
            bands["B08"] = path
        
        # 20m bands
        elif "_B05_20m" in file:
            bands["B05"] = path
        elif "_B06_20m" in file:
            bands["B06"] = path
        elif "_B07_20m" in file:
            bands["B07"] = path
        elif "_B8A_20m" in file:
            bands["B8A"] = path
        elif "_B11_20m" in file:
            bands["B11"] = path
        elif "_B12_20m" in file:
            bands["B12"] = path

        # 60m bands
        elif "_B01_60m" in file:
            bands["B01"] = path
        elif "_B09_60m" in file:
            bands["B09"] = path

        # scl band
        elif "_SCL_20m" in file:
            bands["SCL"] = path

    return bands

# create a cloud mask based on the resampled SCL mask
def create_cloud_mask(scl_resampled, MASK_CLASSES):
    cloud_mask = np.isin(scl_resampled, MASK_CLASSES)
    return cloud_mask

# resample bands
def resample_band(band_path, ref_path):

    with rasterio.open(ref_path) as ref:

        dst_shape = (ref.height, ref.width)
        dst_transform = ref.transform
        dst_crs = ref.crs

        resampled = np.empty(dst_shape, dtype=np.float32)

    with rasterio.open(band_path) as src:

        reproject(
            source=rasterio.band(src,1),
            destination=resampled,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear
        )

    return resampled

# stacking
def make_stack(band_arrays):
    stack = np.stack(band_arrays, axis=0)
    return stack

# Histogram normalization
def histogram_normalization(scene_stack, reference_stack):
    normalized = match_histograms(scene_stack, reference_stack)

    return normalized

# patch extraction
def extract_patches(image_stack, output_dir,scene, patch_size=256 ,overlap=0.5):
    
    stride = int(patch_size * (1 - overlap))
    bands, height, width = image_stack.shape
    patch_count = 0
    with h5py.File(os.path.join(output_dir, f"{scene}_patches.h5"), "w") as f:
        dataset = f.create_dataset(
            "patches",
            shape=(0, bands, patch_size, patch_size),
            maxshape=(None, bands, patch_size, patch_size),
            dtype="float16",
            chunks=(1,bands, patch_size, patch_size),
            compression="gzip",
            compression_opts=4
        )

        for y in range(0, height - patch_size + 1, stride):
            for x in range(0, width - patch_size + 1, stride):

                patch = image_stack[:, y:y+patch_size, x:x+patch_size]

                # skip cloud dominated patches
                if np.isnan(patch).mean() > 0.4:
                    continue
                
                # skip low variance patches
                if np.std(patch) < 0.01:
                    continue
                dataset.resize(patch_count + 1, axis=0)
                dataset[patch_count] = patch.astype(np.float16)

                patch_count += 1
                if patch_count % 1500 == 0:
                    print(f"{patch_count} patches saved...")
    print("Total patches saved:", patch_count)

# process one scene
def process_scene(scene,scene_path, output_dir, MASK_CLASSES, reference_stack=None):
    """
    Complete preprocessing for one Sentinel-2 scene.
    Steps:
    1. Find all bands
    2. Create cloud mask (SCL)
    3. Resample lower resolution bands
    4. Stack bands
    5. Normalize (optional)
    6. Extract patches
    """

    bands = find_bands(scene_path)
    ref_band = bands["B02"]

    scl_resampled = resample_band(bands["SCL"], ref_band)
    cloud_mask = create_cloud_mask(scl_resampled, MASK_CLASSES)

    band_arrays = []
    # 10m bands
    for bnd in ["B02","B03","B04","B08"]:
        with rasterio.open(bands[bnd]) as src:
            data = src.read(1).astype(np.float32)

        data[cloud_mask] = np.nan
        band_arrays.append(data)

    # 20m bands
    for bnd in ["B05","B11","B12"]:
        resampled = resample_band(bands[bnd], ref_band)
        resampled[cloud_mask] = np.nan

        band_arrays.append(resampled)

    # # 60m bands
    for bnd in ["B01","B09"]:
        resampled = resample_band(bands[bnd], ref_band)
        resampled[cloud_mask] = np.nan

        band_arrays.append(resampled)

    stack = make_stack(band_arrays)

    if reference_stack is not None:
        stack = histogram_normalization(stack, reference_stack)

    extract_patches(stack, output_dir, scene)

