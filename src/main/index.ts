import {
  app,
  BrowserWindow,
  ipcMain,
} from 'electron'

import { join } from 'node:path'

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,

    webPreferences: {
      preload: join(
        __dirname,
        '../preload/index.js'
      ),

      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    win.loadURL(
      process.env.ELECTRON_RENDERER_URL
    )
  } else {
    win.loadFile(
      join(
        __dirname,
        '../renderer/index.html'
      )
    )
  }
}


ipcMain.handle('open-revit-result', async (_event, result) => {
  console.log('')
  console.log('================================')
  console.log('Revit result received from React:', result)
  console.log('================================')

  const candidatePorts = [8765, 8766, 8767, 8768, 8769, 8770]

  for (const port of candidatePorts) {
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 3000)

      const response = await fetch(`http://127.0.0.1:${port}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(result),
        signal: controller.signal,
      })

      clearTimeout(timeout)

      if (response.ok) {
        const responseText = await response.text()
        console.log(`HTTP response received from Revit (port ${port}):`, responseText)

        let parsedResponse: any = null
        try {
          parsedResponse = JSON.parse(responseText)
        } catch {}

        if (parsedResponse && typeof parsedResponse === 'object' && parsedResponse.success === false) {
          return {
            success: false,
            message: parsedResponse.message || 'The requested action failed in Revit.',
          }
        }

        return {
          success: true,
          message: parsedResponse?.message || `Request sent to Revit: ${result.name}`,
        }
      }
    } catch {
      // Port unreachable, try next candidate port
    }
  }

  // Fallback to FastAPI backend proxy endpoint
  try {
    console.log('Direct Revit ports failed. Trying FastAPI backend proxy http://127.0.0.1:8000/revit-action...')
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)

    const response = await fetch('http://127.0.0.1:8000/revit-action', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(result),
      signal: controller.signal,
    })

    clearTimeout(timeout)

    if (response.ok) {
      const data = await response.json()
      return data
    }
  } catch (err) {
    console.error('FastAPI backend proxy failed:', err)
  }

  return {
    success: false,
    message: 'Could not communicate with the Revit plugin. Please check that Revit is running.',
  }
})


app.whenReady().then(() => {

  createWindow()


  app.on(
    'activate',
    () => {

      if (
        BrowserWindow.getAllWindows()
          .length === 0
      ) {

        createWindow()

      }

    }
  )

})


app.on(
  'window-all-closed',
  () => {

    if (
      process.platform !== 'darwin'
    ) {

      app.quit()

    }

  }
)