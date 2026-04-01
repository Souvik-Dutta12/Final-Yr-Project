# West Bengal Map Frontend Workflow

## Goal

Build a React map interface where:

1. the map opens on West Bengal
2. the user can switch between:
   - normal map
   - satellite map
3. the user draws a polygon on the map
4. the selected polygon area is sent to the backend
5. the backend analyzes only that selected area
6. the frontend shows farmland and built-up results as overlays on the same map

This file is only about the frontend map workflow and the frontend-backend contract needed to support it.

---

## 1. What We Are Building

The final flow should look like this:

1. open West Bengal map
2. choose base layer:
   - standard map
   - satellite imagery
3. draw polygon around any area of interest
4. click `Analyze`
5. backend clips that polygon area from the source raster
6. model detects:
   - farmland
   - built-up
7. frontend draws the result on top of the map as colored overlays
8. user can toggle:
   - farmland overlay
   - built-up overlay
   - polygon boundary
   - transparency

---

## 2. Recommended Frontend Stack

Use this stack for the first version:

- `React`
- `Vite`
- `TypeScript`
- `Leaflet`
- `React Leaflet`
- `Leaflet.draw` or a React wrapper around it

Why this stack:

- `Leaflet` is simple and strong for 2D GIS-style apps
- `React Leaflet` lets us keep the UI in React
- `Leaflet.draw` already supports polygon drawing and editing
- it is enough for West Bengal state-level map browsing and polygon selection

---

## 3. Base Map Setup

### 3.1 Initial West Bengal View

Start the map centered on West Bengal.

Suggested initial values:

- center: `[23.3, 87.9]`
- zoom: `7`

Suggested map bounds for limiting navigation roughly to West Bengal and nearby context:

- south-west: `[21.4, 85.8]`
- north-east: `[27.3, 89.9]`

These bounds are not for clipping data. They are only for frontend map navigation.

### 3.2 Required Base Layers

You need two base layers:

1. `Normal map`
   - use OpenStreetMap-style standard tiles
   - good for roads, towns, labels, district context

2. `Satellite map`
   - use a licensed imagery provider
   - good for visual land cover review

### 3.3 Layer Switcher

Add a base-layer switch control so the user can move between:

- `Normal`
- `Satellite`

Do not mix these with farmland overlays. Base layers and analysis overlays should be separate controls.

---

## 4. Main React Screen Layout

Create one main page:

- `FarmlandMapPage`

Recommended layout:

1. top bar
   - title
   - base layer label
   - analyze button
   - clear polygon button

2. left sidebar
   - instructions
   - polygon status
   - selected area information
   - analysis status

3. center map
   - West Bengal base map
   - drawing tools
   - overlays

4. right sidebar
   - legend
   - farmland toggle
   - built-up toggle
   - opacity slider
   - result stats

---

## 5. Step-by-Step Implementation Procedure

## Step 1. Create the React Map Page

Create a page with a full-screen Leaflet map.

Frontend tasks:

- create `FarmlandMapPage.tsx`
- render `MapContainer`
- set the West Bengal center and zoom
- set map height to full viewport

At this stage, do only this:

- show the map
- no polygon
- no model call
- no overlay yet

Success condition:

- user opens the page and sees West Bengal immediately

## Step 2. Add Two Base Layers

Add:

- standard base map
- satellite imagery base map

Frontend tasks:

- add one `TileLayer` for normal map
- add one `TileLayer` or imagery layer for satellite view
- add `LayersControl`

Important:

- keep correct attribution visible
- do not hard-code provider assumptions in many places
- store map provider configuration in one file

Recommended config file:

```text
src/config/mapLayers.ts
```

Example shape:

```ts
export const MAP_LAYERS = {
  normal: {
    name: "Normal",
    url: "...",
    attribution: "...",
  },
  satellite: {
    name: "Satellite",
    url: "...",
    attribution: "...",
  },
};
```

Success condition:

- user can switch between standard and satellite view

## Step 3. Restrict the App to a Single Drawn Polygon

Now add polygon drawing.

Frontend tasks:

- add a `FeatureGroup`
- add draw control
- enable only polygon drawing
- disable marker, polyline, circle, rectangle if not needed
- allow edit and delete
- store the selected polygon in React state

Important rule:

- allow only one active polygon at a time

So the UI should behave like this:

1. user draws polygon
2. polygon is saved in state
3. if user draws again, either:
   - replace the old polygon, or
   - ask the user to clear the previous one first

Recommended React state:

```ts
type LatLngPoint = [number, number];

type SelectedPolygon = {
  id: string;
  coordinates: LatLngPoint[];
};
```

Success condition:

- user can draw, edit, and delete one polygon on the map

## Step 4. Convert the Polygon to GeoJSON

The backend should not receive raw Leaflet objects.

Frontend tasks:

- convert the drawn polygon into `GeoJSON`
- store it in state
- show selected area summary in the sidebar

Recommended payload:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[88.1, 22.5], [88.2, 22.5], [88.2, 22.4], [88.1, 22.4], [88.1, 22.5]]]
  },
  "properties": {
    "name": "selected-area"
  }
}
```

Important:

- GeoJSON uses `[longitude, latitude]`
- Leaflet works mostly with `[latitude, longitude]`

Be careful while converting.

Success condition:

- the selected polygon can be exported as valid GeoJSON

## Step 5. Add an Analyze Button

Once polygon drawing works, add an `Analyze` button.

Frontend tasks:

- disable the button when no polygon exists
- send the polygon to the backend
- show loading state while processing
- block duplicate clicks during processing

Recommended API:

- `POST /farmland/analyze-area`

Request body:

```json
{
  "state": "west_bengal",
  "polygon": {
    "type": "Feature",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[88.1, 22.5], [88.2, 22.5], [88.2, 22.4], [88.1, 22.4], [88.1, 22.5]]]
    },
    "properties": {}
  }
}
```

Success condition:

- the frontend can submit a polygon and receive a result

## Step 6. Decide the Overlay Format

There are two good ways to render the result on the map.

### Option A. GeoJSON Overlay

Backend returns farmland and built-up as polygons.

Example:

```json
{
  "farmland": {
    "type": "FeatureCollection",
    "features": []
  },
  "builtup": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

Why this is good:

- easy to style
- easy to toggle
- easy to click for details
- good for map-native interaction

### Option B. Raster Image Overlay

Backend returns georeferenced overlay images with bounds.

Example:

```json
{
  "farmlandOverlayUrl": "/outputs/run_001/farmland.png",
  "builtupOverlayUrl": "/outputs/run_001/builtup.png",
  "bounds": [[22.4, 88.1], [22.5, 88.2]]
}
```

Why this is good:

- simple if the model output is already a raster mask
- good for fast first version

### Recommended Choice

Start with:

- `GeoJSON` if you can vectorize the prediction result
- `ImageOverlay` if your backend naturally produces masks first

If your current pipeline is patch/mask based, a raster overlay is usually the fastest first implementation.

## Step 7. Render Farmland and Built-up Layers

Once the backend returns output, draw it on the map.

Frontend tasks:

- show farmland in green
- show built-up in red or orange
- keep the user polygon visible
- add legend
- allow layer toggles

Recommended colors:

- farmland: `#22c55e`
- built-up: `#ef4444`
- selected polygon boundary: `#2563eb`

Success condition:

- user sees the result exactly over the selected area

## Step 8. Add Overlay Controls

Now add map controls for usability.

Required controls:

- show/hide farmland
- show/hide built-up
- opacity slider
- clear results
- clear polygon
- fit map to result bounds

Optional controls:

- area statistics
- download GeoJSON
- export screenshot

Success condition:

- the user can inspect results without redrawing everything

## Step 9. Show Analysis Stats

The sidebar should show useful numbers for the selected polygon.

Example stats:

- polygon area
- farmland area
- built-up area
- farmland percentage
- built-up percentage
- timestamp of last analysis

Example response from backend:

```json
{
  "stats": {
    "selectedAreaSqKm": 12.8,
    "farmlandSqKm": 7.1,
    "builtupSqKm": 2.3,
    "farmlandPercent": 55.5,
    "builtupPercent": 18.0
  }
}
```

## Step 10. Add Error and Edge Case Handling

Handle these cases clearly:

1. user draws no polygon
2. polygon is too small
3. polygon is too large
4. polygon goes outside supported raster coverage
5. backend processing fails
6. no farmland/built-up detected

Recommended UI messages:

- `Please draw a polygon first.`
- `Selected area is too large. Please choose a smaller region.`
- `No supported imagery found for this area.`
- `Analysis completed, but no farmland or built-up region was detected.`

---

## 6. Recommended React File Structure

```text
src/
  pages/
    FarmlandMapPage.tsx
  components/
    map/
      WestBengalMap.tsx
      BaseLayerSwitcher.tsx
      PolygonDrawControl.tsx
      AnalysisOverlay.tsx
      ResultLegend.tsx
    sidebar/
      SelectionPanel.tsx
      AnalysisStats.tsx
      OverlayControls.tsx
  hooks/
    useMapLayers.ts
    usePolygonSelection.ts
    useAnalyzeArea.ts
  services/
    farmlandApi.ts
  types/
    map.ts
    farmland.ts
  config/
    mapLayers.ts
```

---

## 7. Recommended Frontend State Model

```ts
type MapViewMode = "normal" | "satellite";

type AnalysisResult = {
  farmlandGeoJson?: GeoJSON.FeatureCollection;
  builtupGeoJson?: GeoJSON.FeatureCollection;
  farmlandOverlayUrl?: string;
  builtupOverlayUrl?: string;
  bounds?: [[number, number], [number, number]];
  stats?: {
    selectedAreaSqKm: number;
    farmlandSqKm: number;
    builtupSqKm: number;
    farmlandPercent: number;
    builtupPercent: number;
  };
};
```

Recommended page state:

- `mapViewMode`
- `selectedPolygon`
- `isAnalyzing`
- `analysisResult`
- `showFarmland`
- `showBuiltup`
- `overlayOpacity`
- `error`

---

## 8. Backend Work Expected By the Frontend

The frontend alone cannot detect farmland or built-up. The backend must do these steps:

1. receive the polygon
2. clip the West Bengal raster or imagery to that polygon
3. run inference on the clipped area
4. generate farmland and built-up outputs
5. return either:
   - `GeoJSON`, or
   - `overlay image + bounds`
6. return stats

So the frontend contract should assume this backend API:

- `POST /farmland/analyze-area`
- `GET /farmland/analysis/{jobId}` if async processing is needed

If inference is slow, use async jobs instead of a long blocking request.

---

## 9. Suggested Implementation Order

This is the safest order to build the feature.

### Phase 1. Map Foundation

1. create full-screen Leaflet map
2. center it on West Bengal
3. add normal and satellite base layers
4. add layer switcher

### Phase 2. User Selection

5. add polygon drawing
6. keep only one polygon active
7. convert the polygon to GeoJSON
8. show polygon info in sidebar

### Phase 3. Analysis Trigger

9. add analyze button
10. send polygon to backend
11. show loading and error states

### Phase 4. Visualization

12. render farmland overlay
13. render built-up overlay
14. add legend and toggles
15. add opacity controls

### Phase 5. Polishing

16. show area statistics
17. add clear/reset controls
18. add export options
19. improve mobile responsiveness

---

## 10. Important Design Decisions

### Decision 1. Keep the Base Map Separate from Analysis Overlays

Do not merge farmland or built-up into the base layer.

Use:

- one base map layer
- separate result layers above it

This makes toggling and debugging much easier.

### Decision 2. Start With One Polygon Only

Do not support multiple polygons in version 1.

One polygon is easier for:

- UX
- validation
- backend clipping
- result rendering

### Decision 3. Use the Drawn Polygon Only as Input

The polygon is just the user-selected analysis area.

It is not the farmland output.

The farmland and built-up overlays should come from the model result, not from the user polygon itself.

### Decision 4. Prefer Overlay Rendering on the Map

Do not show results only in side images.

Since your goal is spatial inspection on West Bengal, the result should stay on the same map where the polygon was drawn.

---

## 11. What the First Working Version Should Include

Your first usable version should support exactly this:

1. open West Bengal map
2. switch between normal and satellite base maps
3. draw one polygon
4. click analyze
5. receive farmland and built-up outputs
6. display them as overlays
7. toggle each overlay on/off
8. clear polygon and analyze again

That is enough for the first end-to-end demo.

---

## 12. Practical Recommendation

Build this feature in two layers:

### Frontend layer

Responsible for:

- West Bengal map
- base map switching
- polygon drawing
- sending polygon to backend
- showing overlays
- legend and controls

### Backend layer

Responsible for:

- clipping the selected area
- inference
- farmland and built-up generation
- returning overlay data

This separation is important because the frontend should not try to do raster analysis itself.

---

## 13. Final Build Plan

If we convert this into action items, the build plan is:

1. create `frontend.md`
2. create React map page for West Bengal
3. add normal and satellite base layers
4. add polygon draw and edit
5. convert polygon to GeoJSON
6. connect `Analyze` button to backend
7. return farmland and built-up overlays
8. draw overlays on the same map
9. add legend, toggles, opacity, and stats
10. polish UX and validation

---

## 14. Reference Notes

Helpful implementation references:

- React Leaflet installation: https://react-leaflet.js.org/docs/start-installation/
- Leaflet quick start: https://leafletjs.com/examples/quick-start/
- Leaflet.draw docs: https://leaflet.github.io/Leaflet.draw/docs/leaflet-draw-latest.html
- OpenStreetMap tile usage policy: https://operations.osmfoundation.org/policies/tiles/
- Esri tiled imagery layer docs: https://developers.arcgis.com/documentation/portal-and-data-services/data-services/image-services/display-a-tiled-imagery-layer/

Notes:

- keep attribution visible for all map providers
- avoid depending on community tile servers for heavy production use without checking provider policy
- do not add offline tile prefetching by default
