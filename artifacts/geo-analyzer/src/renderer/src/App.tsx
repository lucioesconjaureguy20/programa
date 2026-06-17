import { useState, useEffect, useCallback, useRef } from 'react'
import TitleBar from './components/TitleBar'
import StatusBar from './components/StatusBar'
import PredictionPanel from './components/PredictionPanel'
import SettingsPanel from './components/SettingsPanel'
import LogsPanel from './components/LogsPanel'

declare global {
  interface Window {
    api: {
      getSettings: () => Promise<{ apiKey: string; region: any }>
      saveSettings: (data: { apiKey?: string; region?: any }) => Promise<void>
      startCapture: () => Promise<void>
      stopCapture: () => Promise<void>
      openSelector: () => Promise<void>
      regionSelected: (region: any) => Promise<void>
      closeSelector: () => Promise<void>
      getLogs: () => Promise<any[]>
      getLogsPath: () => Promise<string>
      openLogsFolder: () => Promise<void>
      minimizeWindow: () => Promise<void>
      closeWindow: () => Promise<void>
      captureSingle: () => Promise<string | null>
      onPrediction: (cb: (data: { result: any; timestamp: string }) => void) => () => void
      onCaptureStatus: (cb: (status: string) => void) => () => void
      onError: (cb: (msg: string) => void) => () => void
      onRegionUpdated: (cb: (region: any) => void) => () => void
    }
  }
}

type Tab = 'predict' | 'logs' | 'settings'
type CaptureStatus = 'idle' | 'capturing' | 'analyzing'

export interface Prediction {
  result: any
  timestamp: string
}

export default function App() {
  const [tab, setTab] = useState<Tab>('predict')
  const [status, setStatus] = useState<CaptureStatus>('idle')
  const [isRunning, setIsRunning] = useState(false)
  const [region, setRegion] = useState<any>(null)
  const [apiKey, setApiKey] = useState('')
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [error, setError] = useState<string | null>(null)
  const [logs, setLogs] = useState<any[]>([])

  const errorTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const showError = useCallback((msg: string) => {
    setError(msg)
    if (errorTimer.current) clearTimeout(errorTimer.current)
    errorTimer.current = setTimeout(() => setError(null), 6000)
  }, [])

  useEffect(() => {
    window.api.getSettings().then((s) => {
      setApiKey(s.apiKey || '')
      setRegion(s.region || null)
    })

    const offPrediction = window.api.onPrediction((data) => {
      setPredictions((prev) => [data, ...prev].slice(0, 20))
      setTab('predict')
    })
    const offStatus = window.api.onCaptureStatus((s) => {
      setStatus(s as CaptureStatus)
      if (s === 'idle') setIsRunning(false)
    })
    const offError = window.api.onError(showError)
    const offRegion = window.api.onRegionUpdated((r) => setRegion(r))

    return () => {
      offPrediction()
      offStatus()
      offError()
      offRegion()
    }
  }, [showError])

  const handleStart = async () => {
    if (!apiKey) {
      showError('Enter your OpenAI API key in Settings first.')
      setTab('settings')
      return
    }
    if (!region) {
      showError('Select a screen region first.')
      return
    }
    setIsRunning(true)
    setError(null)
    await window.api.startCapture()
  }

  const handleStop = async () => {
    await window.api.stopCapture()
    setIsRunning(false)
  }

  const handleSelectRegion = async () => {
    await window.api.openSelector()
  }

  const handleSaveApiKey = async (key: string) => {
    setApiKey(key)
    await window.api.saveSettings({ apiKey: key })
  }

  const handleLoadLogs = async () => {
    const l = await window.api.getLogs()
    setLogs(l)
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      background: 'var(--bg)',
      border: '1px solid #2a2a2a',
      borderRadius: '10px',
      overflow: 'hidden'
    }}>
      <TitleBar />

      {error && (
        <div style={{
          background: '#2a1515',
          border: '1px solid #5c2020',
          borderRadius: 6,
          margin: '0 12px',
          padding: '8px 12px',
          fontSize: 12,
          color: '#ff7070',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)} style={{ background: 'none', color: '#888', fontSize: 16, padding: '0 4px' }}>×</button>
        </div>
      )}

      <StatusBar
        status={status}
        isRunning={isRunning}
        region={region}
        onStart={handleStart}
        onStop={handleStop}
        onSelectRegion={handleSelectRegion}
      />

      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 12px' }}>
        {(['predict', 'logs', 'settings'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t)
              if (t === 'logs') handleLoadLogs()
            }}
            style={{
              background: 'none',
              color: tab === t ? 'var(--accent)' : 'var(--text-secondary)',
              borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
              padding: '10px 14px',
              fontSize: 12,
              fontWeight: tab === t ? 600 : 400,
              textTransform: 'capitalize',
              letterSpacing: '0.02em',
              transition: 'color 0.15s'
            }}
          >
            {t === 'predict' ? '📍 Predict' : t === 'logs' ? '📋 Logs' : '⚙ Settings'}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
        {tab === 'predict' && (
          <PredictionPanel predictions={predictions} isRunning={isRunning} region={region} />
        )}
        {tab === 'logs' && (
          <LogsPanel logs={logs} onRefresh={handleLoadLogs} onOpenFolder={() => window.api.openLogsFolder()} />
        )}
        {tab === 'settings' && (
          <SettingsPanel apiKey={apiKey} onSave={handleSaveApiKey} region={region} />
        )}
      </div>
    </div>
  )
}
