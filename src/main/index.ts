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


ipcMain.handle(
  'open-revit-result',
  async (_event, result) => {

    console.log('')
    console.log('================================')
    console.log(
      'Revit result received from React:'
    )
    console.log(result)
    console.log('================================')


    try {

      console.log(
        'Attempting connection to Revit plugin...'
      )

      console.log(
        'Target: http://127.0.0.1:8765/'
      )


      const controller =
        new AbortController()

      const timeout =
        setTimeout(() => {

          console.log(
            'Revit connection timed out after 5 seconds'
          )

          controller.abort()

        }, 5000)


      console.log(
        'Sending HTTP POST request...'
      )


      const response = await fetch(
        'http://127.0.0.1:8765/',
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json',
          },

          body: JSON.stringify(result),

          signal: controller.signal,
        }
      )


      clearTimeout(timeout)


      console.log(
        'HTTP response received from Revit'
      )

      console.log(
        'HTTP status:',
        response.status
      )


      const responseText =
        await response.text()


      console.log(
        'Revit plugin response:',
        responseText
      )


      if (!response.ok) {

        throw new Error(
          `Revit returned HTTP ${response.status}: ${responseText}`
        )

      }

      let parsedResponse: any = null
      try {
        parsedResponse = JSON.parse(responseText)
      } catch {
        // Not JSON
      }

      if (parsedResponse && typeof parsedResponse === 'object' && parsedResponse.success === false) {

        return {
          success: false,

          message:
            parsedResponse.message || 'The requested action failed in Revit.',
        }

      }

      console.log(
        'Revit communication successful'
      )


      return {
        success: true,

        message:
          parsedResponse?.message || `Request sent to Revit: ${result.name}`,
      }

    }
    catch (error) {

      console.error('')
      console.error(
        '================================'
      )
      console.error(
        'ERROR communicating with Revit'
      )
      console.error(
        '================================'
      )
      console.error(error)


      if (
        error instanceof Error &&
        error.name === 'AbortError'
      ) {

        return {
          success: false,

          message:
            'Connection to the Revit plugin timed out after 5 seconds.',
        }

      }


      return {
        success: false,

        message:
          `Could not communicate with the Revit plugin: ${
            error instanceof Error
              ? error.message
              : 'Unknown error'
          }`,
      }

    }

  }
)


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