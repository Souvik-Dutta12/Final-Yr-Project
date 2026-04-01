import { MapContainer, TileLayer, Marker, useMapEvents } from "react-leaflet"
import { useState } from "react"

function LocationMarker({ setLocation }) {
  const [pos, setPos] = useState(null)

  useMapEvents({
    click(e) {
      setPos(e.latlng)
      setLocation(e.latlng)
    },
  })

  return pos && <Marker position={pos} />
}

function MapSection({ setLocation }) {
  return (
    <div className="bg-gradient-to-tr from-blue-600 to-green-600 rounded-xl shadow-lg p-4">
      <h2 className="text-lg font-semibold mb-2">📍 Select Location</h2>
      <MapContainer
        center={[22.57, 88.36]}
        zoom={5}
        className="h-96 w-full rounded-lg"
      >
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <LocationMarker setLocation={setLocation} />
      </MapContainer>
    </div>
  )
}

export default MapSection
