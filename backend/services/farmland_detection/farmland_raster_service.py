import rasterio
from rasterio.mask import mask
from pyproj import Transformer
from utils.api_error import APIError

NDVI_PATH = r"C:\Users\debas\OneDrive\Desktop\Final Year Project\Main_prj\new ds\WB\indices\NDVI.tif"
NDWI_PATH = r"C:\Users\debas\OneDrive\Desktop\Final Year Project\Main_prj\new ds\WB\indices\NDWI.tif"
NDBI_PATH =  r"C:\Users\debas\OneDrive\Desktop\Final Year Project\Main_prj\new ds\WB\indices\NDBI.tif"

def reproject_polygon(polygon, dst_crs):

    transformer = Transformer.from_crs(
        "EPSG:4326",   # frontend polygon CRS
        dst_crs,       # raster CRS (EPSG:32645)
        always_xy=True
    )

    new_coords = []

    for ring in polygon["coordinates"]:
        new_ring = []

        for lon, lat in ring:
            x, y = transformer.transform(lon, lat)
            new_ring.append([x, y])

        new_coords.append(new_ring)

    return {
        "type": "Polygon",
        "coordinates": new_coords
    }


def clip_single(path, polygon):
    with rasterio.open(path) as src:
        polygon_projected = reproject_polygon(polygon, src.crs)
        try:
            out_img, transform = mask(src, [polygon_projected], crop=True)
            return out_img[0], transform
        except ValueError:
            raise APIError(
                400, "Polygon does not overlap raster after reprojection"
            )


def clip_rasters(polygon):
    ndvi, transform = clip_single(NDVI_PATH, polygon)
    ndwi, _ = clip_single(NDWI_PATH, polygon)
    ndbi, _ = clip_single(NDBI_PATH, polygon)

    return ndvi, ndwi, ndbi, transform