const BASE_URL = import.meta.env.VITE_BASE_URL || '';


export async function getSoilByPoint(lat, lon) {
  const res = await fetch(`${BASE_URL}/soil/?lat=${lat}&lon=${lon}`);  // /soil/ not /soil/point
  if (!res.ok) throw new Error("Soil fetch failed");
  return res.json();
}

export async function getSoilByPolygon(coordinates) {
  const res = await fetch(`${BASE_URL}/soil/polygon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ polygon: { type: "Polygon", coordinates: [coordinates.map(c => [c[1], c[0]])] } }),
  });
  if (!res.ok) throw new Error("Soil polygon fetch failed");
  return res.json();
}

export async function analyseFarmland(coordinates) {
  const res = await fetch(`${BASE_URL}/farmland/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ polygon: { type: "Polygon", coordinates: [coordinates.map(c => [c[1], c[0]])] } }),
  });
  if (!res.ok) throw new Error("Farmland analyse failed");
  // return res.json();
  const data = await res.json();
  console.log(' Farmland Response:', JSON.stringify(data, null, 2)); 
  return data;
}