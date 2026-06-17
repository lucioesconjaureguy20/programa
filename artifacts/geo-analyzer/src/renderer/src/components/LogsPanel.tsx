interface Props {
  logs: any[]
  onRefresh: () => void
  onOpenFolder: () => void
}

function ConfidenceDot({ value }: { value: string }) {
  const colors: Record<string, string> = { high: '#3ecf8e', medium: '#f59e0b', low: '#ef4444' }
  return (
    <span style={{
      display: 'inline-block',
      width: 8,
      height: 8,
      borderRadius: '50%',
      background: colors[value?.toLowerCase()] ?? '#555'
    }} />
  )
}

export default function LogsPanel({ logs, onRefresh, onOpenFolder }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={onRefresh}
          style={{
            flex: 1,
            padding: '7px 0',
            borderRadius: 'var(--radius)',
            background: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border)',
            fontSize: 12
          }}
        >
          ↻ Refresh
        </button>
        <button
          onClick={onOpenFolder}
          style={{
            flex: 1,
            padding: '7px 0',
            borderRadius: 'var(--radius)',
            background: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border)',
            fontSize: 12
          }}
        >
          📁 Open Folder
        </button>
      </div>

      {logs.length === 0 ? (
        <div style={{
          textAlign: 'center',
          color: 'var(--text-muted)',
          padding: '40px 20px',
          fontSize: 12
        }}>
          <div style={{ fontSize: 30, marginBottom: 8, opacity: 0.4 }}>📋</div>
          No logs yet for today. Start capturing to generate predictions.
        </div>
      ) : (
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
            Last {logs.length} predictions (today)
          </div>
          {logs.map((entry, i) => {
            const r = entry.prediction
            return (
              <div key={i} style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '8px 10px',
                marginBottom: 6,
                display: 'grid',
                gridTemplateColumns: '1fr auto',
                alignItems: 'start',
                gap: 8
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                    <ConfidenceDot value={r?.confidence} />
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{r?.country || '—'}</span>
                    {r?.city && <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>· {r.city}</span>}
                  </div>
                  {r?.exact_location && (
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                      {r.exact_location}
                    </div>
                  )}
                  {r?.coordinates?.lat != null && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'monospace', marginTop: 2 }}>
                      {r.coordinates.lat.toFixed(4)}, {r.coordinates.lng.toFixed(4)}
                    </div>
                  )}
                  {r?.clues?.length > 0 && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
                      {r.clues.slice(0, 3).join(' · ')}
                    </div>
                  )}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap', textAlign: 'right' }}>
                  <div>{new Date(entry.timestamp).toLocaleTimeString()}</div>
                  <div style={{ marginTop: 2, color: r?.confidence === 'high' ? '#3ecf8e' : r?.confidence === 'medium' ? '#f59e0b' : '#ef4444' }}>
                    {r?.confidence || '—'}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
