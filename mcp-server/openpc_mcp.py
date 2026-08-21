#!/usr/bin/env python3
"""
Open-PC MCP Server
Model Context Protocol server for AI desktop control using FastMCP

This allows AI assistants like Claude to control a Linux desktop environment.
"""

import asyncio
import base64
import json
import os
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from fastmcp import FastMCP

# ============== Configuration ==============

OPENPC_HOST = os.environ.get('OPENPC_HOST', 'localhost')
OPENPC_PORT = int(os.environ.get('OPENPC_PORT', '8080'))
OPENPC_PASSWORD = os.environ.get('OPENPC_PASSWORD', 'openpc')

BASE_URL = f"http://{OPENPC_HOST}:{OPENPC_PORT}"

# ============== Desktop Client ==============

class OpenPCClient:
    """HTTP client for Open-PC Agent Server"""

    def __init__(self, base_url: str = BASE_URL, token: str = OPENPC_PASSWORD):
        self.base_url = base_url
        self.token = token or ''
        self.session: aiohttp.ClientSession | None = None

    async def connect(self):
        """Initialize HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request to agent server"""
        await self.connect()

        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', aiohttp.ClientTimeout(total=60))

        # Attach REST auth token if configured (end-to-end with agent REST_AUTH_TOKEN)
        if self.token:
            headers = kwargs.get('headers') or {}
            headers.setdefault('X-OpenPC-Token', self.token)
            kwargs['headers'] = headers

        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.content_type == 'application/json':
                    return await response.json()
                elif response.content_type == 'image/png':
                    data = await response.read()
                    return {"success": True, "image": base64.b64encode(data).decode()}
                else:
                    data = await response.read()
                    return {"success": response.status == 200, "data": data.decode()}
        except TimeoutError:
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get(self, endpoint: str) -> dict[str, Any]:
        """GET request"""
        return await self.request('GET', endpoint)

    async def post(self, endpoint: str, json_data: dict = None) -> dict[str, Any]:
        """POST request"""
        return await self.request('POST', endpoint, json=json_data)


# Global client instance
client = OpenPCClient()


# ============== FastMCP Server ==============


@asynccontextmanager
async def app_lifespan(server):
    """Manage the HTTP client lifecycle (close session on shutdown)."""
    yield
    await client.close()


# Use SSE transport for better compatibility with MCP clients
mcp = FastMCP("Open-PC Desktop Control", lifespan=app_lifespan)


# ============== Screenshot Tools ==============

@mcp.tool()
async def take_screenshot() -> str:
    """
    Take a screenshot of the desktop.

    Returns a base64-encoded PNG image of the current screen.
    Use this to see what's currently displayed before taking actions.

    Returns:
        Base64-encoded PNG image string
    """
    await client.connect()
    result = await client.get('/screenshot/base64')
    if result.get('success'):
        return result.get('image', '')
    return f"Error: {result.get('error', 'Unknown error')}"


@mcp.tool()
async def get_screen_size() -> dict[str, int]:
    """
    Get the screen dimensions and current mouse position.

    Returns the width and height of the screen in pixels, plus the
    current cursor position. Use this to understand the coordinate
    system before moving the mouse.

    Returns:
        Dictionary with width, height, cursor_x, cursor_y
    """
    await client.connect()
    return await client.get('/screen')


# ============== Mouse Tools ==============

@mcp.tool()
async def move_mouse(x: int, y: int) -> str:
    """
    Move the mouse cursor to the specified coordinates.

    Args:
        x: X coordinate (0 is left edge of screen)
        y: Y coordinate (0 is top edge of screen)

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/mouse/move', {'x': x, 'y': y})
    if result.get('success'):
        return f"Mouse moved to ({x}, {y})"
    return f"Error: {result.get('error', 'Failed to move mouse')}"


@mcp.tool()
async def click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    """
    Click at the specified coordinates.

    Moves the mouse to the position and performs a click.

    Args:
        x: X coordinate
        y: Y coordinate
        button: Mouse button - 'left', 'right', or 'middle' (default: 'left')
        clicks: Number of clicks - 1 for single, 2 for double (default: 1)

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/mouse/click', {
        'x': x, 'y': y, 'button': button, 'clicks': clicks
    })
    if result.get('success'):
        return f"Clicked {button} at ({x}, {y})"
    return f"Error: {result.get('error', 'Failed to click')}"


@mcp.tool()
async def double_click(x: int, y: int) -> str:
    """
    Double-click at the specified coordinates.

    Convenience function for double-clicking.

    Args:
        x: X coordinate
        y: Y coordinate

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/mouse/double-click', {'x': x, 'y': y})
    if result.get('success'):
        return f"Double-clicked at ({x}, {y})"
    return f"Error: {result.get('error', 'Failed to double-click')}"


@mcp.tool()
async def right_click(x: int, y: int) -> str:
    """
    Right-click at the specified coordinates.

    Opens context menu at the position.

    Args:
        x: X coordinate
        y: Y coordinate

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/mouse/right-click', {'x': x, 'y': y})
    if result.get('success'):
        return f"Right-clicked at ({x}, {y})"
    return f"Error: {result.get('error', 'Failed to right-click')}"


@mcp.tool()
async def scroll(clicks: int, direction: str = "down") -> str:
    """
    Scroll the mouse wheel.

    Scrolls the mouse wheel at the current cursor position.

    Args:
        clicks: Number of scroll clicks/lines
        direction: 'up' or 'down' (default: 'down')

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/mouse/scroll', {'clicks': clicks, 'direction': direction})
    if result.get('success'):
        return f"Scrolled {direction} {clicks} clicks"
    return f"Error: {result.get('error', 'Failed to scroll')}"


@mcp.tool()
async def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> str:
    """
    Drag the mouse from start coordinates to end coordinates.

    Useful for dragging files, selecting text, or drawing.

    Args:
        start_x: Starting X coordinate
        start_y: Starting Y coordinate
        end_x: Ending X coordinate
        end_y: Ending Y coordinate
        duration: Duration of drag in seconds (default: 0.5)

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/mouse/drag', {
        'start_x': start_x, 'start_y': start_y,
        'end_x': end_x, 'end_y': end_y,
        'duration': duration
    })
    if result.get('success'):
        return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"
    return f"Error: {result.get('error', 'Failed to drag')}"


# ============== Keyboard Tools ==============

@mcp.tool()
async def type_text(text: str, interval: float = 0.05) -> str:
    """
    Type text at the current cursor position.

    Types each character with a small delay between keystrokes.

    Args:
        text: The text to type
        interval: Delay between keystrokes in seconds (default: 0.05)

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/keyboard/type', {'text': text, 'interval': interval})
    if result.get('success'):
        return f"Typed: {text}"
    return f"Error: {result.get('error', 'Failed to type')}"


@mcp.tool()
async def press_key(key: str) -> str:
    """
    Press a single key.

    Use this for special keys like enter, escape, tab, etc.

    Common keys: enter, escape, tab, backspace, delete, space,
    up, down, left, right, home, end, pageup, pagedown,
    f1-f12, insert, print, scroll_lock, pause

    Args:
        key: The key to press

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/keyboard/press', {'key': key})
    if result.get('success'):
        return f"Pressed: {key}"
    return f"Error: {result.get('error', 'Failed to press key')}"


@mcp.tool()
async def press_hotkey(keys: str) -> str:
    """
    Press a keyboard combination (hotkey).

    Keys should be separated by commas or plus signs.
    Examples: 'ctrl+c', 'alt+tab', 'ctrl+shift+escape', 'ctrl,alt,delete'

    Args:
        keys: The hotkey combination (e.g., 'ctrl+c', 'alt+tab')

    Returns:
        Success or error message
    """
    await client.connect()
    # Parse keys - handle both 'ctrl+c' and 'ctrl,c' formats
    key_list = keys.replace('+', ',').split(',')
    key_list = [k.strip() for k in key_list]

    result = await client.post('/keyboard/hotkey', {'keys': key_list})
    if result.get('success'):
        return f"Pressed hotkey: {'+'.join(key_list)}"
    return f"Error: {result.get('error', 'Failed to press hotkey')}"


# ============== Window Management Tools ==============

@mcp.tool()
async def list_windows() -> str:
    """
    List all open windows on the desktop.

    Returns a list of windows with their IDs, titles, and positions.
    Use the window ID with focus_window or close_window.

    Returns:
        JSON string with list of windows
    """
    await client.connect()
    result = await client.get('/windows')
    if result.get('windows'):
        windows = result['windows']
        lines = ["Open windows:"]
        for w in windows:
            lines.append(f"  [{w['id']}] {w['title']} ({w['width']}x{w['height']} at {w['x']},{w['y']})")
        return "\n".join(lines)
    return "No windows found"


@mcp.tool()
async def focus_window(window_id: str) -> str:
    """
    Focus (bring to front) a specific window.

    Args:
        window_id: The window ID from list_windows()

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/windows/focus', {'window_id': window_id})
    if result.get('success'):
        return f"Focused window: {window_id}"
    return f"Error: {result.get('error', 'Failed to focus window')}"


@mcp.tool()
async def close_window(window_id: str = "") -> str:
    """
    Close a window.

    Args:
        window_id: The window ID (optional - closes active window if not specified)

    Returns:
        Success or error message
    """
    await client.connect()
    data = {'window_id': window_id} if window_id else {}
    result = await client.post('/windows/close', data)
    if result.get('success'):
        target = window_id if window_id else "active window"
        return f"Closed {target}"
    return f"Error: {result.get('error', 'Failed to close window')}"


@mcp.tool()
async def maximize_window(window_id: str = "") -> str:
    """
    Maximize a window.

    Args:
        window_id: The window ID (optional - maximizes active window if not specified)

    Returns:
        Success or error message
    """
    await client.connect()
    data = {'window_id': window_id} if window_id else {}
    result = await client.post('/windows/maximize', data)
    if result.get('success'):
        return "Window maximized"
    return f"Error: {result.get('error', 'Failed to maximize window')}"


@mcp.tool()
async def minimize_window(window_id: str = "") -> str:
    """
    Minimize a window.

    Args:
        window_id: The window ID (optional - minimizes active window if not specified)

    Returns:
        Success or error message
    """
    await client.connect()
    data = {'window_id': window_id} if window_id else {}
    result = await client.post('/windows/minimize', data)
    if result.get('success'):
        return "Window minimized"
    return f"Error: {result.get('error', 'Failed to minimize window')}"


# ============== Application Tools ==============

@mcp.tool()
async def launch_application(application: str) -> str:
    """
    Launch an application.

    Common applications:
    - google-chrome: Web browser
    - firefox: Firefox browser
    - xfce4-terminal: Terminal emulator
    - thunar: File manager
    - code: VS Code editor

    Args:
        application: Application name or command

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/apps/launch', {'application': application})
    if result.get('success'):
        return f"Launched: {application}"
    return f"Error: {result.get('error', 'Failed to launch application')}"


@mcp.tool()
async def open_url(url: str) -> str:
    """
    Open a URL in the default web browser.

    Opens Chrome by default with the specified URL.

    Args:
        url: The URL to open

    Returns:
        Success or error message
    """
    await client.connect()
    result = await client.post('/apps/open-url', {'url': url})
    if result.get('success'):
        return f"Opened URL: {url}"
    return f"Error: {result.get('error', 'Failed to open URL')}"


@mcp.tool()
async def run_command(command: str, timeout: int = 30) -> str:
    """
    Run a shell command in the terminal.

    Executes the command and returns stdout/stderr.

    Args:
        command: The shell command to run
        timeout: Timeout in seconds (default: 30)

    Returns:
        Command output and status
    """
    await client.connect()
    result = await client.post('/apps/run', {'command': command, 'timeout': timeout})

    output = result.get('stdout', '')
    error = result.get('stderr', '')
    return_code = result.get('return_code', -1)

    response = f"Command: {command}\n"
    response += f"Return code: {return_code}\n"
    if output:
        response += f"Output:\n{output}\n"
    if error:
        response += f"Error:\n{error}\n"
    return response


# ============== Utility Tools ==============

@mcp.tool()
async def perform_ocr() -> str:
    """
    Perform OCR (Optical Character Recognition) on the current screen.

    Extracts visible text from the screen using Tesseract OCR.
    Useful for reading text that might not be accessible programmatically.

    Returns:
        Extracted text from the screen
    """
    await client.connect()
    result = await client.post('/ocr', {})
    if result.get('success'):
        return result.get('text', '')
    return f"Error: {result.get('error', 'OCR failed')}"


@mcp.tool()
async def wait_seconds(seconds: float) -> str:
    """
    Wait for a specified number of seconds.

    Useful for waiting for applications to load or animations to complete.

    Args:
        seconds: Number of seconds to wait

    Returns:
        Confirmation message
    """
    await asyncio.sleep(seconds)
    return f"Waited {seconds} seconds"


# ============== Resource for Context ==============

@mcp.resource("desktop://status")
async def get_desktop_status() -> str:
    """Get current desktop status as a resource"""
    await client.connect()

    screen = await client.get('/screen')
    windows = await client.get('/windows')

    status = {
        "screen": screen,
        "window_count": len(windows.get('windows', [])),
        "agent_url": BASE_URL
    }
    return json.dumps(status, indent=2)


# ============== Main Entry Point ==============

if __name__ == "__main__":
    print("Starting Open-PC MCP Server...")
    print(f"Connecting to Open-PC Agent at: {BASE_URL}")
    print("MCP Server running on: http://0.0.0.0:8000")

    # Run with SSE transport, binding to 0.0.0.0 for Docker
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
