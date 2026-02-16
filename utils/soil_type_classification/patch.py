import os
import numpy as np
import rasterio
from tqdm import tqdm
from rasterio.warp import reproject, Resampling



def load_scene_bands(scene_path, valid_ext=".jp2"):
    """
    Load Sentinel-2 bands and resample all to 10m resolution.
    Returns: (C, H, W)
    """

    band_files = sorted([
        os.path.join(scene_path, f)
        for f in os.listdir(scene_path)
        if f.endswith(valid_ext)
    ])

    # Open reference band (first band → usually 10m)
    with rasterio.open(band_files[0]) as ref:
        ref_shape = ref.read(1).shape
        ref_transform = ref.transform
        ref_crs = ref.crs

    bands = []

    for band_path in band_files:
        with rasterio.open(band_path) as src:
            band = src.read(1)

            # If shape mismatch → resample
            if band.shape != ref_shape:
                resampled = np.empty(ref_shape, dtype=band.dtype)

                reproject(
                    source=band,
                    destination=resampled,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=Resampling.bilinear
                )
                bands.append(resampled)
            else:
                bands.append(band)

    return np.stack(bands, axis=0)



def extract_patches(image, patch_size, stride):
    C, H, W = image.shape
    patches = []

    for y in range(0, H - patch_size + 1, stride):
        for x in range(0, W - patch_size + 1, stride):
            patches.append(image[:, y:y + patch_size, x:x + patch_size])

    return patches


def save_patches(patches, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    for idx, patch in enumerate(patches):
        np.save(os.path.join(output_dir, f"patch_{idx}.npy"), patch)


def process_scene(
    soil_type,
    scene_name,
    dataset_dir,
    output_dir,
    patch_size,
    stride,
    valid_ext=".jp2"
):
    scene_path = os.path.join(dataset_dir, soil_type, scene_name)
    out_path = os.path.join(output_dir, soil_type, scene_name)

    image = load_scene_bands(scene_path, valid_ext)
    patches = extract_patches(image, patch_size, stride)

    save_patches(patches, out_path)

    # 🔹 Scene-level logging
    print(
        f"[SCENE] Soil: {soil_type} | Scene: {scene_name} "
        f"| Patches created: {len(patches)}"
    )

    return len(patches)


def process_dataset(
    dataset_dir,
    output_dir,
    patch_size,
    stride,
    valid_ext=".jp2"
):
    total_patches = 0

    soil_types = ["desert", "mountain", "red"]

    for soil in soil_types:
        soil_path = os.path.join(dataset_dir, soil)
        if not os.path.isdir(soil_path):
            continue

        soil_patch_count = 0
        scenes = os.listdir(soil_path)

        print(f"\n=== Processing soil class: {soil} ===")

        for scene in tqdm(scenes, desc=f"{soil} scenes"):
            count = process_scene(
                soil,
                scene,
                dataset_dir,
                output_dir,
                patch_size,
                stride,
                valid_ext
            )
            soil_patch_count += count
            total_patches += count

        # 🔹 Soil-level summary
        print(
            f"[SUMMARY] Soil: {soil} | Total patches: {soil_patch_count}"
        )

    # 🔹 Dataset-level summary
    print("\n====================================")
    print(f"[DATASET COMPLETE] Total patches created: {total_patches}")
    print("====================================")
