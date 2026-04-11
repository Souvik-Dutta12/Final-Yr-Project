export default function Navbar({ mode, onModeChange }) {
  return (
    <nav style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 20px', background: '#fff', borderBottom: '1px solid #e2e8f0',
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)', flexShrink: 0, zIndex: 50
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10, background: '#2563eb',
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 18
        }}>📍</div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 16, color: '#0f172a', lineHeight: 1.2 }}>West Bengal Map</div>
          <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.2 }}>Polygon Drawing Dashboard</div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>
          {mode === 'click' ? 'Inspect mode active' : 'Drawing mode active'}
        </span>
        <div style={{ display: 'flex', background: '#f1f5f9', borderRadius: 10, padding: 4, gap: 4 }}>
          {['click', 'draw'].map(m => (
            <button
              key={m}
              onClick={() => onModeChange(m)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '7px 16px', fontSize: 13, fontWeight: 500, borderRadius: 7,
                border: mode === m ? '1px solid #e2e8f0' : '1px solid transparent',
                background: mode === m ? '#fff' : 'transparent',
                color: mode === m ? '#2563eb' : '#64748b',
                cursor: 'pointer', boxShadow: mode === m ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.15s'
              }}
            >
              {m === 'click' ? '👆' : '✏️'} {m === 'click' ? 'Click' : 'Draw'}
            </button>
          ))}
        </div>
      </div>
    </nav>
  )
}