import Dashboard from "./pages/Dashboard"
import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, Marker, useMapEvents } from "react-leaflet";
import { useState } from "react";

function App() {
  return <Dashboard />
}

export default App