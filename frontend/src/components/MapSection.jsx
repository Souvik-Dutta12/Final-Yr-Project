import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet-draw'

const WB_CITIES = [
  { name: 'Kolkata', lat: 22.5726, lng: 88.3639, info: 'Capital of West Bengal' },
  { name: 'Darjeeling', lat: 27.041, lng: 88.2663, info: 'Famous hill station' },
  { name: 'Siliguri', lat: 26.7271, lng: 88.3953, info: 'Gateway to North East' },
  { name: 'Asansol', lat: 23.6833, lng: 86.9667, info: 'Second largest city' },
  { name: 'Durgapur', lat: 23.5204, lng: 87.3119, info: 'Industrial steel hub' },
  { name: 'Bankura', lat: 23.23, lng: 87.07, info: 'Bishnupur temples' },
  { name: 'Murshidabad', lat: 24.18, lng: 88.27, info: 'Nawab capital' },
  { name: 'Malda', lat: 25.0108, lng: 88.1438, info: 'Mango cultivation' },
  { name: 'Howrah', lat: 22.5958, lng: 88.2636, info: 'Twin city of Kolkata' },
  { name: 'Jalpaiguri', lat: 26.5175, lng: 88.7273, info: 'Dooars gateway' },
]

let polyCount = 0

function formatArea(m) {
  if (m >= 1e6) return (m / 1e6).toFixed(2) + ' km²'
  if (m >= 1e4) return (m / 1e4).toFixed(2) + ' ha'
  return m.toFixed(0) + ' m²'
}

export default function MapSection({ mode = 'click', polygons = [], selectedPolygonId = null, onPolygonCreated, onPolygonSelect }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const drawControlRef = useRef(null)
  const drawnItemsRef = useRef(new L.FeatureGroup())
  const layerMapRef = useRef(new Map())
  const clickMarkerRef = useRef(null)
  const modeRef = useRef(mode)
  const [loading, setLoading] = useState(true)

  useEffect(() => { modeRef.current = mode }, [mode])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = L.map(containerRef.current, { center: [23.0, 87.5], zoom: 7 })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors', maxZoom: 19
    }).addTo(map)

    map.whenReady(() => setLoading(false))

    L.geoJSON({
      type: 'Feature', properties: {},
      geometry: {
        type: 'Polygon',
        coordinates: [[[85.8,21.5],[88.0,21.3],[89.1,21.8],[89.9,22.5],[89.8,23.8],
          [89.2,24.8],[88.6,25.0],[87.9,26.4],[88.8,26.7],[88.9,27.3],[88.6,27.7],
          [87.1,27.8],[86.5,27.2],[86.2,26.5],[86.5,25.8],[86.2,25.2],[86.0,24.5],
          [85.8,23.5],[85.8,22.5],[85.8,21.5]]]
      }
    }, { style: { color:'#2563eb', weight:2.5, opacity:0.5, fillColor:'#3b82f6', fillOpacity:0.06, dashArray:'6 4' } }).addTo(map)

    WB_CITIES.forEach(city => {
      const m = L.circleMarker([city.lat, city.lng], {
        radius: 5, fillColor: '#1d4ed8', color: '#fff', weight: 1.5, fillOpacity: 0.9
      }).addTo(map)
      m.bindTooltip(city.name, { direction: 'top' })
      m.bindPopup(`<b>${city.name}</b><br/><small>${city.info}</small>`)
    })

    drawnItemsRef.current.addTo(map)

    const dc = new L.Control.Draw({
      edit: { featureGroup: drawnItemsRef.current, remove: true },
      draw: {
        polygon: { allowIntersection: false, showArea: false, shapeOptions: { color:'#2563eb', fillColor:'#3b82f6', fillOpacity:0.25, weight:2 } },
        polyline: false, rectangle: false, circle: false, marker: false, circlemarker: false
      }
    })
    drawControlRef.current = dc
    mapRef.current = map

    map.on('click', e => {
      if (modeRef.current !== 'click') return
      const { lat, lng } = e.latlng

      if (clickMarkerRef.current) {
        map.removeLayer(clickMarkerRef.current)
        clickMarkerRef.current = null
      }

      const icon = L.divIcon({
        html: `<div style="background:#2563eb;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.3);color:white;font-size:13px">📍</div>`,
        iconSize: [26, 26], iconAnchor: [13, 26], className: ''
      })

      const marker = L.marker([lat, lng], { icon }).addTo(map)
      clickMarkerRef.current = marker

      marker.bindPopup(
        `<div style="min-width:180px">
          <b>📍 Fetching location…</b><br/>
          <small style="color:#6b7280;font-family:monospace">${lat.toFixed(5)}, ${lng.toFixed(5)}</small>
        </div>`
      ).openPopup()

      fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&accept-language=en`)
        .then(r => r.json())
        .then(data => {
          if (!clickMarkerRef.current) return
          const addr = data.address || {}
          const place = addr.village || addr.suburb || addr.town || addr.city || addr.county || addr.state || 'Unknown area'
          const district = addr.county || addr.state_district || ''
          const state = addr.state || ''
          marker.setPopupContent(
            `<div style="min-width:185px">
              <b style="font-size:14px;color:#0f172a">${place}</b><br/>
              ${district ? `<span style="font-size:12px;color:#4b5563">📍 ${district}${state ? ', ' + state : ''}</span><br/>` : ''}
              <hr style="margin:5px 0;border:none;border-top:1px solid #e5e7eb"/>
              <small style="font-family:monospace;color:#9ca3af">${lat.toFixed(5)}, ${lng.toFixed(5)}</small>
            </div>`
          )
          marker.openPopup()
        })
        .catch(() => {
          marker.setPopupContent(
            `<div style="min-width:160px">
              <b>Clicked Location</b><br/>
              <small style="font-family:monospace;color:#6b7280">${lat.toFixed(5)}, ${lng.toFixed(5)}</small>
            </div>`
          )
        })
    })

    map.on(L.Draw.Event.CREATED, event => {
      const layer = event.layer
      drawnItemsRef.current.addLayer(layer)
      const raw = layer.getLatLngs()
      const ring = Array.isArray(raw[0]) ? raw[0] : raw
      const coords = ring.map(ll => [ll.lat, ll.lng])
      const area = ring.length > 0 ? L.GeometryUtil.geodesicArea(ring) : 0
      polyCount++
      const id = `poly-${Date.now()}-${polyCount}`
      const name = `Polygon ${polyCount}`
      layerMapRef.current.set(id, layer)
      layer.bindPopup(`<b>${name}</b><br/>${coords.length} pts · ${formatArea(area)}`)
      layer.on('click', () => { if (onPolygonSelect) onPolygonSelect(id) })
      if (onPolygonCreated) onPolygonCreated({ id, name, coordinates: coords, area })
    })

    return () => { map.remove(); mapRef.current = null }
  }, [])

  // Toggle draw control — cancel active drawing when switching to click
  useEffect(() => {
    const map = mapRef.current
    const dc = drawControlRef.current
    if (!map || !dc) return
    if (mode === 'draw') {
      dc.addTo(map)
      map.getContainer().style.cursor = 'crosshair'
      if (clickMarkerRef.current) {
        map.removeLayer(clickMarkerRef.current)
        clickMarkerRef.current = null
      }
    } else {
      document.dispatchEvent(
        new KeyboardEvent('keydown', { keyCode: 27, key: 'Escape', bubbles: true })
      )
      dc.remove()
      map.getContainer().style.cursor = ''
    }
  }, [mode])

  useEffect(() => {
    layerMapRef.current.forEach((layer, id) => {
      layer.setStyle(id === selectedPolygonId
        ? { color:'#dc2626', fillColor:'#ef4444', fillOpacity:0.3, weight:3 }
        : { color:'#2563eb', fillColor:'#3b82f6', fillOpacity:0.25, weight:2 })
    })
  }, [selectedPolygonId])

  useEffect(() => {
    const ids = new Set(polygons.map(p => p.id))
    layerMapRef.current.forEach((layer, id) => {
      if (!ids.has(id)) { drawnItemsRef.current.removeLayer(layer); layerMapRef.current.delete(id) }
    })
  }, [polygons])

  return (
    <div style={{ position:'relative', width:'100%', height:'100%' }}>
      {loading && (
        <div style={{ position:'absolute', inset:0, background:'rgba(255,255,255,.85)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:999, flexDirection:'column', gap:10 }}>
          <div style={{ width:32, height:32, border:'3px solid #e2e8f0', borderTop:'3px solid #2563eb', borderRadius:'50%', animation:'spin .8s linear infinite' }} />
          <div style={{ fontSize:12, color:'#64748b' }}>Loading map…</div>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      )}
      <div style={{ position:'absolute', top:12, left:'50%', transform:'translateX(-50%)', zIndex:1000, padding:'5px 14px', borderRadius:999, fontSize:12, fontWeight:600, whiteSpace:'nowrap', background:mode==='draw'?'#2563eb':'#fff', color:mode==='draw'?'#fff':'#374151', border:mode==='draw'?'none':'1px solid #e2e8f0', boxShadow:'0 2px 8px rgba(0,0,0,.1)' }}>
        {mode==='draw' ? '✏️ Click to place points, double-click to finish' : '👆 Click anywhere on the map to inspect'}
      </div>
      <div ref={containerRef} style={{ width:'100%', height:'100%' }} />
    </div>
  )
}