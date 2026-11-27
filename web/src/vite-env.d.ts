/// <reference types="vite/client" />

interface ElectronAPI {
  minimize: () => Promise<void>
  maximize: () => Promise<void>
  close: () => Promise<void>
  notify?: (title: string, body: string) => Promise<boolean>
}

interface Window {
  electronAPI?: ElectronAPI
}
