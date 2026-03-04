# MCP Server

The **MCP Server** provides native integration with AI assistants using the Model Context Protocol (MCP). Built on FastMCP, it exposes 22+ desktop control tools that AI assistants can use to interact with the Linux desktop.

## 📦 Container Overview

| Property | Value |
|----------|-------|
| **Base Image** | Python 3.11 Slim |
| **Framework** | FastMCP 3.x |
| **Transport** | SSE (Server-Sent Events) |
| **Port** | 8000 (mapped to 8091) |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          MCP Server                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    FastMCP Application                          │ │
│  │                    SSE Transport                               │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │                  Tool Registry                           │  │ │
│  │  │  • Screenshot Tools    • Mouse Tools                      │  │ │
│  │  │  • Keyboard Tools      • Window Tools                     │  │ │
│  │  │  • Application Tools   • Utility Tools                    │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────┬────────────────────────────────────┘ │
│                                │                                     │
│                                ▼                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                   OpenPC Client                                │ │
│  │                   (HTTP Client)                                │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │  • Screenshot capture    • Mouse operations              │  │ │
│  │  │  • Keyboard input        • Window management             │  │ │
│  │  │  • Application launch    • OCR & commands               │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────┬────────────────────────────────────┘ │
│                                │                                     │
│                                ▼                                     │
│                     HTTP Requests to Desktop Container               │
│                           (Port 8080)                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Source Files

| File | Purpose |
|------|---------|
| `mcp-server/Dockerfile` | Container image definition |
| `mcp-server/openpc_mcp.py` | FastMCP server implementation |
| `mcp-server/requirements.txt` | Python dependencies |

## 🚀 Connection

### MCP Client Configuration

Configure your AI assistant to connect to Open-PC:

**Claude Desktop / MCP Client:**
```json
{
  "mcpServers": {
    "open-pc": {
      "type": "streamable-http",
      "url": "http://localhost:8091"
    }
  }
}
```

**Alternative SSE configuration:**
```json
{
  "mcpServers": {
    "open-pc": {
      "transport": "sse",
      "url": "http://localhost:8091/sse"
    }
  }
}
```

### Docker Compose

```yaml
open-pc-mcp:
  build:
    context: ./mcp-server
    dockerfile: Dockerfile
  ports:
    - "8091:8000"
  environment:
    - OPENPC_HOST=open-pc-desktop
    - OPENPC_PORT=8080
    - OPENPC_PASSWORD=${VNC_PASSWORD:-openpc}
  depends_on:
    open-pc-desktop:
      condition: service_healthy
```

## 🛠️ Available Tools

### 👁️ Screenshot Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `take_screenshot` | Capture screen as base64 | — |
| `get_screen_size` | Get dimensions and cursor position | — |

**Example:**
```python
# Take screenshot
result = await take_screenshot()
# Returns: base64-encoded PNG

# Get screen info
info = await get_screen_size()
# Returns: {"width": 1920, "height": 1080, "cursor_x": 500, "cursor_y": 300}
```

### 🖱️ Mouse Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `move_mouse` | Move cursor to position | `x`, `y` |
| `click` | Click at position | `x`, `y`, `button` (left/right/middle), `clicks` |
| `double_click` | Double click | `x`, `y` |
| `right_click` | Right click | `x`, `y` |
| `scroll` | Scroll mouse wheel | `clicks`, `direction` (up/down) |
| `drag` | Drag from A to B | `start_x`, `start_y`, `end_x`, `end_y`, `duration` |

**Example:**
```python
# Move and click
await move_mouse(x=500, y=300)
await click(x=500, y=300, button="left", clicks=1)

# Drag operation
await drag(start_x=100, start_y=100, end_x=400, end_y=400, duration=0.5)

# Scroll
await scroll(clicks=5, direction="down")
```

### ⌨️ Keyboard Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `type_text` | Type text string | `text`, `interval` (0.05 default) |
| `press_key` | Press single key | `key` |
| `press_hotkey` | Press key combination | `keys` (comma or plus separated) |

**Example:**
```python
# Type text
await type_text("Hello, World!")

# Press keys
await press_key("enter")
await press_key("escape")

# Hotkey combinations
await press_hotkey("ctrl+c")
await press_hotkey("ctrl+shift+escape")
await press_hotkey("ctrl,alt,delete")
```

**Common Keys:**
- Letters: `a` through `z`
- Numbers: `0` through `9`
- Special: `enter`, `escape`, `tab`, `backspace`, `delete`, `space`
- Arrows: `up`, `down`, `left`, `right`
- Navigation: `home`, `end`, `pageup`, `pagedown`
- Function: `f1` through `f12`
- Modifiers: `ctrl`, `alt`, `shift`, `meta`/`cmd`

### 🪟 Window Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `list_windows` | List all open windows | — |
| `focus_window` | Focus (bring to front) window | `window_id` |
| `close_window` | Close window | `window_id` (optional, closes active if omitted) |
| `maximize_window` | Maximize window | `window_id` (optional) |
| `minimize_window` | Minimize window | `window_id` (optional) |

**Example:**
```python
# List windows
windows = await list_windows()
# Returns: List of {"id": "...", "title": "...", "x": 0, "y": 0, "width": 800, "height": 600}

# Focus specific window
await focus_window(window_id="0x1234567")

# Close active window
await close_window()

# Maximize window
await maximize_window(window_id="0x1234567")
```

### 📱 Application Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `launch_application` | Launch application | `application` |
| `open_url` | Open URL in browser | `url` |
| `run_command` | Run shell command | `command`, `timeout` (30 default) |

**Example:**
```python
# Launch applications
await launch_application("google-chrome")
await launch_application("xfce4-terminal")
await launch_application("thunar")  # File manager

# Open URL
await open_url("https://github.com")

# Run shell command
result = await run_command("ls -la", timeout=30)
# Returns: {"stdout": "...", "stderr": "...", "return_code": 0}
```

### 🔧 Utility Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `perform_ocr` | OCR text from screen | — |
| `wait_seconds` | Wait for duration | `seconds` |

**Example:**
```python
# OCR screen
text = await perform_ocr()
# Returns: Extracted text from screen

# Wait for app to load
await wait_seconds(2.5)
```

## 📚 Resources

The MCP server also provides a resource for getting desktop status:

| Resource URI | Description |
|--------------|-------------|
| `desktop://status` | Current screen info and window count |

**Example:**
```python
# Read resource
status = await read_resource("desktop://status")
# Returns: {"screen": {...}, "window_count": 5, "agent_url": "..."}
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENPC_HOST` | `open-pc-desktop` | Desktop container hostname |
| `OPENPC_PORT` | `8080` | Desktop API port |
| `OPENPC_PASSWORD` | `openpc` | Authentication password |

### Tool Execution Flow

```
AI Assistant Request
        │
        ▼
┌───────────────────┐
│   FastMCP Server  │
│   (Port 8091)     │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Tool Handler     │
│  (openpc_mcp.py)  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  OpenPC Client    │
│  (HTTP Client)    │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Desktop Container│
│  (Port 8080)      │
└───────────────────┘
```

## 📝 Example AI Prompts

Here are examples of what you can ask an AI assistant connected to Open-PC:

```
"Take a screenshot and tell me what you see."

"Open Chrome and navigate to github.com"

"List all open windows and focus on the terminal."

"Click on the 'Submit' button in the screenshot."

"Type 'Hello World' in the active text field."

"Press Ctrl+S to save the current document."

"Run 'ls -la' in the terminal and show me the output."
```

## 🔍 Debugging

### Check MCP Server Logs

```bash
docker compose logs -f open-pc-mcp
```

### Test Connection

```bash
# Health check
curl http://localhost:8091/

# Should return FastMCP info
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Connection refused | Ensure desktop container is healthy |
| Tool execution fails | Check desktop container logs |
| Screenshot timeout | Increase timeout, check X11 status |

---

<p align="center">
  <a href="../desktop/">← Desktop</a> •
  <a href="../README.md">Main Docs</a> •
  <a href="../dashboard/">Dashboard →</a>
</p>