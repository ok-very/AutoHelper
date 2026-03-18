import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
  selectFolder: () => ipcRenderer.invoke("select-folder"),
});
