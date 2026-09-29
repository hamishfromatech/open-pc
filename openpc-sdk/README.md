# Open-PC SDK

Official SDKs for Open-PC, giving AI agents a complete desktop environment they can control programmatically.

```typescript
// TypeScript/JavaScript
const client = new OpenPCClient('localhost', 8090);
await client.type('Hello from SDK!');
await client.click();

// Python
async with OpenPCClient() as client:
    await client.type('Hello from SDK!')
    await client.click()
```

## Quick Start

### Python

```bash
pip install openpc-sdk
```

```python
import asyncio
from openpc_sdk import OpenPCClient

async def main():
    async with OpenPCClient() as client:
        # Take a screenshot
        screenshot = await client.screenshot()

        # Type text
        await client.type('Hello, World!')

        # Click
        await client.click()

asyncio.run(main())
```

### TypeScript/JavaScript

```bash
npm install @openpc/sdk
```

```typescript
import { OpenPCClient } from '@openpc/sdk';

const client = new OpenPCClient('localhost', 8090);

// Take a screenshot
const screenshot = await client.screenshot();

// Type text
await client.type('Hello, World!');

// Click
await client.click();
```

## Features

- **Screen Control**: Screenshot, screen info, OCR
- **Mouse Control**: Move, click, scroll, drag, image-based location
- **Keyboard Control**: Type, press keys, hotkeys
- **Window Management**: List, focus, close, minimize, maximize
- **Apps**: Launch applications, open URLs, run commands
- **Batch Operations**: Execute multiple steps atomically
- **Async-First**: Both SDKs support async/await
- **Type Safety**: Full TypeScript support, Python type hints

## Installation

### Python

```bash
# From PyPI (once published)
pip install openpc-sdk

# From source
pip install git+https://github.com/hamishfromatech/open-pc.git#subdirectory=openpc-sdk/python
```

### Node.js

```bash
# From npm (once published)
npm install @openpc/sdk

# From source
npm install github:hamishfromatech/open-pc#subdirectory=openpc-sdk/typescript
```

## API Reference

### OpenPCClient (Python)

#### Initialization

```python
from openpc_sdk import OpenPCClient

client = OpenPCClient(
    host="localhost",  # Open-PC server host
    port=8090,         # Open-PC server port
    token="your-token" # Optional authentication token
)
```

#### Screenshot

```python
# Full screen
screenshot = await client.screenshot()
print(screenshot.image_base64)

# Region
region = await client.screenshot_region(x=100, y=100, width=500, height=500)
```

#### Mouse

```python
# Move mouse
await client.move_mouse(x=500, y=300)

# Click
await client.click(button="left", clicks=1)

# Scroll
await client.scroll(direction="down", clicks=5)

# Drag
await client.drag(start_x=100, start_y=100, end_x=500, end_y=300)

# Locate image on screen
result = await client.locate_image("button.png", confidence=0.9)
print(result.x, result.y)
```

#### Keyboard

```python
# Type text
await client.type("Hello, World!")

# Press single key
await client.press_key("enter")

# Hotkey combination
await client.hotkey(["ctrl", "c"])

# Hold/release keys
await client.key_down("shift")
await client.key_up("shift")
```

#### Windows

```python
# List windows
windows = await client.list_windows()
for win in windows:
    print(f"{win.id}: {win.title}")

# Focus/close/maximize
await client.focus_window(window_id="12345")
await client.close_window(window_id="12345")
await client.maximize_window(window_id="12345")
```

#### Applications

```python
# Launch application
await client.launch("google-chrome")

# Open URL
await client.open_url("https://example.com")

# Run command
result = await client.run_command("echo 'Hello'")
print(result.output)
```

#### Batch Operations

```python
from openpc_sdk.batch import BatchExecutor

async with OpenPCClient() as client:
    executor = BatchExecutor(client)

    # Type then click
    await executor.type_and_click(
        text="Hello",
        x=100,
        y=200
    )

    # Fill form
    await executor.fill_form([
        {"text": "user@example.com", "key": "email"},
        {"text": "password123", "key": "password"},
    ])

    # Hotkey sequence
    await executor.hotkey_sequence([
        ["ctrl", "c"],
        ["ctrl", "v"],
    ])
```

### OpenPCClient (TypeScript)

#### Initialization

```typescript
const client = new OpenPCClient('localhost', 8090, 'token');
```

#### Screenshot

```typescript
const screenshot = await client.screenshot();
console.log(screenshot.image); // base64 string

const region = await client.screenshotRegion(100, 100, 500, 500);
```

#### Mouse

```typescript
// Move mouse
await client.mouseMove(500, 300);

// Click
await client.click(100, 200, 'left');

// Scroll
await client.scroll(5, 'down');

// Locate image
const result = await client.locateImage('button.png');
console.log(result.x, result.y);
```

#### Keyboard

```typescript
// Type
await client.type('Hello, World!');

// Press key
await client.pressKey('enter');

// Hotkey
await client.hotkey(['ctrl', 'c']);
```

#### Batch

```typescript
// Fill form
await client.fillForm([
    {text: 'user@example.com', key: 'email'},
    {text: 'password123', key: 'password'},
]);

// Type and press
await client.typeAndPress('Hello', 'enter');

// Move and click
await client.moveToAndClick(100, 200);
```

## Authentication

If your Open-PC instance has `REST_AUTH_TOKEN` set, include the token:

**Python:**
```python
client = OpenPCClient(token="your-token")
```

**TypeScript:**
```typescript
const client = new OpenPCClient('localhost', 8090, 'your-token');
```

## Examples

### Python

See `python/examples/`:
- `basic_usage.py` - Basic operations
- `batch_operations.py` - Atomic batch workflows

### TypeScript

Create your own examples using the client:

```typescript
import { OpenPCClient } from '@openpc/sdk';

async function example() {
    const client = new OpenPCClient('localhost', 8090);
    
    // Take screenshot
    const screenshot = await client.screenshot();
    
    // Type and press enter
    await client.type('Hello from TypeScript SDK!');
    await client.pressKey('enter');
    
    // List windows
    const windows = await client.listWindows();
    console.log(windows);
}

example();
```

## Development

### Python

```bash
cd openpc-sdk/python
pip install -e ".[dev]"
pytest
```

### TypeScript

```bash
cd openpc-sdk/typescript
npm install
npm run build
```

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! See the main [Open-PC repository](https://github.com/hamishfromatech/open-pc) for guidelines.
