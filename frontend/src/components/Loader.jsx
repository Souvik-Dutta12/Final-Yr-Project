export default function Loader({ message = 'Loading…' }) {
  return (
    <div style={{
      position: 'absolute', inset: 0, background: 'rgba(255,255,255,0.85)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      zIndex: 999, gap: 12
    }}>
      <div style={{
        width: 36, height: 36, border: '3px solid #e2e8f0',
        borderTop: '3px solid #2563eb', borderRadius: '50%',
        animation: 'spin 0.8s linear infinite'
      }} />
      <div style={{ fontSize: 13, color: '#64748b' }}>{message}</div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}