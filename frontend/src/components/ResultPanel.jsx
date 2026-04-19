import { useState } from "react"

function formatArea(m) {
  if (m >= 1e6) return (m / 1e6).toFixed(2) + ' km²'
  if (m >= 1e4) return (m / 1e4).toFixed(2) + ' ha'
  return m.toFixed(0) + ' m²'
}

const LAND_COLORS = {
  farmland: '#22c55e',
  builtup:  '#f97316',
  water:    '#3b82f6',
  unknown:  '#a855f7',
}

const SOIL_COLORS = [
  '#b45309','#d97706','#f59e0b','#84cc16','#10b981',
  '#06b6d4','#6366f1','#ec4899','#ef4444','#8b5cf6',
]

function qualityColor(score) {
  if (score >= 0.8) return { bg: '#f0fdf4', border: '#86efac', text: '#15803d', bar: '#22c55e', label: 'Good' }
  if (score >= 0.5) return { bg: '#fffbeb', border: '#fde68a', text: '#d97706', bar: '#f59e0b', label: 'Average' }
  return { bg: '#fef2f2', border: '#fecaca', text: '#dc2626', bar: '#ef4444', label: 'Poor' }
}

const PARAMS = [
  { key: 'ph',           label: 'pH',            unit: '',         max: 14 },
  { key: 'nitrogen',     label: 'Nitrogen (N)',   unit: ' g/kg',    max: 2  },
  { key: 'soc',          label: 'SOC',            unit: ' %',       max: 5  },
  { key: 'cec',          label: 'CEC',            unit: ' cmol/kg', max: 50 },
  { key: 'bulk_density', label: 'Bulk Density',   unit: ' g/cm³',   max: 2  },
]

function ParamRow({ label, value, unit, max }) {
  if (value == null) return null
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 11, color: '#374151' }}>{label}</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: '#0f172a' }}>{value.toFixed(3)}{unit}</span>
      </div>
      <div style={{ height: 4, borderRadius: 99, background: '#f1f5f9', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: '#6366f1', borderRadius: 99, transition: 'width .4s' }} />
      </div>
    </div>
  )
}

function SoilClassCard({ cls, ci }) {
  const [open, setOpen] = useState(false)
  const sqi  = cls.properties?.soil_quality_index
  const qual = cls.properties?.soil_quality
  const conf = cls.properties?.confidence
  if (sqi == null) return null
  const qc = qualityColor(sqi)

  return (
    <div style={{ marginBottom: 6, border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
      {/* Clickable header */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 10px', cursor: 'pointer', background: open ? '#f8fafc' : '#fff', userSelect: 'none' }}
      >
        <div style={{ width: 8, height: 8, borderRadius: 2, background: SOIL_COLORS[ci % SOIL_COLORS.length], flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: '#0f172a', flex: 1 }}>{cls.soil_class}</span>
        <span style={{ fontSize: 10, color: '#94a3b8', marginRight: 4 }}>{cls.area_percentage?.toFixed(1)}%</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: qc.text }}>{sqi.toFixed(2)}</span>
          <span style={{ fontSize: 10, fontWeight: 600, color: qc.text, background: qc.bg, border: `1px solid ${qc.border}`, borderRadius: 4, padding: '1px 5px' }}>
            {qual || qc.label}
          </span>
        </div>
        <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 4, display: 'inline-block', transition: 'transform .2s', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
      </div>

      {/* SQI progress bar */}
      <div style={{ height: 3, background: '#f1f5f9' }}>
        <div style={{ height: '100%', width: `${sqi * 100}%`, background: qc.bar, transition: 'width .4s' }} />
      </div>

      {/* Expanded detail */}
      {open && (
        <div style={{ padding: '8px 10px', background: '#f8fafc', borderTop: '1px solid #f1f5f9' }}>
          {conf != null && (
            <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 8 }}>
              Confidence: {(conf * 100).toFixed(0)}%
            </div>
          )}
          {PARAMS.map(p => (
            <ParamRow key={p.key} label={p.label} value={cls.properties?.[p.key]} unit={p.unit} max={p.max} />
          ))}
        </div>
      )}
    </div>
  )
}

function OverallQualityCard({ overallQuality, soilQualityByClass }) {
  const [paramsOpen, setParamsOpen] = useState(false)
  if (!overallQuality && (!soilQualityByClass || soilQualityByClass.length === 0)) return null

  // Compute weighted overall SQI
  let overallSqi = null
  if (soilQualityByClass?.length > 0) {
    const totalPct = soilQualityByClass.reduce((s, c) => s + (c.area_percentage || 0), 0)
    if (totalPct > 0) {
      const w = soilQualityByClass.reduce((s, c) => {
        const sqi = c.properties?.soil_quality_index
        return sqi != null ? s + sqi * (c.area_percentage / totalPct) : s
      }, 0)
      if (w > 0) overallSqi = w
    }
  }

  const qc = overallSqi != null ? qualityColor(overallSqi) : null

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 6 }}>
        🧪 Soil Quality
      </div>

      {/* Overall SQI badge */}
      {overallSqi != null && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: qc.bg, border: `1px solid ${qc.border}`, borderRadius: 8, padding: '6px 10px', marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: '#374151', fontWeight: 500 }}>Overall SQI</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: qc.text }}>{overallSqi.toFixed(2)}</span>
            <span style={{ fontSize: 10, fontWeight: 600, color: qc.text, background: qc.border, borderRadius: 4, padding: '1px 6px' }}>{qc.label}</span>
          </div>
        </div>
      )}

      {/* Area-weighted params - collapsible */}
      {overallQuality && (
        <div style={{ marginBottom: 8, border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
          <div
            onClick={() => setParamsOpen(o => !o)}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 10px', cursor: 'pointer', background: paramsOpen ? '#f8fafc' : '#fff', userSelect: 'none' }}
          >
            <span style={{ fontSize: 11, fontWeight: 600, color: '#374151' }}>Area-weighted parameters</span>
            <span style={{ fontSize: 10, color: '#94a3b8', display: 'inline-block', transition: 'transform .2s', transform: paramsOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
          </div>
          {paramsOpen && (
            <div style={{ padding: '8px 10px', background: '#f8fafc', borderTop: '1px solid #f1f5f9' }}>
              {PARAMS.map(p => (
                <ParamRow key={p.key} label={p.label} value={overallQuality[p.key]} unit={p.unit} max={p.max} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Per soil class - each collapsible */}
      {soilQualityByClass?.length > 0 && (
        <div>
          {soilQualityByClass.map((cls, ci) => (
            <SoilClassCard key={cls.soil_class} cls={cls} ci={ci} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function ResultPanel({ polygons, selectedId, onSelect, onDelete, onClearAll }) {
  return (
    <aside style={{ width: 300, background: '#fff', borderLeft: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}>

      {/* Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>Drawn Polygons</div>
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
            {polygons.length === 0 ? 'No polygons drawn yet' : `${polygons.length} polygon${polygons.length > 1 ? 's' : ''} on map`}
          </div>
        </div>
        {polygons.length > 0 && (
          <button onClick={onClearAll} style={{ fontSize: 11, color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 500, padding: '4px 8px', borderRadius: 6 }}>
            Clear all
          </button>
        )}
      </div>

      {/* Polygon list */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {polygons.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 180, padding: '0 24px', textAlign: 'center', gap: 12 }}>
            <div style={{ width: 48, height: 48, borderRadius: '50%', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22 }}>🗺️</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>No polygons yet</div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>Switch to <strong style={{ color: '#2563eb' }}>Draw</strong> mode and click on the map to start drawing.</div>
            </div>
          </div>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {polygons.map((poly, i) => {
              const active = selectedId === poly.id
              return (
                <li key={poly.id} onClick={() => onSelect(poly.id)} style={{ padding: '10px 14px', cursor: 'pointer', borderLeft: active ? '3px solid #2563eb' : '3px solid transparent', background: active ? '#eff6ff' : '#fff', borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 28, height: 28, borderRadius: 8, flexShrink: 0, background: active ? '#2563eb' : '#f1f5f9', color: active ? '#fff' : '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700 }}>
                      {poly.status === 'loading' ? (
                        <div style={{ width: 12, height: 12, border: '2px solid', borderColor: active ? 'rgba(255,255,255,.4)' : '#cbd5e1', borderTopColor: active ? '#fff' : '#2563eb', borderRadius: '50%', animation: 'spin .8s linear infinite' }} />
                      ) : (i + 1)}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{poly.name}</div>
                      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                        {poly.status === 'loading' ? 'Analysing…' : `${poly.coordinates.length} pts · ${formatArea(poly.area)}`}
                      </div>
                    </div>
                    <button onClick={e => { e.stopPropagation(); onDelete(poly.id) }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: 14, padding: 4, borderRadius: 6 }} title="Delete">🗑️</button>
                  </div>

                  {active && poly.status === 'done' && (
                    <div style={{ marginTop: 10, marginLeft: 36 }}>

                      {/* Soil Type */}
                      {poly.soilDistribution?.length > 0 && (
                        <div style={{ marginBottom: 10 }}>
                          <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 6 }}>🌱 Soil Type</div>
                          {poly.soilDistribution.map((d, si) => (
                            <div key={d.soil_class} style={{ marginBottom: 5 }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                                <span style={{ fontSize: 11, color: '#374151' }}>{d.soil_class}</span>
                                <span style={{ fontSize: 11, fontWeight: 600, color: '#0f172a' }}>{d.percentage?.toFixed(1)}%</span>
                              </div>
                              <div style={{ height: 5, borderRadius: 99, background: '#f1f5f9', overflow: 'hidden' }}>
                                <div style={{ height: '100%', width: `${d.percentage}%`, background: SOIL_COLORS[si % SOIL_COLORS.length], borderRadius: 99, transition: 'width .4s' }} />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Soil Quality with collapsible dropdowns */}
                      <OverallQualityCard
                        overallQuality={poly.overallQuality}
                        soilQualityByClass={poly.soilQualityByClass}
                      />

                      {/* Land Use */}
                      {poly.landUse && Object.keys(poly.landUse).length > 0 && (
                        <div>
                          <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 6 }}>🛰️ Land Use</div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                            {Object.entries(poly.landUse).map(([label, count]) => (
                              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, padding: '3px 8px', fontSize: 11 }}>
                                <div style={{ width: 8, height: 8, borderRadius: '50%', background: LAND_COLORS[label] || '#888' }} />
                                <span style={{ textTransform: 'capitalize', color: '#374151' }}>{label}</span>
                                <span style={{ color: '#94a3b8' }}>×{count}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
            <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
          </ul>
        )}
      </div>

      {/* Footer */}
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
