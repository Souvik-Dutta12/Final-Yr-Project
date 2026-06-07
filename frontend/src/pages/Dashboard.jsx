import { useState, useCallback } from 'react'
import Navbar from '../components/Navbar'
import MapSection from '../components/MapSection'
import InfoCards from '../components/InfoCards'
import ResultPanel from '../components/ResultPanel'
import { PanelRightOpen } from 'lucide-react'
import { Tooltip } from '../components/Tooltip'

export default function Dashboard() {
  const [polygons, setPolygons] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [isOpen, setIsOpen] = useState(false);

  const handlePolygonCreated = useCallback((poly) => {
    setPolygons(prev => {
      const exists = prev.find(p => p.id === poly.id)

      // Crop update: only update cropRecommendations + weather, keep rest intact
      if (poly._cropUpdate && exists) {
        return prev.map(p => p.id === poly.id
          ? { ...p, cropRecommendations: poly.cropRecommendations, weather: poly.weather }
          : p
        )
      }

      if (exists) return prev.map(p => p.id === poly.id ? { ...p, ...poly } : p)
      return [...prev, poly]
    })
  }, [])

  return (
    <div className="flex flex-col h-screen p-3 overflow-hidden bg-gradient-to-t from-gray-100 to-gray-50">

      <Navbar />
      <div className="min-h-[92vh] w-full py-2 flex gap-3 overflow-hidden">
        <div className="left flex-1 left bg-white rounded-md border shadow-md border-neutral-300">
          <MapSection
            polygons={polygons}
            selectedPolygonId={selectedId}
            onPolygonCreated={handlePolygonCreated}
            onPolygonSelect={setSelectedId}
          />
        </div>
        <Tooltip content={isOpen ? "Collapse sidebar" : "Expand sidebar"} position="bottom">
          <button
            onClick={() => setIsOpen(o => !o)}
            className="self-start p-2 bg-white border border-neutral-300 rounded-md text-white cursor-pointer flex-shrink-0"
            title={isOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            <PanelRightOpen isOpen={isOpen} className='text-neutral-500' />

          </button>
        </Tooltip>
        <div
          style={{ width: isOpen ? "300px" : "0px", transition: "width 0.3s ease" }}
          className="min-w-0 overflow-hidden flex-shrink-0 flex "
        >

          <div className="w-[300px] right overflow-y-scroll bg-white rounded-md shadow-md border h-full border-neutral-300 whitespace-nowrap">

            <ResultPanel
              polygons={polygons}
              selectedId={selectedId}
              onSelect={(id) => setSelectedId(prev => prev === id ? null : id)}
              onDelete={id => {
                setPolygons(prev => prev.filter(p => p.id !== id))
                if (selectedId === id) setSelectedId(null)
              }}
              onClearAll={() => { setPolygons([]); setSelectedId(null) }}
            />
          </div>
        </div>
      </div>









      {/* <Navbar  mode={mode} onModeChange={setMode} />
      <InfoCards polygons={polygons} selectedId={selectedId} />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', minHeight: 0 }}>
        <div style={{ flex: 1, position: 'relative', minHeight: 0, minWidth: 0 }}>
          
        </div>
        
      </div> */}
    </div>
  )
}
