import numpy as np
from utils.api_error import APIError
from services.farmland_detection.farmland_raster_service import clip_rasters
from services.farmland_detection.clustering_service import run_kmeans_with_mapping
from services.farmland_detection.geo_json_service import masks_to_geojson

async def process_farmland(polygon):

    try:
        # 1. Clip rasters
        ndvi, ndwi, ndbi, transform = clip_rasters(polygon)

        # 2. Create feature matrix
        X = np.stack([
            ndvi.flatten(),
            ndwi.flatten(),
            ndbi.flatten()
        ], axis=1)

        # 3. Remove NaN pixels
        valid_mask = ~np.isnan(X).any(axis=1)
        X_valid = X[valid_mask]

        if len(X_valid) == 0:
            raise APIError(400, "No valid pixels inside polygon")

        # 4. KMeans + semantic mapping
        labels, mapping, masks = run_kmeans_with_mapping(
                                        X_valid,
                                        valid_mask,
                                        ndvi,
                                        ndwi,
                                        ndbi
                                        )

        # 5. Rebuild raster
        # full_labels = np.full(X.shape[0], -1)
        # full_labels[valid_mask] = labels
        # full_labels = full_labels.reshape(ndvi.shape)

        # 6. Convert to GeoJSON
        geojson_features = masks_to_geojson(masks, transform)

        return {
            "type": "FeatureCollection",
            "features": geojson_features
        }

    except APIError:
        raise

    except Exception as e:
        raise APIError(500, f"Farmland detection failed: {str(e)}")