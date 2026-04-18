import { useEffect, useRef, useState } from "react"
import L from "leaflet"
import "leaflet/dist/leaflet.css"
import "leaflet-draw/dist/leaflet.draw.css"
import "leaflet-draw"
import { getSoilByPoint, getSoilByPolygon, analyseFarmland } from "../services/api"

let polyCount = 0

function formatArea(m) {
  if (m >= 1e6) return (m / 1e6).toFixed(2) + " km²"
  if (m >= 1e4) return (m / 1e4).toFixed(2) + " ha"
  return m.toFixed(0) + " m²"
}

const LAND_COLORS = {
  farmland: "#22c55e",
  builtup:  "#ec4899",
  water:    "#3b82f6",
  unknown:  "#a855f7",
}

const SOIL_COLORS = [
  "#b45309", "#d97706", "#f59e0b", "#84cc16", "#10b981",
  "#06b6d4", "#6366f1", "#ec4899", "#ef4444", "#8b5cf6",
]

export default function MapSection({
  mode = "click",
  polygons = [],
  selectedPolygonId = null,
  onPolygonCreated,
  onPolygonSelect,
}) {
  const containerRef      = useRef(null)
  const mapRef            = useRef(null)
  const drawControlRef    = useRef(null)
  const drawnItemsRef     = useRef(new L.FeatureGroup())
  const analysisLayerRef  = useRef(new L.FeatureGroup()) // farmland/water/builtup overlay
  const soilLayerRef      = useRef(new L.FeatureGroup()) // soil type color overlay
  const layerMapRef       = useRef(new Map())            // polygon id → leaflet layer
  const clickMarkerRef    = useRef(null)
  const modeRef           = useRef(mode)
  const normalLayerRef    = useRef(null)
  const satelliteLayerRef = useRef(null)
  const labelLayerRef     = useRef(null)
  const onPolygonCreatedRef = useRef(onPolygonCreated)

   useEffect(() => { onPolygonCreatedRef.current = onPolygonCreated }, [onPolygonCreated])

  const [loading,   setLoading]   = useState(true)
  const [analysing, setAnalysing] = useState(false)
  const [mapView,   setMapView]   = useState("normal")

  // Keep modeRef in sync so map event handlers always see latest mode
  useEffect(() => { modeRef.current = mode }, [mode])

  // ── Map initialisation (runs once) ──────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const WB_BOUNDS = L.latLngBounds(L.latLng(21.3, 85.8), L.latLng(27.8, 89.9))

    const map = L.map(containerRef.current, {
      center: [23.5, 87.8],
      zoom: 7,
      minZoom: 7,
      maxZoom: 18,
      maxBounds: WB_BOUNDS,
      maxBoundsViscosity: 1.0,
    })
    map.fitBounds(WB_BOUNDS, { padding: [10, 10] })

    // Base tile layers
    const normalLayer = L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { attribution: "© OpenStreetMap contributors", maxZoom: 19 },
    )
    normalLayer.addTo(map)
    normalLayerRef.current = normalLayer

    satelliteLayerRef.current = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "© Esri", maxZoom: 19 },
    )

    labelLayerRef.current = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      { attribution: "", maxZoom: 19, pane: "overlayPane" },
    )

    map.whenReady(() => setLoading(false))

    // West Bengal boundary mask from public/west-bengal.geojson
    fetch("/west-bengal.geojson")
      .then((r) => r.json())
      .then((data) => {
        const map = mapRef.current
        if (!map) return

        let geom
        if (data.type === "FeatureCollection") geom = data.features[0]?.geometry
        else if (data.type === "Feature") geom = data.geometry
        else geom = data
        if (!geom) return

        const WORLD = [[-180,-90],[180,-90],[180,90],[-180,90],[-180,-90]]
        const outerRings = geom.type === "Polygon"
          ? [geom.coordinates[0]]
          : geom.coordinates.map((p) => p[0])

        // Dark mask outside WB
        L.geoJSON(
          { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [WORLD, ...outerRings.map((r) => [...r].reverse())] } },
          { style: { color: "#0f172a", weight: 0, fillColor: "#0f172a", fillOpacity: 0.88 }, interactive: false },
        ).addTo(map)

        // WB border line
        L.geoJSON(
          { type: "Feature", properties: {}, geometry: geom },
          { style: { color: "#60a5fa", weight: 2.5, opacity: 1, fill: false }, interactive: false },
        ).addTo(map)
      })
      .catch(() => {})

    drawnItemsRef.current.addTo(map)
    analysisLayerRef.current.addTo(map)
    soilLayerRef.current.addTo(map)

    const dc = new L.Control.Draw({
      edit: { featureGroup: drawnItemsRef.current, remove: true },
      draw: {
        polygon: {
          allowIntersection: false,
          showArea: false,
          shapeOptions: { color: "#2563eb", fillColor: "#3b82f6", fillOpacity: 0.25, weight: 2 },
        },
        polyline: false, rectangle: false, circle: false, marker: false, circlemarker: false,
      },
    })
    drawControlRef.current = dc
    mapRef.current = map

    // ── Click mode: show soil type for a point ──
    map.on("click", async (e) => {
      if (modeRef.current !== "click") return
      const { lat, lng } = e.latlng

      if (clickMarkerRef.current) {
        map.removeLayer(clickMarkerRef.current)
        clickMarkerRef.current = null
      }

      const icon = L.divIcon({
        html: `<div style="background:#2563eb;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.3);color:white;font-size:13px">📍</div>`,
        iconSize: [26, 26], iconAnchor: [13, 26], className: "",
      })

      const marker = L.marker([lat, lng], { icon }).addTo(map)
      clickMarkerRef.current = marker
      marker
        .bindPopup(`<div style="min-width:200px"><b>📍 Loading…</b><br/><small style="color:#6b7280;font-family:monospace">${lat.toFixed(5)}, ${lng.toFixed(5)}</small></div>`)
        .openPopup()

      // Fetch reverse geocode and soil type in parallel
      const [geoRes, soilRes] = await Promise.allSettled([
        fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&accept-language=en`).then((r) => r.json()),
        getSoilByPoint(lat, lng),
      ])

      if (!clickMarkerRef.current) return

      const addr  = geoRes.status === "fulfilled" ? geoRes.value.address || {} : {}
      const place = addr.village || addr.suburb || addr.town || addr.city || addr.county || addr.state || "Unknown area"
      const dist  = addr.county || addr.state_district || ""
      const state = addr.state || ""
      const soil  = soilRes.status === "fulfilled" ? soilRes.value?.data?.soil_type : null

      marker.setPopupContent(`
        <div style="min-width:210px;font-family:system-ui,sans-serif">
          <div style="font-size:14px;font-weight:700;color:#0f172a">${place}</div>
          ${dist ? `<div style="font-size:12px;color:#4b5563;margin-top:2px">📍 ${dist}${state ? ", " + state : ""}</div>` : ""}
          <hr style="margin:8px 0;border:none;border-top:1px solid #e5e7eb"/>
          <div style="display:flex;align-items:center;gap:8px;background:#f0fdf4;border-radius:8px;padding:8px 10px">
            <div>
              <div style="font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Soil Type</div>
              <div style="font-size:13px;font-weight:700;color:#15803d">${soil || "Unavailable"}</div>
            </div>
          </div>
          <div style="margin-top:6px;font-size:10px;font-family:monospace;color:#9ca3af">${lat.toFixed(5)}, ${lng.toFixed(5)}</div>
        </div>
      `)
      marker.openPopup()
    })

    // ── Draw mode: analyse polygon for soil + farmland ──
    map.on(L.Draw.Event.CREATED, async (event) => {
      const layer  = event.layer
      drawnItemsRef.current.addLayer(layer)

      const raw    = layer.getLatLngs()
      const ring   = Array.isArray(raw[0]) ? raw[0] : raw
      const coords = ring.map((ll) => [ll.lat, ll.lng])
      const area   = ring.length > 0 ? L.GeometryUtil.geodesicArea(ring) : 0
      polyCount++
      const id   = `poly-${Date.now()}-${polyCount}`
      const name = `Polygon ${polyCount}`
      layerMapRef.current.set(id, layer)

      layer.bindPopup(`
        <div style="min-width:220px;font-family:system-ui,sans-serif">
          <b>${name}</b> · ${formatArea(area)}<br/>
          <div style="margin-top:8px;display:flex;align-items:center;gap:8px;color:#64748b;font-size:12px">
            <div style="width:16px;height:16px;border:2px solid #2563eb;border-top-color:transparent;border-radius:50%;animation:spin .8s linear infinite"></div>
            Analysing…
          </div>
          <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
        </div>
      `).openPopup()

      layer.on("click", () => { if (onPolygonSelect) onPolygonSelect(id) })
      if (onPolygonCreatedRef.current) onPolygonCreatedRef.current({ id, name, coordinates: coords, area, status: "loading" })

      setAnalysing(true)
      const [soilRes, farmRes] = await Promise.allSettled([
        getSoilByPolygon(coords),
        analyseFarmland(coords),
      ])
      setAnalysing(false)

      const soilData   = soilRes.status === "fulfilled" ? soilRes.value?.data : null
      const farmGeoJson = farmRes.status === "fulfilled" ? farmRes.value?.data : null
      const distrib    = soilData?.distribution || []
      const features   = farmGeoJson?.features || []

      analysisLayerRef.current.clearLayers()
      soilLayerRef.current.clearLayers()

      // Layer 1: Light farmland base fill over the drawn polygon
      L.geoJSON(
        { type: "Feature", geometry: { type: "Polygon", coordinates: [coords.map((c) => [c[1], c[0]])] }, properties: {} },
        { interactive: false, style: { color: LAND_COLORS.farmland, fillColor: LAND_COLORS.farmland, fillOpacity: 0.2, weight: 0, stroke: false } },
      ).addTo(analysisLayerRef.current)

      // Layer 2: Soil type color patches from soil GeoJSON
      if (soilData?.geojson) {
        try {
          const soilGeoJson   = typeof soilData.geojson === "string" ? JSON.parse(soilData.geojson) : soilData.geojson
          const soilColorMap  = Object.fromEntries(distrib.map((d, i) => [d.soil_class, SOIL_COLORS[i % SOIL_COLORS.length]]))

          L.geoJSON(soilGeoJson, {
            interactive: true,
            style: (feature) => {
              const color = soilColorMap[feature.properties?.soil_class] || "#94a3b8"
              return { color, fillColor: color, fillOpacity: 0.9, weight: 1.5, opacity: 1 }
            },
            onEachFeature: (feature, lyr) => {
              const soilClass = feature.properties?.soil_class
              if (!soilClass) return
              const color = soilColorMap[soilClass] || "#94a3b8"
              lyr.bindTooltip(
                `<div style="font-family:system-ui,sans-serif;background:#fff;padding:6px 10px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.15)">
                  <div style="display:flex;align-items:center;gap:7px">
                    <div style="width:12px;height:12px;border-radius:3px;background:${color};flex-shrink:0"></div>
                    <span style="font-size:13px;font-weight:700;color:#0f172a">${soilClass}</span>
                  </div>
                </div>`,
                { sticky: true, permanent: false, direction: "top", opacity: 1 },
              )
              lyr.on("mouseover", function (e) { this.setStyle({ fillOpacity: 0.95, weight: 2.5 }); this.openTooltip(e.latlng) })
              lyr.on("mousemove", function (e) { this.getTooltip()?.setLatLng(e.latlng) })
              lyr.on("mouseout",  function ()  { this.setStyle({ fillOpacity: 0.8, weight: 1.5 }); this.closeTooltip() })
            },
          }).addTo(soilLayerRef.current)
        } catch (e) {
          console.error("Soil GeoJSON parse error:", e)
        }
      }

      // Layer 3: Water and builtup patches from farmland analysis
      if (features.length > 0) {
        const drawnBounds = L.geoJSON({ type: "Feature", geometry: { type: "Polygon", coordinates: [coords.map((c) => [c[1], c[0]])] }, properties: {} }).getBounds()
        features.forEach((feat) => {
          const label = feat.properties?.class || "unknown"
          if (label === "farmland") return // farmland already shown as base fill
          const color = LAND_COLORS[label] || "#888"
          const swapped = feat.geometry?.coordinates?.map((ring) => ring.map((pt) => [pt[1], pt[0]]))
          if (!swapped) return
          if (!drawnBounds.contains(L.polygon(swapped).getBounds().getCenter())) return
          L.polygon(swapped, { color, fillColor: color, fillOpacity: 0.8, weight: 1, stroke: false })
            .bindTooltip(label.charAt(0).toUpperCase() + label.slice(1), { sticky: true })
            .addTo(analysisLayerRef.current)
        })
      }

      // Ensure drawn polygon outline stays on top
      soilLayerRef.current.bringToFront()
      analysisLayerRef.current.bringToFront()
      drawnItemsRef.current.bringToFront()

      // Popup: soil distribution + land use summary
      const soilRows = distrib.map((d, i) => `
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <div style="width:10px;height:10px;border-radius:3px;background:${SOIL_COLORS[i % SOIL_COLORS.length]};flex-shrink:0"></div>
          <div style="flex:1;font-size:12px;color:#374151">${d.soil_class}</div>
          <div style="font-size:12px;font-weight:600;color:#0f172a">${d.percentage?.toFixed(1)}%</div>
        </div>
      `).join("")

      const landCount = features.reduce((acc, f) => {
        const l = f.properties?.class || "unknown"
        acc[l] = (acc[l] || 0) + 1
        return acc
      }, {})

      const landRows = Object.entries(landCount).map(([label, count]) => `
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <div style="width:10px;height:10px;border-radius:3px;background:${LAND_COLORS[label] || "#888"};flex-shrink:0"></div>
          <div style="flex:1;font-size:12px;color:#374151;text-transform:capitalize">${label}</div>
          <div style="font-size:11px;color:#64748b">${count} zone${count > 1 ? "s" : ""}</div>
        </div>
      `).join("")

      layer.setPopupContent(`
        <div style="min-width:240px;max-height:380px;overflow-y:auto;font-family:system-ui,sans-serif">
          <div style="font-size:14px;font-weight:700;color:#0f172a">${name}</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px">${coords.length} pts · ${formatArea(area)}</div>
          <hr style="margin:10px 0;border:none;border-top:1px solid #e5e7eb"/>
          <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">🌱 Soil Distribution</div>
          ${distrib.length > 0 ? soilRows : '<div style="font-size:12px;color:#94a3b8">No soil data available</div>'}
          <hr style="margin:10px 0;border:none;border-top:1px solid #e5e7eb"/>
          <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">🛰️ Land Use</div>
          ${features.length > 0 ? landRows : '<div style="font-size:12px;color:#94a3b8">Draw a larger polygon to detect land use</div>'}
        </div>
      `)
      layer.openPopup()

      if (onPolygonCreatedRef.current) onPolygonCreatedRef.current({ 
        id, name, coordinates: coords, area, status: "done",
        soilDistribution: distrib,
        landUse: landCount,
        soilQualityByClass: soilData?.soil_quality_by_class || [],
        overallQuality: soilData?.overall_weighted_quality || null
      })
    })

    return () => { map.remove(); mapRef.current = null }
  }, []) // eslint-disable-line

  // ── Swap between normal and satellite tiles ──
  useEffect(() => {
    const map   = mapRef.current
    const norm  = normalLayerRef.current
    const sat   = satelliteLayerRef.current
    const label = labelLayerRef.current
    if (!map || !norm || !sat || !label) return

    if (mapView === "satellite") {
      if (map.hasLayer(norm))   map.removeLayer(norm)
      if (!map.hasLayer(sat))  { sat.addTo(map); sat.bringToBack() }
      if (!map.hasLayer(label))  label.addTo(map)
    } else {
      if (map.hasLayer(sat))    map.removeLayer(sat)
      if (map.hasLayer(label))  map.removeLayer(label)
      if (!map.hasLayer(norm)) { norm.addTo(map); norm.bringToBack() }
    }
  }, [mapView])

  // ── Toggle leaflet-draw controls when mode changes ──
  useEffect(() => {
    const map = mapRef.current
    const dc  = drawControlRef.current
    if (!map || !dc) return

    if (mode === "draw") {
      dc.addTo(map)
      map.getContainer().style.cursor = "crosshair"
      if (clickMarkerRef.current) { map.removeLayer(clickMarkerRef.current); clickMarkerRef.current = null }
    } else {
      document.dispatchEvent(new KeyboardEvent("keydown", { keyCode: 27, key: "Escape", bubbles: true }))
      dc.remove()
      map.getContainer().style.cursor = ""
    }
  }, [mode])

  // ── Highlight the selected polygon ──
  useEffect(() => {
    layerMapRef.current.forEach((layer, id) => {
      layer.setStyle(
        id === selectedPolygonId
          ? { color: "#dc2626", fillColor: "#ef4444", fillOpacity: 0.3, weight: 3 }
          : { color: "#2563eb", fillColor: "#3b82f6", fillOpacity: 0.25, weight: 2 },
      )
    })
  }, [selectedPolygonId])

  // ── Remove map layers for polygons deleted from state ──
  useEffect(() => {
    const ids = new Set(polygons.map((p) => p.id))
    layerMapRef.current.forEach((layer, id) => {
      if (!ids.has(id)) {
        drawnItemsRef.current.removeLayer(layer)
        layerMapRef.current.delete(id)
        analysisLayerRef.current.clearLayers()
        soilLayerRef.current.clearLayers()
      }
    })
  }, [polygons])

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>

      {/* Full-screen spinner while map tiles load */}
      {loading && (
        <div style={{ position: "absolute", inset: 0, background: "rgba(255,255,255,.85)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 999, flexDirection: "column", gap: 10 }}>
          <div style={{ width: 32, height: 32, border: "3px solid #e2e8f0", borderTop: "3px solid #2563eb", borderRadius: "50%", animation: "spin .8s linear infinite" }} />
          <div style={{ fontSize: 12, color: "#64748b" }}>Loading map…</div>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      )}

      {/* Banner shown while backend analysis is running */}
      {analysing && (
        <div style={{ position: "absolute", bottom: 80, left: "50%", transform: "translateX(-50%)", zIndex: 1000, background: "#1e293b", color: "#fff", padding: "8px 18px", borderRadius: 999, fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 8, boxShadow: "0 4px 12px rgba(0,0,0,.25)" }}>
          <div style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,.3)", borderTop: "2px solid #fff", borderRadius: "50%", animation: "spin .8s linear infinite" }} />
          Analysing polygon… this may take a moment
        </div>
      )}

      {/* Mode hint pill */}
      <div style={{ position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)", zIndex: 1000, padding: "5px 14px", borderRadius: 999, fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", background: mode === "draw" ? "#2563eb" : "#fff", color: mode === "draw" ? "#fff" : "#374151", border: mode === "draw" ? "none" : "1px solid #e2e8f0", boxShadow: "0 2px 8px rgba(0,0,0,.1)" }}>
        {mode === "draw" ? "✏️ Click to place points, double-click to finish" : "👆 Click anywhere on the map to inspect"}
      </div>

      {/* Map / Satellite toggle */}
      <div style={{ position: "absolute", bottom: 32, left: 12, zIndex: 1000, display: "flex", borderRadius: 10, overflow: "hidden", boxShadow: "0 2px 10px rgba(0,0,0,.2)", border: "1.5px solid #e2e8f0" }}>
        {[{ id: "normal", label: "🗺️ Map" }, { id: "satellite", label: "🛰️ Satellite" }].map((v) => (
          <button key={v.id} onClick={() => setMapView(v.id)} style={{ padding: "8px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", background: mapView === v.id ? "#2563eb" : "#fff", color: mapView === v.id ? "#fff" : "#374151", border: "none", transition: "background 0.18s, color 0.18s" }}>
            {v.label}
          </button>
        ))}
      </div>

      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  )
}