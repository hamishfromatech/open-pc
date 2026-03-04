"""
Open-PC Desktop Manager
Handles all desktop automation: screenshots, mouse, keyboard, windows
"""

import os
import time
import subprocess
import logging
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

# Disable pyautogui failsafe for container environment
os.environ['PYAUTOGUI_FAILSAFE'] = '0'

import pyautogui
from PIL import Image
import io
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set pyautogui settings
pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = False


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

    def get_screen_info(self) -> ScreenInfo:
        """Get screen dimensions and cursor position"""
        width, height = pyautogui.size()
        x, y = pyautogui.position()
        return ScreenInfo(width=width, height=height, cursor_x=x, cursor_y=y)

    # ============== Screenshot Methods ==============

    def take_screenshot(self) -> bytes:
        """Take a screenshot and return as PNG bytes"""
        try:
            # Use mss for better performance
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                buffer = io.BytesIO()
                img.save(buffer, format='PNG', optimize=True)
                return buffer.getvalue()
        except Exception as e:
            logger.error(f"MSS screenshot failed, falling back to pyautogui: {e}")
            # Fallback to pyautogui
            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            return buffer.getvalue()

    def take_screenshot_jpeg(self, quality: int = 80) -> bytes:
        """Take a screenshot and return as JPEG bytes (faster for streaming)"""
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=quality)
                return buffer.getvalue()
        except Exception as e:
            logger.error(f"JPEG screenshot failed: {e}")
            # Fallback to pyautogui
            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format='JPEG', quality=quality)
            return buffer.getvalue()

    def take_screenshot_base64(self) -> str:
        """Take a screenshot and return as base64 string"""
        img_bytes = self.take_screenshot()
        return base64.b64encode(img_bytes).decode('utf-8')

    def take_screenshot_region(self, x: int, y: int, width: int, height: int) -> bytes:
        """Take a screenshot of a specific region"""
        try:
            import mss
            with mss.mss() as sct:
                monitor = {"left": x, "top": y, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                return buffer.getvalue()
        except Exception:
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            return buffer.getvalue()

    def take_screenshot_jpeg(self, quality: int = 80) -> bytes:
        """Take a screenshot and return as JPEG bytes (faster for streaming)"""
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=quality)
                return buffer.getvalue()
        except Exception as e:
            logger.error(f"MSS screenshot failed, falling back to pyautogui: {e}")
            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format='JPEG', quality=quality)
            return buffer.getvalue()

    # ============== Mouse Methods ==============

    def mouse_move(self, x: int, y: int, duration: float = 0.0) -> Dict[str, Any]:
        """Move mouse to coordinates"""
        try:
            if duration > 0:
                pyautogui.moveTo(x, y, duration=duration)
            else:
                pyautogui.moveTo(x, y)
            return {"success": True, "x": x, "y": y}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: MouseButton = MouseButton.LEFT,
        clicks: int = 1,
        duration: float = 0.0
    ) -> Dict[str, Any]:
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

    def mouse_double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Perform double click"""
        return self.mouse_click(x, y, clicks=2)

    def mouse_right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Perform right click"""
        return self.mouse_click(x, y, button=MouseButton.RIGHT)

    def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> Dict[str, Any]:
        """Drag mouse from start to end"""
        try:
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

    def mouse_scroll(self, clicks: int, direction: str = "down", x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Scroll mouse wheel"""
        try:
            if x is not None and y is not None:
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

    def keyboard_type(self, text: str, interval: float = 0.05) -> Dict[str, Any]:
        """Type text at current cursor position"""
        try:
            pyautogui.write(text, interval=interval)
            return {"success": True, "action": "type", "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_press(self, key: str) -> Dict[str, Any]:
        """Press a single key"""
        try:
            pyautogui.press(key)
            return {"success": True, "action": "press", "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_hotkey(self, *keys: str) -> Dict[str, Any]:
        """Press keyboard combination (e.g., ctrl+c)"""
        try:
            pyautogui.hotkey(*keys)
            return {"success": True, "action": "hotkey", "keys": list(keys)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_key_down(self, key: str) -> Dict[str, Any]:
        """Hold key down"""
        try:
            pyautogui.keyDown(key)
            return {"success": True, "action": "key_down", "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def keyboard_key_up(self, key: str) -> Dict[str, Any]:
        """Release key"""
        try:
            pyautogui.keyUp(key)
            return {"success": True, "action": "key_up", "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============== Window Methods ==============

    def list_windows(self) -> List[WindowInfo]:
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

    def get_active_window(self) -> Optional[WindowInfo]:
        """Get currently active window"""
        try:
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowgeometry'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse window info
                lines = result.stdout.strip().split('\n')
                window_id = None
                x, y, w, h = 0, 0, 0, 0

                for line in lines:
                    if 'Window' in line:
                        window_id = line.split()[-1]
                    elif 'Position:' in line:
                        parts = line.split()
                        x, y = int(parts[1].rstrip(',')), int(parts[2])
                    elif 'Geometry:' in line:
                        parts = line.split()
                        w, h = int(parts[1].rstrip('x')), int(parts[2])

                if window_id:
                    return WindowInfo(id=window_id, title="", x=x, y=y, width=w, height=h)
        except Exception as e:
            logger.error(f"Failed to get active window: {e}")
        return None

    def focus_window(self, window_id: str) -> Dict[str, Any]:
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

    def close_window(self, window_id: Optional[str] = None) -> Dict[str, Any]:
        """Close window by ID or active window"""
        try:
            if window_id:
                subprocess.run(['wmctrl', '-i', '-c', window_id], timeout=5)
            else:
                pyautogui.hotkey('alt', 'F4')
            return {"success": True, "action": "close_window", "window_id": window_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def maximize_window(self, window_id: Optional[str] = None) -> Dict[str, Any]:
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

    def minimize_window(self, window_id: Optional[str] = None) -> Dict[str, Any]:
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

    def launch_application(self, app_name: str) -> Dict[str, Any]:
        """Launch an application"""
        try:
            subprocess.Popen([app_name], start_new_session=True)
            time.sleep(1)  # Wait for app to start
            return {"success": True, "action": "launch", "application": app_name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_url(self, url: str, browser: str = "google-chrome") -> Dict[str, Any]:
        """Open URL in browser"""
        try:
            subprocess.Popen(
                [browser, '--no-sandbox', '--disable-setuid-sandbox', url],
                start_new_session=True
            )
            return {"success": True, "action": "open_url", "url": url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Run shell command"""
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

    def ocr_screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """Perform OCR on screenshot"""
        try:
            import pytesseract

            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()

            text = pytesseract.image_to_string(screenshot)
            return {"success": True, "text": text.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============== Utility Methods ==============

    def wait(self, seconds: float) -> Dict[str, Any]:
        """Wait for specified seconds"""
        time.sleep(seconds)
        return {"success": True, "action": "wait", "seconds": seconds}

    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position"""
        return pyautogui.position()

    def locate_on_screen(self, image_path: str, confidence: float = 0.9) -> Optional[Dict[str, Any]]:
        """Locate an image on screen"""
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


# Export for use in agent_server
__all__ = ['DesktopManager', 'ScreenInfo', 'WindowInfo', 'MouseButton']