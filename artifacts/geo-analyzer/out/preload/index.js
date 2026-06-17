"use strict";
const electron = require("electron");
electron.contextBridge.exposeInMainWorld("api", {
  getSettings: () => electron.ipcRenderer.invoke("get-settings"),
  saveSettings: (data) => electron.ipcRenderer.invoke("save-settings", data),
  startCapture: () => electron.ipcRenderer.invoke("start-capture"),
  stopCapture: () => electron.ipcRenderer.invoke("stop-capture"),
  openSelector: () => electron.ipcRenderer.invoke("open-selector"),
  regionSelected: (region) => electron.ipcRenderer.invoke("region-selected", region),
  closeSelector: () => electron.ipcRenderer.invoke("close-selector"),
  getLogs: () => electron.ipcRenderer.invoke("get-logs"),
  getLogsPath: () => electron.ipcRenderer.invoke("get-logs-path"),
  openLogsFolder: () => electron.ipcRenderer.invoke("open-logs-folder"),
  minimizeWindow: () => electron.ipcRenderer.invoke("minimize-window"),
  closeWindow: () => electron.ipcRenderer.invoke("close-window"),
  captureSingle: () => electron.ipcRenderer.invoke("capture-single"),
  onPrediction: (cb) => {
    const handler = (_, data) => cb(data);
    electron.ipcRenderer.on("prediction", handler);
    return () => electron.ipcRenderer.removeListener("prediction", handler);
  },
  onCaptureStatus: (cb) => {
    const handler = (_, status) => cb(status);
    electron.ipcRenderer.on("capture-status", handler);
    return () => electron.ipcRenderer.removeListener("capture-status", handler);
  },
  onError: (cb) => {
    const handler = (_, msg) => cb(msg);
    electron.ipcRenderer.on("error", handler);
    return () => electron.ipcRenderer.removeListener("error", handler);
  },
  onRegionUpdated: (cb) => {
    const handler = (_, region) => cb(region);
    electron.ipcRenderer.on("region-updated", handler);
    return () => electron.ipcRenderer.removeListener("region-updated", handler);
  }
});
