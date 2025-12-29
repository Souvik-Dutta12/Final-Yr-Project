import rasterio
import numpy as np
from rasterio.enums import Resampling
from rasterio.warp import reproject

#Read Sentinel-2 bands safely with metadata.
def read_band(path):
    with rasterio.open(path) as src:
        band = src.read(1)
        profile = src.profile
    return band, profile

#Make B11 and SCL match 10 m bands.
def resample_band(src_band, src_profile, ref_profile, resampling_method):

    dst = np.empty(
        (ref_profile['height'], ref_profile['width']),
        dtype=src_band.dtype
    )

    reproject(
        source=src_band,
        destination=dst,
        src_transform=src_profile['transform'],
        src_crs=src_profile['crs'],
        dst_transform=ref_profile['transform'],
        dst_crs=ref_profile['crs'],
        resampling=resampling_method
    )
    return dst

#save band with updated profile.
def save_band(path, band, profile):
    profile.update(dtype=band.dtype, count=1)
    with rasterio.open(path, 'w', **profile) as dst:
        dst.write(band, 1)