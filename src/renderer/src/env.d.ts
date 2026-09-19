/// <reference types="vite/client" />


interface SearchResult {
  type: string
  name: string
  description: string
  action: string
  revit_view_id: number
  project_id: number
}


interface ElectronAPI {

  ping: () => string

  openRevitResult: (
    result: SearchResult
  ) => Promise<{
    success: boolean
    message: string
  }>

}


declare global {

  interface Window {
    electronAPI: ElectronAPI
  }

}


export {}