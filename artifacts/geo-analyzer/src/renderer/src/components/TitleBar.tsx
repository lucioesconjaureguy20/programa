export default function TitleBar() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 14px 8px',
        WebkitAppRegion: 'drag' as any,
        borderBottom: '1px solid var(--border)'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 16 }}>🌍</span>
        <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--accent)', letterSpacing: '-0.02em' }}>
          GeoAnalyzer
        </span>
      </div>
      <div style={{ display: 'flex', gap: 6, WebkitAppRegion: 'no-drag' as any }}>
        <button
          onClick={() => window.api.minimizeWindow()}
          style={{
            width: 26,
            height: 26,
            borderRadius: 6,
            background: 'var(--bg-elevated)',
            color: 'var(--text-secondary)',
            fontSize: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          title="Minimize"
        >
          −
        </button>
        <button
          onClick={() => window.api.closeWindow()}
          style={{
            width: 26,
            height: 26,
            borderRadius: 6,
            background: 'var(--bg-elevated)',
            color: 'var(--text-secondary)',
            fontSize: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          title="Close"
          onMouseEnter={(e) => (e.currentTarget.style.background = '#5c2020')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg-elevated)')}
        >
          ×
        </button>
      </div>
    </div>
  )
}
