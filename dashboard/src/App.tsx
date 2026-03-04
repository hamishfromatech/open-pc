import { useState, useEffect, useCallback, useRef } from 'react'

// API base URL
const API_BASE = '/api'

// Types
interface ScreenInfo {
  width: number
  height: number
  cursor_x: number
  cursor_y: number
}

interface WindowInfo {
  id: string
  title: string
  x: number
  y: number
  width: number
  height: number
}

// API functions
const api = {
  async get(endpoint: string) {
    const response = await fetch(`${API_BASE}${endpoint}`)
    if (!response.ok) throw new Error(`API error: ${response.status}`)
    return response.json()
  },

  async post(endpoint: string, data?: Record<string, unknown>) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined
    })
    if (!response.ok) throw new Error(`API error: ${response.status}`)
    return response.json()
  }
}

function App() {
  // State
  const [screenInfo, setScreenInfo] = useState<ScreenInfo | null>(null)
  const [windows, setWindows] = useState<WindowInfo[]>([])
  const [connected, setConnected] = useState(false)
  const [commandInput, setCommandInput] = useState('')
  const [commandOutput, setCommandOutput] = useState<string[]>([])
  const [logs, setLogs] = useState<string[]>([])

  // MJPEG stream URL - browser handles streaming automatically
  const streamUrl = `${API_BASE}/stream?fps=30&quality=80`

  // Mouse tracking
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const screenRef = useRef<HTMLDivElement>(null)

  // Add log entry
  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [...prev.slice(-100), `[${timestamp}] ${message}`])
  }, [])

  // Fetch screen info
  const fetchScreenInfo = useCallback(async () => {
    try {
      const info = await api.get('/screen')
      setScreenInfo(info)
      setConnected(true)
    } catch (err) {
      setConnected(false)
      addLog(`Connection error: ${err}`)
    }
  }, [addLog])

  // Fetch windows
  const fetchWindows = useCallback(async () => {
    try {
      const result = await api.get('/windows')
      setWindows(result.windows || [])
    } catch (err) {
      addLog(`Windows error: ${err}`)
    }
  }, [addLog])

  // Initial load
  useEffect(() => {
    fetchScreenInfo()
    fetchWindows()
  }, [fetchScreenInfo, fetchWindows])

  // Execute command
  const executeCommand = async (command: string) => {
    setCommandOutput(prev => [...prev, `$ ${command}`])
    try {
      const result = await api.post('/apps/run', { command, timeout: 30 })
      if (result.stdout) setCommandOutput(prev => [...prev, result.stdout])
      if (result.stderr) setCommandOutput(prev => [...prev, result.stderr])
      addLog(`Command: ${command}`)
    } catch (err) {
      setCommandOutput(prev => [...prev, `Error: ${err}`])
      addLog(`Command error: ${err}`)
    }
  }

  // Mouse click on screen
  const handleScreenClick = async (e: React.MouseEvent<HTMLImageElement>) => {
    if (!screenInfo) return

    const img = e.currentTarget
    const rect = img.getBoundingClientRect()

    // Calculate actual coordinates
    const scaleX = screenInfo.width / rect.width
    const scaleY = screenInfo.height / rect.height

    const x = Math.round((e.clientX - rect.left) * scaleX)
    const y = Math.round((e.clientY - rect.top) * scaleY)

    try {
      await api.post('/mouse/click', { x, y, button: 'left', clicks: 1 })
      addLog(`Clicked at (${x}, ${y})`)
    } catch (err) {
      addLog(`Click error: ${err}`)
    }
  }

  // Track mouse position
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!screenInfo || !screenRef.current) return

    const rect = screenRef.current.getBoundingClientRect()
    const img = screenRef.current.querySelector('img')
    if (!img) return

    const imgRect = img.getBoundingClientRect()
    const scaleX = screenInfo.width / imgRect.width
    const scaleY = screenInfo.height / imgRect.height

    const x = Math.round((e.clientX - imgRect.left) * scaleX)
    const y = Math.round((e.clientY - imgRect.top) * scaleY)

    setMousePos({ x: Math.max(0, Math.min(x, screenInfo.width)), y: Math.max(0, Math.min(y, screenInfo.height)) })
  }

  // Quick actions
  const quickActions = [
    { label: '↖', action: () => api.post('/keyboard/hotkey', { keys: ['Alt', 'F9'] }), title: 'Minimize' },
    { label: '↗', action: () => api.post('/keyboard/hotkey', { keys: ['Alt', 'F10'] }), title: 'Maximize' },
    { label: '✕', action: () => api.post('/keyboard/hotkey', { keys: ['Alt', 'F4'] }), title: 'Close' },
  ]

  const appActions = [
    { label: 'Chrome', action: () => api.post('/apps/launch', { application: 'google-chrome' }) },
    { label: 'Terminal', action: () => api.post('/apps/launch', { application: 'xfce4-terminal' }) },
    { label: 'Files', action: () => api.post('/apps/launch', { application: 'thunar' }) },
  ]

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <h1>
          <span>◉</span> Open-PC Dashboard
        </h1>
        <div className="status">
          <div className={`status-dot ${connected ? 'connected' : ''}`} />
          <span>{connected ? 'Connected' : 'Disconnected'}</span>
          {screenInfo && (
            <span style={{ marginLeft: '12px', color: 'var(--text-secondary)' }}>
              {screenInfo.width} × {screenInfo.height}
            </span>
          )}
          <span style={{ marginLeft: '12px', color: 'var(--accent-green)', fontSize: '12px' }}>
            ● LIVE
          </span>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {/* Screen View - MJPEG Stream */}
        <div className="screen-container" ref={screenRef} onMouseMove={handleMouseMove}>
          <img
            src={streamUrl}
            alt="Desktop Stream"
            onClick={handleScreenClick}
            style={{ width: '100%', height: 'auto' }}
          />
          <div className="screenshot-info">
            Mouse: ({mousePos.x}, {mousePos.y})
          </div>
        </div>

        {/* Controls Bar */}
        <div className="controls-bar">
          <button className="btn btn-primary" onClick={fetchWindows}>
            🔄 Refresh Windows
          </button>

          <div className="input-group">
            <input
              type="text"
              placeholder="Open URL..."
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.currentTarget.value) {
                  api.post('/apps/open-url', { url: e.currentTarget.value })
                  e.currentTarget.value = ''
                }
              }}
            />
          </div>

          <div className="input-group">
            <input
              type="text"
              placeholder="Type text..."
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.currentTarget.value) {
                  api.post('/keyboard/type', { text: e.currentTarget.value })
                  e.currentTarget.value = ''
                }
              }}
            />
          </div>

          {quickActions.map((action, i) => (
            <button key={i} className="btn" onClick={action.action} title={action.title}>
              {action.label}
            </button>
          ))}
        </div>
      </main>

      {/* Sidebar */}
      <aside className="sidebar">
        {/* Quick Actions */}
        <section className="sidebar-section">
          <h3>Quick Actions</h3>
          <div className="quick-actions">
            {appActions.map((action, i) => (
              <button key={i} className="btn" onClick={action.action}>
                {action.label}
              </button>
            ))}
          </div>
          <div className="quick-actions" style={{ marginTop: '8px' }}>
            <button className="btn" onClick={() => api.post('/keyboard/hotkey', { keys: ['ctrl', 'c'] })}>
              Copy
            </button>
            <button className="btn" onClick={() => api.post('/keyboard/hotkey', { keys: ['ctrl', 'v'] })}>
              Paste
            </button>
            <button className="btn" onClick={() => api.post('/keyboard/press', { key: 'escape' })}>
              Esc
            </button>
          </div>
        </section>

        {/* Mouse Position */}
        <section className="sidebar-section">
          <h3>Mouse Control</h3>
          <div className="mouse-pos">
            <span>X: {mousePos.x}</span>
            <span>Y: {mousePos.y}</span>
          </div>
          <div className="quick-actions">
            <button className="btn" onClick={() => api.post('/mouse/click', { x: mousePos.x, y: mousePos.y, button: 'left' })}>
              Left
            </button>
            <button className="btn" onClick={() => api.post('/mouse/click', { x: mousePos.x, y: mousePos.y, button: 'right' })}>
              Right
            </button>
            <button className="btn" onClick={() => api.post('/mouse/double-click', { x: mousePos.x, y: mousePos.y })}>
              Double
            </button>
          </div>
        </section>

        {/* Windows */}
        <section className="sidebar-section">
          <h3>Windows</h3>
          <div className="windows-list">
            {windows.length === 0 ? (
              <div style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>No windows detected</div>
            ) : (
              windows.map((win) => (
                <div
                  key={win.id}
                  className="window-item"
                  onClick={() => api.post('/windows/focus', { window_id: win.id })}
                >
                  <span>{win.title || 'Untitled'}</span>
                  <span className="window-id">{win.id.slice(0, 8)}</span>
                </div>
              ))
            )}
          </div>
          <button className="btn" style={{ width: '100%', marginTop: '8px' }} onClick={fetchWindows}>
            ↻ Refresh
          </button>
        </section>

        {/* Terminal */}
        <section className="sidebar-section">
          <h3>Terminal</h3>
          <div className="terminal-container">
            <div className="terminal-output">
              <pre>{commandOutput.join('\n') || 'Terminal output will appear here...'}</pre>
            </div>
            <div className="terminal-input">
              <input
                type="text"
                value={commandInput}
                onChange={(e) => setCommandInput(e.target.value)}
                placeholder="Run command..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && commandInput.trim()) {
                    executeCommand(commandInput)
                    setCommandInput('')
                  }
                }}
              />
              <button className="btn btn-primary" onClick={() => {
                if (commandInput.trim()) {
                  executeCommand(commandInput)
                  setCommandInput('')
                }
              }}>
                Run
              </button>
            </div>
          </div>
        </section>

        {/* Logs */}
        <section className="sidebar-section" style={{ flex: 1, minHeight: 0 }}>
          <h3>Logs</h3>
          <div className="logs-container">
            <textarea
              value={logs.join('\n')}
              readOnly
              placeholder="Activity logs..."
            />
          </div>
        </section>
      </aside>
    </div>
  )
}

export default App