import { useState, useEffect, useCallback, useRef } from 'react'
import { openpc, type Capabilities, type ScreenInfo, type WindowInfo } from './api/openpc'

// Auth token is still needed for the MJPEG <img> stream, which can't set
// headers (it appends ?token=...). All JSON calls go through the typed SDK
// in ./api/openpc, generated from the committed OpenAPI contract.
const AUTH_TOKEN = import.meta.env.VITE_OPENPC_TOKEN
const API_BASE = '/api'

function App() {
  // State
  const [screenInfo, setScreenInfo] = useState<ScreenInfo | null>(null)
  const [windows, setWindows] = useState<WindowInfo[]>([])
  const [connected, setConnected] = useState(false)
  const [commandInput, setCommandInput] = useState('')
  const [commandOutput, setCommandOutput] = useState<string[]>([])
  const [logs, setLogs] = useState<string[]>([])
  const [caps, setCaps] = useState<Capabilities | null>(null)

  // MJPEG stream URL - browser handles streaming automatically
  // Append auth token as query param when configured (img tags can't set headers)
  const streamUrl = `${API_BASE}/stream?fps=30&quality=80${AUTH_TOKEN ? `&token=${encodeURIComponent(AUTH_TOKEN)}` : ''}`

  // Stream reconnect: bumping this key forces the <img> to reload
  const [streamKey, setStreamKey] = useState(0)
  const streamRetry = useRef<number | null>(null)
  const handleStreamError = useCallback(() => {
    if (streamRetry.current) return
    streamRetry.current = window.setTimeout(() => {
      streamRetry.current = null
      setStreamKey(k => k + 1)
    }, 2000)
  }, [])

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
      const info = await openpc.screen()
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
      const wins = await openpc.windows()
      setWindows(wins)
    } catch (err) {
      addLog(`Windows error: ${err}`)
    }
  }, [addLog])

  // Initial load: screen + windows + server capabilities
  useEffect(() => {
    fetchScreenInfo()
    fetchWindows()
    openpc
      .capabilities()
      .then(setCaps)
      .catch(() => setCaps(null))
  }, [fetchScreenInfo, fetchWindows])

  // Live window list: poll the REST source of truth on an interval (SmolVM's
  // "REST is the source of truth" pattern). The dashboard stays in sync
  // without a manual refresh.
  useEffect(() => {
    const id = window.setInterval(() => {
      fetchWindows()
    }, 5000)
    return () => window.clearInterval(id)
  }, [fetchWindows])

  // Execute command
  const executeCommand = async (command: string) => {
    setCommandOutput(prev => [...prev, `$ ${command}`])
    try {
      const result = await openpc.runCommand(command, 30)
      const out = result.stdout
      const err = result.stderr
      if (out) setCommandOutput(prev => [...prev, out])
      if (err) setCommandOutput(prev => [...prev, err])
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
      await openpc.mouseClick(x, y, 'left', 1)
      addLog(`Clicked at (${x}, ${y})`)
    } catch (err) {
      addLog(`Click error: ${err}`)
    }
  }

  // Track mouse position
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!screenInfo || !screenRef.current) return

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
    { label: '↖', action: () => openpc.keyboardHotkey(['Alt', 'F9']), title: 'Minimize' },
    { label: '↗', action: () => openpc.keyboardHotkey(['Alt', 'F10']), title: 'Maximize' },
    { label: '✕', action: () => openpc.keyboardHotkey(['Alt', 'F4']), title: 'Close' },
  ]

  const appActions = [
    { label: 'Chrome', action: () => openpc.launchApp('google-chrome') },
    { label: 'Terminal', action: () => openpc.launchApp('xfce4-terminal') },
    { label: 'Files', action: () => openpc.launchApp('thunar') },
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
          {caps && (
            <span style={{ marginLeft: '12px', color: 'var(--text-secondary)', fontSize: '12px' }}>
              server v{caps.version} · {caps.ws_commands.length} tools
            </span>
          )}
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
            key={streamKey}
            src={streamUrl}
            alt="Desktop Stream"
            onClick={handleScreenClick}
            onError={handleStreamError}
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
                  openpc.openUrl(e.currentTarget.value)
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
                  openpc.keyboardType(e.currentTarget.value)
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
            <button className="btn" onClick={() => openpc.keyboardHotkey(['ctrl', 'c'])}>
              Copy
            </button>
            <button className="btn" onClick={() => openpc.keyboardHotkey(['ctrl', 'v'])}>
              Paste
            </button>
            <button className="btn" onClick={() => openpc.keyboardPress('escape')}>
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
            <button className="btn" onClick={() => openpc.mouseClick(mousePos.x, mousePos.y, 'left')}>
              Left
            </button>
            <button className="btn" onClick={() => openpc.mouseClick(mousePos.x, mousePos.y, 'right')}>
              Right
            </button>
            <button className="btn" onClick={() => openpc.mouseDoubleClick(mousePos.x, mousePos.y)}>
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
                  onClick={() => openpc.focusWindow(win.id)}
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