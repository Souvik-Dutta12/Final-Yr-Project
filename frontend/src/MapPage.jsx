import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet-draw'


let polyCount = 0

function formatArea(m) {
  if (m >= 1e6) return (m / 1e6).toFixed(2) + ' km²'
  if (m >= 1e4) return (m / 1e4).toFixed(2) + ' ha'
  return m.toFixed(0) + ' m²'
}

export default function MapPage() {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const drawControlRef = useRef(null)
  const drawnItems = useRef(null)
  const layerMap = useRef(new Map())
  const modeRef = useRef('click')

  const [mode, setMode] = useState('click')
  const [polygons, setPolygons] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)

  // Sync modeRef
  useEffect(() => { modeRef.current = mode }, [mode])

  // Init map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    drawnItems.current = new L.FeatureGroup()

    const map = L.map(containerRef.current, { center: [23.0, 87.5], zoom: 7 })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors', maxZoom: 19
    }).addTo(map)

    map.whenReady(() => setLoading(false))

    // WB border
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


    drawnItems.current.addTo(map)

    const dc = new L.Control.Draw({
      edit: { featureGroup: drawnItems.current, remove: true },
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
      const icon = L.divIcon({
        html: `<div style="background:#2563eb;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.3);color:white;font-size:13px">📍</div>`,
        iconSize: [26, 26], iconAnchor: [13, 26], className: ''
      })
      L.marker([lat, lng], { icon }).addTo(map)
        .bindPopup(`<b>Clicked</b><br/>Lat: ${lat.toFixed(5)}<br/>Lng: ${lng.toFixed(5)}`).openPopup()
    })

    map.on(L.Draw.Event.CREATED, event => {
      const layer = event.layer
      drawnItems.current.addLayer(layer)
      const raw = layer.getLatLngs()
      const ring = Array.isArray(raw[0]) ? raw[0] : raw
      const coords = ring.map(ll => [ll.lat, ll.lng])
      const area = ring.length > 0 ? L.GeometryUtil.geodesicArea(ring) : 0
      polyCount++
      const id = `poly-${Date.now()}`
      const name = `Polygon ${polyCount}`
      layerMap.current.set(id, layer)
      layer.bindPopup(`<b>${name}</b><br/>${coords.length} pts · ${formatArea(area)}`)
      layer.on('click', () => setSelectedId(id))
      setPolygons(prev => [...prev, { id, name, coordinates: coords, area }])
    })

    return () => { map.remove(); mapRef.current = null }
  }, [])

  // Toggle draw control
  useEffect(() => {
    const map = mapRef.current
    const dc = drawControlRef.current
    if (!map || !dc) return
    if (mode === 'draw') {
      dc.addTo(map)
      map.getContainer().style.cursor = 'crosshair'
    } else {
      dc.remove()
      map.getContainer().style.cursor = ''
    }
  }, [mode])

  // Highlight selected
  useEffect(() => {
    layerMap.current.forEach((layer, id) => {
      layer.setStyle(id === selectedId
        ? { color:'#dc2626', fillColor:'#ef4444', fillOpacity:0.3, weight:3 }
        : { color:'#2563eb', fillColor:'#3b82f6', fillOpacity:0.25, weight:2 })
    })
  }, [selectedId])

  // Sync deleted polygons
  useEffect(() => {
    const ids = new Set(polygons.map(p => p.id))
    layerMap.current.forEach((layer, id) => {
      if (!ids.has(id)) { drawnItems.current.removeLayer(layer); layerMap.current.delete(id) }
    })
  }, [polygons])

  const totalArea = polygons.reduce((s, p) => s + p.area, 0)
  const selected = polygons.find(p => p.id === selectedId)

  return (
    <div 
    className='flex flex-col h-screen overflow-hidden bg-[#f8fafc]'
    // style={{ display:'flex', flexDirection:'column', height:'100vh', overflow:'hidden', fontFamily:'system-ui,sans-serif', background:'#f8fafc' }}
    >

      {/* Navbar */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 20px', background:'#fff', borderBottom:'1px solid #e2e8f0', flexShrink:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <div style={{ width:34, height:34, borderRadius:8, background:'#2563eb', display:'flex', alignItems:'center', justifyContent:'center', color:'#fff', fontSize:17 }}>📍</div>
          <div>
            <div style={{ fontWeight:700, fontSize:15, color:'#0f172a' }}>West Bengal Map</div>
            <div style={{ fontSize:11, color:'#64748b' }}>Polygon Drawing Dashboard</div>
          </div>
        </div>
        <div style={{ display:'flex', background:'#f1f5f9', borderRadius:10, padding:4, gap:4 }}>
          {['click','draw'].map(m => (
            <button key={m} onClick={() => setMode(m)} style={{
              padding:'7px 18px', fontSize:13, fontWeight:500, borderRadius:7, cursor:'pointer',
              border: mode===m ? '1px solid #e2e8f0' : '1px solid transparent',
              background: mode===m ? '#fff' : 'transparent',
              color: mode===m ? '#2563eb' : '#64748b',
              boxShadow: mode===m ? '0 1px 3px rgba(0,0,0,.08)' : 'none',
            }}>
              {m==='click' ? '👆 Click' : '✏️ Draw'}
            </button>
          ))}
        </div>
      </div>

      {/* Info cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:10, padding:'10px 14px', background:'#f8fafc', borderBottom:'1px solid #e2e8f0', flexShrink:0 }}>
        {[
          { label:'Polygons', val: polygons.length, icon:'⬡', color:'#2563eb', bg:'#eff6ff' },
          { label:'Total Area', val: polygons.length ? formatArea(totalArea) : '—', icon:'⊞', color:'#16a34a', bg:'#f0fdf4' },
          { label:'Avg Points', val: polygons.length ? Math.round(polygons.reduce((s,p)=>s+p.coordinates.length,0)/polygons.length) : '—', icon:'◎', color:'#7c3aed', bg:'#f5f3ff' },
          { label:'Selected', val: selected ? selected.name : 'None', icon:'📌', color:'#ea580c', bg:'#fff7ed' },
        ].map(c => (
          <div key={c.label} style={{ background:'#fff', borderRadius:10, border:'1px solid #e2e8f0', padding:'10px 12px', display:'flex', alignItems:'center', gap:10 }}>
            <div style={{ width:34, height:34, borderRadius:8, background:c.bg, display:'flex', alignItems:'center', justifyContent:'center', color:c.color, fontSize:15, flexShrink:0 }}>{c.icon}</div>
            <div>
              <div style={{ fontSize:11, color:'#64748b', fontWeight:500 }}>{c.label}</div>
              <div style={{ fontSize:c.label==='Selected'?13:19, fontWeight:700, color:'#0f172a', lineHeight:1.2, maxWidth:80, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{String(c.val)}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Map + Sidebar */}
      <div style={{ display:'flex', flex:1, overflow:'hidden', minHeight:0 }}>
        {/* Map */}
        <div style={{ flex:1, position:'relative', minHeight:0, minWidth:0 }}>
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

        {/* Sidebar */}
        <div style={{ width:270, background:'#fff', borderLeft:'1px solid #e2e8f0', display:'flex', flexDirection:'column', overflow:'hidden', flexShrink:0 }}>
          <div style={{ padding:'12px 14px', borderBottom:'1px solid #e2e8f0', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
            <div>
              <div style={{ fontSize:13, fontWeight:600, color:'#0f172a' }}>Drawn Polygons</div>
              <div style={{ fontSize:11, color:'#94a3b8', marginTop:1 }}>{polygons.length===0 ? 'None yet' : `${polygons.length} polygon${polygons.length>1?'s':''}`}</div>
            </div>
            {polygons.length > 0 && <button onClick={() => { setPolygons([]); setSelectedId(null) }} style={{ fontSize:11, color:'#ef4444', background:'none', border:'none', cursor:'pointer', fontWeight:500 }}>Clear all</button>}
          </div>
          <div style={{ flex:1, overflowY:'auto' }}>
            {polygons.length === 0 ? (
              <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:160, textAlign:'center', gap:8, padding:'0 20px' }}>
                <div style={{ fontSize:28 }}>🗺️</div>
                <div style={{ fontSize:12, color:'#94a3b8' }}>Switch to <b style={{ color:'#2563eb' }}>Draw</b> mode and draw on the map</div>
              </div>
            ) : polygons.map((p, i) => (
              <div key={p.id} onClick={() => setSelectedId(p.id)} style={{ padding:'10px 14px', cursor:'pointer', borderLeft: selectedId===p.id ? '3px solid #2563eb' : '3px solid transparent', background: selectedId===p.id ? '#eff6ff' : '#fff', borderBottom:'1px solid #f1f5f9' }}>
                <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <div style={{ width:26, height:26, borderRadius:7, background: selectedId===p.id?'#2563eb':'#f1f5f9', color: selectedId===p.id?'#fff':'#64748b', display:'flex', alignItems:'center', justifyContent:'center', fontSize:12, fontWeight:700, flexShrink:0 }}>{i+1}</div>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:13, fontWeight:600, color:'#0f172a' }}>{p.name}</div>
                    <div style={{ fontSize:11, color:'#94a3b8' }}>{p.coordinates.length} pts · {formatArea(p.area)}</div>
                  </div>
                  <button onClick={e => { e.stopPropagation(); setPolygons(prev => prev.filter(x => x.id !== p.id)); if(selectedId===p.id) setSelectedId(null) }} style={{ background:'none', border:'none', cursor:'pointer', color:'#94a3b8', fontSize:14 }}>🗑️</button>
                </div>
                {selectedId===p.id && <div style={{ marginTop:5, marginLeft:34, fontSize:11, color:'#64748b' }}>
                  Area: <b style={{ color:'#2563eb' }}>{formatArea(p.area)}</b>
                </div>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}