#!/usr/bin/env python3
"""
Open-PC Agent Server
WebSocket + REST API server for desktop control

Provides both WebSocket (for real-time control) and HTTP REST (for simple API access)
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import websockets

from desktop_manager import DesktopManager, MouseButton

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment configuration
AGENT_HOST = os.environ.get('AGENT_HOST', '0.0.0.0')
AGENT_PORT = int(os.environ.get('AGENT_PORT', 8080))
VNC_PASSWORD = os.environ.get('VNC_PASSWORD', 'openpc')
AUTH_REQUIRED = os.environ.get('AUTH_REQUIRED', 'true').lower() == 'true'

# Global desktop manager
desktop_manager: Optional[DesktopManager] = None


# ============== Pydantic Models ==============

class MouseMoveRequest(BaseModel):
    x: int
    y: int
    duration: float = 0.0


class MouseClickRequest(BaseModel):
    x: Optional[int] = None
    y: Optional[int] = None
    button: str = "left"
    clicks: int = 1
    duration: float = 0.0


class MouseScrollRequest(BaseModel):
    clicks: int
    direction: str = "down"
    x: Optional[int] = None
    y: Optional[int] = None


class MouseDragRequest(BaseModel):
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    duration: float = 0.5


class KeyboardTypeRequest(BaseModel):
    text: str
    interval: float = 0.05


class KeyboardKeyRequest(BaseModel):
    key: str


class KeyboardHotkeyRequest(BaseModel):
    keys: list[str]


class CommandRequest(BaseModel):
    command: str
    parameters: Optional[Dict[str, Any]] = None


class WindowRequest(BaseModel):
    window_id: Optional[str] = None


class RunCommandRequest(BaseModel):
    command: str
    timeout: int = 30


class LaunchRequest(BaseModel):
    application: str


class URLRequest(BaseModel):
    url: str
    browser: str = "google-chrome"


class OCRRequest(BaseModel):
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None


# ============== WebSocket Connection Manager ==============

class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.authenticated_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.authenticated_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def authenticate(self, websocket: WebSocket, password: str) -> bool:
        if not AUTH_REQUIRED or password == VNC_PASSWORD:
            self.authenticated_connections.add(websocket)
            return True
        return False

    def is_authenticated(self, websocket: WebSocket) -> bool:
        return not AUTH_REQUIRED or websocket in self.authenticated_connections


connection_manager = ConnectionManager()


# ============== FastAPI Application ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize desktop manager on startup"""
    global desktop_manager
    logger.info("Initializing Open-PC Agent Server...")

    # Wait for X11 display to be ready
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            desktop_manager = DesktopManager()
            screen_info = desktop_manager.get_screen_info()
            logger.info(f"Display ready. Screen: {screen_info.width}x{screen_info.height}")
            break
        except Exception as e:
            logger.warning(f"Waiting for display... ({attempt + 1}/{max_attempts})")
            await asyncio.sleep(1)
    else:
        logger.error("Failed to initialize display after 30 seconds")
        desktop_manager = DesktopManager()  # Try anyway

    logger.info(f"Open-PC Agent Server ready on {AGENT_HOST}:{AGENT_PORT}")
    yield

    # Cleanup
    logger.info("Shutting down Open-PC Agent Server")


app = FastAPI(
    title="Open-PC Agent API",
    description="Desktop automation API for AI agents",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== REST API Endpoints ==============

@app.get("/")
async def root():
    """API root"""
    return {
        "name": "Open-PC Agent Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "screenshot": "/screenshot",
            "screen": "/screen",
            "mouse": "/mouse/*",
            "keyboard": "/keyboard/*",
            "windows": "/windows",
            "applications": "/apps/*",
            "ws": "/ws"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        screen_info = desktop_manager.get_screen_info()
        return {
            "status": "healthy",
            "display": f"{screen_info.width}x{screen_info.height}",
            "cursor": f"{screen_info.cursor_x},{screen_info.cursor_y}"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


# ============== Screenshot Endpoints ==============

@app.get("/screenshot")
async def get_screenshot():
    """Get screenshot as PNG image"""
    try:
        img_bytes = desktop_manager.take_screenshot()
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/screenshot/base64")
async def get_screenshot_base64():
    """Get screenshot as base64 encoded JSON"""
    try:
        b64 = desktop_manager.take_screenshot_base64()
        return {"success": True, "image": b64}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/screenshot/region")
async def get_screenshot_region(x: int, y: int, width: int, height: int):
    """Get screenshot of a specific region"""
    try:
        img_bytes = desktop_manager.take_screenshot_region(x, y, width, height)
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== MJPEG Streaming Endpoint ==============

@app.get("/stream")
async def video_stream(fps: int = 30, quality: int = 80):
    """
    MJPEG video stream for real-time desktop viewing.

    Args:
        fps: Frames per second (default: 30)
        quality: JPEG quality 1-100 (default: 80)

    Returns:
        StreamingResponse with multipart/x-mixed-replace content
    """
    async def generate_frames():
        frame_interval = 1.0 / fps
        while True:
            try:
                # Capture frame as JPEG
                frame_bytes = desktop_manager.take_screenshot_jpeg(quality=quality)

                # MJPEG frame format
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
                )

                await asyncio.sleep(frame_interval)

            except Exception as e:
                logger.error(f"Stream frame error: {e}")
                await asyncio.sleep(0.1)  # Brief pause on error

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ============== Screen Info ==============

@app.get("/screen")
async def get_screen_info():
    """Get screen dimensions and cursor position"""
    try:
        info = desktop_manager.get_screen_info()
        return {
            "width": info.width,
            "height": info.height,
            "cursor_x": info.cursor_x,
            "cursor_y": info.cursor_y
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Mouse Endpoints ==============

@app.post("/mouse/move")
async def mouse_move(request: MouseMoveRequest):
    """Move mouse to position"""
    result = desktop_manager.mouse_move(request.x, request.y, request.duration)
    return result


@app.post("/mouse/click")
async def mouse_click(request: MouseClickRequest):
    """Perform mouse click"""
    button = MouseButton(request.button)
    result = desktop_manager.mouse_click(
        request.x, request.y, button, request.clicks, request.duration
    )
    return result


@app.post("/mouse/double-click")
async def mouse_double_click(request: MouseClickRequest):
    """Perform double click"""
    result = desktop_manager.mouse_double_click(request.x, request.y)
    return result


@app.post("/mouse/right-click")
async def mouse_right_click(request: MouseClickRequest):
    """Perform right click"""
    result = desktop_manager.mouse_right_click(request.x, request.y)
    return result


@app.post("/mouse/scroll")
async def mouse_scroll(request: MouseScrollRequest):
    """Scroll mouse wheel"""
    result = desktop_manager.mouse_scroll(request.clicks, request.direction, request.x, request.y)
    return result


@app.post("/mouse/drag")
async def mouse_drag(request: MouseDragRequest):
    """Drag mouse from start to end"""
    result = desktop_manager.mouse_drag(
        request.start_x, request.start_y, request.end_x, request.end_y, request.duration
    )
    return result


@app.get("/mouse/position")
async def get_mouse_position():
    """Get current mouse position"""
    x, y = desktop_manager.get_mouse_position()
    return {"x": x, "y": y}


# ============== Keyboard Endpoints ==============

@app.post("/keyboard/type")
async def keyboard_type(request: KeyboardTypeRequest):
    """Type text"""
    result = desktop_manager.keyboard_type(request.text, request.interval)
    return result


@app.post("/keyboard/press")
async def keyboard_press(request: KeyboardKeyRequest):
    """Press a key"""
    result = desktop_manager.keyboard_press(request.key)
    return result


@app.post("/keyboard/hotkey")
async def keyboard_hotkey(request: KeyboardHotkeyRequest):
    """Press keyboard combination"""
    result = desktop_manager.keyboard_hotkey(*request.keys)
    return result


@app.post("/keyboard/down")
async def keyboard_down(request: KeyboardKeyRequest):
    """Hold key down"""
    result = desktop_manager.keyboard_key_down(request.key)
    return result


@app.post("/keyboard/up")
async def keyboard_up(request: KeyboardKeyRequest):
    """Release key"""
    result = desktop_manager.keyboard_key_up(request.key)
    return result


# ============== Window Endpoints ==============

@app.get("/windows")
async def list_windows():
    """List all windows"""
    windows = desktop_manager.list_windows()
    return {"windows": [asdict(w) for w in windows]}


@app.get("/windows/active")
async def get_active_window():
    """Get active window"""
    window = desktop_manager.get_active_window()
    if window:
        return asdict(window)
    return {"error": "No active window"}


@app.post("/windows/focus")
async def focus_window(request: WindowRequest):
    """Focus a window"""
    result = desktop_manager.focus_window(request.window_id)
    return result


@app.post("/windows/close")
async def close_window(request: WindowRequest):
    """Close a window"""
    result = desktop_manager.close_window(request.window_id)
    return result


@app.post("/windows/maximize")
async def maximize_window(request: WindowRequest):
    """Maximize a window"""
    result = desktop_manager.maximize_window(request.window_id)
    return result


@app.post("/windows/minimize")
async def minimize_window(request: WindowRequest):
    """Minimize a window"""
    result = desktop_manager.minimize_window(request.window_id)
    return result


# ============== Application Endpoints ==============

@app.post("/apps/launch")
async def launch_app(request: LaunchRequest):
    """Launch an application"""
    result = desktop_manager.launch_application(request.application)
    return result


@app.post("/apps/open-url")
async def open_url(request: URLRequest):
    """Open URL in browser"""
    result = desktop_manager.open_url(request.url, request.browser)
    return result


@app.post("/apps/run")
async def run_command(request: RunCommandRequest):
    """Run shell command"""
    result = desktop_manager.run_command(request.command, request.timeout)
    return result


# ============== OCR Endpoint ==============

@app.post("/ocr")
async def ocr_screenshot(request: OCRRequest = None):
    """Perform OCR on screenshot"""
    region = None
    if request and all([request.x is not None, request.y is not None,
                         request.width is not None, request.height is not None]):
        region = (request.x, request.y, request.width, request.height)

    result = desktop_manager.ocr_screenshot(region)
    return result


# ============== Utility Endpoints ==============

@app.post("/wait")
async def wait_seconds(seconds: float):
    """Wait for specified seconds"""
    await asyncio.sleep(seconds)
    return {"success": True, "action": "wait", "seconds": seconds}


# ============== WebSocket Endpoint ==============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time desktop control"""
    await connection_manager.connect(websocket)
    client_id = str(uuid.uuid4())[:8]
    logger.info(f"[{client_id}] WebSocket connection opened")

    try:
        # Authentication
        if AUTH_REQUIRED:
            auth_message = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            auth_data = json.loads(auth_message)

            if auth_data.get("type") == "auth":
                password = auth_data.get("password", "")
                if await connection_manager.authenticate(websocket, password):
                    await websocket.send_json({
                        "type": "auth_success",
                        "client_id": client_id
                    })
                    logger.info(f"[{client_id}] Authenticated successfully")
                else:
                    await websocket.send_json({
                        "type": "auth_error",
                        "error": "Invalid password"
                    })
                    await websocket.close()
                    return
            else:
                await websocket.send_json({
                    "type": "auth_error",
                    "error": "Authentication required"
                })
                await websocket.close()
                return

        # Command loop
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=300)
                data = json.loads(message)

                if data.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time()
                    })
                    continue

                if data.get("type") == "command":
                    command = data.get("command")
                    params = data.get("parameters", {})

                    result = await execute_command(command, params)
                    await websocket.send_json({
                        "type": "result",
                        "command": command,
                        "data": result
                    })

            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "ping"})
                continue

            except json.JSONDecodeError as e:
                await websocket.send_json({
                    "type": "error",
                    "error": f"Invalid JSON: {str(e)}"
                })

    except WebSocketDisconnect:
        logger.info(f"[{client_id}] WebSocket disconnected")

    except Exception as e:
        logger.error(f"[{client_id}] WebSocket error: {e}")

    finally:
        connection_manager.disconnect(websocket)


async def execute_command(command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a desktop command"""
    try:
        if command == "screenshot":
            return {
                "success": True,
                "screenshot": desktop_manager.take_screenshot_base64(),
                "timestamp": time.time()
            }

        elif command == "click":
            return desktop_manager.mouse_click(
                params.get('x'), params.get('y'),
                MouseButton(params.get('button', 'left')),
                params.get('clicks', 1),
                params.get('duration', 0.0)
            )

        elif command == "double_click":
            return desktop_manager.mouse_double_click(params.get('x'), params.get('y'))

        elif command == "right_click":
            return desktop_manager.mouse_right_click(params.get('x'), params.get('y'))

        elif command == "move_mouse":
            return desktop_manager.mouse_move(
                params['x'], params['y'],
                params.get('duration', 0.0)
            )

        elif command == "drag":
            return desktop_manager.mouse_drag(
                params['start_x'], params['start_y'],
                params['end_x'], params['end_y'],
                params.get('duration', 0.5)
            )

        elif command == "scroll":
            return desktop_manager.mouse_scroll(
                params.get('clicks', 3),
                params.get('direction', 'down'),
                params.get('x'), params.get('y')
            )

        elif command == "type":
            return desktop_manager.keyboard_type(
                params['text'],
                params.get('interval', 0.05)
            )

        elif command == "press":
            return desktop_manager.keyboard_press(params['key'])

        elif command == "hotkey":
            return desktop_manager.keyboard_hotkey(*params['keys'])

        elif command == "key_down":
            return desktop_manager.keyboard_key_down(params['key'])

        elif command == "key_up":
            return desktop_manager.keyboard_key_up(params['key'])

        elif command == "list_windows":
            windows = desktop_manager.list_windows()
            return {"success": True, "windows": [asdict(w) for w in windows]}

        elif command == "focus_window":
            return desktop_manager.focus_window(params['window_id'])

        elif command == "close_window":
            return desktop_manager.close_window(params.get('window_id'))

        elif command == "maximize_window":
            return desktop_manager.maximize_window(params.get('window_id'))

        elif command == "minimize_window":
            return desktop_manager.minimize_window(params.get('window_id'))

        elif command == "launch":
            return desktop_manager.launch_application(params['application'])

        elif command == "open_url":
            return desktop_manager.open_url(params['url'], params.get('browser', 'google-chrome'))

        elif command == "run_command":
            return desktop_manager.run_command(params['command'], params.get('timeout', 30))

        elif command == "ocr":
            return desktop_manager.ocr_screenshot()

        elif command == "screen_info":
            info = desktop_manager.get_screen_info()
            return {"success": True, "screen": asdict(info)}

        elif command == "wait":
            await asyncio.sleep(params.get('seconds', 1))
            return {"success": True, "action": "wait"}

        else:
            return {"success": False, "error": f"Unknown command: {command}"}

    except Exception as e:
        logger.error(f"Command {command} failed: {e}")
        return {"success": False, "error": str(e)}


# ============== Main Entry Point ==============

if __name__ == "__main__":
    logger.info(f"Starting Open-PC Agent Server on {AGENT_HOST}:{AGENT_PORT}")
    uvicorn.run(
        app,
        host=AGENT_HOST,
        port=AGENT_PORT,
        log_level="info"
    )