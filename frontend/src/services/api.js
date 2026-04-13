const BASE_URL = "http://localhost:3000/api/v1";

export async function getSoilByPoint(lat, lon) {
  const res = await fetch(`${BASE_URL}/soil/point?lat=${lat}&lon=${lon}`);
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
  return res.json();
}