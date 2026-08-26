#!/usr/bin/env python3
"""Dump the Open-PC agent server's OpenAPI spec to a committed JSON contract.

The committed spec (``dashboard/openapi.json``) is the contract: the dashboard's
TypeScript SDK is generated from it, and CI fails if the committed copy drifts
from the live FastAPI server. This keeps the Python server as the single source
of truth, exactly like SmolVM's ``scripts/dump_openapi.py`` + the
``openapi.yml`` drift workflow.

The agent server imports ``desktop_manager`` -> ``pyautogui`` at import time.
Dumping the schema needs neither a display nor pyautogui installed, so we inject
a tiny stub module before importing (the real one is only used at request time).

Usage:
    python scripts/dump_openapi.py [output.json]
"""
from __future__ import annotations

import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Make docker/ importable so `import agent_server` resolves `desktop_manager`.
sys.path.insert(0, os.path.join(ROOT, "docker"))


def _install_pyautogui_stub() -> None:
    """Install a minimal pyautogui module so importing the server is headless-safe.

    Only the attributes touched at import time (PAUSE, FAILSAFE) are needed; the
    real pyautogui is used inside request handlers, never during schema dump.
    """
    if "pyautogui" in sys.modules:
        return
    mod = types.ModuleType("pyautogui")
    mod.PAUSE = 0.0
    mod.FAILSAFE = False
    sys.modules["pyautogui"] = mod


def main() -> int:
    _install_pyautogui_stub()
    import agent_server  # noqa: E402  (path set up above)

    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dashboard", "openapi.json")
    spec = agent_server.app.openapi()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Wrote OpenAPI spec to {out} ({len(spec.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())