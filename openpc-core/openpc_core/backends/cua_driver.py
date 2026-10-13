"""CUA Driver backend — native desktop control via CUA.

Implements the ``DesktopBackend`` protocol for bare-metal macOS, Windows,
and Linux using the real ``cua-driver`` Python SDK (Rust-backed, async):

    driver = CuaDriver.create()                 # same-process runtime
    await driver.type_text(TypeTextInput(text=..., target=..., scope=None, session=None))
    await driver.get_desktop_state(GetDesktopStateInput(session=None, screenshot_out_file=None))

Every operation tries the CUA Driver first and falls back to pyautogui when
CUA is unavailable or errors — so the backend degrades gracefully instead
of failing. Click/scroll/key-down/key-up have no direct CUA input types in
the current SDK surface, so they always use pyautogui.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
import signal
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)


class CUABackendUnavailable(RuntimeError):
    """Raised when no desktop control path (CUA or pyautogui) is available."""
    pass


class CUADriverBackend:
    """DesktopBackend implementation via CUA Driver SDK, pyautogui fallback.

    Connects to a same-process cua-driver runtime and delegates actions
    through it. Falls back to pyautogui when cua-driver is not installed
    or a CUA call fails.
    """

    backend = "bare-metal-cua"

    def __init__(self, mode: str = "bounded", prefer_native: bool = False):
        self.mode = mode
        self._driver = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._fallback_ok = False

        if not prefer_native:
            try:
                import cua_driver  # noqa: F401
                self._has_cua_pkg = True
            except ImportError:
                self._has_cua_pkg = False
        else:
            self._has_cua_pkg = False

        if self._has_cua_pkg:
            try:
                from cua_driver import CuaDriver
                self._driver = CuaDriver.create()
                logger.info("CUA Driver backend: same-process runtime created")
            except Exception as e:
                logger.warning(f"CUA Driver create failed: {e}")
                self._driver = None

        try:
            import pyautogui  # noqa: F401
            os.environ.setdefault("PYAUTOGUI_FAILSAFE", "0")
            self._fallback_ok = True
        except ImportError:
            self._fallback_ok = False

        if self._driver is None and not self._fallback_ok:
            raise CUABackendUnavailable(
                "No desktop control path available. Install either: "
                "pip install cua-driver  (preferred) or pip install pyautogui"
            )

    # ── CUA Driver runtime helpers ───────────────────────────────────

    def _run_async(self, coro, timeout: float = 30.0):
        """Run an async driver coroutine on a dedicated event loop."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))

    def _target(self):
        """Default CUA action target: the primary desktop display."""
        from cua_driver import ActionTarget
        return ActionTarget.DESKTOP(display_id="primary")

    # ── Screen ───────────────────────────────────────────────────────

    def get_screen_info(self) -> Any:
        if self._driver is not None:
            try:
                from cua_driver import GetScreenSizeInput
                result = self._run_async(
                    self._driver.get_screen_size(GetScreenSizeInput(session=None))
                )
                if getattr(result, "is_error", False):
                    raise RuntimeError(getattr(result, "text", "screen size failed"))
                w, h = getattr(result, "width", None), getattr(result, "height", None)
                if w and h:
                    return {"width": int(w), "height": int(h)}
            except Exception as e:
                logger.warning(f"CUA screen info failed: {e}")
        import pyautogui
        w, h = pyautogui.size()
        x, y = pyautogui.position()
        return {"width": w, "height": h, "cursor_x": x, "cursor_y": y}

    def take_screenshot(self) -> bytes:
        if self._driver is not None:
            try:
                from cua_driver import GetDesktopStateInput
                result = self._run_async(
                    self._driver.get_desktop_state(
                        GetDesktopStateInput(session=None, screenshot_out_file=None)
                    )
                )
                if getattr(result, "is_error", True) or not getattr(result, "images", None):
                    raise RuntimeError(getattr(result, "text", "desktop capture returned no image"))
                import base64
                return base64.b64decode(result.images[0].data_base64)
            except Exception as e:
                logger.warning(f"CUA screenshot failed: {e}")
        import io
        import pyautogui
        from PIL import Image
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def take_screenshot_jpeg(self, quality: int = 80) -> bytes:
        raw = self.take_screenshot()
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(raw))
        # JPEG has no alpha channel — macOS captures are RGBA, so flatten.
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

    def take_screenshot_base64(self) -> str:
        import base64
        raw = self.take_screenshot()
        return base64.b64encode(raw).decode()

    def take_screenshot_scaled_base64(self, max_width: int = 640, quality: int = 55) -> str:
        """Scaled-down JPEG screenshot as base64 — optimised for LLM context."""
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(self.take_screenshot()))
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        # JPEG has no alpha channel — macOS captures are RGBA, so flatten.
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        import base64
        return base64.b64encode(buf.getvalue()).decode()

    def take_screenshot_region(self, x: int, y: int, width: int, height: int) -> bytes:
        raw = self.take_screenshot()
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(raw))
        region = img.crop((x, y, x + width, y + height))
        buf = io.BytesIO()
        region.save(buf, format="PNG")
        return buf.getvalue()

    # ── Mouse ────────────────────────────────────────────────────────

    def mouse_move(self, x: int, y: int, duration: float = 0.0) -> Any:
        if self._driver is not None:
            try:
                from cua_driver import MoveCursorInput
                self._run_async(
                    self._driver.move_cursor(MoveCursorInput(
                        x=float(x), y=float(y), target=self._target(), scope=None, session=None,
                    ))
                )
                return {"x": x, "y": y}
            except Exception as e:
                logger.warning(f"CUA mouse_move failed: {e}")
        import pyautogui
        pyautogui.moveTo(x, y, duration=duration)
        return {"x": x, "y": y}

    def mouse_click(
        self, x: int | None = None, y: int | None = None,
        button: str = "left", clicks: int = 1, duration: float = 0.0,
    ) -> Any:
        # No direct CUA click input in the current SDK surface — use pyautogui.
        # The agent server passes docker's MouseButton enum; pyautogui wants
        # the plain string — normalise both.
        btn = button.value if hasattr(button, "value") else str(button)
        import pyautogui
        pyautogui.click(x=x, y=y, clicks=clicks, duration=duration, button=btn)
        return {"x": x, "y": y}

    def mouse_double_click(self, x: int | None = None, y: int | None = None) -> Any:
        return self.mouse_click(x=x, y=y, clicks=2, button="left")

    def mouse_right_click(self, x: int | None = None, y: int | None = None) -> Any:
        return self.mouse_click(x=x, y=y, clicks=1, button="right")

    def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> Any:
        if self._driver is not None:
            try:
                from cua_driver import DragInput
                self._run_async(
                    self._driver.drag(DragInput(
                        from_x=float(start_x), from_y=float(start_y),
                        to_x=float(end_x), to_y=float(end_y),
                        target=self._target(), scope=None, session=None,
                        duration_ms=int(duration * 1000), steps=None, button=None, modifier=None,
                    ))
                )
                return {"start": (start_x, start_y), "end": (end_x, end_y)}
            except Exception as e:
                logger.warning(f"CUA mouse_drag failed: {e}")
        import pyautogui
        pyautogui.moveTo(start_x, start_y)
        pyautogui.mouseDown()
        pyautogui.dragTo(end_x, end_y, duration=duration)
        pyautogui.mouseUp()
        return {"start": (start_x, start_y), "end": (end_x, end_y)}

    def mouse_scroll(self, clicks: int = 3, direction: str = "down", x: int | None = None, y: int | None = None) -> Any:
        # No direct CUA scroll input in the current SDK surface — use pyautogui.
        import pyautogui
        scroll_amount = clicks if direction == "up" else -clicks
        if x is not None and y is not None:
            pyautogui.scroll(scroll_amount, x, y)
        else:
            pyautogui.scroll(scroll_amount)
        return {"clicks": clicks, "direction": direction}

    def get_mouse_position(self) -> tuple[int, int]:
        if self._driver is not None:
            try:
                from cua_driver import GetCursorPositionInput
                result = self._run_async(
                    self._driver.get_cursor_position(GetCursorPositionInput(session=None))
                )
                if not getattr(result, "is_error", False):
                    pos = getattr(result, "position", None)
                    if pos:
                        return (int(pos.x), int(pos.y))
            except Exception as e:
                logger.warning(f"CUA cursor position failed: {e}")
        import pyautogui
        x, y = pyautogui.position()
        return (x, y)

    # ── Keyboard ─────────────────────────────────────────────────────

    def keyboard_type(self, text: str, interval: float = 0.05) -> Any:
        if self._driver is not None:
            try:
                from cua_driver import TypeTextInput
                result = self._run_async(
                    self._driver.type_text(TypeTextInput(
                        text=text, target=self._target(), scope=None, session=None,
                    ))
                )
                if getattr(result, "is_error", False):
                    raise RuntimeError(getattr(result, "text", "type_text failed"))
                return {"text": text}
            except Exception as e:
                logger.warning(f"CUA keyboard_type failed: {e}")
        import pyautogui
        pyautogui.typewrite(text, interval=interval)
        return {"text": text}

    def keyboard_press(self, key: str) -> Any:
        if self._driver is not None:
            try:
                from cua_driver import PressKeyInput
                result = self._run_async(
                    self._driver.press_key(PressKeyInput(
                        key=key.upper() if key.isalpha() else key,
                        target=self._target(), scope=None, session=None, modifiers=None,
                    ))
                )
                if getattr(result, "is_error", False):
                    raise RuntimeError(getattr(result, "text", "press_key failed"))
                return {"key": key}
            except Exception as e:
                logger.warning(f"CUA keyboard_press failed: {e}")
        import pyautogui
        pyautogui.press(key)
        return {"key": key}

    def keyboard_hotkey(self, *keys: str) -> Any:
        if self._driver is not None:
            try:
                from cua_driver import HotkeyInput
                result = self._run_async(
                    self._driver.hotkey(HotkeyInput(
                        keys=list(keys), target=self._target(), scope=None, session=None,
                    ))
                )
                if getattr(result, "is_error", False):
                    raise RuntimeError(getattr(result, "text", "hotkey failed"))
                return {"keys": list(keys)}
            except Exception as e:
                logger.warning(f"CUA keyboard_hotkey failed: {e}")
        import pyautogui
        pyautogui.hotkey(*keys)
        return {"keys": list(keys)}

    def keyboard_key_down(self, key: str) -> Any:
        # No CUA key-down input in the current SDK surface — use pyautogui.
        import pyautogui
        pyautogui.keyDown(key)
        return {"key": key}

    def keyboard_key_up(self, key: str) -> Any:
        # No CUA key-up input in the current SDK surface — use pyautogui.
        import pyautogui
        pyautogui.keyUp(key)
        return {"key": key}

    # ── Windows ──────────────────────────────────────────────────────

    def list_windows(self) -> list[Any]:
        if self._driver is not None:
            try:
                from cua_driver import ListWindowsInput
                out = self._run_async(
                    self._driver.list_windows(ListWindowsInput(pid=None, on_screen_only=True))
                )
                return [{"id": str(w.window_id), "title": w.title} for w in out.windows]
            except Exception as e:
                logger.warning(f"CUA list_windows failed: {e}")
        system = platform.system()
        if system == "Darwin":
            return self._list_windows_macos()
        elif system == "Windows":
            return self._list_windows_windows()
        return self._list_windows_linux()

    def _list_windows_macos(self) -> list[Any]:
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of every process '
                 'whose background only is false'],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                titles = [t.strip() for t in result.stdout.split("\n") if t.strip()]
                return [{"id": f"macos:{t}", "title": t} for t in titles[:50]]
        except Exception:
            pass
        return []

    def get_active_window(self) -> Any:
        windows = self.list_windows()
        if not windows:
            return None
        return windows[0]

    def focus_window(self, window_id: str) -> Any:
        system = platform.system()
        if system == "Darwin":
            app_name = window_id.split(":", 1)[1] if ":" in window_id else window_id
            try:
                subprocess.run(
                    ["osascript", "-e",
                     f'tell application "System Events" to set frontmost of process "{app_name}" to true'],
                    capture_output=True, timeout=5,
                )
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        elif system == "Windows":
            try:
                import win32gui
                hwnd = int(window_id)
                win32gui.SetForegroundWindow(hwnd)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            try:
                subprocess.run(["xdotool", "windowactivate", window_id], capture_output=True, timeout=5)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def close_window(self, window_id: str | None = None) -> Any:
        system = platform.system()
        if system == "Darwin":
            self.keyboard_hotkey("command", "w")
        else:
            self.keyboard_hotkey("alt", "f4")
        return {"success": True}

    def maximize_window(self, window_id: str | None = None) -> Any:
        system = platform.system()
        if system == "Darwin":
            self.keyboard_hotkey("command", "control", "return")
        elif system == "Windows":
            self.keyboard_hotkey("win", "up")
        else:
            self.keyboard_hotkey("alt", "f10")
        return {"success": True}

    def minimize_window(self, window_id: str | None = None) -> Any:
        system = platform.system()
        if system == "Darwin":
            self.keyboard_hotkey("command", "m")
        elif system == "Windows":
            self.keyboard_hotkey("win", "down")
        else:
            self.keyboard_hotkey("alt", "space", "n")
        return {"success": True}

    def launch_application(self, app_name: str) -> Any:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", "-a", app_name], capture_output=True, timeout=10)
        elif system == "Windows":
            subprocess.Popen([app_name], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(["xdg-open", app_name], capture_output=True, timeout=10)
        return {"success": True}

    def open_url(self, url: str, browser: str = "google-chrome") -> Any:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", url], capture_output=True, timeout=10)
        elif system == "Windows":
            os.system(f'start "" "{url}"')
        else:
            subprocess.run(["xdg-open", url], capture_output=True, timeout=10)
        return {"success": True}

    def _list_windows_windows(self) -> list[Any]:
        try:
            import win32gui
            windows = []
            def callback(hwnd, accum):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        accum.append({"id": str(hwnd), "title": title})
                except Exception:
                    pass
                return True
            win32gui.EnumWindows(callback, windows)
            return windows[:50]
        except ImportError:
            return []

    def _list_windows_linux(self) -> list[Any]:
        try:
            result = subprocess.run(
                ["xdotool", "search", "--maxwindow", "50", "--onlywith", "_NET_WM_NAME"],
                capture_output=True, text=True, timeout=5,
            )
            windows = []
            for wid in result.stdout.strip().split("\n"):
                if not wid:
                    continue
                try:
                    title_result = subprocess.run(
                        ["xdotool", "getwindowname", wid],
                        capture_output=True, text=True, timeout=3,
                    )
                    title = title_result.stdout.strip() if title_result.returncode == 0 else ""
                    windows.append({"id": wid.strip(), "title": title})
                except Exception:
                    windows.append({"id": wid.strip(), "title": ""})
            return windows
        except Exception:
            pass
        return []

    # ── Commands (guardrails-validated) ─────────────────────────────

    def run_command(self, command: str, timeout: int = 30) -> Any:
        """Run a shell command on the host OS.

        In bounded/standard modes the command is validated against the
        guardrails whitelist before execution and every attempt is audited.
        """
        engine = None
        try:
            from openpc_core.guardrails.engine import get_shared_engine
            engine = get_shared_engine()
        except Exception:  # pragma: no cover - guardrails optional at runtime
            engine = None

        if engine is not None:
            verdict = engine.validate_command(command)
            if not verdict.get("allowed", False):
                engine.audit_log_action(
                    action="run_command", target=command,
                    result="blocked", blocked=True, reason=verdict.get("reason", ""),
                )
                return {"success": False, "error": verdict.get("reason", "Command blocked by guardrails.")}
            engine.audit_log_action(action="run_command", target=command, result="allowed")

        # Run in its own session so a timeout can kill the whole process
        # group (subprocess.run(timeout=...) only kills the direct child and
        # orphans grandchildren — mirrors docker/command_runner.py behaviour).
        proc = subprocess.Popen(
            command, shell=True, start_new_session=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return {
                "success": True,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            try:
                stdout, stderr = proc.communicate(timeout=2)
            except Exception:  # noqa: BLE001
                stdout, stderr = "", ""
            return {
                "success": False,
                "stdout": stdout or "",
                "stderr": stderr or "",
                "error": (
                    f"Command timed out after {timeout}s and was killed. "
                    "Increase the timeout or make the command terminate on its own."
                ),
            }

    # ── Vision / OCR ────────────────────────────────────────────────

    def ocr_screenshot(self, region: tuple[int, int, int, int] | None = None) -> Any:
        """OCR the screen using pytesseract (requires: pip install pytesseract)."""
        try:
            from PIL import Image
            import io
            raw = self.take_screenshot()
            img = Image.open(io.BytesIO(raw))
            if region:
                img = img.crop(region)
            try:
                import pytesseract
                text = pytesseract.image_to_string(img)
                return {"success": True, "text": text}
            except ImportError:
                return {"success": False, "error": "pytesseract not installed. Run: pip install pytesseract"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def locate_on_screen(self, image_path: str, confidence: float = 0.9) -> Any:
        import pyautogui
        try:
            loc = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if loc is None:
                return {"found": False}
            center = pyautogui.center(loc)
            return {"found": True, "x": int(center.x), "y": int(center.y)}
        except Exception as e:
            return {"found": False, "error": str(e)}

    def locate_on_screen_base64(self, image_b64: str, confidence: float = 0.9) -> Any:
        import base64
        import io
        from PIL import Image
        raw = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(raw))
        import pyautogui
        try:
            loc = pyautogui.locateOnImage(img, confidence=confidence)
            if loc is None:
                return {"found": False}
            center = pyautogui.center(loc)
            return {"found": True, "x": int(center.x), "y": int(center.y)}
        except Exception as e:
            return {"found": False, "error": str(e)}