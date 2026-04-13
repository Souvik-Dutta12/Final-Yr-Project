import { useState, useCallback } from 'react'
import Navbar      from '../components/Navbar'
import MapSection  from '../components/MapSection'
import InfoCards   from '../components/InfoCards'
import ResultPanel from '../components/ResultPanel'

export default function Dashboard() {
  const [mode,       setMode]       = useState('click')
  const [polygons,   setPolygons]   = useState([])
  const [selectedId, setSelectedId] = useState(null)

  // Called twice: once with status:'loading', once with status:'done' + data
  const handlePolygonCreated = useCallback((poly) => {
    setPolygons(prev => {
      const exists = prev.find(p => p.id === poly.id)
      if (exists) return prev.map(p => p.id === poly.id ? { ...p, ...poly } : p)
      return [...prev, poly]
    })
  }, [])

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100vh', overflow:'hidden', fontFamily:'system-ui, sans-serif', background:'#f8fafc' }}>
      <Navbar mode={mode} onModeChange={setMode} />
      <InfoCards polygons={polygons} selectedId={selectedId} />
      <div style={{ display:'flex', flex:1, overflow:'hidden', minHeight:0 }}>
        <div style={{ flex:1, position:'relative', minHeight:0, minWidth:0 }}>
          <MapSection
            mode={mode}
            polygons={polygons}
            selectedPolygonId={selectedId}
            onPolygonCreated={handlePolygonCreated}
            onPolygonSelect={setSelectedId}
          />
        </div>
        <ResultPanel
          polygons={polygons}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onDelete={id => {
            setPolygons(prev => prev.filter(p => p.id !== id))
            if (selectedId === id) setSelectedId(null)
          }}
          onClearAll={() => { setPolygons([]); setSelectedId(null) }}
        />
      </div>
    </div>
  )
}