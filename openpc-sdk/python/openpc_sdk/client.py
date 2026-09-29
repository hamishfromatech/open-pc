"""
Open-PC Python SDK Client

Async HTTP client for Open-PC Agent Server REST API.
"""

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any, Literal, Optional


class OpenPCError(Exception):
    """Base exception for Open-PC SDK errors."""
    pass


@dataclass
class ScreenInfo:
    """Screen information returned by the API."""
    width: int
    height: int
    cursor_x: int
    cursor_y: int


@dataclass
class ScreenshotResult:
    """Screenshot result from the API."""
    success: bool
    image_base64: Optional[str] = None
    error: Optional[str] = None


@dataclass
class LocationResult:
    """Location result from image matching."""
    success: bool
    x: Optional[int] = None
    y: Optional[int] = None
    confidence: Optional[float] = None
    error: Optional[str] = None


@dataclass
class WindowInfo:
    """Window information."""
    id: str
    title: str
    class_name: str


@dataclass
class CommandResult:
    """Command execution result."""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None


class OpenPCClient:
    """
    Async client for Open-PC Agent Server.

    Usage:
        async with OpenPCClient() as client:
            screenshot = await client.take_screenshot()
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8090,
        token: Optional[str] = None,
    ):
        """
        Initialize the Open-PC client.

        Args:
            host: Open-PC server host
            port: Open-PC server port
            token: API token for authentication (optional)
        """
        self._base_url = f"http://{host}:{port}"
        self._token = token
        self._session = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_session(self):
        """Ensure HTTP session exists."""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()

    async def close(self):
        """Close HTTP session."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Make HTTP request to Open-PC API."""
        await self._ensure_session()

        url = f"{self._base_url}{endpoint}"
        headers = {"X-OpenPC-Token": self._token} if self._token else {}

        async with self._session.request(
            method, url, json=json_data, headers=headers,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            if response.content_type == "application/json":
                return await response.json()
            elif response.content_type == "image/png":
                data = await response.read()
                return {
                    "success": True,
                    "image": base64.b64encode(data).decode(),
                }
            else:
                return {
                    "success": response.status == 200,
                    "data": (await response.text()) if response.content_type != "application/octet-stream" else None,
                }

    # ============== Health & Capabilities ==============

    async def health(self) -> dict[str, Any]:
        """Check server health status."""
        return await self._request("GET", "/health")

    async def capabilities(self) -> dict[str, Any]:
        """Get available tools and endpoints."""
        return await self._request("GET", "/capabilities")

    # ============== Screenshot ==============

    async def screenshot(self) -> ScreenshotResult:
        """Take a full screen screenshot."""
        try:
            result = await self._request("GET", "/screenshot/base64")
            return ScreenshotResult(
                success=result.get("success", False),
                image_base64=result.get("image"),
            )
        except Exception as e:
            return ScreenshotResult(success=False, error=str(e))

    async def screenshot_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> ScreenshotResult:
        """Take a screenshot of a specific region."""
        endpoint = f"/screenshot/region?x={x}&y={y}&width={width}&height={height}"
        try:
            result = await self._request("GET", endpoint)
            return ScreenshotResult(
                success=result.get("success", False),
                image_base64=result.get("image"),
            )
        except Exception as e:
            return ScreenshotResult(success=False, error=str(e))

    # ============== Screen Info ==============

    async def screen_info(self) -> ScreenInfo:
        """Get screen dimensions and mouse position."""
        result = await self._request("GET", "/screen")
        return ScreenInfo(
            width=result.get("width", 1920),
            height=result.get("height", 1080),
            cursor_x=result.get("cursor_x", 0),
            cursor_y=result.get("cursor_y", 0),
        )

    # ============== Mouse Control ==============

    async def move_mouse(self, x: int, y: int, duration: float = 0.0) -> dict[str, Any]:
        """Move mouse cursor to coordinates."""
        return await self._request(
            "POST", "/mouse/move",
            json_data={"x": x, "y": y, "duration": duration}
        )

    async def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: Literal["left", "right", "middle"] = "left",
        clicks: int = 1,
        duration: float = 0.0,
    ) -> dict[str, Any]:
        """Click at position or current cursor."""
        return await self._request(
            "POST", "/mouse/click",
            json_data={"x": x, "y": y, "button": button, "clicks": clicks, "duration": duration}
        )

    async def double_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> dict[str, Any]:
        """Double-click at position or current cursor."""
        return await self._request(
            "POST", "/mouse/double-click",
            json_data={"x": x, "y": y}
        )

    async def right_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> dict[str, Any]:
        """Right-click at position or current cursor."""
        return await self._request(
            "POST", "/mouse/right-click",
            json_data={"x": x, "y": y}
        )

    async def scroll(
        self,
        clicks: int = 3,
        direction: Literal["up", "down"] = "down",
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> dict[str, Any]:
        """Scroll at position or current cursor."""
        return await self._request(
            "POST", "/mouse/scroll",
            json_data={"clicks": clicks, "direction": direction, "x": x, "y": y}
        )

    async def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> dict[str, Any]:
        """Drag from start to end position."""
        return await self._request(
            "POST", "/mouse/drag",
            json_data={
                "start_x": start_x, "start_y": start_y,
                "end_x": end_x, "end_y": end_y,
                "duration": duration
            }
        )

    async def locate_image(
        self,
        image_path: str,
        confidence: float = 0.9,
    ) -> LocationResult:
        """Locate an image file on screen."""
        try:
            result = await self._request(
                "POST", "/mouse/locate",
                json_data={"image_path": image_path, "confidence": confidence}
            )
            return LocationResult(
                success=result.get("success", False),
                x=result.get("x"),
                y=result.get("y"),
                confidence=result.get("confidence"),
            )
        except Exception as e:
            return LocationResult(success=False, error=str(e))

    async def locate_image_base64(
        self,
        image_b64: str,
        confidence: float = 0.9,
    ) -> LocationResult:
        """Locate a base64-encoded image on screen."""
        try:
            result = await self._request(
                "POST", "/mouse/locate-base64",
                json_data={"image_b64": image_b64, "confidence": confidence}
            )
            return LocationResult(
                success=result.get("success", False),
                x=result.get("x"),
                y=result.get("y"),
                confidence=result.get("confidence"),
            )
        except Exception as e:
            return LocationResult(success=False, error=str(e))

    # ============== Keyboard Control ==============

    async def type(self, text: str, interval: float = 0.05) -> dict[str, Any]:
        """Type text at current cursor position."""
        return await self._request(
            "POST", "/keyboard/type",
            json_data={"text": text, "interval": interval}
        )

    async def press_key(self, key: str) -> dict[str, Any]:
        """Press a single key."""
        return await self._request(
            "POST", "/keyboard/press",
            json_data={"key": key}
        )

    async def hotkey(self, keys: list[str]) -> dict[str, Any]:
        """Press a hotkey combination (e.g., ['ctrl', 'c'])."""
        return await self._request(
            "POST", "/keyboard/hotkey",
            json_data={"keys": keys}
        )

    async def key_down(self, key: str) -> dict[str, Any]:
        """Hold a key down."""
        return await self._request(
            "POST", "/keyboard/down",
            json_data={"key": key}
        )

    async def key_up(self, key: str) -> dict[str, Any]:
        """Release a held key."""
        return await self._request(
            "POST", "/keyboard/up",
            json_data={"key": key}
        )

    # ============== Window Management ==============

    async def list_windows(self) -> list[WindowInfo]:
        """List all open windows."""
        result = await self._request("GET", "/windows")
        return [WindowInfo(**w) for w in result if isinstance(w, dict)]

    async def focus_window(self, window_id: str) -> dict[str, Any]:
        """Focus a window by ID."""
        return await self._request(
            "POST", "/windows/focus",
            json_data={"window_id": window_id}
        )

    async def close_window(self, window_id: str) -> dict[str, Any]:
        """Close a window by ID."""
        return await self._request(
            "POST", "/windows/close",
            json_data={"window_id": window_id}
        )

    async def maximize_window(self, window_id: str) -> dict[str, Any]:
        """Maximize a window by ID."""
        return await self._request(
            "POST", "/windows/maximize",
            json_data={"window_id": window_id}
        )

    async def minimize_window(self, window_id: str) -> dict[str, Any]:
        """Minimize a window by ID."""
        return await self._request(
            "POST", "/windows/minimize",
            json_data={"window_id": window_id}
        )

    # ============== Applications ==============

    async def launch(self, application: str) -> dict[str, Any]:
        """Launch an application."""
        return await self._request(
            "POST", "/apps/launch",
            json_data={"application": application}
        )

    async def open_url(self, url: str, browser: str = "google-chrome") -> dict[str, Any]:
        """Open a URL in a browser."""
        return await self._request(
            "POST", "/apps/open-url",
            json_data={"url": url, "browser": browser}
        )

    async def run_command(
        self,
        command: str,
        timeout: int = 30,
    ) -> CommandResult:
        """Run a shell command in the desktop container."""
        try:
            result = await self._request(
                "POST", "/apps/run",
                json_data={"command": command, "timeout": timeout}
            )
            return CommandResult(
                success=result.get("success", False),
                output=result.get("output"),
                error=result.get("error"),
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    # ============== OCR ==============

    async def ocr(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> dict[str, Any]:
        """Perform OCR on screen (full screen or region)."""
        params = {}
        if x is not None:
            params["x"] = x
        if y is not None:
            params["y"] = y
        if width is not None:
            params["width"] = width
        if height is not None:
            params["height"] = height
        endpoint = f"/ocr" + (f"?{'&'.join(f'{k}={v}' for k, v in params.items())}" if params else "")
        return await self._request("GET", endpoint)

    # ============== Utilities ==============

    async def wait(self, seconds: float) -> dict[str, Any]:
        """Wait for specified seconds."""
        return await self._request(
            "POST", "/wait",
            json_data={"seconds": seconds}
        )
