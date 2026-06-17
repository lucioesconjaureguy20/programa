type CaptureStatus = 'idle' | 'capturing' | 'analyzing'

interface StatusBarProps {
  status: CaptureStatus
  isRunning: boolean
  region: any
  onStart: () => void
  onStop: () => void
  onSelectRegion: () => void
}

const statusColors: Record<CaptureStatus, string> = {
  idle: '#555',
  capturing: '#3ecf8e',
  analyzing: '#f59e0b'
}

const statusLabels: Record<CaptureStatus, string> = {
  idle: 'Idle',
  capturing: 'Capturing…',
  analyzing: 'Analyzing…'
}

export default function StatusBar({ status, isRunning, region, onStart, onStop, onSelectRegion }: StatusBarProps) {
  return (
    <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={isRunning ? onStop : onStart}
          style={{
            flex: 1,
            padding: '9px 0',
            borderRadius: 'var(--radius)',
            background: isRunning ? '#2a1515' : 'var(--accent)',
            color: isRunning ? '#ef4444' : '#000',
            fontWeight: 700,
            fontSize: 13,
            letterSpacing: '0.02em',
            border: isRunning ? '1px solid #5c2020' : 'none'
          }}
        >
          {isRunning ? '⏹ Stop' : '▶ Start'}
        </button>
        <button
          onClick={onSelectRegion}
          disabled={isRunning}
          style={{
            flex: 1,
            padding: '9px 0',
            borderRadius: 'var(--radius)',
            background: isRunning ? 'var(--bg-elevated)' : 'var(--bg-surface)',
            color: isRunning ? 'var(--text-muted)' : 'var(--text-secondary)',
            border: '1px solid var(--border)',
            fontWeight: 500,
            fontSize: 12,
            cursor: isRunning ? 'not-allowed' : 'pointer'
          }}
        >
          🔲 Select Region
        </button>
      </div>

      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 10px',
        background: 'var(--bg-surface)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: statusColors[status],
            boxShadow: status !== 'idle' ? `0 0 8px ${statusColors[status]}` : 'none',
            animation: status === 'capturing' ? 'pulse 1.5s infinite' : 'none'
          }} />
          <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }`}</style>
          <span style={{ fontSize: 12, color: status !== 'idle' ? statusColors[status] : 'var(--text-muted)' }}>
            {statusLabels[status]}
          </span>
        </div>
        {region ? (
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
            {region.width}×{region.height} @ ({region.x},{region.y})
          </span>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>No region selected</span>
        )}
      </div>
    </div>
  )
}
