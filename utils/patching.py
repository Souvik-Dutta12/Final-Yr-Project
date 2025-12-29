import numpy as np
import os
from utils.normalize import normalize
from utils.stacking import stack_bands 
def extract_and_save_patches_streaming(
    b04, b03, b02, b08, scl,
    patch_size,
    out_dir,
    scene_id
):
    """
    Memory-safe patch extraction.
    No full scene stacking.
    """
    os.makedirs(out_dir, exist_ok=True)

    h, w = b02.shape
    row_idx = 0
    saved = 0

    for i in range(0, h - patch_size, patch_size):
        col_idx = 0
        for j in range(0, w - patch_size, patch_size):

            # slice each band
            p_b04 = b04[i:i+patch_size, j:j+patch_size]
            p_b03 = b03[i:i+patch_size, j:j+patch_size]
            p_b02 = b02[i:i+patch_size, j:j+patch_size]
            p_b08 = b08[i:i+patch_size, j:j+patch_size]
            p_scl = scl[i:i+patch_size, j:j+patch_size]

            # discard non-soil patches
            if np.mean(p_scl != 5) > 0.3:
                col_idx += 1
                continue

            # stack ONLY this patch
            patch = stack_bands(
                p_b04, p_b03, p_b02, p_b08
            ).astype("float16")

            # normalize
            normalize(patch)

            # save
            fname = f"{scene_id}_p{row_idx:03d}_{col_idx:03d}.npy"
            np.save(os.path.join(out_dir, fname), patch)
            saved += 1

            col_idx += 1
        row_idx += 1

    print(f"Saved {saved} patches for {scene_id}")
