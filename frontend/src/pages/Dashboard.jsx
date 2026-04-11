import { useState } from 'react'
import Navbar from '../components/Navbar'        // ← your existing Navbar stays
import MapSection from '../components/MapSection'
import InfoCards from '../components/InfoCards'
import ResultPanel from '../components/ResultPanel'

export default function Dashboard() {
  const [mode, setMode] = useState('click')
  const [polygons, setPolygons] = useState([])
  const [selectedId, setSelectedId] = useState(null)

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100vh', overflow:'hidden' }}>

      {/* Your existing Navbar */}
      <Navbar />

      {/* Mode toggle bar */}
      <div style={{ display:'flex', alignItems:'center', gap:8, padding:'8px 16px', background:'#fff', borderBottom:'1px solid #e2e8f0', flexShrink:0 }}>
        <span style={{ fontSize:12, color:'#64748b', marginRight:4 }}>Map Mode:</span>
        {['click','draw'].map(m => (
          <button key={m} onClick={() => setMode(m)} style={{
            padding:'6px 16px', fontSize:13, fontWeight:500, borderRadius:8, cursor:'pointer',
            background: mode===m ? '#2563eb' : '#f1f5f9',
            color: mode===m ? '#fff' : '#64748b',
            border: 'none',
          }}>
            {m === 'click' ? '👆 Click' : '✏️ Draw'}
          </button>
        ))}
      </div>

      {/* Info cards */}
      <InfoCards polygons={polygons} selectedPolygonId={selectedId} />

      {/* Map + Sidebar */}
      <div style={{ display:'flex', flex:1, overflow:'hidden', minHeight:0 }}>
        <div style={{ flex:1, position:'relative', minHeight:0, minWidth:0 }}>
          <MapSection
            mode={mode}
            polygons={polygons}
            selectedPolygonId={selectedId}
            onPolygonCreated={p => setPolygons(prev => [...prev, p])}
            onPolygonSelect={setSelectedId}
          />
        </div>
        <ResultPanel
          polygons={polygons}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onDelete={id => { setPolygons(prev => prev.filter(p => p.id !== id)); if(selectedId===id) setSelectedId(null) }}
          onClearAll={() => { setPolygons([]); setSelectedId(null) }}
        />
      </div>
    </div>
  )
}