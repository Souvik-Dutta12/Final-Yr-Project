function formatArea(m) {
  if (m >= 1e6) return (m / 1e6).toFixed(2) + ' km²'
  if (m >= 1e4) return (m / 1e4).toFixed(2) + ' ha'
  return m.toFixed(0) + ' m²'
}

export default function ResultPanel({ polygons, selectedId, onSelect, onDelete, onClearAll }) {
  return (
    <aside style={{
      width: 280, background: '#fff', borderLeft: '1px solid #e2e8f0',
      display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0
    }}>
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid #e2e8f0',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between'
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>Drawn Polygons</div>
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
            {polygons.length === 0 ? 'No polygons drawn yet' : `${polygons.length} polygon${polygons.length > 1 ? 's' : ''} on map`}
          </div>
        </div>
        {polygons.length > 0 && (
          <button onClick={onClearAll} style={{
            fontSize: 11, color: '#ef4444', background: 'none', border: 'none',
            cursor: 'pointer', fontWeight: 500, padding: '4px 8px', borderRadius: 6
          }}>Clear all</button>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {polygons.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 180, padding: '0 24px', textAlign: 'center', gap: 12 }}>
            <div style={{ width: 48, height: 48, borderRadius: '50%', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22 }}>🗺️</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>No polygons yet</div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                Switch to <strong style={{ color: '#2563eb' }}>Draw</strong> mode and click on the map to start drawing.
              </div>
            </div>
          </div>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {polygons.map((poly, i) => {
              const active = selectedId === poly.id
              return (
                <li
                  key={poly.id}
                  onClick={() => onSelect(poly.id)}
                  style={{
                    padding: '10px 14px', cursor: 'pointer',
                    borderLeft: active ? '3px solid #2563eb' : '3px solid transparent',
                    background: active ? '#eff6ff' : '#fff',
                    borderBottom: '1px solid #f1f5f9',
                    transition: 'background 0.15s'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                      background: active ? '#2563eb' : '#f1f5f9',
                      color: active ? '#fff' : '#64748b',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 12, fontWeight: 700
                    }}>{i + 1}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{poly.name}</div>
                      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                        {poly.coordinates.length} pts · {formatArea(poly.area)}
                      </div>
                    </div>
                    <button
                      onClick={e => { e.stopPropagation(); onDelete(poly.id) }}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: 14, padding: 4, borderRadius: 6 }}
                      title="Delete"
                    >🗑️</button>
                  </div>
                  {active && poly.coordinates.length > 0 && (
                    <div style={{ marginTop: 6, marginLeft: 36, fontSize: 11, color: '#64748b' }}>
                      <div>Start: <span style={{ fontFamily: 'monospace', color: '#374151' }}>{poly.coordinates[0][0].toFixed(4)}, {poly.coordinates[0][1].toFixed(4)}</span></div>
                      <div>Area: <strong style={{ color: '#2563eb' }}>{formatArea(poly.area)}</strong></div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {polygons.length > 0 && (
        <div style={{ padding: '10px 16px', borderTop: '1px solid #e2e8f0', background: '#f8fafc' }}>
          <div style={{ fontSize: 11, color: '#64748b' }}>
            Total area: <strong style={{ color: '#0f172a' }}>{formatArea(polygons.reduce((s, p) => s + p.area, 0))}</strong>
          </div>
        </div>
      )}
    </aside>
  )
}