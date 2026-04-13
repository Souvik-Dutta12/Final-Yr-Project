import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet-draw'
import { getSoilByPoint, getSoilByPolygon, analyseFarmland } from '../services/api'

const WB_CITIES = [
  { name: 'Kolkata',     lat: 22.5726, lng: 88.3639, info: 'Capital of West Bengal' },
  { name: 'Darjeeling',  lat: 27.041,  lng: 88.2663, info: 'Famous hill station' },
  { name: 'Siliguri',    lat: 26.7271, lng: 88.3953, info: 'Gateway to North East' },
  { name: 'Asansol',     lat: 23.6833, lng: 86.9667, info: 'Second largest city' },
  { name: 'Durgapur',    lat: 23.5204, lng: 87.3119, info: 'Industrial steel hub' },
  { name: 'Bankura',     lat: 23.23,   lng: 87.07,   info: 'Bishnupur temples' },
  { name: 'Murshidabad', lat: 24.18,   lng: 88.27,   info: 'Nawab capital' },
  { name: 'Malda',       lat: 25.0108, lng: 88.1438, info: 'Mango cultivation' },
  { name: 'Howrah',      lat: 22.5958, lng: 88.2636, info: 'Twin city of Kolkata' },
  { name: 'Jalpaiguri',  lat: 26.5175, lng: 88.7273, info: 'Dooars gateway' },
]

let polyCount = 0

function formatArea(m) {
  if (m >= 1e6) return (m / 1e6).toFixed(2) + ' km²'
  if (m >= 1e4) return (m / 1e4).toFixed(2) + ' ha'
  return m.toFixed(0) + ' m²'
}

const LAND_COLORS = {
  farmland: '#22c55e',
  builtup:  '#f97316',
  water:    '#3b82f6',
  unknown:  '#a855f7',
}

const SOIL_COLORS = [
  '#b45309','#d97706','#f59e0b','#84cc16','#10b981',
  '#06b6d4','#6366f1','#ec4899','#ef4444','#8b5cf6',
]

export default function MapSection({
  mode = 'click',
  polygons = [],
  selectedPolygonId = null,
  onPolygonCreated,
  onPolygonSelect,
}) {
  const containerRef      = useRef(null)
  const mapRef            = useRef(null)
  const drawControlRef    = useRef(null)
  const drawnItemsRef     = useRef(new L.FeatureGroup())
  const analysisLayerRef  = useRef(new L.FeatureGroup())
  const layerMapRef       = useRef(new Map())
  const clickMarkerRef    = useRef(null)
  const modeRef           = useRef(mode)
  const normalLayerRef    = useRef(null)
  const satelliteLayerRef = useRef(null)
  const labelLayerRef     = useRef(null)

  const [loading,    setLoading]    = useState(true)
  const [analysing,  setAnalysing]  = useState(false)
  const [mapView,    setMapView]    = useState('normal')

  useEffect(() => { modeRef.current = mode }, [mode])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const WB_BOUNDS = L.latLngBounds(L.latLng(21.3, 85.8), L.latLng(27.8, 89.9))
    const map = L.map(containerRef.current, {
      center: [23.5, 87.8], zoom: 7, minZoom: 7, maxZoom: 18,
      maxBounds: WB_BOUNDS, maxBoundsViscosity: 1.0,
    })
    map.fitBounds(WB_BOUNDS, { padding: [10, 10] })

    const normalLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      { attribution: '© OpenStreetMap contributors', maxZoom: 19 })
    normalLayer.addTo(map)
    normalLayerRef.current = normalLayer

    satelliteLayerRef.current = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { attribution: '© Esri', maxZoom: 19 })

    labelLayerRef.current = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      { attribution: '', maxZoom: 19, pane: 'overlayPane' })

    map.whenReady(() => setLoading(false))

    fetch('/west-bengal.geojson').then(r => r.json()).then(data => {
      const map = mapRef.current; if (!map) return
      let geom
      if (data.type === 'FeatureCollection') geom = data.features[0]?.geometry
      else if (data.type === 'Feature') geom = data.geometry
      else geom = data
      if (!geom) return
      const WORLD = [[-180,-90],[180,-90],[180,90],[-180,90],[-180,-90]]
      const outerRings = geom.type === 'Polygon'
        ? [geom.coordinates[0]]
        : geom.coordinates.map(p => p[0])
      L.geoJSON(
        { type:'Feature', properties:{}, geometry:{ type:'Polygon', coordinates:[WORLD, ...outerRings.map(r=>[...r].reverse())] } },
        { style:{ color:'#0f172a', weight:0, fillColor:'#0f172a', fillOpacity:0.88 }, interactive:false }
      ).addTo(map)
      L.geoJSON(
        { type:'Feature', properties:{}, geometry:geom },
        { style:{ color:'#60a5fa', weight:2.5, opacity:1, fill:false }, interactive:false }
      ).addTo(map)
    }).catch(() => {})

    WB_CITIES.forEach(city => {
      const m = L.circleMarker([city.lat, city.lng], {
        radius:5, fillColor:'#1d4ed8', color:'#fff', weight:1.5, fillOpacity:0.9
      }).addTo(map)
      m.bindTooltip(city.name, { direction:'top' })
      m.bindPopup(`<b>${city.name}</b><br/><small>${city.info}</small>`)
    })

    drawnItemsRef.current.addTo(map)
    analysisLayerRef.current.addTo(map)

    const dc = new L.Control.Draw({
      edit: { featureGroup: drawnItemsRef.current, remove: true },
      draw: {
        polygon: { allowIntersection:false, showArea:false, shapeOptions:{ color:'#2563eb', fillColor:'#3b82f6', fillOpacity:0.25, weight:2 } },
        polyline:false, rectangle:false, circle:false, marker:false, circlemarker:false,
      }
    })
    drawControlRef.current = dc
    mapRef.current = map

    // ── Click to inspect ──
    map.on('click', async e => {
      if (modeRef.current !== 'click') return
      const { lat, lng } = e.latlng
      if (clickMarkerRef.current) { map.removeLayer(clickMarkerRef.current); clickMarkerRef.current = null }

      const icon = L.divIcon({
        html: `<div style="background:#2563eb;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.3);color:white;font-size:13px">📍</div>`,
        iconSize:[26,26], iconAnchor:[13,26], className:''
      })
      const marker = L.marker([lat,lng],{icon}).addTo(map)
      clickMarkerRef.current = marker
      marker.bindPopup(`<div style="min-width:200px"><b>📍 Loading…</b><br/><small style="color:#6b7280;font-family:monospace">${lat.toFixed(5)}, ${lng.toFixed(5)}</small></div>`).openPopup()

      // Parallel: reverse geocode + soil type
      const [geoRes, soilRes] = await Promise.allSettled([
        fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&accept-language=en`).then(r=>r.json()),
        getSoilByPoint(lat, lng)
      ])

      if (!clickMarkerRef.current) return

      const addr   = geoRes.status === 'fulfilled' ? (geoRes.value.address || {}) : {}
      const place  = addr.village || addr.suburb || addr.town || addr.city || addr.county || addr.state || 'Unknown area'
      const dist   = addr.county || addr.state_district || ''
      const state  = addr.state || ''
      const soil   = soilRes.status === 'fulfilled' ? soilRes.value?.data?.soil_type : null

      marker.setPopupContent(`
        <div style="min-width:210px;font-family:system-ui,sans-serif">
          <div style="font-size:14px;font-weight:700;color:#0f172a">${place}</div>
          ${dist ? `<div style="font-size:12px;color:#4b5563;margin-top:2px">📍 ${dist}${state ? ', '+state : ''}</div>` : ''}
          <hr style="margin:8px 0;border:none;border-top:1px solid #e5e7eb"/>
          <div style="display:flex;align-items:center;gap:8px;background:#f0fdf4;border-radius:8px;padding:8px 10px">
            <span style="font-size:20px">🌱</span>
            <div>
              <div style="font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Soil Type</div>
              <div style="font-size:13px;font-weight:700;color:#15803d">${soil || 'Unavailable'}</div>
            </div>
          </div>
          <div style="margin-top:6px;font-size:10px;font-family:monospace;color:#9ca3af">${lat.toFixed(5)}, ${lng.toFixed(5)}</div>
        </div>
      `)
      marker.openPopup()
    })

    // ── Polygon drawn ──
    map.on(L.Draw.Event.CREATED, async event => {
      const layer = event.layer
      drawnItemsRef.current.addLayer(layer)
      const raw   = layer.getLatLngs()
      const ring  = Array.isArray(raw[0]) ? raw[0] : raw
      const coords = ring.map(ll => [ll.lat, ll.lng])
      const area  = ring.length > 0 ? L.GeometryUtil.geodesicArea(ring) : 0
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

      layer.on('click', () => { if (onPolygonSelect) onPolygonSelect(id) })
      if (onPolygonCreated) onPolygonCreated({ id, name, coordinates: coords, area, status: 'loading' })

      setAnalysing(true)

      const [soilRes, farmRes] = await Promise.allSettled([
        getSoilByPolygon(coords),
        analyseFarmland(coords),
      ])

      setAnalysing(false)

      // Draw farmland overlay on map
      if (farmRes.status === 'fulfilled') {
        const fc = farmRes.value?.data
        if (fc?.features) {
          analysisLayerRef.current.clearLayers()
          fc.features.forEach(feat => {
            const label = feat.properties?.label || 'unknown'
            const color = LAND_COLORS[label] || '#888'
            L.geoJSON(feat, {
              style: { color, fillColor: color, fillOpacity: 0.45, weight: 1.5 },
            }).bindTooltip(label.charAt(0).toUpperCase() + label.slice(1), { sticky: true })
              .addTo(analysisLayerRef.current)
          })
        }
      }

      // Build popup
      const soilData = soilRes.status === 'fulfilled' ? soilRes.value?.data : null
      const dist     = soilData?.distribution || []
      const farmData = farmRes.status === 'fulfilled' ? farmRes.value?.data : null
      const features = farmData?.features || []

      // Soil distribution rows
      const soilRows = dist.map((d, i) => `
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <div style="width:10px;height:10px;border-radius:3px;background:${SOIL_COLORS[i % SOIL_COLORS.length]};flex-shrink:0"></div>
          <div style="flex:1;font-size:12px;color:#374151">${d.soil_class}</div>
          <div style="font-size:12px;font-weight:600;color:#0f172a">${d.percentage?.toFixed(1)}%</div>
        </div>
      `).join('')

      // Land use counts
      const landCount = features.reduce((acc, f) => {
        const l = f.properties?.label || 'unknown'
        acc[l] = (acc[l] || 0) + 1
        return acc
      }, {})
      const landRows = Object.entries(landCount).map(([label, count]) => `
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <div style="width:10px;height:10px;border-radius:3px;background:${LAND_COLORS[label]||'#888'};flex-shrink:0"></div>
          <div style="flex:1;font-size:12px;color:#374151;text-transform:capitalize">${label}</div>
          <div style="font-size:11px;color:#64748b">${count} zone${count>1?'s':''}</div>
        </div>
      `).join('')

      layer.setPopupContent(`
        <div style="min-width:240px;max-height:380px;overflow-y:auto;font-family:system-ui,sans-serif">
          <div style="font-size:14px;font-weight:700;color:#0f172a">${name}</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px">${coords.length} pts · ${formatArea(area)}</div>

          <hr style="margin:10px 0;border:none;border-top:1px solid #e5e7eb"/>

          <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">🌱 Soil Distribution</div>
          ${dist.length > 0 ? soilRows : '<div style="font-size:12px;color:#94a3b8">No soil data available</div>'}

          <hr style="margin:10px 0;border:none;border-top:1px solid #e5e7eb"/>

          <div style="font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">🛰️ Land Use</div>
          ${features.length > 0 ? landRows : '<div style="font-size:12px;color:#94a3b8">No land use data available</div>'}
        </div>
      `)
      layer.openPopup()

      if (onPolygonCreated) onPolygonCreated({
        id, name, coordinates: coords, area,
        status: 'done',
        soilDistribution: dist,
        landUse: landCount,
      })
    })

    return () => { map.remove(); mapRef.current = null }
  }, []) // eslint-disable-line

  // Tile layer swap
  useEffect(() => {
    const map=mapRef.current, norm=normalLayerRef.current
    const sat=satelliteLayerRef.current, label=labelLayerRef.current
    if (!map||!norm||!sat||!label) return
    if (mapView==='satellite') {
      if (map.hasLayer(norm))  map.removeLayer(norm)
      if (!map.hasLayer(sat))  { sat.addTo(map); sat.bringToBack() }
      if (!map.hasLayer(label)) label.addTo(map)
    } else {
      if (map.hasLayer(sat))   map.removeLayer(sat)
      if (map.hasLayer(label)) map.removeLayer(label)
      if (!map.hasLayer(norm)) { norm.addTo(map); norm.bringToBack() }
    }
  }, [mapView])

  // Draw control toggle
  useEffect(() => {
    const map=mapRef.current, dc=drawControlRef.current
    if (!map||!dc) return
    if (mode==='draw') {
      dc.addTo(map)
      map.getContainer().style.cursor='crosshair'
      if (clickMarkerRef.current) { map.removeLayer(clickMarkerRef.current); clickMarkerRef.current=null }
    } else {
      document.dispatchEvent(new KeyboardEvent('keydown',{keyCode:27,key:'Escape',bubbles:true}))
      dc.remove()
      map.getContainer().style.cursor=''
    }
  }, [mode])

  // Highlight selected
  useEffect(() => {
    layerMapRef.current.forEach((layer,id) => {
      layer.setStyle(
        id===selectedPolygonId
          ? { color:'#dc2626', fillColor:'#ef4444', fillOpacity:0.3, weight:3 }
          : { color:'#2563eb', fillColor:'#3b82f6', fillOpacity:0.25, weight:2 }
      )
    })
  }, [selectedPolygonId])

  // Sync deleted polygons
  useEffect(() => {
    const ids = new Set(polygons.map(p=>p.id))
    layerMapRef.current.forEach((layer,id) => {
      if (!ids.has(id)) {
        drawnItemsRef.current.removeLayer(layer)
        layerMapRef.current.delete(id)
        analysisLayerRef.current.clearLayers()
      }
    })
  }, [polygons])

  return (
    <div style={{ position:'relative', width:'100%', height:'100%' }}>

      {/* Map loading */}
      {loading && (
        <div style={{ position:'absolute', inset:0, background:'rgba(255,255,255,.85)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:999, flexDirection:'column', gap:10 }}>
          <div style={{ width:32, height:32, border:'3px solid #e2e8f0', borderTop:'3px solid #2563eb', borderRadius:'50%', animation:'spin .8s linear infinite' }} />
          <div style={{ fontSize:12, color:'#64748b' }}>Loading map…</div>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      )}

      {/* Analysis loading banner */}
      {analysing && (
        <div style={{ position:'absolute', bottom:80, left:'50%', transform:'translateX(-50%)', zIndex:1000, background:'#1e293b', color:'#fff', padding:'8px 18px', borderRadius:999, fontSize:12, fontWeight:600, display:'flex', alignItems:'center', gap:8, boxShadow:'0 4px 12px rgba(0,0,0,.25)' }}>
          <div style={{ width:14, height:14, border:'2px solid rgba(255,255,255,.3)', borderTop:'2px solid #fff', borderRadius:'50%', animation:'spin .8s linear infinite' }} />
          Analysing polygon… this may take a moment
        </div>
      )}

      {/* Mode hint */}
      <div style={{ position:'absolute', top:12, left:'50%', transform:'translateX(-50%)', zIndex:1000, padding:'5px 14px', borderRadius:999, fontSize:12, fontWeight:600, whiteSpace:'nowrap', background:mode==='draw'?'#2563eb':'#fff', color:mode==='draw'?'#fff':'#374151', border:mode==='draw'?'none':'1px solid #e2e8f0', boxShadow:'0 2px 8px rgba(0,0,0,.1)' }}>
        {mode==='draw' ? '✏️ Click to place points, double-click to finish' : '👆 Click anywhere on the map to inspect'}
      </div>

      {/* Map/Satellite toggle */}
      <div style={{ position:'absolute', bottom:32, left:12, zIndex:1000, display:'flex', borderRadius:10, overflow:'hidden', boxShadow:'0 2px 10px rgba(0,0,0,.2)', border:'1.5px solid #e2e8f0' }}>
        {[{id:'normal',label:'🗺️ Map'},{id:'satellite',label:'🛰️ Satellite'}].map(v => (
          <button key={v.id} onClick={() => setMapView(v.id)} style={{ padding:'8px 14px', fontSize:12, fontWeight:600, cursor:'pointer', background:mapView===v.id?'#2563eb':'#fff', color:mapView===v.id?'#fff':'#374151', border:'none', transition:'background 0.18s, color 0.18s' }}>
            {v.label}
          </button>
        ))}
      </div>

      <div ref={containerRef} style={{ width:'100%', height:'100%' }} />
    </div>
  )
}