import rasterio

def validate_polygon(polygon):
    """
    {
        "type": "Polygon",
        "coordinates": [
            [
                [88.36, 22.57],
                [88.37, 22.58],
                [88.38, 22.56],
                [88.36, 22.57]
            ]
        ]
    }
    """

    if not polygon or len(polygon["coordinates"]) == 0:
        raise ValueError("Invalid polygon")

    return polygon


def clip_raster(polygon):
    with rasterio.open("app/data/west_bengal_stack.tif") as src:
        out_image, _ = mask(src, [polygon], crop=True)

    return out_image  # (bands, H, W)