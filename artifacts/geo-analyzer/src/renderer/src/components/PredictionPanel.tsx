import { Prediction } from '../App'

interface Props {
  predictions: Prediction[]
  isRunning: boolean
  region: any
}

function ConfidenceBadge({ value }: { value: string }) {
  const map: Record<string, string> = {
    high: 'badge badge-high',
    medium: 'badge badge-medium',
    low: 'badge badge-low'
  }
  const icons: Record<string, string> = { high: '●', medium: '◑', low: '○' }
  const cls = map[value?.toLowerCase()] ?? 'badge badge-neutral'
  return <span className={cls}>{icons[value?.toLowerCase()] ?? '?'} {value || '—'}</span>
}

function ClueList({ clues }: { clues: string[] }) {
  if (!clues?.length) return null
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
      {clues.map((c, i) => (
        <span key={i} style={{
          padding: '2px 7px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 999,
          fontSize: 11,
          color: 'var(--text-secondary)'
        }}>
          {c}
        </span>
      ))}
    </div>
  )
}

function CoordDisplay({ lat, lng }: { lat: number | null; lng: number | null }) {
  if (lat == null || lng == null) return <span style={{ color: 'var(--text-muted)' }}>—</span>
  const mapsUrl = `https://maps.google.com/?q=${lat},${lng}`
  return (
    <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--accent)' }}>
      {lat.toFixed(4)}, {lng.toFixed(4)}
    </span>
  )
}

function PredCard({ pred, isLatest }: { pred: Prediction; isLatest: boolean }) {
  const r = pred.result
  const hasError = r?.error

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: `1px solid ${isLatest ? 'var(--accent-dim)' : 'var(--border)'}`,
      borderRadius: 'var(--radius)',
      padding: '12px',
      marginBottom: 8
    }}>
      {hasError ? (
        <div style={{ color: '#ef4444', fontSize: 12 }}>
          <strong>Parse error</strong>
          <pre style={{ marginTop: 4, fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-muted)' }}>
            {r.raw}
          </pre>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.2 }}>
                {r.country || '—'}
              </div>
              {r.city && (
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                  📍 {r.city}
                </div>
              )}
            </div>
            <ConfidenceBadge value={r.confidence} />
          </div>

          {r.exact_location && (
            <div style={{
              padding: '6px 10px',
              background: 'var(--bg-elevated)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 12,
              color: 'var(--text-primary)',
              marginBottom: 8,
              borderLeft: '2px solid var(--accent)'
            }}>
              🏛 {r.exact_location}
            </div>
          )}

          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr',
            gap: 4,
            padding: '6px 10px',
            background: 'var(--bg-elevated)',
            borderRadius: 'var(--radius-sm)',
            marginBottom: 8
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Coordinates</div>
            <CoordDisplay lat={r.coordinates?.lat} lng={r.coordinates?.lng} />
          </div>

          {r.clues?.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Clues detected</div>
              <ClueList clues={r.clues} />
            </div>
          )}

          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
            {new Date(pred.timestamp).toLocaleTimeString()}
          </div>
        </>
      )}
    </div>
  )
}

export default function PredictionPanel({ predictions, isRunning, region }: Props) {
  if (predictions.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px 20px',
        color: 'var(--text-muted)',
        textAlign: 'center',
        gap: 12
      }}>
        <div style={{ fontSize: 36, opacity: 0.4 }}>🌍</div>
        {!region ? (
          <>
            <div style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>No region selected</div>
            <div style={{ fontSize: 12, lineHeight: 1.5 }}>
              Click <strong style={{ color: 'var(--text-primary)' }}>Select Region</strong> to draw a rectangle
              around your Street View area, then hit <strong style={{ color: 'var(--accent)' }}>Start</strong>.
            </div>
          </>
        ) : !isRunning ? (
          <>
            <div style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Ready to analyze</div>
            <div style={{ fontSize: 12, lineHeight: 1.5 }}>
              Hit <strong style={{ color: 'var(--accent)' }}>Start</strong> to begin capturing and analyzing
              your Street View every 5 seconds.
            </div>
          </>
        ) : (
          <>
            <div style={{ fontWeight: 600, color: 'var(--accent)' }}>Analyzing…</div>
            <div style={{ fontSize: 12 }}>Waiting for first prediction</div>
          </>
        )}
      </div>
    )
  }

  return (
    <div>
      {predictions.map((p, i) => (
        <PredCard key={p.timestamp} pred={p} isLatest={i === 0} />
      ))}
    </div>
  )
}
