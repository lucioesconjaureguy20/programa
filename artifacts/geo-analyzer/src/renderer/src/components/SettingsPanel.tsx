import { useState } from 'react'

interface Props {
  apiKey: string
  region: any
  onSave: (key: string) => Promise<void>
}

export default function SettingsPanel({ apiKey, region, onSave }: Props) {
  const [draft, setDraft] = useState(apiKey)
  const [visible, setVisible] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    await onSave(draft)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const maskedKey = draft
    ? draft.slice(0, 7) + '●'.repeat(Math.max(0, draft.length - 11)) + draft.slice(-4)
    : ''

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <label style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          OpenAI API Key
        </label>
        <div style={{ position: 'relative' }}>
          <input
            type={visible ? 'text' : 'password'}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="sk-..."
            style={{
              width: '100%',
              padding: '9px 40px 9px 12px',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              color: 'var(--text-primary)',
              fontSize: 13
            }}
          />
          <button
            onClick={() => setVisible((v) => !v)}
            style={{
              position: 'absolute',
              right: 10,
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'none',
              color: 'var(--text-muted)',
              fontSize: 14,
              padding: 4
            }}
          >
            {visible ? '🙈' : '👁'}
          </button>
        </div>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
          Your API key is stored locally and never sent anywhere except OpenAI's API.
        </p>
      </div>

      <button
        onClick={handleSave}
        disabled={!draft}
        style={{
          padding: '9px 0',
          borderRadius: 'var(--radius)',
          background: saved ? 'var(--accent-dim)' : 'var(--accent)',
          color: saved ? 'var(--accent)' : '#000',
          fontWeight: 700,
          fontSize: 13,
          opacity: !draft ? 0.4 : 1,
          cursor: !draft ? 'not-allowed' : 'pointer'
        }}
      >
        {saved ? '✓ Saved' : 'Save API Key'}
      </button>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
          Current Region
        </div>
        {region ? (
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '10px 12px',
            fontFamily: 'monospace',
            fontSize: 12,
            color: 'var(--text-secondary)',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '6px 12px'
          }}>
            <span style={{ color: 'var(--text-muted)' }}>X:</span><span>{region.x}px</span>
            <span style={{ color: 'var(--text-muted)' }}>Y:</span><span>{region.y}px</span>
            <span style={{ color: 'var(--text-muted)' }}>Width:</span><span>{region.width}px</span>
            <span style={{ color: 'var(--text-muted)' }}>Height:</span><span>{region.height}px</span>
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, fontStyle: 'italic' }}>
            No region selected yet. Use the "Select Region" button on the main screen.
          </div>
        )}
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
          Analysis settings
        </div>
        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '10px 12px',
          fontSize: 12,
          color: 'var(--text-secondary)',
          display: 'grid',
          gap: 8
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)' }}>Model</span>
            <span>gpt-4o</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)' }}>Interval</span>
            <span>5 seconds</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)' }}>Image quality</span>
            <span>85% JPEG (low detail)</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)' }}>Max tokens</span>
            <span>400</span>
          </div>
        </div>
      </div>
    </div>
  )
}
