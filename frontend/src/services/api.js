const BASE_URL = import.meta.env.VITE_BASE_URL || '';
 
// ── Helpers ──────────────────────────────────────────────────────────────────
 
function closedRing(coordinates) {
  const ring = coordinates.map(c => [c[1], c[0]])
  const first = ring[0], last = ring[ring.length - 1]
  return (first[0] !== last[0] || first[1] !== last[1]) ? [...ring, first] : ring
}
 
// ── Soil ─────────────────────────────────────────────────────────────────────
 
export async function getSoilByPoint(lat, lon) {
  const res = await fetch(`${BASE_URL}/soil/point?lat=${lat}&lon=${lon}`)
  if (!res.ok) throw new Error('Soil fetch failed')
  const data = await res.json()
  console.log(data)
  return data
}
 
export async function getSoilByPolygon(coordinates) { 
  const res = await fetch(`${BASE_URL}/soil/polygon`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ polygon: { type: 'Polygon', coordinates: [closedRing(coordinates)] } }),
  })
  if (!res.ok) throw new Error('Soil polygon fetch failed')
  const data = await res.json()
  console.log(data)
  return data
}
 
// ── Farmland ──────────────────────────────────────────────────────────────────
 
export async function analyseFarmland(coordinates) {
  const res = await fetch(`${BASE_URL}/farmland/analyse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ polygon: { type: 'Polygon', coordinates: [closedRing(coordinates)] } }),
  })
  if (!res.ok) throw new Error('Farmland analyse failed')
  const data = await res.json()
  console.log(data)
  return data
}
 
// ── Dynamic World 9-class land cover ─────────────────────────────────────────
// farmland_routes.py has @router.post("/analyze") registered without prefix in main.py
// so the actual URL is /analyze
 
export async function analyzeLandCover(coordinates, daysBack = 60) {
  const res = await fetch(`${BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      polygon:   { type: 'Polygon', coordinates: [closedRing(coordinates)] },
      days_back: daysBack,
    }),
  })
  if (!res.ok) throw new Error('Land cover analysis failed')
  return res.json()
}
 
// ── Change Detection ──────────────────────────────────────────────────────────
// farmland_routes.py has @router.post("/change") registered without prefix in main.py
// so the actual URL is /change
 
export async function detectChanges(coordinates, dateFrom, dateTo) {
  const res = await fetch(`${BASE_URL}/change`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      polygon:   { type: 'Polygon', coordinates: [closedRing(coordinates)] },
      date_from: dateFrom,
      date_to:   dateTo,
    }),
  })
  if (!res.ok) throw new Error('Change detection failed')
  return res.json()
}
 
// ── Weather (Open-Meteo, no API key) ─────────────────────────────────────────
 
export async function getWeather(lat, lon) {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m&daily=precipitation_sum&timezone=auto&forecast_days=7`
  const res = await fetch(url)
  if (!res.ok) throw new Error('Weather fetch failed')
  const data = await res.json()
  return {
    temperature: data.current?.temperature_2m ?? null,
    humidity:    data.current?.relative_humidity_2m ?? null,
    rainfall:    data.daily?.precipitation_sum
      ? data.daily.precipitation_sum.reduce((a, b) => a + (b || 0), 0)
      : null,
  }
}
 
// ── Crop Recommendation ───────────────────────────────────────────────────────
 
export async function getCropRecommendation(ph, nitrogen, lat, lon) {
  const weather = await getWeather(lat, lon)
  // nitrogen coming as g/kg e (e.g. 1.36)
  // but model expects kg/ha (0-140 range)
  // 1 g/kg soil ≈ 20 kg/ha (standard agronomic conversion: multiply by ~20)
  const N_converted = Math.min(nitrogen * 20, 140)
  const res = await fetch(`${BASE_URL}/crops-reccomendation/crop-insights`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      features: {
        N:           N_converted,
        ph,
        temperature: weather.temperature,
        humidity:    weather.humidity,
        rainfall:    weather.rainfall,
      },
    }),
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}))
    throw new Error(`Crop failed: ${JSON.stringify(errBody)}`)
  }
  const data = await res.json()
  return { ...data, weather }
}