"""
Open-PC Desktop Manager
Handles all desktop automation: screenshots, mouse, keyboard, windows
"""

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Disable pyautogui failsafe for container environment
os.environ['PYAUTOGUI_FAILSAFE'] = '0'

import base64
import io

# Shared logger — agent_server.py configures the root handler;
# this module only sets its name and propagation.
import sys as _sys

import pyautogui
from PIL import Image

_logger_handler = logging.StreamHandler(_sys.stdout)
_logger_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger = logging.getLogger(__name__)
logger.addHandler(_logger_handler)
logger.setLevel(logging.INFO)

# Set pyautogui settings
pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = False

# Thread-local mss instance for performance (avoid recreate per frame)
_thread_local = threading.local()

from sanitization import detect_dangerous_chars


class MouseButton(Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


@dataclass
class ScreenInfo:
    width: int
    height: int
    cursor_x: int
    cursor_y: int


@dataclass
class WindowInfo:
    id: str
    title: str
    x: int
    y: int
    width: int
    height: int


class DesktopManager:
    """
    Manages desktop automation for Open-PC.
    Provides mouse, keyboard, screenshot, and window management.
    """

    def __init__(self, display: str = ":1"):
        self.display = display
        os.environ['DISPLAY'] = display
        self._verify_display()

    def _verify_display(self) -> bool:
        """Verify X11 display is available"""
        try:
            result = subprocess.run(
                ['xset', 'q'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Display verification failed: {e}")
            return False

    def _get_mss(self):
        """Get per-thread mss instance (create on first use)."""
        sct = getattr(_thread_local, 'sct', None)
        if sct is None:
            import mss
            sct = mss.mss()
            _thread_local.sct = sct
        return sct

    def _grab(self, region=None) -> Image.Image | None:
        """Grab screen via mss (cached per thread). Returns PIL Image or None on failure."""
        try:
            sct = self._get_mss()
            if region is None:
                region = sct.monitors[1]
            else:
                # region is dict with left/top/width/height
                region = {
                    'left': region.get('left', 0),
                    'top': region.get('top', 0),
                    'width': region.get('width', sct.monitors[1]['width']),
                    'height': region.get('height', sct.monitors[1]['height']),
                }
            shot = sct.grab(region)
            return Image.frombytes('RGB', shot.size, shot.rgb)
        except Exception as e:
            logger.warning(f"mss grab failed: {e}")
            return None

    def get_screen_info(self) -> ScreenInfo:
        """Get screen dimensions and cursor position"""
        width, height = pyautogui.size()
        x, y = pyautogui.position()
        return ScreenInfo(width=width, height=height, cursor_x=x, cursor_y=y)

    # ============== Screenshot Methods ==============

    def take_screenshot(self) -> bytes:
        """Take a screenshot and return as PNG bytes"""
        img = self._grab()
        if img is None:
            logger.error("mss failed, falling back to pyautogui")
            img = pyautogui.screenshot()
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()

    def take_screenshot_jpeg(self, quality: int = 80) -> bytes:
        """Take a screenshot and return as JPEG bytes (faster for streaming)"""
        img = self._grab()
        if img is None:
            logger.warning("mss failed for JPEG, falling back to pyautogui")
            img = pyautogui.screenshot()
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality)
        return buffer.getvalue()

    def take_screenshot_base64(self) -> str:
        """Take a screenshot and return as base64 string"""
        img_bytes = self.take_screenshot()
        return base64.b64encode(img_bytes).decode('utf-8')

    def take_screenshot_region(self, x: int, y: int, width: int, height: int) -> bytes:
        """Take a screenshot of a specific region"""
        region = {'left': x, 'top': y, 'width': width, 'height': height}
        img = self._grab(region)
        if img is None:
            logger.warning("mss region failed, falling back to pyautogui")
            img = pyautogui.screenshot(region=(x, y, width, height))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    # ============== Mouse Methods ==============

    def mouse_move(self, x: int, y: int, duration: float = 0.0) -> dict[str, Any]:
        """Move mouse to coordinates (clamped to screen bounds)"""
        try:
            screen_w, screen_h = pyautogui.size()
            x = max(0, min(x, screen_w - 1))
            y = max(0, min(y, screen_h - 1))
            if duration > 0:
                pyautogui.moveTo(x, y, duration=duration)
            else:
                pyautogui.moveTo(x, y)
            return {"success": True, "x": x, "y": y}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_click(
        self,
        x: int | None = None,
        y: int | None = None,
        button: MouseButton = MouseButton.LEFT,
        clicks: int = 1,
        duration: float = 0.0
    ) -> dict[str, Any]:
        """Perform mouse click"""
        try:
            if x is not None and y is not None:
                if duration > 0:
                    pyautogui.moveTo(x, y, duration=duration)
                pyautogui.click(x, y, clicks=clicks, button=button.value)
            else:
                pyautogui.click(clicks=clicks, button=button.value)

            return {
                "success": True,
                "action": "click",
                "button": button.value,
                "clicks": clicks,
                "position": {"x": x, "y": y} if x and y else "current"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_double_click(self, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        """Perform double click"""
        return self.mouse_click(x, y, clicks=2)

    def mouse_right_click(self, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        """Perform right click"""
        return self.mouse_click(x, y, button=MouseButton.RIGHT)

    def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> dict[str, Any]:
        """Drag mouse from start to end (coordinates clamped to screen bounds)"""
        try:
            screen_w, screen_h = pyautogui.size()
            start_x = max(0, min(start_x, screen_w - 1))
            start_y = max(0, min(start_y, screen_h - 1))
            end_x = max(0, min(end_x, screen_w - 1))
            end_y = max(0, min(end_y, screen_h - 1))
            pyautogui.moveTo(start_x, start_y)
            pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration)
            return {
                "success": True,
                "action": "drag",
                "from": {"x": start_x, "y": start_y},
                "to": {"x": end_x, "y": end_y}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_scroll(self, clicks: int = 3, direction: str = "down", x: int | None = None, y: int | None = None) -> dict[str, Any]:
        """Scroll mouse wheel (default 3 clicks for reliability)"""
        try:
            if x is not None and y is not None:
                screen_w, screen_h = pyautogui.size()
                x = max(0, min(x, screen_w - 1))
                y = max(0, min(y, screen_h - 1))
                pyautogui.moveTo(x, y)

            scroll_amount = clicks if direction == "down" else -clicks
            pyautogui.scroll(scroll_amount)

            return {
                "success": True,
                "action": "scroll",
                "direction": direction,
                "clicks": clicks
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============== Keyboard Methods ==============

    def keyboard_type(self, text: str, interval: float = 0.05) -> dict[str, Any]:
        """Type text at current cursor position"""
        try:
            pyautogui.write(text, interval=interval)
            return {"success": True, "action": "type", "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_press(self, key: str) -> dict[str, Any]:
        """Press a single key"""
        try:
            pyautogui.press(key)
            return {"success": True, "action": "press", "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_hotkey(self, *keys: str) -> dict[str, Any]:
        """Press keyboard combination (e.g., ctrl+c)"""
        try:
            pyautogui.hotkey(*keys)
            return {"success": True, "action": "hotkey", "keys": list(keys)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_key_down(self, key: str) -> dict[str, Any]:
        """Hold key down"""
        try:
            pyautogui.keyDown(key)
            return {"success": True, "action": "key_down", "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_key_up(self, key: str) -> dict[str, Any]:
        """Release key"""
        try:
            pyautogui.keyUp(key)
            return {"success": True, "action": "key_up", "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============== Window Methods ==============

    def list_windows(self) -> list[WindowInfo]:
        """List all open windows"""
        try:
            result = subprocess.run(
                ['wmctrl', '-lG'],
                capture_output=True,
                text=True,
                timeout=5
            )

            windows = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split()
                    if len(parts) >= 7:
                        windows.append(WindowInfo(
                            id=parts[0],
                            title=' '.join(parts[7:]),
                            x=int(parts[2]),
                            y=int(parts[3]),
                            width=int(parts[4]),
                            height=int(parts[5])
                        ))
            return windows
        except Exception as e:
            logger.error(f"Failed to list windows: {e}")
            return []

    def get_active_window(self) -> WindowInfo | None:
        """Get currently active window"""
        try:
            # Get window ID, geometry, and title in one call
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowgeometry'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return None

            lines = result.stdout.strip().split('\n')
            window_id = None
            x, y, w, h = 0, 0, 0, 0

            for line in lines:
                if line.startswith('Window'):
                    window_id = line.split()[-1]
                elif line.startswith('Position:'):
                    parts = line.split()
                    x = int(parts[1].rstrip(','))
                    y = int(parts[2])
                elif line.startswith('Geometry:'):
                    parts = line.split()
                    w = int(parts[1].rstrip('x'))
                    h = int(parts[2])

            if window_id:
                # Get window title
                title_res = subprocess.run(
                    ['xdotool', 'getactivewindow', 'getwindowname'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                title = title_res.stdout.strip() if title_res.returncode == 0 else ""
                return WindowInfo(id=window_id, title=title, x=x, y=y, width=w, height=h)
        except Exception as e:
            logger.error(f"Failed to get active window: {e}")
        return None

    def focus_window(self, window_id: str) -> dict[str, Any]:
        """Focus a window by ID"""
        try:
            subprocess.run(
                ['wmctrl', '-i', '-a', window_id],
                capture_output=True,
                timeout=5
            )
            return {"success": True, "action": "focus_window", "window_id": window_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_window(self, window_id: str | None = None) -> dict[str, Any]:
        """Close window by ID or active window"""
        try:
            if window_id:
                subprocess.run(['wmctrl', '-i', '-c', window_id], timeout=5)
            else:
                pyautogui.hotkey('alt', 'F4')
            return {"success": True, "action": "close_window", "window_id": window_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def maximize_window(self, window_id: str | None = None) -> dict[str, Any]:
        """Maximize window"""
        try:
            if window_id:
                subprocess.run(
                    ['wmctrl', '-i', '-r', window_id, '-b', 'add,maximized_vert,maximized_horz'],
                    timeout=5
                )
            else:
                pyautogui.hotkey('alt', 'F10')
            return {"success": True, "action": "maximize_window"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def minimize_window(self, window_id: str | None = None) -> dict[str, Any]:
        """Minimize window"""
        try:
            if window_id:
                subprocess.run(
                    ['wmctrl', '-i', '-r', window_id, '-b', 'add,hidden'],
                    timeout=5
                )
            else:
                pyautogui.hotkey('alt', 'F9')
            return {"success": True, "action": "minimize_window"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============== Application Methods ==============

    def launch_application(self, app_name: str) -> dict[str, Any]:
        """Launch an application"""
        try:
            subprocess.Popen([app_name], start_new_session=True)
            time.sleep(1)  # Wait for app to start
            return {"success": True, "action": "launch", "application": app_name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_url(self, url: str, browser: str = "google-chrome") -> dict[str, Any]:
        """Open URL in browser"""
        try:
            subprocess.Popen(
                [browser, '--no-sandbox', '--disable-setuid-sandbox', url],
                start_new_session=True
            )
            return {"success": True, "action": "open_url", "url": url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_command(self, command: str, timeout: int = 30) -> dict[str, Any]:
        """Run shell command with dangerous character sanitization.

        Blocks characters that enable command chaining or injection:
        ; | & ` $() ${ } and newlines are stripped to prevent arbitrary code execution.
        Note: Sanitization is best-effort; for production, prefer allowlisting and running
        as an unprivileged user inside the container.
        """
        if not command or not command.strip():
            return {"success": False, "error": "Empty command"}

        # Detect dangerous shell constructs (delegates to pure, testable helper)
        found = detect_dangerous_chars(command)

        if found:
            blocked = ', '.join(found)
            return {"success": False, "error": f"Command blocked due to dangerous characters: {blocked}"}

        # At this point command is considered safe enough to run
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============== OCR Methods ==============

    def ocr_screenshot(self, region: tuple[int, int, int, int] | None = None) -> dict[str, Any]:
        """Perform OCR on screenshot"""
        try:
            import pytesseract

            screenshot = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()

            text = pytesseract.image_to_string(screenshot)
            return {"success": True, "text": text.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============== Utility Methods ==============

    def wait(self, seconds: float) -> dict[str, Any]:
        """Wait for specified seconds"""
        time.sleep(seconds)
        return {"success": True, "action": "wait", "seconds": seconds}

    def get_mouse_position(self) -> tuple[int, int]:
        """Get current mouse position"""
        return pyautogui.position()

    def locate_on_screen(self, image_path: str, confidence: float = 0.9) -> dict[str, Any] | None:
        """Locate an image on screen using template matching.

        Args:
            image_path: Path to the reference image file
            confidence: Minimum confidence score (0-1)

        Returns:
            Dict with x, y, width, height, center or error message
        """
        try:
            location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if location:
                return {
                    "success": True,
                    "x": location.left,
                    "y": location.top,
                    "width": location.width,
                    "height": location.height,
                    "center": {"x": location.left + location.width // 2,
                              "y": location.top + location.height // 2}
                }
            return {"success": False, "error": "Image not found on screen"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def locate_on_screen_base64(self, image_b64: str, confidence: float = 0.9) -> dict[str, Any] | None:
        """Locate an image on screen from a base64-encoded PNG.

        Useful for API endpoints that receive images as base64 rather than file paths.

        Args:
            image_b64: Base64-encoded PNG image string
            confidence: Minimum confidence score (0-1)

        Returns:
            Dict with x, y, width, height, center or error message
        """
        import tempfile
        try:
            img_data = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(img_data))
            # Write to temp file for pyautogui.locateOnScreen
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                img.save(tmp.name, 'PNG')
                tmp_path = tmp.name
            try:
                return self.locate_on_screen(tmp_path, confidence)
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            return {"success": False, "error": str(e)}


# Export for use in agent_server
__all__ = ['DesktopManager', 'ScreenInfo', 'WindowInfo', 'MouseButton']
