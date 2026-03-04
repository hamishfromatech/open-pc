# Desktop Container

The **Desktop Container** is the heart of Open-PC. It runs a complete Linux desktop environment with full automation capabilities, accessible via VNC and controllable through REST API and WebSocket.

## 📦 Container Overview

| Property | Value |
|----------|-------|
| **Base Image** | Ubuntu 22.04 LTS |
| **Desktop Environment** | XFCE4 |
| **VNC Server** | TigerVNC |
| **Web VNC** | noVNC |
| **API Framework** | FastAPI + Uvicorn |
| **Automation** | PyAutoGUI, MSS, xdotool |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Desktop Container                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Agent Server (Python)                        │ │
│  │                    Port 8080 (mapped to 8090)                  │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │ │
│  │  │ REST API     │  │ WebSocket    │  │ MJPEG Stream         │  │ │
│  │  │ Endpoints    │  │ /ws          │  │ /stream              │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │ │
│  └───────────────────────────┬────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                 Desktop Manager (Python)                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │ │
│  │  │ Mouse    │ │ Keyboard │ │ Windows  │ │ Screenshots      │  │ │
│  │  │ Control  │ │ Control  │ │ Manager │ │ & OCR            │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │ │
│  └───────────────────────────┬────────────────────────────────────┘ │
│                              │                                       │
│                              ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                  X11 / Display Server                          │ │
│  │                        Display :1                               │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │                  XFCE4 Desktop                            │  │ │
│  │  │  • Window Manager    • Panel    • File Manager            │  │ │
│  │  │  • Terminal         • Chrome   • System Tools            │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     VNC Layer                                   │ │
│  │  ┌────────────────────┐  ┌────────────────────────────────────┐ │ │
│  │  │ TigerVNC Server   │  │ noVNC Web Server                   │ │ │
│  │  │ Port 5901          │  │ Port 6080                          │ │ │
│  │  │ (Native Clients)  │  │ (Browser-based)                    │ │ │
│  │  └────────────────────┘  └────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Source Files

| File | Purpose |
|------|---------|
| `docker/Dockerfile` | Container image definition |
| `docker/agent_server.py` | FastAPI REST/WebSocket server |
| `docker/desktop_manager.py` | Desktop automation layer |
| `docker/startup.sh` | Container initialization script |
| `docker/xstartup` | VNC session startup |
| `docker/health_check.py` | Docker health check |
| `docker/requirements.txt` | Python dependencies |

## 🚀 Services & Ports

| Port | Service | Protocol | Description |
|------|---------|----------|-------------|
| 5901 | TigerVNC | VNC | Native VNC client connections |
| 6080 | noVNC | HTTP/WebSocket | Browser-based VNC access |
| 8080 | Agent API | HTTP | REST API and WebSocket (mapped to 8090) |

## 🔌 REST API Reference

### Screenshot Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/screenshot` | Get screenshot as PNG image |
| `GET` | `/screenshot/base64` | Get screenshot as base64 JSON |
| `GET` | `/screenshot/region?x=&y=&width=&height=` | Get region screenshot |
| `GET` | `/stream` | MJPEG video stream (30 FPS) |

**MJPEG Stream Parameters:**
- `fps` — Frames per second (default: 30)
- `quality` — JPEG quality 1-100 (default: 80)

```bash
# Example: Get screenshot
curl http://localhost:8090/screenshot --output screen.png

# Example: MJPEG stream in browser
<img src="http://localhost:8090/stream?fps=30&quality=80">
```

### Mouse Endpoints

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `GET` | `/mouse/position` | — | Get current cursor position |
| `POST` | `/mouse/move` | `{"x": 500, "y": 300}` | Move cursor to position |
| `POST` | `/mouse/click` | `{"x": 100, "y": 200, "button": "left"}` | Click at position |
| `POST` | `/mouse/double-click` | `{"x": 100, "y": 200}` | Double click |
| `POST` | `/mouse/right-click` | `{"x": 100, "y": 200}` | Right click |
| `POST` | `/mouse/scroll` | `{"clicks": 3, "direction": "down"}` | Scroll wheel |
| `POST` | `/mouse/drag` | `{"start_x": 100, "start_y": 100, "end_x": 300, "end_y": 300}` | Drag operation |

**Click Parameters:**
- `x`, `y` — Screen coordinates
- `button` — `"left"`, `"right"`, `"middle"` (default: left)
- `clicks` — Number of clicks (default: 1)
- `duration` — Click duration in seconds

### Keyboard Endpoints

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/keyboard/type` | `{"text": "Hello", "interval": 0.05}` | Type text |
| `POST` | `/keyboard/press` | `{"key": "enter"}` | Press single key |
| `POST` | `/keyboard/hotkey` | `{"keys": ["ctrl", "c"]}` | Press key combination |
| `POST` | `/keyboard/down` | `{"key": "shift"}` | Hold key down |
| `POST` | `/keyboard/up` | `{"key": "shift"}` | Release key |

**Common Keys:**
- Letters: `"a"`, `"b"`, `"c"`, etc.
- Special: `"enter"`, `"escape"`, `"tab"`, `"backspace"`, `"delete"`, `"space"`
- Arrows: `"up"`, `"down"`, `"left"`, `"right"`
- Function: `"f1"` through `"f12"`

### Window Endpoints

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `GET` | `/windows` | — | List all windows |
| `GET` | `/windows/active` | — | Get active window |
| `POST` | `/windows/focus` | `{"window_id": "abc123"}` | Focus window |
| `POST` | `/windows/close` | `{"window_id": "abc123"}` | Close window |
| `POST` | `/windows/maximize` | `{"window_id": "abc123"}` | Maximize window |
| `POST` | `/windows/minimize` | `{"window_id": "abc123"}` | Minimize window |

### Application Endpoints

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/apps/launch` | `{"application": "google-chrome"}` | Launch application |
| `POST` | `/apps/open-url` | `{"url": "https://github.com"}` | Open URL in browser |
| `POST` | `/apps/run` | `{"command": "ls -la", "timeout": 30}` | Run shell command |

**Pre-installed Applications:**
- `google-chrome` — Web browser
- `xfce4-terminal` — Terminal emulator
- `thunar` — File manager
- `code` — VS Code (if installed)

### Screen Info

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/screen` | Get screen dimensions and cursor position |
| `GET` | `/health` | Health check endpoint |

### OCR Endpoint

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/ocr` | `{"x": 0, "y": 0, "width": 500, "height": 200}` | OCR screen region |

## 🔌 WebSocket API

Connect to `ws://localhost:8090/ws` for real-time control.

### Authentication

```json
{
  "type": "auth",
  "password": "openpc"
}
```

Response:
```json
{
  "type": "auth_success",
  "client_id": "abc12345"
}
```

### Execute Commands

```json
{
  "type": "command",
  "command": "click",
  "parameters": {"x": 100, "y": 200}
}
```

Response:
```json
{
  "type": "result",
  "command": "click",
  "data": {"success": true}
}
```

### Available Commands

| Command | Parameters | Description |
|---------|------------|-------------|
| `screenshot` | — | Capture screenshot |
| `click` | `x`, `y`, `button`, `clicks` | Mouse click |
| `double_click` | `x`, `y` | Double click |
| `right_click` | `x`, `y` | Right click |
| `move_mouse` | `x`, `y`, `duration` | Move cursor |
| `drag` | `start_x`, `start_y`, `end_x`, `end_y`, `duration` | Drag operation |
| `scroll` | `clicks`, `direction` | Scroll wheel |
| `type` | `text`, `interval` | Type text |
| `press` | `key` | Press key |
| `hotkey` | `keys[]` | Key combination |
| `list_windows` | — | List windows |
| `focus_window` | `window_id` | Focus window |
| `close_window` | `window_id` | Close window |
| `launch` | `application` | Launch app |
| `open_url` | `url`, `browser` | Open URL |
| `run_command` | `command`, `timeout` | Run shell command |
| `ocr` | — | OCR screenshot |
| `screen_info` | — | Get screen info |
| `wait` | `seconds` | Wait duration |

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VNC_PASSWORD` | `openpc` | VNC access password |
| `VNC_RESOLUTION` | `1920x1080` | Screen resolution |
| `VNC_COL_DEPTH` | `24` | Color depth |
| `AGENT_HOST` | `0.0.0.0` | Agent server bind host |
| `AGENT_PORT` | `8080` | Agent server port |
| `AUTH_REQUIRED` | `true` | Require WebSocket auth |

### Docker Compose

```yaml
open-pc-desktop:
  build:
    context: ./docker
    dockerfile: Dockerfile
  ports:
    - "5901:5901"   # VNC
    - "6080:6080"   # noVNC
    - "8090:8080"   # API
  environment:
    - VNC_PASSWORD=${VNC_PASSWORD:-openpc}
    - VNC_RESOLUTION=${VNC_RESOLUTION:-1920x1080}
    - AUTH_REQUIRED=${AUTH_REQUIRED:-true}
  volumes:
    - openpc-home:/home/desktop
    - openpc-logs:/var/log/openpc
```

## 🔧 Extending

### Adding New Automation Capabilities

The `DesktopManager` class in `desktop_manager.py` handles all automation. Add new methods here:

```python
def new_automation_feature(self, param: str) -> Dict[str, Any]:
    """New automation capability"""
    # Implementation
    return {"success": True, "result": "..."}
```

Then expose it via REST API in `agent_server.py`:

```python
@app.post("/new-feature")
async def new_feature(request: NewFeatureRequest):
    return desktop_manager.new_automation_feature(request.param)
```

### Custom Applications

Add applications to the Dockerfile:

```dockerfile
RUN apt-get update && apt-get install -y \
    your-application
```

---

<p align="center">
  <a href="../README.md">← Back to Main</a> •
  <a href="../mcp-server/">MCP Server →</a>
</p>