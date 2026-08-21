# Changelog

All notable changes to Open-PC are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-20

First tagged release.

### Added
- Complete AI-controlled Linux desktop (XFCE4 + TigerVNC + noVNC + Chrome)
- Agent server: REST API + WebSocket for mouse, keyboard, windows, apps, OCR,
  screenshots, and MJPEG streaming
- FastMCP server exposing 22+ tools for AI assistants
- Real-time React dashboard with live MJPEG view and controls
- Optional REST API token authentication (`REST_AUTH_TOKEN`), wired end-to-end
  to the MCP server and dashboard
- Docker Compose stack with health checks and auto-restart
- pytest suite (API + sanitization tests with a mocked display) and GitHub
  Actions CI (ruff lint, pytest, dashboard eslint + typecheck + build)
- Per-thread `mss` reuse for efficient 30 FPS streaming

### Security
- `run_command` rejects dangerous shell constructs (`; | & \` $() ${ } > < || && $`
  and newlines) instead of silently mutating them
- Container hardening: `init`, `no-new-privileges`, `tmpfs /tmp`, `.dockerignore`
- `/wait` clamped to 0–300 s; input validation on REST models

### Fixed
- Rate limiting was broken (every rate-limited endpoint returned 500 because
  slowapi requires a `request: Request` param and the route decorator above
  `@limiter.limit`) — now fixed across `/screenshot*`, `/mouse/locate*`,
  `/batch`, and `/ocr`
- `get_active_window()` now returns the real window title
- Inverted `run_command` sanitization guard that rejected clean commands