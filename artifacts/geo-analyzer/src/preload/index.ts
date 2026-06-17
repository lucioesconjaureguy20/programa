import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('api', {
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (data: { apiKey?: string; region?: any }) => ipcRenderer.invoke('save-settings', data),
  startCapture: () => ipcRenderer.invoke('start-capture'),
  stopCapture: () => ipcRenderer.invoke('stop-capture'),
  openSelector: () => ipcRenderer.invoke('open-selector'),
  regionSelected: (region: { x: number; y: number; width: number; height: number }) =>
    ipcRenderer.invoke('region-selected', region),
  closeSelector: () => ipcRenderer.invoke('close-selector'),
  getLogs: () => ipcRenderer.invoke('get-logs'),
  getLogsPath: () => ipcRenderer.invoke('get-logs-path'),
  openLogsFolder: () => ipcRenderer.invoke('open-logs-folder'),
  minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
  closeWindow: () => ipcRenderer.invoke('close-window'),
  captureSingle: () => ipcRenderer.invoke('capture-single'),

  onPrediction: (cb: (data: { result: any; timestamp: string }) => void) => {
    const handler = (_: any, data: any) => cb(data)
    ipcRenderer.on('prediction', handler)
    return () => ipcRenderer.removeListener('prediction', handler)
  },
  onCaptureStatus: (cb: (status: string) => void) => {
    const handler = (_: any, status: string) => cb(status)
    ipcRenderer.on('capture-status', handler)
    return () => ipcRenderer.removeListener('capture-status', handler)
  },
  onError: (cb: (msg: string) => void) => {
    const handler = (_: any, msg: string) => cb(msg)
    ipcRenderer.on('error', handler)
    return () => ipcRenderer.removeListener('error', handler)
  },
  onRegionUpdated: (cb: (region: any) => void) => {
    const handler = (_: any, region: any) => cb(region)
    ipcRenderer.on('region-updated', handler)
    return () => ipcRenderer.removeListener('region-updated', handler)
  }
})
