// ─────────────────────────────────────────────────────────────────────────────
// API mode — frontend/.env e ek line diye change kora jay:
//   VITE_API_MODE=python  → Python server er sathe direct (default, TS server lagbe na)
//   VITE_API_MODE=ts      → TypeScript server er through (Redis + TS + Python lagbe)
// .env change korle `npm run dev` restart korte hobe.
// ─────────────────────────────────────────────────────────────────────────────
const USE_TS = (import.meta.env.VITE_API_MODE || 'python').toLowerCase() === 'ts'

const TS_BASE = import.meta.env.VITE_API_URL || '/api/v1' // TS server (vite proxy: /api)
const PY_BASE = import.meta.env.VITE_PY_URL || ''         // Python server (vite proxy)

// ── Helpers ──────────────────────────────────────────────────────────────────

function closedRing(coordinates) {
  const ring = coordinates.map(c => [c[1], c[0]])
  const first = ring[0], last = ring[ring.length - 1]
  return (first[0] !== last[0] || first[1] !== last[1]) ? [...ring, first] : ring
}

const polygonBody = (coordinates) => ({
  type: 'Polygon',
  coordinates: [closedRing(coordinates)],
})

// fetch + timeout + readable errors (spinner kokhono infinite atke thakbe na)
async function request(url, options = {}, timeoutMs = 120000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, { ...options, signal: controller.signal })
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        const d = body?.detail ?? body?.message ?? body
        detail = typeof d === 'string' ? d : JSON.stringify(d)
        if (Array.isArray(body?.errors) && body.errors.length) {
          detail += ' - ' + body.errors
            .map(e => (e?.message ? `${(e.path || []).join('.')}: ${e.message}` : JSON.stringify(e)))
            .join('; ')
        }
        if (body?.retryAfter) detail += ` (retry after ${body.retryAfter}s)`
      } catch { /* body JSON na hole statusText thakbe */ }
      throw new Error(`HTTP ${res.status} - ${detail}`)
    }
    return await res.json()
  } catch (err) {
    if (err?.name === 'AbortError') {
      throw new Error(`Timed out after ${Math.round(timeoutMs / 1000)}s: ${url}`)
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

function postJson(url, body, timeoutMs) {
  return request(
    url,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    timeoutMs,
  )
}

// TS server Python er response ke abar wrap kore:
//   TS:     { statusCode, data: <PYTHON>, message, success }
//   PYTHON: { message, success, data: <payload> }
// Component gulo `res.data` = payload dhore kaj kore, tai TS mode e Python er
// response ta-i return kori (python mode e kichu korar dorkar nei).
function unwrap(json) {
  if (!USE_TS) return json
  const inner = json?.data
  return inner && typeof inner === 'object' && 'data' in inner ? inner : json
}

// ── Soil ─────────────────────────────────────────────────────────────────────

export async function getSoilByPoint(lat, lon) {
  const url = USE_TS
    ? `${TS_BASE}/soil/point?lat=${lat}&lon=${lon}`
    : `${PY_BASE}/soil/?lat=${lat}&lon=${lon}`
  return unwrap(await request(url, {}, 120000))
}

export async function getSoilByPolygon(coordinates) {
  const url = `${USE_TS ? TS_BASE : PY_BASE}/soil/polygon`
  return unwrap(await postJson(url, { polygon: polygonBody(coordinates) }, 180000))
}

// ── Farmland ─────────────────────────────────────────────────────────────────
// Ekhon kothao call kora hoy na (Python e `/farmland/analyse` route nei).
// Land cover er jonno niche analyzeLandCover() use hoy.
export async function analyseFarmland(coordinates) {
  const url = `${USE_TS ? TS_BASE : PY_BASE}/farmland/analyse`
  return unwrap(await postJson(url, { polygon: polygonBody(coordinates) }, 180000))
}

// ── Dynamic World land cover (dui mode e-i direct Python — TS e route nei) ───

export function analyzeLandCover(coordinates, daysBack = 60) {
  return postJson(
    `${PY_BASE}/analyze`,
    { polygon: polygonBody(coordinates), days_back: daysBack },
    300000,
  )
}

export function detectChanges(coordinates, dateFrom, dateTo) {
  return postJson(
    `${PY_BASE}/change`,
    { polygon: polygonBody(coordinates), date_from: dateFrom, date_to: dateTo },
    300000,
  )
}

// ── Weather (Open-Meteo, no API key) ─────────────────────────────────────────

export async function getWeather(lat, lon) {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m&daily=precipitation_sum&timezone=auto&forecast_days=7`
  const data = await request(url, {}, 20000)
  return {
    temperature: data.current?.temperature_2m ?? null,
    humidity:    data.current?.relative_humidity_2m ?? null,
    rainfall:    data.daily?.precipitation_sum
      ? data.daily.precipitation_sum.reduce((a, b) => a + (b || 0), 0)
      : null,
  }
}

// ── Crop Recommendation ──────────────────────────────────────────────────────

export async function getCropRecommendation(ph, nitrogen, lat, lon) {
  const weather = await getWeather(lat, lon)
  // nitrogen g/kg e ashe, model kg/ha (0-140) chay → ~20x conversion
  const N_converted = Math.min(nitrogen * 20, 140)
  const url = USE_TS
    ? `${TS_BASE}/crops-recomendations`
    : `${PY_BASE}/crops-reccomendation/crop-insights`
  const json = await postJson(
    url,
    {
      features: {
        N:           N_converted,
        ph,
        temperature: weather.temperature,
        humidity:    weather.humidity,
        rainfall:    weather.rainfall,
      },
    },
    120000,
  )
  return { ...unwrap(json), weather }
}