const BASE_URL = import.meta.env.VITE_BASE_URL || '';

export async function getSoilByPoint(lat, lon) {
  const res = await fetch(`${BASE_URL}/soil/?lat=${lat}&lon=${lon}`);
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
  const closed = (ring[0][0] !== ring[ring.length-1][0] || ring[0][1] !== ring[ring.length-1][1])
    ? [...ring, ring[0]]
    : ring
  const res = await fetch(`${BASE_URL}/farmland/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ polygon: { type: "Polygon", coordinates: [closed] } }),
  });
  if (!res.ok) throw new Error("Farmland analyse failed");
  const data = await res.json();
  // console.log('Farmland Response:', JSON.stringify(data, null, 2));
  return data;
}

// Fetch current weather from Open-Meteo (no API key needed)
export async function getWeather(lat, lon) {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m&daily=precipitation_sum&timezone=auto&forecast_days=7`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Weather fetch failed");
  const data = await res.json();

  const temperature = data.current?.temperature_2m ?? null;
  const humidity    = data.current?.relative_humidity_2m ?? null;
  // Sum of 7-day precipitation as monthly rainfall approximation
  const rainfall    = data.daily?.precipitation_sum
    ? data.daily.precipitation_sum.reduce((a, b) => a + (b || 0), 0)
    : null;

  return { temperature, humidity, rainfall };
}

// Get crop recommendation for a point
export async function getCropRecommendation(ph, nitrogen, lat, lon) {
  const weather = await getWeather(lat, lon);
  const res = await fetch(`${BASE_URL}/crops-reccomendation/crop-insights`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      features: {
        N:           nitrogen,
        ph:          ph,
        temperature: weather.temperature,
        humidity:    weather.humidity,
        rainfall:    weather.rainfall,
      }
    }),
  });
  if (!res.ok) throw new Error("Crop recommendation failed");
  const data = await res.json();
  return { ...data, weather };
}
