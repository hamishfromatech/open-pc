# Open-PC Documentation

Welcome to the Open-PC documentation. This folder contains detailed technical documentation for each component of the system.

## 📁 Documentation Structure

```
docs/
├── README.md              # This file - documentation index
├── desktop/               # Desktop Container Documentation
│   └── README.md          # Agent server, automation layer, VNC setup
├── mcp-server/            # MCP Server Documentation
│   └── README.md          # FastMCP integration, AI tools, configuration
└── dashboard/             # Web Dashboard Documentation
    └── README.md          # React components, real-time streaming, API proxy
```

## 🧭 Quick Navigation

| Component | Description | Documentation |
|-----------|-------------|--------------|
| **Desktop Container** | Linux desktop with XFCE4, VNC, and automation APIs | [docs/desktop/](desktop/) |
| **MCP Server** | FastMCP server for AI assistant integration | [docs/mcp-server/](mcp-server/) |
| **Web Dashboard** | React-based real-time control panel | [docs/dashboard/](dashboard/) |

## 🏗️ System Overview

Open-PC consists of three Docker containers that work together:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Open-PC System                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │ Web Dashboard   │    │ MCP Server      │    │ noVNC (built-in)│     │
│  │ Port 8092       │    │ Port 8091       │    │ Port 6080        │     │
│  │                 │    │                 │    │                  │     │
│  │ • React UI      │    │ • FastMCP       │    │ • Browser VNC   │     │
│  │ • MJPEG Stream  │    │ • SSE Transport │    │ • Direct View   │     │
│  │ • Control Panel │    │ • 22+ AI Tools  │    │                 │     │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘     │
│           │                      │                      │               │
│           └──────────────────────┼──────────────────────┘               │
│                                  │                                       │
│                                  ▼                                       │
│                  ┌───────────────────────────────┐                       │
│                  │      Desktop Container        │                       │
│                  │      Port 8090 (API)          │                       │
│                  │      Port 5901 (VNC)          │                       │
│                  │                               │                       │
│                  │  • FastAPI Agent Server       │                       │
│                  │  • Desktop Automation Layer   │                       │
│                  │  • XFCE4 Desktop Environment  │                       │
│                  │  • TigerVNC Server            │                       │
│                  └───────────────────────────────┘                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 📖 Documentation by Topic

### Getting Started
- [Desktop Container Setup](desktop/) - Configure the Linux desktop environment
- [MCP Server Configuration](mcp-server/) - Connect AI assistants
- [Dashboard Usage](dashboard/) - Use the web control panel

### API Reference
- [REST API Endpoints](desktop/rest-api.md) - HTTP endpoints for automation
- [WebSocket API](desktop/websocket.md) - Real-time bidirectional control
- [MCP Tools](mcp-server/tools.md) - AI assistant capabilities

### Integration
- [Connecting Claude](mcp-server/integration/claude.md) - MCP client configuration
- [Custom Integrations](desktop/integration.md) - Build your own client

## 🔧 Configuration

Each component can be configured via environment variables. See the individual documentation for details:

| Variable | Component | Description |
|----------|-----------|-------------|
| `VNC_PASSWORD` | Desktop | VNC access password |
| `VNC_RESOLUTION` | Desktop | Screen resolution |
| `AUTH_REQUIRED` | Desktop | WebSocket authentication |
| `OPENPC_HOST` | MCP Server | Desktop container hostname |
| `OPENPC_PORT` | MCP Server | Desktop API port |

## 🐳 Docker Services

Start individual services or the full stack:

```bash
# Start everything
docker-compose up -d

# Start specific services
docker-compose up -d open-pc-desktop    # Desktop only
docker-compose up -d open-pc-mcp        # MCP server (needs desktop)
docker-compose up -d open-pc-dashboard  # Dashboard (needs desktop)
```

## 📝 Contributing

When adding new features or fixing bugs:

1. Update the relevant documentation in `docs/<component>/`
2. Add inline code comments for complex logic
3. Update API reference if endpoints change
4. Include usage examples

## 📚 Additional Resources

- [Main README](../README.md) - Project overview and quick start
- [Docker Compose Reference](../docker-compose.yml) - Service definitions
- [Environment Variables](../.env.example) - Configuration template

---

<p align="center">
  Made by <a href="https://atechcorporation.com">The A-Tech Corporation PTY LTD</a>
</p>