# openpc-core

Core library for Open-PC bare-metal mode — cross-platform desktop backend abstraction and guardrails engine.

## Quick start

```bash
# From the Open-PC repo root (no pip install needed — the CLI wires the path)
python3 openpc.py start --mode bare-metal

# Or install the package directly:
cd openpc-core && pip install -e .
```

## What's inside

| Module | Purpose |
|--------|---------|
| `backends.base` | `DesktopBackend` Protocol — the single contract all backends implement |
| `backends.cua_driver` | CUA Driver backend: wraps `cua_driver` SDK for native macOS/Windows/Linux control |
| `guardrails.engine` | Permission gates, command validation, audit logging, rate limiting |
| `guardrails.config` | Pydantic models + file/env config for guardrail settings |

## Usage

### Guardrails engine

```python
from openpc_core.guardrails import GuardrailsEngine, load_guardrails_config

# Load or create config
config = load_guardrails_config()

# Validate commands
engine = GuardrailsEngine(config)
result = engine.validate_command("ls -la")  # {"allowed": True}
result = engine.validate_command("rm -rf /")  # {"allowed": False, "reason": "..."}

# Check permissions
engine.check_permission("mouse_click")    # True in bounded mode
engine.check_permission("launch_app")     # False in bounded mode

# Configure settings
GuardrailsEngine.configure(
    permission="standard",
    whitelist_mode="moderate",
    max_actions_per_minute=60,
)
```

### CUA Driver backend

```python
from openpc_core.backends.cua_driver import CUADriverBackend

driver = CUADriverBackend(mode="bounded")
screenshot = driver.take_screenshot()
driver.mouse_click(x=100, y=200)
driver.keyboard_type("Hello!")
windows = driver.list_windows()
```

Requires either `cua-driver` or `pyautogui` installed.

## Configuration

Settings are persisted to `~/.openpc/guardrails.json`:

| Setting | Values | Default |
|---------|--------|---------|
| `permission` | `bounded`, `standard`, `unrestricted` | `bounded` |
| `whitelist_mode` | `strict`, `moderate`, `permissive` | `strict` |
| `max_actions_per_minute` | 1–600 | 30 |
| `command_timeout` | 1–300 seconds | 30 |
| `workspace_dir` | Any path (restricts command execution) | "" |

## CLI integration

Used by `openpc.py configure` and `openpc guard` commands. See the main [Open-PC README](../README.md) for full usage.
