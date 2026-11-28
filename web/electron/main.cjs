const { app, BrowserWindow, ipcMain, Notification } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')
const os = require('os')

const isDev = !app.isPackaged
const WIN_TOAST_APP_ID = 'digitalboo.demo'

// Windows: cần AppUserModelId khớp toast AppId
if (process.platform === 'win32') {
  app.setAppUserModelId(WIN_TOAST_APP_ID)
}

/** @type {BrowserWindow | null} */
let mainWindow = null

function escapeXml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Toast thật ra Action Center / góc màn hình Windows 10/11. */
function showWindowsDesktopToast(title, body) {
  if (process.platform !== 'win32') return false
  const xml = `<?xml version="1.0" encoding="utf-8"?>
<toast activationType="foreground">
  <visual>
    <binding template="ToastGeneric">
      <text>${escapeXml(title)}</text>
      <text>${escapeXml(body)}</text>
    </binding>
  </visual>
</toast>`
  const tmp = path.join(os.tmpdir(), `digitalboo-toast-${Date.now()}.xml`)
  try {
    fs.writeFileSync(tmp, xml, 'utf8')
    const tmpPs = tmp.replace(/'/g, "''")
    const ps = `
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$xml = Get-Content -LiteralPath '${tmpPs}' -Raw -Encoding UTF8
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('${WIN_TOAST_APP_ID}')
$notifier.Show($toast)
Start-Sleep -Milliseconds 400
Remove-Item -LiteralPath '${tmpPs}' -Force -ErrorAction SilentlyContinue
`
    const child = spawn(
      'powershell.exe',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-Command', ps],
      { detached: true, stdio: 'ignore', windowsHide: true },
    )
    child.unref()
    return true
  } catch (e) {
    console.error('[notify] Windows desktop toast failed', e)
    try {
      fs.unlinkSync(tmp)
    } catch {
      /* ignore */
    }
    return false
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 720,
    minWidth: 800,
    minHeight: 560,
    backgroundColor: '#ffffff',
    show: false,
    frame: false,
    title: 'Haven',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

ipcMain.handle('window:minimize', () => {
  mainWindow?.minimize()
})

ipcMain.handle('window:maximize', () => {
  if (!mainWindow) return
  if (mainWindow.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow.maximize()
  }
})

ipcMain.handle('window:close', () => {
  mainWindow?.close()
})

ipcMain.handle('app:notify', (_event, payload) => {
  const title = String(payload?.title || 'digitalboo')
  const body = String(payload?.body || 'Có thông báo mới')
  // Ưu tiên toast desktop Windows (ra ngoài app)
  const desktop = showWindowsDesktopToast(title, body)
  try {
    if (Notification.isSupported()) {
      const n = new Notification({ title, body, silent: false })
      n.show()
    }
  } catch (e) {
    console.error('[notify] Electron Notification failed', e)
  }
  console.log('[notify] desktop=', desktop, title, body)
  return desktop
})

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
