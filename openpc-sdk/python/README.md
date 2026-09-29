# Open-PC SDK (Python)

Official Python client for Open-PC Desktop Control.

## Installation

```bash
pip install openpc-sdk
```

## Quick Start

```python
import asyncio
from openpc_sdk import OpenPCClient

async def main():
    async with OpenPCClient() as client:
        # Check health
        health = await client.health()
        print(health)

        # Get screen info
        screen = await client.screen_info()
        print(f"Screen: {screen.width}x{screen.height}")

        # Take screenshot
        screenshot = await client.screenshot()
        print(screenshot.image_base64)

        # Control mouse
        await client.move_mouse(100, 100)
        await client.click()

        # Control keyboard
        await client.type("Hello, World!")
        await client.hotkey(["ctrl", "c"])

        # List windows
        windows = await client.list_windows()
        for w in windows:
            print(f"{w.id}: {w.title}")

        # Run command
        result = await client.run_command("ls -la")
        print(result.output)

asyncio.run(main())
```

## API Reference

### OpenPCClient

```python
from openpc_sdk import OpenPCClient

client = OpenPCClient(
    host="localhost",    # Server host
    port=8090,         # Server port
    token="your-token" # Optional auth token
)
```

#### Screenshot

```python
# Full screen
screenshot = await client.screenshot()

# Region
region = await client.screenshot_region(x=100, y=100, width=500, height=500)
```

#### Mouse

```python
# Move
await client.move_mouse(x=100, y=200)

# Click
await client.click(button="left", clicks=1)

# Scroll
await client.scroll(direction="down", clicks=5)

# Drag
await client.drag(start_x=0, start_y=0, end_x=100, end_y=100)

# Locate image on screen
result = await client.locate_image("button.png", confidence=0.9)
print(result.x, result.y)
```

#### Keyboard

```python
# Type
await client.type("Hello, World!")

# Press single key
await client.press_key("enter")

# Hotkey
await client.hotkey(["ctrl", "c"])

# Hold/release
await client.key_down("shift")
await client.key_up("shift")
```

#### Windows

```python
# List windows
windows = await client.list_windows()

# Manage
await client.focus_window(window_id="12345")
await client.close_window(window_id="12345")
await client.maximize_window(window_id="12345")
```

#### Applications

```python
# Launch app
await client.launch("google-chrome")

# Open URL
await client.open_url("https://example.com")

# Run command
result = await client.run_command("echo hello", timeout=30)
print(result.output)
```

#### OCR

```python
# Full screen OCR
ocr = await client.ocr()

# Region OCR
ocr = await client.ocr(x=100, y=100, width=500, height=500)
```

### BatchExecutor

Execute multiple operations atomically:

```python
from openpc_sdk.batch import BatchExecutor

async with OpenPCClient() as client:
    executor = BatchExecutor(client)

    # Fill form
    await executor.fill_form([
        {"text": "user@example.com", "key": "email"},
        {"text": "password123", "key": "password"},
    ])

    # Type and click
    await executor.type_and_click(text="Hello", x=100, y=200)

    # Hotkey sequence
    await executor.hotkey_sequence([
        ["ctrl", "c"],
        ["ctrl", "v"],
    ])
```

## Authentication

Set REST_AUTH_TOKEN in your Open-PC environment, then pass token to client:

```python
client = OpenPCClient(token="your-token")
```

## Examples

See `examples/` directory for complete examples.
