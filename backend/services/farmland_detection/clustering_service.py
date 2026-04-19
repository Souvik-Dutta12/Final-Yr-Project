import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

THRESHOLDS = {
    "farmland": {"ndvi": 0.25, "evi": 0.2},
    "water":    {"ndwi": 0.0,  "mndwi": 0.0},
    "builtup":  {"ndbi": 0.05},
}

def _score_cluster(mean: dict) -> dict:
    """
    Return a named score for each land-cover class.
    Higher = more likely to be that class.
    """
    return {
        # farmland: high NDVI AND high EVI (rules out noise)
        "farmland": mean["ndvi"] * 0.6 + mean["evi"] * 0.4,
        # water: high NDWI AND high MNDWI (MNDWI suppresses built-up confusion)
        "water":    mean["ndwi"] * 0.5 + mean["mndwi"] * 0.5,
        # builtup: high NDBI, penalise greenness
        "builtup":  mean["ndbi"] - mean["ndvi"] * 0.3,
    }

def run_kmeans_with_mapping(X_valid, valid_mask, indices: dict):
    """
    Parameters
    ----------
    X_valid     : (N, 5) float array of valid pixels
    valid_mask  : bool mask over the flat pixel array
    indices     : dict with keys ndvi, ndwi, ndbi, mndwi, evi (2-D arrays)

    Returns
    -------
    labels, mapping, masks
    """

    ndvi, ndwi, ndbi = indices["ndvi"], indices["ndwi"], indices["ndbi"]
    mndwi, evi       = indices["mndwi"], indices["evi"]

    n_clusters = 6   # extra cluster absorbs ambiguous barren/shadow pixels

     # ── 1. Scale features before clustering ──────────────────────────────
    scaler  = StandardScaler()
    X_scaled = scaler.fit_transform(X_valid)

    # ── 2. KMeans++ (better initialisation than random) ───────────────────
    kmeans = KMeans(n_clusters=n_clusters, init="k-means++",
                    n_init=10, random_state=42, max_iter=300)
    labels = kmeans.fit_predict(X_scaled)

    full_labels = np.full(valid_mask.shape[0], -1)
    full_labels[valid_mask] = labels
    segmented   = full_labels.reshape(ndvi.shape)

    # ── 3. Per-cluster mean for each index ───────────────────────────────
    cluster_means = []
    for i in range(n_clusters):
        m = segmented == i
        if m.sum() == 0:
            cluster_means.append({k: -np.inf for k in ["ndvi","ndwi","ndbi","mndwi","evi"]})
            continue
        cluster_means.append({
            "ndvi":  float(ndvi[m].mean()),
            "ndwi":  float(ndwi[m].mean()),
            "ndbi":  float(ndbi[m].mean()),
            "mndwi": float(mndwi[m].mean()),
            "evi":   float(evi[m].mean()),
        })

     # ── 4. Score-based assignment (no conflicts, priority order) ──────────
    scores = [_score_cluster(cm) for cm in cluster_means]
    # Rank clusters by each class score; assign best available, then next-best
    mapping = {}
    assigned = set()
    priority = ["water", "farmland", "builtup"]   # water first — least ambiguous
    

    for cls in priority:
        ranked = sorted(range(n_clusters),
                        key=lambda i: scores[i][cls], reverse=True)
        for c in ranked:
            if c in assigned:
                continue
            # Hard threshold guard — don't label if cluster is below minimum
            mean = cluster_means[c]
            if cls == "farmland" and mean["ndvi"] < THRESHOLDS["farmland"]["ndvi"]:
                continue
            if cls == "water" and mean["ndwi"] < THRESHOLDS["water"]["ndwi"] and \
                                  mean["mndwi"] < THRESHOLDS["water"]["mndwi"]:
                continue
            if cls == "builtup" and mean["ndbi"] < THRESHOLDS["builtup"]["ndbi"]:
                continue
            mapping[c] = cls
            assigned.add(c)
            break
    for i in range(n_clusters):
        if i not in mapping:
            mapping[i] = "unknown"

    print("Cluster assignments:")
    for i, cls in mapping.items():
        m = cluster_means[i]
        print(f"  {i} → {cls:10s} | NDVI={m['ndvi']:.3f} NDWI={m['ndwi']:.3f} "
              f"NDBI={m['ndbi']:.3f} EVI={m['evi']:.3f}")
        
      # ── 5. Per-pixel threshold refinement (reduces salt-and-pepper noise) ──
    farmland_cluster = [c for c, v in mapping.items() if v == "farmland"]
    builtup_cluster  = [c for c, v in mapping.items() if v == "builtup"]
    water_cluster    = [c for c, v in mapping.items() if v == "water"]

    farmland_base = np.isin(segmented, farmland_cluster)
    builtup_base  = np.isin(segmented, builtup_cluster)
    water_base    = np.isin(segmented, water_cluster)

    farmland_mask = farmland_base & (ndvi > THRESHOLDS["farmland"]["ndvi"])
    builtup_mask  = builtup_base  & (ndbi > THRESHOLDS["builtup"]["ndbi"])
    water_mask    = (water_base   & (ndwi > THRESHOLDS["water"]["ndwi"])) | \
                    (mndwi > 0.1)   # MNDWI catches water missed by clustering
    
    return labels, mapping, {
        "farmland": farmland_mask,
        "builtup":  builtup_mask,
        "water":    water_mask,
    }

