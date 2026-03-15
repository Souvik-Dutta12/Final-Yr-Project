import numpy as np
import h5py

eps = 1e-6

def calculate_indices(patch_path):
    '''
    NDVI,
    SAVI,
    NDMI,
    FERROUS_RATIO,
    CLAY_RATIO,
    NDSI,
    BSI
    '''

    with h5py.File(patch_path, "r+") as file:
        patches = file["patches"][:]

        B02 = patches[:, 0, :, :]
        B04 = patches[:, 2, :, :]
        B08 = patches[:, 3, :, :]
        B11 = patches[:, 5, :, :]
        B12 = patches[:, 6, :, :]

        NDVI = (B08 - B04) / (B08 + B04 + eps)
        SAVI = 1.5 * ((B08 - B04) / (B08 + B04 + 0.5 + eps))
        NDMI = (B08 - B11) / (B08 + B11 + eps)
        FERROUS_RATIO = B11 / (B08 + eps)
        CLAY_RATIO = B11 / (B12 + eps)
        NDSI = (B11 - B08) / (B11 + B08 + eps)
        BSI = ((B11 - B04) - (B08 - B02)) / (((B11 + B04) * (B08 + B02))+ eps)
        

        indices = np.stack([NDVI, SAVI, NDMI, FERROUS_RATIO, CLAY_RATIO, NDSI, BSI], axis=1)

        if "indices" in file:
            del file["indices"]

        file.create_dataset(
            "indices",
            data=indices,
            compression="gzip"
        )


        