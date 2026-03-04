# Web Dashboard

The **Web Dashboard** provides a real-time, browser-based control panel for monitoring and interacting with the Open-PC desktop. Built with React and featuring MJPEG streaming, it offers a live view of the AI-controlled desktop.

## 📦 Container Overview

| Property | Value |
|----------|-------|
| **Base Image** | Node 20 Alpine (build) + Nginx Alpine (runtime) |
| **Framework** | React 18 + Vite + TypeScript |
| **Features** | MJPEG streaming, real-time control, window management |
| **Port** | 3000 (mapped to 8092) |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Web Dashboard                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    React Application                            │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │                  App.tsx (Main)                          │  │ │
│  │  │  ┌─────────────────┐  ┌──────────────────────────────┐ │  │ │
│  │  │  │ Screen View     │  │ Sidebar                      │ │  │ │
│  │  │  │ • MJPEG Stream  │  │ • Quick Actions              │ │  │ │
│  │  │  │ • Click Handler │  │ • Mouse Control              │ │  │ │
│  │  │  │ • Mouse Track   │  │ • Window List                │ │  │ │
│  │  │  └─────────────────┘  │ • Terminal                   │ │  │ │
│  │  │                       │ • Activity Logs               │ │  │ │
│  │  │  ┌─────────────────┐  └──────────────────────────────┘ │  │ │
│  │  │  │ Controls Bar    │                                 │  │ │
│  │  │  │ • URL Input     │                                 │  │ │
│  │  │  │ • Text Type     │                                 │  │ │
│  │  │  │ • Quick Actions │                                 │  │ │
│  │  │  └─────────────────┘                                 │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────┬────────────────────────────────────┘ │
│                                │                                     │
│                                ▼                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Nginx Reverse Proxy                         │ │
│  │  /api/* → Desktop Container :8080                              │ │
│  │  /ws   → Desktop Container :8080/ws                            │ │
│  └───────────────────────────┬────────────────────────────────────┘ │
│                                │                                     │
│                                ▼                                     │
│                     HTTP/WebSocket to Desktop Container              │
│                           (Port 8080)                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Source Files

| File | Purpose |
|------|---------|
| `dashboard/Dockerfile` | Multi-stage build (Node → Nginx) |
| `dashboard/nginx.conf` | Reverse proxy configuration |
| `dashboard/package.json` | NPM dependencies |
| `dashboard/vite.config.ts` | Vite bundler configuration |
| `dashboard/src/App.tsx` | Main React component |
| `dashboard/src/main.tsx` | Application entry point |
| `dashboard/src/index.css` | Dark theme styling |
| `dashboard/index.html` | HTML template |

## 🚀 Features

### Real-Time Screen View
- **MJPEG Streaming** — Live 30 FPS video feed
- **Click-to-Interact** — Click anywhere on the screen to send mouse clicks
- **Mouse Position Tracking** — Real-time coordinate display

### Control Panel
- **URL Input** — Open websites directly
- **Text Input** — Type text into active fields
- **Quick Actions** — Minimize, Maximize, Close buttons
- **Copy/Paste/Esc** — Common keyboard shortcuts

### Window Management
- **Window List** — See all open windows
- **Focus Windows** — Click to bring window to front
- **Refresh List** — Update window listing

### Terminal
- **Command Execution** — Run shell commands from dashboard
- **Output Display** — View stdout and stderr

### Activity Logging
- **Timestamped Logs** — Track all actions
- **Recent History** — Last 100 log entries

## 🔌 API Integration

The dashboard communicates with the Desktop Container through Nginx reverse proxy:

### Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/stream` | GET | MJPEG video stream |
| `/api/screen` | GET | Screen dimensions |
| `/api/windows` | GET | List all windows |
| `/api/mouse/click` | POST | Send mouse click |
| `/api/keyboard/type` | POST | Type text |
| `/api/keyboard/hotkey` | POST | Press key combination |
| `/api/apps/launch` | POST | Launch application |
| `/api/apps/open-url` | POST | Open URL |
| `/api/apps/run` | POST | Run shell command |
| `/api/windows/focus` | POST | Focus window |

## ⚙️ Configuration

### Nginx Configuration

The `nginx.conf` file configures the reverse proxy:

```nginx
server {
    listen 3000;

    # API Proxy
    location /api/ {
        proxy_pass http://open-pc-desktop:8080/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # WebSocket Proxy
    location /ws {
        proxy_pass http://open-pc-desktop:8080/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static Files
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_URL` | `http://open-pc-desktop:8080` | Desktop container URL |
| `VNC_URL` | `http://localhost:6080` | noVNC URL |
| `DASHBOARD_PORT` | `3000` | Dashboard listen port |

### Docker Compose

```yaml
open-pc-dashboard:
  build:
    context: ./dashboard
    dockerfile: Dockerfile
  ports:
    - "8092:3000"
  environment:
    - AGENT_URL=http://open-pc-desktop:8080
    - VNC_URL=http://localhost:6080
    - DASHBOARD_PORT=3000
  depends_on:
    open-pc-desktop:
      condition: service_healthy
```

## 🎨 User Interface

### Screen View Area
```
┌────────────────────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                                                          │  │
│  │              MJPEG Stream (Live Desktop)                 │  │
│  │              Click anywhere to interact                  │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Mouse: (500, 300)                                              │
└────────────────────────────────────────────────────────────────┘
```

### Controls Bar
```
┌────────────────────────────────────────────────────────────────┐
│ [🔄 Refresh] [Open URL...] [Type text...] [↖] [↗] [✕]         │
└────────────────────────────────────────────────────────────────┘
```

### Sidebar
```
┌──────────────────────┐
│ Quick Actions        │
│ [Chrome] [Terminal]  │
│ [Files]              │
│ [Copy] [Paste] [Esc] │
├──────────────────────┤
│ Mouse Control        │
│ X: 500  Y: 300       │
│ [Left] [Right] [Dbl] │
├──────────────────────┤
│ Windows              │
│ [Chrome]             │
│ [Terminal]           │
│ [Files]              │
│ [↻ Refresh]          │
├──────────────────────┤
│ Terminal             │
│ $ ls -la             │
│ $ _                  │
│ [Run]                │
├──────────────────────┤
│ Logs                 │
│ [11:30:45] Clicked   │
│ [11:30:42] Opened... │
└──────────────────────┘
```

## 🔧 Development

### Local Development

```bash
cd dashboard
npm install
npm run dev
```

### Build for Production

```bash
npm run build
```

### Project Structure

```
dashboard/
├── Dockerfile           # Multi-stage build
├── nginx.conf          # Reverse proxy config
├── package.json        # Dependencies
├── vite.config.ts      # Vite configuration
├── tsconfig.json       # TypeScript config
├── index.html          # HTML template
└── src/
    ├── main.tsx        # Entry point
    ├── App.tsx         # Main component
    └── index.css       # Styles
```

## 🖼️ Customization

### Change Stream FPS/Quality

In `App.tsx`:
```tsx
const streamUrl = `${API_BASE}/stream?fps=30&quality=80`
```

### Add Custom Quick Actions

In `App.tsx`:
```tsx
const appActions = [
  { label: 'Chrome', action: () => api.post('/apps/launch', { application: 'google-chrome' }) },
  { label: 'Terminal', action: () => api.post('/apps/launch', { application: 'xfce4-terminal' }) },
  { label: 'Files', action: () => api.post('/apps/launch', { application: 'thunar' }) },
  // Add your custom actions here
]
```

### Style Customization

Edit `src/index.css` for:
- Color scheme (CSS variables)
- Layout dimensions
- Font sizes
- Animation effects

## 📊 Performance

### MJPEG Stream

The dashboard uses MJPEG (Motion JPEG) streaming for real-time desktop view:

- **Format**: `multipart/x-mixed-replace`
- **Default FPS**: 30 frames per second
- **Default Quality**: 80% JPEG compression
- **Latency**: ~33ms per frame

### Optimization Tips

1. **Reduce FPS** for slower connections: `?fps=15`
2. **Lower Quality** for bandwidth: `?quality=50`
3. **Increase Quality** for clarity: `?quality=95`

## 🐛 Debugging

### View Dashboard Logs

```bash
docker compose logs -f open-pc-dashboard
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Stream not loading | Check desktop container health |
| Clicks not registering | Verify screen size matches |
| Windows not updating | Click refresh button |

---

<p align="center">
  <a href="../mcp-server/">← MCP Server</a> •
  <a href="../README.md">Main Docs</a>
</p>