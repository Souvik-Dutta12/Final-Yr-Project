# 🛰️ Land Cover Analysis — Architecture & Engineering Guide

## Core engineering decisions

### 1. Dynamic World V1 — pre-trained deep learning (no local GPU needed)

Dynamic World is a **globally deployed semantic segmentation model**
trained by Google DeepMind / WRI on hundreds of millions of Sentinel-2
images. It runs entirely on Google Earth Engine — your server only
receives the output label raster. This means:

- No local model weights, no CUDA, no training cost.
- 10 m native resolution — 3× sharper than the old 30 m approach.
- Near-real-time: new outputs every 2–5 days per area.
- 9 semantic classes with calibrated probability scores.

### 2. Adaptive resolution

```
Area          Scale    Max download size (9 bands)
──────────    ──────   ─────────────────────────────
< 25 km²      10 m     ~22 MB   (fast)
25–100 km²    20 m     ~22 MB   (fast)
100–300 km²   30 m     ~20 MB   (fast)
300–500 km²   50 m     ~18 MB   (fast)
> 500 km²     ✗        Rejected (return HTTP 400)
```

### 3. Probability / confidence scoring

Dynamic World provides 9 probability bands alongside the label band.
The service computes:

- **Per-class confidence** — mean probability within each detected class.
- **Dominant confidence** — mean of the max-probability across all pixels.  
  Values below ~0.5 indicate spatially ambiguous areas worth flagging.

### 4. Change detection

The `/land-cover/change` endpoint compares two date windows and produces:

- **Transition matrix** (9×9) — exact pixel-level class transitions.
- **Notable transitions** — pre-defined ecologically meaningful changes
  (deforestation, urban expansion, glacial retreat, etc.).
- **NDVI delta** — net vegetation index change between periods.
- **Changed area %** — fraction of the polygon that shifted class.

### 5. TTL cache

GEE calls for the same polygon + window are cached for 15 minutes.
This makes repeated frontend requests (e.g. re-rendering the map)
instant after the first call.

---

## API usage

### Snapshot analysis

```http
POST /land-cover/analyze
Content-Type: application/json

{
  "polygon": {
    "type": "Polygon",
    "coordinates": [[[78.15,29.97],[78.20,29.97],[78.20,29.92],[78.15,29.92],[78.15,29.97]]]
  },
  "days_back": 60
}
```

**Response** — GeoJSON FeatureCollection:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { ... },
      "properties": {
        "class": "crops",
        "label": "Crops",
        "color": "#E49635",
        "area_ha": 142.3,
        "pixel_count": 14230,
        "confidence": 0.812
      }
    }
  ],
  "metadata": {
    "model": "Dynamic World V1 (Google / WRI, pre-trained deep learning)",
    "resolution_m": 10,
    "area_km2": 27.4,
    "scene_count": 18,
    "dominant_confidence": 0.764,
    "class_stats": { ... },
    "index_stats": { ... }
  }
}
```

### Change detection

```http
POST /land-cover/change
Content-Type: application/json

{
  "polygon": { ... },
  "date_from": { "start": "2023-01-01", "end": "2023-03-31" },
  "date_to":   { "start": "2024-01-01", "end": "2024-03-31" }
}
```

**Response**:
```json
{
  "class_deltas": {
    "trees":  { "delta_ha": -12.4, "delta_pct": -3.2 },
    "built":  { "delta_ha":  +8.1, "delta_pct": +2.1 }
  },
  "notable_transitions": [
    { "from": "trees", "to": "built", "label": "Deforestation → Urban", "area_ha": 8.1 }
  ],
  "ndvi_delta_mean": -0.043,
  "changed_pct": 14.7
}
```

---

## Polygon size guide

| Area | Expected latency | Resolution |
|------|-----------------|------------|
| < 5 km² | 8–15 s | 10 m |
| 5–50 km² | 15–30 s | 10–20 m |
| 50–200 km² | 30–60 s | 20–30 m |
| 200–500 km² | 60–120 s | 50 m |
| > 500 km² | ✗ Rejected | — |

Tip: for very large areas, split into a grid of tiles and merge the
FeatureCollections on the client side.

---

## What to build next

1. **NDVI time series** — monthly NDVI mean for a polygon over 1–2 years.
   Reveals crop calendars, drought stress, deforestation trends.

2. **Tile-based processing** — split polygons > 500 km² into a grid,
   process in parallel, merge results. Enables national-scale analysis.

3. **Webhook / async jobs** — for large polygons, return a job ID
   immediately and POST results to a callback URL when ready.

4. **Alert rules** — monitor a polygon on a schedule; fire a webhook when
   `notable_transitions` exceeds a threshold (e.g. deforestation > 5 ha).

5. **Vector tile export** — serve GeoJSON as Mapbox Vector Tiles (MVT)
   for smooth rendering of large segmentation results on the frontend.