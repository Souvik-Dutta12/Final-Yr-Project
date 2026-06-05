import { useState } from 'react'
import { analyzeLandCover, detectChanges } from '../services/api'

// DW class registry - matches backend dw_classes.py
const DW_CLASSES = [
  { name:'water',              label:'Water',              color:'#419BDF' },
  { name:'trees',              label:'Trees',              color:'#397D49' },
  { name:'grass',              label:'Grass',              color:'#88B053' },
  { name:'flooded_vegetation', label:'Flooded Vegetation', color:'#7A87C6' },
  { name:'crops',              label:'Crops',              color:'#E49635' },
  { name:'shrub_and_scrub',    label:'Shrub & Scrub',      color:'#DFC35A' },
  { name:'built',              label:'Built-up',           color:'#C4281B' },
  { name:'bare',               label:'Bare Ground',        color:'#A59B8F' },
  { name:'snow_and_ice',       label:'Snow & Ice',         color:'#B39FE1' },
]
const clsMap = Object.fromEntries(DW_CLASSES.map(c=>[c.name,c]))

function today() { return new Date().toISOString().slice(0,10) }
function monthsAgo(n) { const d=new Date(); d.setMonth(d.getMonth()-n); return d.toISOString().slice(0,10) }

function ClassBar({ name, stats, color }) {
  const c = clsMap[name]
  const displayColor = color || c?.color || '#94a3b8'
  const label = c?.label || name
  if (!stats) return null
  const pct = stats.coverage_pct ?? 0
  if (pct < 0.05) return null
  return (
    <div style={{ marginBottom:6 }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:2 }}>
        <div style={{ display:'flex', alignItems:'center', gap:5 }}>
          <div style={{ width:8, height:8, borderRadius:2, background:displayColor, flexShrink:0 }} />
          <span style={{ fontSize:11, color:'#374151' }}>{label}</span>
        </div>
        <span style={{ fontSize:11, fontWeight:600, color:'#0f172a' }}>
          {pct.toFixed(1)}%
          {stats.area_ha!=null && <span style={{ fontWeight:400, color:'#94a3b8', marginLeft:4 }}>({stats.area_ha.toFixed(0)} ha)</span>}
        </span>
      </div>
      <div style={{ height:4, borderRadius:99, background:'#f1f5f9', overflow:'hidden' }}>
        <div style={{ height:'100%', width:`${Math.min(pct,100)}%`, background:displayColor, borderRadius:99, transition:'width .4s' }} />
      </div>
    </div>
  )
}

function DeltaRow({ name, delta }) {
  const c = clsMap[name]
  if (!c||!delta) return null
  const dh = delta.delta_ha??0
  if (Math.abs(dh)<0.1) return null
  const gain = dh>0
  return (
    <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:5 }}>
      <div style={{ width:8, height:8, borderRadius:2, background:c.color, flexShrink:0 }} />
      <span style={{ fontSize:11, color:'#374151', flex:1 }}>{c.label}</span>
      <span style={{ fontSize:11, fontWeight:700, color:gain?'#16a34a':'#dc2626' }}>{gain?'+':''}{dh.toFixed(1)} ha</span>
      <span style={{ fontSize:10, color:gain?'#16a34a':'#dc2626' }}>({gain?'+':''}{(delta.delta_pct??0).toFixed(1)}%)</span>
    </div>
  )
}

export default function LandCoverPanel({ polygon }) {
  const [tab, setTab] = useState('snapshot')

  const [daysBack,    setDaysBack]    = useState(60)
  const [snapLoading, setSnapLoading] = useState(false)
  const [snapResult,  setSnapResult]  = useState(null)   // the FeatureCollection + metadata
  const [snapError,   setSnapError]   = useState(null)

  const [periodA,      setPeriodA]      = useState({ start:monthsAgo(18), end:monthsAgo(12) })
  const [periodB,      setPeriodB]      = useState({ start:monthsAgo(6),  end:today() })
  const [chgLoading,   setChgLoading]   = useState(false)
  const [chgResult,    setChgResult]    = useState(null)
  const [chgError,     setChgError]     = useState(null)
  const [activePeriod, setActivePeriod] = useState('A')

  if (!polygon) return null

  // ── Snapshot ──────────────────────────────────────────────────────────────
  async function runSnapshot() {
    setSnapLoading(true); setSnapError(null); setSnapResult(null)
    try {
      const res = await analyzeLandCover(polygon.coordinates, daysBack)
      // API response: { success, message, data: { type:'FeatureCollection', features:[], metadata:{} } }
      const fc = res?.data ?? res
      setSnapResult(fc)
      // Send FeatureCollection directly to map
      if (window.__onLandCoverResult) window.__onLandCoverResult(fc)
    } catch(e) {
      setSnapError(e.message)
    } finally {
      setSnapLoading(false)
    }
  }

  // ── Change Detection ──────────────────────────────────────────────────────
  async function runChange() {
    setChgLoading(true); setChgError(null); setChgResult(null)
    try {
      const res  = await detectChanges(polygon.coordinates, periodA, periodB)
      const data = res?.data ?? res
      setChgResult(data)
      // Backend change detection returns period_a_geojson and period_b_geojson
      // If those exist, use them; otherwise build simple coloured overlay from stats
      const fcA = data.period_a_geojson ?? _buildStatsFC(data.period_a_stats, data.period_a)
      const fcB = data.period_b_geojson ?? _buildStatsFC(data.period_b_stats, data.period_b)
      if (window.__onChangeResult) window.__onChangeResult(fcA, fcB)
      setActivePeriod('A')
      if (window.__showPeriod) window.__showPeriod('A')
    } catch(e) {
      setChgError(e.message)
    } finally {
      setChgLoading(false)
    }
  }

  // Build a simple coloured FeatureCollection from class stats + polygon coords
  // Used only if backend doesn't return period GeoJSONs
  function _buildStatsFC(stats, periodInfo) {
    if (!stats || !polygon?.coordinates?.length) return { type:'FeatureCollection', features:[] }

    const coords = polygon.coordinates
    const ring = [...coords.map(c=>[c[1],c[0]])]
    if (ring[0][0]!==ring[ring.length-1][0]||ring[0][1]!==ring[ring.length-1][1]) ring.push(ring[0])

    const lngs = ring.map(p=>p[0]), lats = ring.map(p=>p[1])
    const minLng=Math.min(...lngs), maxLng=Math.max(...lngs)
    const minLat=Math.min(...lats), maxLat=Math.max(...lats)
    const width = maxLng - minLng

    const classes = DW_CLASSES
      .map(c=>({ ...c, pct:(stats[c.name]?.coverage_pct??0) }))
      .filter(c=>c.pct>1)
      .sort((a,b)=>b.pct-a.pct)

    const total = classes.reduce((s,c)=>s+c.pct, 0)||1
    const features = []
    let curLng = minLng

    classes.forEach(cls => {
      const sliceW   = (cls.pct/total)*width
      const sliceLng = curLng + sliceW
      features.push({
        type:'Feature',
        properties:{ class:cls.name, label:cls.label, color:cls.color, coverage_pct:cls.pct },
        geometry:{
          type:'Polygon',
          coordinates:[[
            [curLng, minLat],[sliceLng, minLat],
            [sliceLng, maxLat],[curLng, maxLat],[curLng, minLat]
          ]]
        }
      })
      curLng = sliceLng
    })

    return { type:'FeatureCollection', features }
  }

  function switchPeriod(p) {
    setActivePeriod(p)
    if (window.__showPeriod) window.__showPeriod(p)
  }

  const TAB = (active) => ({
    flex:1, padding:'6px 0', fontSize:11, fontWeight:600, cursor:'pointer', border:'none',
    background:active?'#2563eb':'#f1f5f9', color:active?'#fff':'#64748b',
    borderRadius:6, transition:'background .15s',
  })
  const INPUT = { width:'100%', padding:'5px 8px', fontSize:11, border:'1px solid #e2e8f0', borderRadius:6, background:'#f8fafc', color:'#374151', boxSizing:'border-box' }
  const BTN = (loading, color='#2563eb') => ({
    width:'100%', padding:'8px', fontSize:12, fontWeight:600, border:'none',
    borderRadius:8, cursor:loading?'not-allowed':'pointer',
    background:loading?'#94a3b8':color, color:'#fff', marginTop:8,
  })

  return (
    <div style={{ marginBottom:10 }}>
      <div style={{ fontSize:10, fontWeight:700, color:'#64748b', textTransform:'uppercase', letterSpacing:.5, marginBottom:6 }}>
        🛰️ Dynamic World Analysis
      </div>

      <div style={{ display:'flex', gap:4, marginBottom:10 }}>
        <button style={TAB(tab==='snapshot')} onClick={()=>setTab('snapshot')}>📸 Snapshot</button>
        <button style={TAB(tab==='change')}   onClick={()=>setTab('change')}>🔄 Change Detection</button>
      </div>

      {/* ── SNAPSHOT ── */}
      {tab==='snapshot' && (
        <div>
          <div style={{ marginBottom:8 }}>
            <label style={{ fontSize:11, color:'#64748b', display:'block', marginBottom:3 }}>Days back for imagery</label>
            <select value={daysBack} onChange={e=>setDaysBack(Number(e.target.value))} style={INPUT}>
              {[30,60,90,120,180,365].map(d=><option key={d} value={d}>{d} days</option>)}
            </select>
          </div>
          <button onClick={runSnapshot} disabled={snapLoading} style={BTN(snapLoading,'#2563eb')}>
            {snapLoading?'⏳ Analysing… (~30s)':'🌍 Analyse Land Cover'}
          </button>

          {snapError && (
            <div style={{ marginTop:8, padding:'8px 10px', background:'#fef2f2', border:'1px solid #fecaca', borderRadius:8, fontSize:11, color:'#dc2626' }}>⚠️ {snapError}</div>
          )}

          {snapResult && (() => {
            const meta  = snapResult.metadata ?? {}
            const stats = meta.class_stats ?? {}
            const dr    = meta.date_range
            const sorted = DW_CLASSES
              .map(c => ({ ...c, s: stats[c.name], bc: stats[c.name]?.color || c.color }))
              .filter(c => c.s && c.s.coverage_pct > 0.05)
              .sort((a,b) => b.s.coverage_pct - a.s.coverage_pct)

            return (
              <div style={{ marginTop:10 }}>
                {dr && (
                  <div style={{ fontSize:10, color:'#94a3b8', marginBottom:6 }}>
                    {dr.start} → {dr.end}
                    {meta.resolution_m && ` · ${meta.resolution_m}m`}
                    {meta.scene_count  && ` · ${meta.scene_count} scenes`}
                  </div>
                )}
                <div style={{ fontSize:10, color:'#16a34a', fontWeight:600, marginBottom:8, display:'flex', alignItems:'center', gap:4 }}>
                  <span>✅</span> 9-class land cover shown on map
                </div>
                {sorted.map(c => (
                  <ClassBar key={c.name} name={c.name} stats={c.s} color={c.bc} />
                ))}
              </div>
            )
          })()}
        </div>
      )}

      {/* ── CHANGE DETECTION ── */}
      {tab==='change' && (
        <div>
          {[['📅 Period A (Baseline)',periodA,setPeriodA],['📅 Period B (Comparison)',periodB,setPeriodB]].map(([label,period,setPeriod])=>(
            <div key={label} style={{ marginBottom:8 }}>
              <div style={{ fontSize:11, fontWeight:600, color:'#374151', marginBottom:4 }}>{label}</div>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:4 }}>
                {['start','end'].map(k=>(
                  <div key={k}>
                    <label style={{ fontSize:10, color:'#94a3b8', display:'block', marginBottom:2 }}>{k.charAt(0).toUpperCase()+k.slice(1)}</label>
                    <input type="date" value={period[k]} max={today()} onChange={e=>setPeriod(p=>({...p,[k]:e.target.value}))} style={INPUT}/>
                  </div>
                ))}
              </div>
            </div>
          ))}

          <button onClick={runChange} disabled={chgLoading} style={BTN(chgLoading,'#7c3aed')}>
            {chgLoading?'⏳ Detecting… (~60s)':'🔄 Detect Changes'}
          </button>

          {chgError && (
            <div style={{ marginTop:8, padding:'8px 10px', background:'#fef2f2', border:'1px solid #fecaca', borderRadius:8, fontSize:11, color:'#dc2626' }}>⚠️ {chgError}</div>
          )}

          {chgResult && (
            <div style={{ marginTop:10 }}>
              {/* Period A / B toggle */}
              <div style={{ marginBottom:10 }}>
                <div style={{ fontSize:10, fontWeight:700, color:'#64748b', textTransform:'uppercase', letterSpacing:.5, marginBottom:6 }}>🗺️ Show on Map</div>
                <div style={{ display:'flex', gap:4 }}>
                  <button onClick={()=>switchPeriod('A')} style={{ flex:1, padding:'7px', fontSize:11, fontWeight:600, border:'none', borderRadius:7, cursor:'pointer', background:activePeriod==='A'?'#2563eb':'#f1f5f9', color:activePeriod==='A'?'#fff':'#374151' }}>
                    Period A
                  </button>
                  <button onClick={()=>switchPeriod('B')} style={{ flex:1, padding:'7px', fontSize:11, fontWeight:600, border:'none', borderRadius:7, cursor:'pointer', background:activePeriod==='B'?'#7c3aed':'#f1f5f9', color:activePeriod==='B'?'#fff':'#374151' }}>
                    Period B
                  </button>
                </div>
                <div style={{ fontSize:10, color:'#94a3b8', marginTop:4 }}>
                  {activePeriod==='A'
                    ? `A: ${chgResult.period_a?.start ?? periodA.start} → ${chgResult.period_a?.end ?? periodA.end}`
                    : `B: ${chgResult.period_b?.start ?? periodB.start} → ${chgResult.period_b?.end ?? periodB.end}`}
                </div>
              </div>

              {/* Summary */}
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:5, marginBottom:10 }}>
                <div style={{ background:'#f8fafc', border:'1px solid #e2e8f0', borderRadius:8, padding:'6px 10px', textAlign:'center' }}>
                  <div style={{ fontSize:9, color:'#94a3b8', fontWeight:600, textTransform:'uppercase' }}>Changed</div>
                  <div style={{ fontSize:14, fontWeight:700, color:chgResult.changed_pct>20?'#dc2626':'#d97706' }}>{chgResult.changed_pct?.toFixed(1)}%</div>
                </div>
                <div style={{ background:'#f8fafc', border:'1px solid #e2e8f0', borderRadius:8, padding:'6px 10px', textAlign:'center' }}>
                  <div style={{ fontSize:9, color:'#94a3b8', fontWeight:600, textTransform:'uppercase' }}>NDVI Δ</div>
                  <div style={{ fontSize:14, fontWeight:700, color:chgResult.ndvi_delta_mean>0?'#16a34a':chgResult.ndvi_delta_mean<0?'#dc2626':'#64748b' }}>
                    {chgResult.ndvi_delta_mean!=null?(chgResult.ndvi_delta_mean>0?'+':'')+chgResult.ndvi_delta_mean.toFixed(3):'—'}
                  </div>
                </div>
              </div>

              {/* Area changes */}
              {(() => {
                const deltas  = chgResult.class_deltas??{}
                const sorted  = DW_CLASSES.map(c=>({...c,d:deltas[c.name]})).filter(c=>c.d&&Math.abs(c.d.delta_ha)>=0.1).sort((a,b)=>Math.abs(b.d.delta_ha)-Math.abs(a.d.delta_ha))
                if (!sorted.length) return null
                return (
                  <div style={{ marginBottom:10 }}>
                    <div style={{ fontSize:10, fontWeight:700, color:'#64748b', textTransform:'uppercase', letterSpacing:.5, marginBottom:6 }}>Area Changes (A → B)</div>
                    {sorted.map(c=><DeltaRow key={c.name} name={c.name} delta={c.d}/>)}
                  </div>
                )
              })()}

              {/* Notable transitions */}
              {chgResult.notable_transitions?.length>0 && (
                <div style={{ marginBottom:10 }}>
                  <div style={{ fontSize:10, fontWeight:700, color:'#64748b', textTransform:'uppercase', letterSpacing:.5, marginBottom:6 }}>⚠️ Notable Transitions</div>
                  {chgResult.notable_transitions.slice(0,5).map((t,i)=>(
                    <div key={i} style={{ display:'flex', alignItems:'flex-start', gap:6, marginBottom:6, padding:'6px 8px', background:'#fffbeb', border:'1px solid #fde68a', borderRadius:7 }}>
                      <div style={{ display:'flex', gap:2, marginTop:2 }}>
                        <div style={{ width:7, height:7, borderRadius:2, background:clsMap[t.from_class]?.color??'#888' }}/>
                        <span style={{ fontSize:9, color:'#94a3b8' }}>→</span>
                        <div style={{ width:7, height:7, borderRadius:2, background:clsMap[t.to_class]?.color??'#888' }}/>
                      </div>
                      <div style={{ flex:1 }}>
                        <div style={{ fontSize:11, fontWeight:600, color:'#92400e' }}>{t.label}</div>
                        <div style={{ fontSize:10, color:'#b45309' }}>{t.area_ha?.toFixed(1)} ha</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Period comparison bars */}
              <div>
                <div style={{ fontSize:10, fontWeight:700, color:'#64748b', textTransform:'uppercase', letterSpacing:.5, marginBottom:6 }}>Period Comparison</div>
                {DW_CLASSES.map(c=>{
                  const a=(chgResult.period_a_stats??{})[c.name], b=(chgResult.period_b_stats??{})[c.name]
                  if (!a||!b||Math.max(a.coverage_pct,b.coverage_pct)<0.5) return null
                  return (
                    <div key={c.name} style={{ marginBottom:6 }}>
                      <div style={{ display:'flex', alignItems:'center', gap:5, marginBottom:2 }}>
                        <div style={{ width:8, height:8, borderRadius:2, background:c.color }}/>
                        <span style={{ fontSize:10, color:'#374151', flex:1 }}>{c.label}</span>
                        <span style={{ fontSize:10, color:'#2563eb' }}>{a.coverage_pct.toFixed(1)}%</span>
                        <span style={{ fontSize:9, color:'#94a3b8' }}>→</span>
                        <span style={{ fontSize:10, color:'#7c3aed' }}>{b.coverage_pct.toFixed(1)}%</span>
                      </div>
                      <div style={{ position:'relative', height:5, borderRadius:99, background:'#f1f5f9', overflow:'hidden' }}>
                        <div style={{ position:'absolute', height:'100%', width:`${a.coverage_pct}%`, background:c.color, opacity:0.35, borderRadius:99 }}/>
                        <div style={{ position:'absolute', height:'100%', width:`${b.coverage_pct}%`, background:c.color, borderRadius:99 }}/>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}