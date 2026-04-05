import rasterio.features
from pyproj import Transformer

def reproject_geometry(geometry, src_crs="EPSG:32645", dst_crs="EPSG:4326"):

    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    def transform_coords(coords):
        return [list(transformer.transform(x, y)) for x, y in coords]

    if geometry["type"] == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [
                transform_coords(ring)
                for ring in geometry["coordinates"]
            ]
        }

    return geometry

def masks_to_geojson(masks, transform):

    features = []

    for class_name, mask in masks.items():

        shapes = rasterio.features.shapes(
            mask.astype("uint8"),
            transform=transform
        )

        for geom, value in shapes:

            if value == 0:
                continue

            geom = reproject_geometry(geom)

            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "class": class_name
                }
            })

    return features