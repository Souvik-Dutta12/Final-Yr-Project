import os
import numpy as np
import rasterio

def normalize_patch(patch):
    # patch shape: (C, H, W)
    patch = patch.astype(np.float32)

    for c in range(patch.shape[0]):
        band = patch[c]
        min_val = np.min(band)
        max_val = np.max(band)

        if max_val - min_val > 1e-6:
            patch[c] = (band - min_val) / (max_val - min_val)
        else:
            patch[c] = 0

    return patch

def extract_patches(RASTER_PATH, PATCH_SIZE, STRIDE, NORMALIZE, OUTPUT_DIR):
    with rasterio.open(RASTER_PATH) as src:
        img = src.read()   # shape: (C, H, W)

    C, H, W = img.shape
    print(f"Image shape: {img.shape}")

    patch_id = 0

    for i in range(0, H - PATCH_SIZE + 1, STRIDE):
        for j in range(0, W - PATCH_SIZE + 1, STRIDE):

            patch = img[:, i:i+PATCH_SIZE, j:j+PATCH_SIZE]

            # Normalize
            if NORMALIZE:
                patch = normalize_patch(patch)

            # Convert to (H, W, C)
            patch = np.transpose(patch, (1, 2, 0))

            # Save
            save_path = os.path.join(OUTPUT_DIR, f"patch_{patch_id:05d}.npy")
            np.save(save_path, patch)

            patch_id += 1

    print(f"Total patches saved: {patch_id}")
