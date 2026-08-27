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

import contextlib
import tempfile

from command_runner import run_shell_command
from io_utils import atomic_write_bytes


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

    This is the in-process X11 desktop backend (see backends.DesktopBackend).
    """

    backend = "local"

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

    def take_screenshot_scaled(self, max_width: int = 640, quality: int = 55, format: str = 'JPEG') -> bytes:
        """Take a screenshot, scale down if wider than max_width, return compressed bytes.

        Ideal for LLM context windows — a 1920x1080 screenshot becomes ~640x360 JPEG
        which is ~28KB of base64 instead of ~830KB. LLMs internally downscale to
        512x512 tiles anyway, so 640px preserves all readable detail.
        """
        img = self._grab()
        if img is None:
            logger.warning("mss failed for scaled screenshot, falling back to pyautogui")
            img = pyautogui.screenshot()
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        buffer = io.BytesIO()
        fmt = format.upper()
        if fmt == 'JPEG':
            img = img.convert('RGB')  # JPEG needs RGB
        img.save(buffer, format=fmt, quality=quality if fmt == 'JPEG' else None, optimize=True)
        return buffer.getvalue()

    def take_screenshot_base64(self) -> str:
        """Take a screenshot and return as base64 string"""
        img_bytes = self.take_screenshot()
        return base64.b64encode(img_bytes).decode('utf-8')

    def take_screenshot_scaled_base64(self, max_width: int = 640, quality: int = 55) -> str:
        """Take a scaled screenshot and return as base64 string (LLM-friendly)."""
        img_bytes = self.take_screenshot_scaled(max_width=max_width, quality=quality)
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
            # Ensure X11 environment is passed to the subprocess
            env = os.environ.copy()
            env['DISPLAY'] = self.display
            # Ensure Xauthority is set for X11 access
            if 'XAUTHORITY' not in env:
                xauthority = os.path.expanduser('~/.Xauthority')
                if os.path.exists(xauthority):
                    env['XAUTHORITY'] = xauthority
                elif os.path.exists('/home/desktop/.Xauthority'):
                    env['XAUTHORITY'] = '/home/desktop/.Xauthority'

            subprocess.Popen(
                [app_name],
                env=env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait for window to appear
            time.sleep(2)

            # Try to raise the window using xdotool
            # Find the newest window and raise it
            subprocess.run(
                ['xdotool', 'search', '--onlyvisible', '--class', app_name, 'windowraise', '%1'],
                capture_output=True,
                timeout=5
            )

            return {"success": True, "action": "launch", "application": app_name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_url(self, url: str, browser: str = "google-chrome") -> dict[str, Any]:
        """Open URL in browser"""
        try:
            # Ensure X11 environment is passed to the subprocess
            env = os.environ.copy()
            env['DISPLAY'] = self.display
            if 'XAUTHORITY' not in env:
                xauthority = os.path.expanduser('~/.Xauthority')
                if os.path.exists(xauthority):
                    env['XAUTHORITY'] = xauthority
                elif os.path.exists('/home/desktop/.Xauthority'):
                    env['XAUTHORITY'] = '/home/desktop/.Xauthority'

            # Chrome flags to ensure window is visible and focused
            chrome_flags = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--start-maximized',
                '--disable-extensions',
                '--no-first-run',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-translate',
                '--disable-sync',
                '--disable-dev-shm-usage',
                '--new-window',           # Force new window
                '--disable-background-mode',  # Prevent background mode
                '--disable-minimized',    # Prevent minimized state
                '--active-on-launch',     # Make active on launch
            ]

            subprocess.Popen(
                [browser] + chrome_flags + [url],
                env=env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait for window to appear
            time.sleep(3)

            # Force activate Chrome window using xdotool
            # First find the Chrome window
            find_result = subprocess.run(
                ['xdotool', 'search', '--onlyvisible', '--class', 'chrome'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if find_result.returncode == 0 and find_result.stdout.strip():
                # Get the last (newest) window ID
                window_ids = find_result.stdout.strip().split('\n')
                if window_ids:
                    window_id = window_ids[-1]
                    # Activate, raise, and focus the window
                    subprocess.run(
                        ['xdotool', 'windowactivate', window_id],
                        capture_output=True,
                        timeout=5
                    )
                    subprocess.run(
                        ['xdotool', 'windowraise', window_id],
                        capture_output=True,
                        timeout=5
                    )
                    subprocess.run(
                        ['xdotool', 'windowfocus', window_id],
                        capture_output=True,
                        timeout=5
                    )

            # Also use wmctrl as fallback
            subprocess.run(
                ['wmctrl', '-a', 'Chrome'],
                capture_output=True,
                timeout=5
            )

            return {"success": True, "action": "open_url", "url": url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_command(self, command: str, timeout: int = 30) -> dict[str, Any]:
        """Run a shell command safely.

        Sanitizes dangerous shell constructs (delegates to the pure
        ``detect_dangerous_chars`` helper), then runs the command in its own
        process group so a timeout kills the whole tree rather than orphaning
        children. The actual execution lives in ``command_runner.run_shell_command``
        so it can be unit-tested in CI without a display.
        """
        return run_shell_command(command, timeout)

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
        try:
            img_data = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(img_data))
            buf = io.BytesIO()
            img.save(buf, 'PNG')
            # Write the temp reference image atomically and always clean it up,
            # so a crash never leaks a file and a concurrent reader never sees a
            # half-written image. (See io_utils.atomic_write_bytes.)
            with contextlib.ExitStack() as stack:
                fd, tmp_path = tempfile.mkstemp(suffix='.png')
                os.close(fd)
                stack.callback(lambda p=tmp_path: os.unlink(p) if os.path.exists(p) else None)
                atomic_write_bytes(tmp_path, buf.getvalue())
                return self.locate_on_screen(tmp_path, confidence)
        except Exception as e:
            return {"success": False, "error": str(e)}


# Export for use in agent_server
__all__ = ['DesktopManager', 'ScreenInfo', 'WindowInfo', 'MouseButton']
