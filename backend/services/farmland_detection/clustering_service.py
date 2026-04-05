from sklearn.cluster import KMeans
import numpy as np


def run_kmeans_with_mapping(X_valid,valid_mask, ndvi, ndwi, ndbi):

    # 1. Run KMeans
    kmeans = KMeans(n_clusters=5, random_state=42)
    labels = kmeans.fit_predict(X_valid)

    # reshape labels to raster shape
    full_labels = np.full(valid_mask.shape[0], -1)
    full_labels[valid_mask] = labels
    segmented = full_labels.reshape(ndvi.shape)

    # 2. Compute cluster-wise means
    cluster_ndvi_mean = []
    cluster_ndbi_mean = []
    cluster_ndwi_mean = []

    for i in range(5):

        mask = (segmented == i)

        if np.sum(mask) == 0:
            cluster_ndvi_mean.append(-np.inf)
            cluster_ndbi_mean.append(-np.inf)
            cluster_ndwi_mean.append(-np.inf)
            continue

        mean_ndvi = ndvi[mask].mean()
        mean_ndbi = ndbi[mask].mean()
        mean_ndwi = ndwi[mask].mean()

        cluster_ndvi_mean.append(mean_ndvi)
        cluster_ndbi_mean.append(mean_ndbi)
        cluster_ndwi_mean.append(mean_ndwi)

        print(f"Cluster {i}: NDVI={mean_ndvi:.3f}, NDBI={mean_ndbi:.3f}, NDWI={mean_ndwi:.3f}")

    # 3. Identify clusters
    farmland_cluster = np.argmax(cluster_ndvi_mean)
    built_up_cluster = np.argmax(cluster_ndbi_mean)
    water_cluster = np.argmax(cluster_ndwi_mean)

    print("Farmland cluster:", farmland_cluster)
    print("Built-up cluster:", built_up_cluster)
    print("Water cluster:", water_cluster)

    # 4. Create mapping
    mapping = {}

    for i in range(5):
        if i == farmland_cluster:
            mapping[i] = "farmland"
        elif i == built_up_cluster:
            mapping[i] = "builtup"
        elif i == water_cluster:
            mapping[i] = "water"
        else:
            mapping[i] = "unknown"

    # 5. Optional masks (useful for debugging / overlays)
    farmland_mask = (segmented == farmland_cluster)

    # hybrid rule (improves accuracy)
    built_up_mask = (segmented == built_up_cluster) & (ndbi > 0.1)
    water_mask = (segmented == water_cluster) & (ndwi > 0)

    return labels, mapping, {
        "farmland": farmland_mask,
        "builtup": built_up_mask,
        "water": water_mask
    }