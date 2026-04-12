function formatArea(m) {
  if (m >= 1e6) return (m / 1e6).toFixed(2) + ' km²'
  if (m >= 1e4) return (m / 1e4).toFixed(2) + ' ha'
  return m.toFixed(0) + ' m²'
}

const cards = [
  { label: 'Polygons', color: '#2563eb', bg: '#eff6ff', icon: '⬡' },
  { label: 'Total Area', color: '#16a34a', bg: '#f0fdf4', icon: '⊞' },
  { label: 'Avg Points', color: '#7c3aed', bg: '#f5f3ff', icon: '◎' },
  { label: 'Selected', color: '#ea580c', bg: '#fff7ed', icon: '📌' },
]

export default function InfoCards({ polygons, selectedId }) {
  const totalArea = polygons.reduce((s, p) => s + p.area, 0)
  const selected = polygons.find(p => p.id === selectedId)
  const avgPts = polygons.length > 0
    ? Math.round(polygons.reduce((s, p) => s + p.coordinates.length, 0) / polygons.length)
    : 0

  const values = [
    polygons.length,
    polygons.length === 0 ? '—' : formatArea(totalArea),
    polygons.length === 0 ? '—' : avgPts,
    selected ? selected.name : 'None',
  ]

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12,
      padding: '10px 16px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', flexShrink: 0
    }}>
      {cards.map((c, i) => (
        <div key={c.label} style={{
          background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0',
          padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10, background: c.bg,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, flexShrink: 0, color: c.color
          }}>{c.icon}</div>
          <div>
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 500 }}>{c.label}</div>
            <div style={{ fontSize: i === 3 ? 13 : 20, fontWeight: 700, color: '#0f172a', lineHeight: 1.2, maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {values[i]}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}