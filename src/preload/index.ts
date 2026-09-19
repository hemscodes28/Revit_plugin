import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  ping: () => 'pong',

  openRevitResult: (result: Record<string, unknown>) => {
    return ipcRenderer.invoke(
      'open-revit-result',
      result
    )
  },
})