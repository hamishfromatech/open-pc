"""Pytest configuration: make the agent server importable without a real display.

We inject a fake ``pyautogui`` module before any test imports ``agent_server``
(which imports ``desktop_manager`` -> ``pyautogui``). ``mss`` is left uninstalled
so the screenshot code falls back to ``pyautogui.screenshot()`` (also faked).
Pillow is used for real (no display required) so PNG encoding works.
"""
import sys
import types
from pathlib import Path

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
