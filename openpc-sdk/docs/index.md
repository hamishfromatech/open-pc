# Open-PC SDK

Official SDKs for Open-PC Desktop Control.

## Table of Contents

- [Python SDK](#python-sdk)
- [TypeScript SDK](#typescript-sdk)
- [Batch Operations](#batch-operations)
- [Authentication](#authentication)

## Python SDK

### Installation

```bash
pip install openpc-sdk
```

### Quick Example

```python
import asyncio
from openpc_sdk import OpenPCClient

async def main():
    async with OpenPCClient() as client:
        screenshot = await client.screenshot()
        await client.type('Hello!')
        await client.click()

asyncio.run(main())
```

### API Reference

#### OpenPCClient

```python
client = OpenPCClient(
    host="localhost",
    port=8090,
    token="your-token"  # Optional
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `health()` | Check server status |
| `screenshot()` | Capture full screen |
| `screenshot_region(x, y, width, height)` | Capture region |
| `screen_info()` | Get dimensions and cursor position |
| `move_mouse(x, y)` | Move cursor |
| `click(x, y, button, clicks)` | Click at position |
| `type(text)` | Type text |
| `hotkey(keys)` | Press key combination |
| `list_windows()` | List open windows |
| `run_command(command)` | Execute shell command |
| `ocr()` | Perform optical character recognition |

#### BatchExecutor

```python
from openpc_sdk.batch import BatchExecutor

executor = BatchExecutor(client)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `fill_form(fields)` | Fill multiple form fields |
| `type_and_click(text, x, y)` | Type then click |
| `hotkey_sequence(sequences)` | Execute multiple hotkeys |

## TypeScript SDK

### Installation

```bash
npm install @openpc/sdk
```

### Quick Example

```typescript
import { OpenPCClient } from '@openpc/sdk';

const client = new OpenPCClient('localhost', 8090);
await client.screenshot();
await client.type('Hello!');
await client.click();
```

### API Reference

#### OpenPCClient

```typescript
const client = new OpenPCClient('localhost', 8090, 'token'); // token optional
```

**Methods:**

| Method | Description |
|--------|-------------|
| `health()` | Check server status |
| `screenshot()` | Capture full screen |
| `screenshotRegion(x, y, width, height)` | Capture region |
| `screenInfo()` | Get dimensions and cursor position |
| `mouseMove(x, y)` | Move cursor |
| `click(x, y, button)` | Click at position |
| `type(text)` | Type text |
| `hotkey(keys)` | Press key combination |
| `listWindows()` | List open windows |
| `runCommand(command)` | Execute shell command |
| `ocr()` | Perform optical character recognition |

#### BatchExecutor

```typescript
import { BatchExecutor } from '@openpc/sdk';

const executor = new BatchExecutor(client);
```

**Methods:**

| Method | Description |
|--------|-------------|
| `fillForm(fields)` | Fill multiple form fields |
| `typeAndClick(text, x, y)` | Type then click |
| `hotkeySequence(sequences)` | Execute multiple hotkeys |

## Batch Operations

Batch operations execute atomically - if one step fails, the rest are skipped.

**Python:**
```python
from openpc_sdk.batch import BatchExecutor

executor = BatchExecutor(client)
await executor.fill_form([
    {"text": "user@example.com", "key": "email"},
    {"text": "password123", "key": "password"},
])
```

**TypeScript:**
```typescript
import { BatchExecutor } from '@openpc/sdk';

const executor = new BatchExecutor(client);
await executor.fillForm([
    {text: 'user@example.com', key: 'email'},
    {text: 'password123', key: 'password'},
]);
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

## License

MIT License
