import numpy as np
from utils.api_error import APIError
from services.earth_engine.ee_service import fetch_indices
from services.farmland_detection.clustering_service import run_kmeans_with_mapping
from services.farmland_detection.geo_json_service import masks_to_geojson
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from services.farmland_detection.clustering_service import run_kmeans_with_mapping


async def process_farmland(polygon: dict) -> dict:
    try:
        # ── 1. Fetch real-time Sentinel-2 indices via GEE ─────────────────
        indices = fetch_indices(polygon, days_back=30)

        ndvi      = indices["ndvi"]
        ndwi      = indices["ndwi"]
        ndbi      = indices["ndbi"]
        mndwi     = indices["mndwi"]
        evi       = indices["evi"]
        transform = indices["transform"]


        # ── 2. Build feature matrix (5 indices) ───────────────────────────
        X = np.stack([
            ndvi.flatten(),
            ndwi.flatten(),
            ndbi.flatten(),
            mndwi.flatten(),
            evi.flatten(),
        ], axis=1)

        # ── 3. Mask out NaN / Inf ─────────────────────────────────────────
        finite_mask = np.isfinite(X).all(axis=1)
        X_valid     = X[finite_mask]

        if len(X_valid) < 50:
            raise APIError(400, "Too few valid pixels inside the polygon "
                               "(cloud cover or polygon too small?)")

        # ── 4. Subsample for large areas (keeps clustering fast) ──────────
        MAX_PIXELS = 50_000
        if len(X_valid) > MAX_PIXELS:
            idx     = np.random.choice(len(X_valid), MAX_PIXELS, replace=False)
            # We still need the full valid_mask for rasterization
            X_sample = X_valid[idx]
        else:
            X_sample = X_valid

        
        # ── 5. Cluster on sample, predict on all valid pixels ─────────────
        labels, mapping, masks = run_kmeans_with_mapping(
            X_sample, finite_mask, indices
        )

        # ── 6. Convert masks → optimised GeoJSON ─────────────────────────
        geojson_features = masks_to_geojson(
            masks,
            transform,
            src_crs="EPSG:4326",   # GEE returns EPSG:4326
            min_area_m2=1_000,     # ignore patches < 0.1 ha
        )

        # ── 7. Summary stats ──────────────────────────────────────────────
        total_pixels = finite_mask.sum()
        stats = {
            cls: {
                "pixel_count": int(mask.sum()),
                "coverage_pct": round(float(mask.sum() / total_pixels * 100), 1),
            }
            for cls, mask in masks.items()
        }

        return {
            "type":     "FeatureCollection",
            "features": geojson_features,
            "metadata": {
                "total_pixels":   int(total_pixels),
                "class_stats":    stats,
                "imagery_source": "Sentinel-2 SR (last 30 days)",
            },
        }
    except APIError:
        raise
    except Exception as e:
        raise APIError(500, f"Farmland detection failed: {str(e)}") from e