"""Pytest configuration: make the agent server importable without a real display.

We inject a fake ``pyautogui`` module before any test imports ``agent_server``
(which imports ``desktop_manager`` -> ``pyautogui``). ``mss`` is left uninstalled
so the screenshot code falls back to ``pyautogui.screenshot()`` (also faked).
Pillow is used for real (no display required) so PNG encoding works.
"""
import os
import sys
import types
from pathlib import Path

# Pin terminal/env so any future Rich/Click rendering stays deterministic in
# assertions (SmolVM pins NO_COLOR/TERM and unsets FORCE_COLOR in its conftest).
os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("TERM", "dumb")
os.environ.pop("FORCE_COLOR", None)

DOCKER_DIR = str(Path(__file__).resolve().parent.parent / "docker")
if DOCKER_DIR not in sys.path:
    sys.path.insert(0, DOCKER_DIR)

from PIL import Image  # noqa: E402  (real Pillow, available in CI test deps)


def _make_fake_pyautogui() -> types.ModuleType:
    mod = types.ModuleType("pyautogui")

    mod.PAUSE = 0.0
    mod.FAILSAFE = False

    mod._screen_size = (1920, 1080)
    mod._pos = [0, 0]

    def size():
        return mod._screen_size

    def position():
        return tuple(mod._pos)

    def moveTo(x, y, duration=0.0):
        mod._pos[0], mod._pos[1] = int(x), int(y)

    def click(x=None, y=None, clicks=1, button="left"):
        if x is not None and y is not None:
            mod._pos[0], mod._pos[1] = int(x), int(y)
        return None

    def scroll(amount):
        return None

    def drag(dx, dy, duration=0.0):
        mod._pos[0] += int(dx)
        mod._pos[1] += int(dy)
        return None

    def write(text, interval=0.0):
        return None

    def press(key):
        return None

    def hotkey(*keys):
        return None

    def keyDown(key):
        return None

    def keyUp(key):
        return None

    def screenshot(region=None):
        return Image.new("RGB", (1920, 1080), color=(0, 0, 0))

    def locateOnScreen(image_path, confidence=0.9):
        return None

    mod.size = size
    mod.position = position
    mod.moveTo = moveTo
    mod.click = click
    mod.scroll = scroll
    mod.drag = drag
    mod.write = write
    mod.press = press
    mod.hotkey = hotkey
    mod.keyDown = keyDown
    mod.keyUp = keyUp
    mod.screenshot = screenshot
    mod.locateOnScreen = locateOnScreen
    return mod


# Install the fake before any test module imports agent_server/desktop_manager.
if "pyautogui" not in sys.modules:
    sys.modules["pyautogui"] = _make_fake_pyautogui()


# ---------------------------------------------------------------------------
# Fake cua_driver package
#
# The semantic backend (docker/semantic_backend.py) imports ``cua_driver`` at
# call time. We install a fake package whose ``CuaDriver`` serves a small
# deterministic element tree so tests can exercise the happy path without the
# real driver. Tests targeting degradation paths use driver_url pointing at a
# closed port; those hit CuaDriverUnavailable as usual.
# ---------------------------------------------------------------------------

class _FakeElement:
    def __init__(self, element_id, role, name, app, bbox=None,
                 actionable=None, children=None, description=""):
        self.id = element_id
        self.role = role
        self.name = name
        self.app = app
        self.bbox = bbox
        self.actionable = actionable or []
        self.children = children or []
        self.children_count = len(self.children)
        self.description = description


class _FakeActionResult:
    def __init__(self, element_id, element_name, detail="", ok=True, duration_ms=12):
        self.action_completed = ok
        self.detail = detail or f"{element_name} action completed"
        self.element_id = element_id
        self.element_name = element_name
        self.duration_ms = duration_ms


class _FakeCuaDriver:
    """Deterministic stand-in for cua_driver.CuaDriver.

    ``version(driver_url=...)`` is the liveness probe: it succeeds only for
    reachable URLs (anything but the closed-port test URL), mirroring a real
    driver that would fail to answer at an unbound address.
    """

    DEAD_URL = "http://127.0.0.1:1"

    def __init__(self, driver_url=None, timeout=None):
        self.driver_url = driver_url
        self.timeout = timeout

    def version(self, driver_url=None):
        url = driver_url or self.driver_url
        if url == self.DEAD_URL:
            raise ConnectionError(f"driver not reachable at {url}")
        return "0.0.0-fake"

    def status(self):
        from semantic_backend import DriverStatus
        reachable = self.driver_url != self.DEAD_URL
        return DriverStatus(
            enabled=reachable,
            driver_version=self.version() if reachable else None,
            reachable=reachable,
            error=None if reachable else f"driver not reachable at {self.driver_url}",
            element_counts={"button": 2, "text": 1} if reachable else {},
        )

    def screen_info(self):
        if self.driver_url == self.DEAD_URL:
            raise ConnectionError(f"driver not reachable at {self.driver_url}")
        from semantic_backend import ScreenInfo
        return ScreenInfo(width=1920, height=1080, cursor_x=0, cursor_y=0)

    def get_elements(self, app="", window=""):
        if self.driver_url == self.DEAD_URL:
            raise ConnectionError(f"driver not reachable at {self.driver_url}")
        return [
            _FakeElement(
                element_id="element-1", role="button", name="OK",
                app=app or "xfce4-files", bbox=[10, 20, 80, 30],
                actionable=["click", "press"],
            ),
            _FakeElement(
                element_id="element-2", role="text", name="Files",
                app=app or "xfce4-files", bbox=[10, 60, 200, 24],
            ),
        ]

    def get_element_detail(self, element_id):
        if self.driver_url == self.DEAD_URL:
            raise ConnectionError(f"driver not reachable at {self.driver_url}")
        if element_id == "does-not-exist":
            return None
        return _FakeElement(
            element_id=element_id, role="button", name="OK",
            app="xfce4-files", bbox=[10, 20, 80, 30],
            actionable=["click"], description="The OK button",
        )

    def click(self, element_id):
        if self.driver_url == self.DEAD_URL:
            raise ConnectionError(f"driver not reachable at {self.driver_url}")
        return _FakeActionResult(element_id, "OK")

    def set_value(self, element_id, value):
        if self.driver_url == self.DEAD_URL:
            raise ConnectionError(f"driver not reachable at {self.driver_url}")
        return _FakeActionResult(element_id, "OK", detail=f"set to {value!r}")

    def read_text(self, element_id, max_depth=6):
        if self.driver_url == self.DEAD_URL:
            raise ConnectionError(f"driver not reachable at {self.driver_url}")
        return "Files"


class _FakeCuaDriverModule(types.ModuleType):
    def __init__(self):
        super().__init__("cua_driver")
        self.CuaDriver = _FakeCuaDriver


if "cua_driver" not in sys.modules:
    sys.modules["cua_driver"] = _FakeCuaDriverModule()
