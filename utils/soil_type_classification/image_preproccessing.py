import rasterio
import numpy as np
from rasterio.enums import Resampling

def read_and_normalize_band(jp2_path):
    '''
    Normalized Pixel Value=DN/10000
    '''
    with rasterio.open(jp2_path) as src:
        band = src.read(1).astype(np.float32)
        
    # Radiometric normalization
    band = band / 10000.0
    band = np.clip(band, 0, 1)
    
    return band

# cloud mask function
def read_and_resample_scl(scl_path, target_shape):
    with rasterio.open(scl_path) as src:
        scl_10m = src.read(
            1,
            out_shape=target_shape,
            resampling=Resampling.nearest  # IMPORTANT for labels
        )
    return scl_10m

def generate_cloud_mask(scl_10m):
    cloud_classes = [3, 7, 8, 9, 10, 11]
    return np.isin(scl_10m, cloud_classes)

def apply_cloud_mask(band, cloud_mask):
    band_masked = band.copy()
    band_masked[cloud_mask] = 0  # or np.nan
    return band_masked



    try:
        with rasterio.open(jp2_path) as src:
            _ = src.read(1)
        return False
    except:
        return True