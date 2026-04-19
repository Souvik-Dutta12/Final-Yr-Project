const BASE_URL = import.meta.env.VITE_BASE_URL || '';


export async function getSoilByPoint(lat, lon) {
  const res = await fetch(`${BASE_URL}/soil/?lat=${lat}&lon=${lon}`);  // /soil/ not /soil/point
  if (!res.ok) throw new Error("Soil fetch failed");
  return res.json();
}

export async function getSoilByPolygon(coordinates) {
  const ring = coordinates.map(c => [c[1], c[0]])
  const closed = (ring[0][0] !== ring[ring.length-1][0] || ring[0][1] !== ring[ring.length-1][1])
    ? [...ring, ring[0]]
    : ring

  const res = await fetch(`${BASE_URL}/soil/polygon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ polygon: { type: "Polygon", coordinates: [closed] } }),
  });
  if (!res.ok) throw new Error("Soil polygon fetch failed");
  return res.json();
}

export async function analyseFarmland(coordinates) {
  const ring = coordinates.map(c => [c[1], c[0]])
  // GeoJSON polygon must be closed (first point = last point)
  const closed = (ring[0][0] !== ring[ring.length-1][0] || ring[0][1] !== ring[ring.length-1][1])
    ? [...ring, ring[0]]
    : ring

  const res = await fetch(`${BASE_URL}/farmland/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ polygon: { type: "Polygon", coordinates: [closed] } }),
  });
  if (!res.ok) throw new Error("Farmland analyse failed");
  // return res.json();
  const data = await res.json();
  return data;
}