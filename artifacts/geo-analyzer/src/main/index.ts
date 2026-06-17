import {
  app,
  BrowserWindow,
  ipcMain,
  screen,
  shell,
  nativeImage,
  desktopCapturer,
  globalShortcut
} from 'electron'
import { join } from 'path'
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs'
import Store from 'electron-store'
import OpenAI from 'openai'

const store = new Store<{
  apiKey: string
  region: { x: number; y: number; width: number; height: number } | null
}>()

let mainWindow: BrowserWindow | null = null
let selectorWindow: BrowserWindow | null = null
let captureInterval: ReturnType<typeof setInterval> | null = null
let isCapturing = false
let currentRegion: { x: number; y: number; width: number; height: number } | null =
  store.get('region', null)

const logsDir = join(app.getPath('userData'), 'prediction-logs')
if (!existsSync(logsDir)) mkdirSync(logsDir, { recursive: true })

function createMainWindow(): void {
  mainWindow = new BrowserWindow({
    width: 440,
    height: 680,
    alwaysOnTop: true,
    frame: false,
    transparent: false,
    resizable: true,
    skipTaskbar: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true
    },
    backgroundColor: '#0f0f0f',
    titleBarStyle: 'hidden',
    vibrancy: 'under-window'
  })

  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  mainWindow.setAlwaysOnTop(true, 'screen-saver')

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function createSelectorWindow(): void {
  const { width, height } = screen.getPrimaryDisplay().bounds

  selectorWindow = new BrowserWindow({
    x: 0,
    y: 0,
    width,
    height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    fullscreen: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true
    }
  })

  selectorWindow.setIgnoreMouseEvents(false)

  if (process.env.ELECTRON_RENDERER_URL) {
    selectorWindow.loadURL(process.env.ELECTRON_RENDERER_URL + '/selector.html')
  } else {
    selectorWindow.loadFile(join(__dirname, '../renderer/selector.html'))
  }

  selectorWindow.on('closed', () => {
    selectorWindow = null
  })
}

async function captureRegion(region: {
  x: number
  y: number
  width: number
  height: number
}): Promise<string | null> {
  try {
    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: {
        width: screen.getPrimaryDisplay().bounds.width,
        height: screen.getPrimaryDisplay().bounds.height
      }
    })

    if (!sources.length) return null

    const source = sources[0]
    const fullImage = source.thumbnail

    const cropped = fullImage.crop({
      x: Math.max(0, region.x),
      y: Math.max(0, region.y),
      width: Math.min(region.width, fullImage.getSize().width - region.x),
      height: Math.min(region.height, fullImage.getSize().height - region.y)
    })

    const resized = cropped.resize({ width: Math.min(1280, cropped.getSize().width) })
    return resized.toJPEG(85).toString('base64')
  } catch (err) {
    console.error('Capture error:', err)
    return null
  }
}

async function analyzeWithOpenAI(base64Image: string, apiKey: string): Promise<object> {
  const client = new OpenAI({ apiKey })

  const response = await client.chat.completions.create({
    model: 'gpt-4o',
    max_tokens: 400,
    messages: [
      {
        role: 'system',
        content: `You are a GeoGuessr expert. Analyze the Street View image and respond ONLY with a valid JSON object (no markdown, no code blocks) with this exact structure:
{
  "country": "string or null",
  "city": "string or null",
  "exact_location": "string or null",
  "coordinates": { "lat": number or null, "lng": number or null },
  "confidence": "high|medium|low",
  "clues": ["string", ...]
}
Be fast and concise. Focus on visual clues: road signs, vegetation, architecture, driving side, sun angle, language.`
      },
      {
        role: 'user',
        content: [
          {
            type: 'image_url',
            image_url: {
              url: `data:image/jpeg;base64,${base64Image}`,
              detail: 'low'
            }
          },
          {
            type: 'text',
            text: 'Where is this Street View location? Respond only with the JSON.'
          }
        ]
      }
    ]
  })

  const text = response.choices[0]?.message?.content?.trim() ?? '{}'
  try {
    return JSON.parse(text)
  } catch {
    const match = text.match(/\{[\s\S]*\}/)
    if (match) return JSON.parse(match[0])
    return { error: 'Parse error', raw: text }
  }
}

function savePredictionLog(prediction: object, imageBase64?: string): void {
  const timestamp = new Date().toISOString()
  const logEntry = {
    timestamp,
    prediction,
    region: currentRegion
  }

  const logFile = join(logsDir, `predictions-${new Date().toISOString().split('T')[0]}.jsonl`)
  const line = JSON.stringify(logEntry) + '\n'
  writeFileSync(logFile, line, { flag: 'a' })
}

async function runCaptureLoop(): Promise<void> {
  if (!currentRegion || isCapturing) return

  const apiKey = store.get('apiKey', '')
  if (!apiKey) {
    mainWindow?.webContents.send('error', 'No API key set. Please enter your OpenAI API key in settings.')
    return
  }

  isCapturing = true
  mainWindow?.webContents.send('capture-status', 'capturing')

  const tick = async () => {
    if (!isCapturing || !currentRegion) return

    mainWindow?.webContents.send('capture-status', 'analyzing')

    try {
      const base64 = await captureRegion(currentRegion)
      if (!base64) {
        mainWindow?.webContents.send('error', 'Failed to capture screen region')
        return
      }

      const result = await analyzeWithOpenAI(base64, apiKey)
      savePredictionLog(result)
      mainWindow?.webContents.send('prediction', { result, timestamp: new Date().toISOString() })
      mainWindow?.webContents.send('capture-status', 'capturing')
    } catch (err: any) {
      const msg = err?.message ?? String(err)
      mainWindow?.webContents.send('error', `Analysis error: ${msg}`)
      mainWindow?.webContents.send('capture-status', 'capturing')
    }
  }

  await tick()
  captureInterval = setInterval(tick, 5000)
}

function stopCaptureLoop(): void {
  isCapturing = false
  if (captureInterval) {
    clearInterval(captureInterval)
    captureInterval = null
  }
  mainWindow?.webContents.send('capture-status', 'idle')
}

ipcMain.handle('get-settings', () => ({
  apiKey: store.get('apiKey', ''),
  region: store.get('region', null)
}))

ipcMain.handle('save-settings', (_e, { apiKey, region }: { apiKey: string; region: any }) => {
  if (apiKey !== undefined) store.set('apiKey', apiKey)
  if (region !== undefined) {
    store.set('region', region)
    currentRegion = region
  }
})

ipcMain.handle('start-capture', async () => {
  if (!currentRegion) {
    mainWindow?.webContents.send('error', 'No region selected. Click "Select Region" first.')
    return
  }
  await runCaptureLoop()
})

ipcMain.handle('stop-capture', () => {
  stopCaptureLoop()
})

ipcMain.handle('open-selector', () => {
  if (selectorWindow) {
    selectorWindow.focus()
    return
  }
  createSelectorWindow()
})

ipcMain.handle('region-selected', (_e, region: { x: number; y: number; width: number; height: number }) => {
  currentRegion = region
  store.set('region', region)
  selectorWindow?.close()
  mainWindow?.webContents.send('region-updated', region)
  mainWindow?.focus()
})

ipcMain.handle('close-selector', () => {
  selectorWindow?.close()
  mainWindow?.focus()
})

ipcMain.handle('get-logs', () => {
  try {
    const logFile = join(logsDir, `predictions-${new Date().toISOString().split('T')[0]}.jsonl`)
    if (!existsSync(logFile)) return []
    const lines = readFileSync(logFile, 'utf-8').trim().split('\n').filter(Boolean)
    return lines.map((l) => {
      try { return JSON.parse(l) } catch { return null }
    }).filter(Boolean).reverse().slice(0, 50)
  } catch {
    return []
  }
})

ipcMain.handle('get-logs-path', () => logsDir)

ipcMain.handle('open-logs-folder', () => {
  shell.openPath(logsDir)
})

ipcMain.handle('minimize-window', () => mainWindow?.minimize())
ipcMain.handle('close-window', () => app.quit())

ipcMain.handle('capture-single', async () => {
  if (!currentRegion) return null
  return await captureRegion(currentRegion)
})

app.whenReady().then(() => {
  createMainWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
